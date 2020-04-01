# Copyright 2020-present Ralf Kundel, Moritz Jordan
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import subprocess
import struct
import time
import traceback
from abstract_target import AbstractTarget
from thrift import Thrift
from thrift.transport import TSocket, TTransport, TZlibTransport
from thrift.protocol import TBinaryProtocol

from targets.netronome.sdk6_rte import RunTimeEnvironment
from targets.netronome.sdk6_rte.ttypes import RegisterArrayArg, McastCfgEntry, TableEntry, DesignLoadArgs

TIMESTAMP_FRC = True

CNTR_DUT1 = 1
CNTR_DUT2 = 2
CNTR_SRV = 3

class RteError(Exception):
    pass

class TargetImpl(AbstractTarget):
    def __init__(self, target_cfg):
        super().__init__(target_cfg)
        self.speed_list = []

    def _get_rte_client(self, cfg):
        transport = TZlibTransport.TZlibTransport(TTransport.TBufferedTransport(TSocket.TSocket(cfg["p4_dev_ssh"], cfg["thrift_port"])))
        rte_client = RunTimeEnvironment.Client(TBinaryProtocol.TBinaryProtocol(transport))

        try:
            transport.open()
        except TTransport.TTransportException:
            self.execute_ssh(cfg, "sudo systemctl start nfp-sdk6-rte.service")
            time.sleep(1)
            transport.open()

        return rte_client

    # returns a dict["real_ports"] and ["logical_ports"]
    def port_lists(self):
        real_ports = []
        logical_ports = []

        # physical ports
        for p in range(4):
            real_ports.append("p" + str(p))
            logical_ports.append(str((p & 0xff) | (0 << 8)))

        # host ports
        for p in range(64):
            real_ports.append("v0." + str(p))
            logical_ports.append(str((p & 0xff) | (3 << 8)))

        return {"real_ports": real_ports, "logical_ports": logical_ports}

    # deploy config file (table entries) to p4 device
    def deploy(self, cfg):
        try:
            print("DEPLOY STARTED AT NETRONOME")
            rte_client = self._get_rte_client(cfg)
            tables = {t.tbl_name: t for t in rte_client.table_list_all()}

            # clear tables of non-default rules
            for table in tables.values():
                for entry in rte_client.table_retrieve(table.tbl_id):
                    if not entry.default_rule:
                        rte_client.table_entry_delete(table.tbl_id, entry)

            # clear multicast
            for mccfg in rte_client.mcast_config_get_all():
                mccfg.ports = []
                rte_client.mcast_config_set(mccfg)

            # set register r_extHost_max
            reg_id = list(filter(lambda r: r.name == "r_extHost_max", rte_client.register_list_all()))[0].id
            rte_client.register_field_set(RegisterArrayArg(reg_id=reg_id), 0, str(int(cfg["multicast"]) - 1))

            # multicast group for loadgen servers and clients
            srv_ports = [int(s["p4_port"]) for s in cfg["loadgen_servers"]]
            clt_ports = [int(c["p4_port"]) for c in cfg["loadgen_clients"]]
            all_ports = [int(s["p4_port"]) for s in (cfg["loadgen_servers"] + cfg["loadgen_clients"])]
            rte_client.mcast_config_set(McastCfgEntry(group_id=0, ports=all_ports))
            rte_client.mcast_config_set(McastCfgEntry(group_id=1, ports=all_ports))
            print(all_ports)

            # multicast group for loadgen servers and clients with external host
            # possible enhacement: a dedicated group with each server/client (max 15)
            srv_ports.append(int(cfg["ext_host"]))
            clt_ports.append(int(cfg["ext_host"]))
            rte_client.mcast_config_set(McastCfgEntry(group_id=2, ports=srv_ports))
            rte_client.mcast_config_set(McastCfgEntry(group_id=3, ports=clt_ports))

            def table_entry_add(table, rule_name, match, action):
                match_json = "{{{0}}}".format(",".join(['"{0}":{{"value":"{1}"}}'.format(k, v) for k, v in match.items()])) #{"": {"value": ""}}
                action_json = "{{{0}}}".format('"type":"{0}","data":{{{1}}}'.format(action[0], ",".join(['"{0}":{{"value":"{1}"}}'.format(k, v) for k, v in action[1].items()]))) #{"type": "", "data": {"": {"value": ""}}}
                ret = rte_client.table_entry_add(tables[table].tbl_id, TableEntry(
                    rule_name=rule_name,
                    match=match_json.encode('ascii'),
                    actions=action_json.encode('ascii')))
                if ret.value != 0:
                    print("Raise Error in Netronome table_entry_add")
                    raise RteError(ret.reason)

            # server/clients -> dut
            for i, server in enumerate(cfg["loadgen_servers"]):
                table_entry_add("ingress::t_l1_forwarding", "server{}_dut0".format(i),
                        {"standard_metadata.ingress_port": server["p4_port"]},
                        ["ingress::send", {"spec": cfg["dut1"]}])
            for i, client in enumerate(cfg["loadgen_clients"]):
                table_entry_add("ingress::t_l1_forwarding", "client{}_dut1".format(i),
                        {"standard_metadata.ingress_port": client["p4_port"]},
                        ["ingress::send", {"spec": cfg["dut2"]}])

            # dut -> server/clients (forwarding mode)
            # must be executed before t_lx_forwarding
            if int(cfg["forwarding_mode"]) >= 2:
                table_entry_add("ingress::t_bcast_forwarding", "bcast_mg1",
                        {"ethernet.dstAddr": "0xffffffffffff"},
                        ["ingress::send", {"spec": "mg1"}])

            if cfg["forwarding_mode"] == "1":
                table_entry_add("ingress::t_l1_forwarding", "dut0_server0",
                        {"standard_metadata.ingress_port": cfg["dut1"]},
                        ["ingress::send", {"spec": cfg["loadgen_servers"][0]["p4_port"]}])
                table_entry_add("ingress::t_l1_forwarding", "dut1_client0",
                        {"standard_metadata.ingress_port": cfg["dut2"]},
                        ["ingress::send", {"spec": cfg["loadgen_clients"][0]["p4_port"]}])
            elif cfg["forwarding_mode"] == "2":
                for i, server in enumerate(cfg["loadgen_servers"]):
                    table_entry_add("ingress::t_l2_forwarding", "dut0_server{}".format(i),
                            {"standard_metadata.ingress_port": cfg["dut1"],
                                "ethernet.dstAddr": "0x{}".format(server["loadgen_mac"].replace(":", ""))},
                            ["ingress::send", {"spec": server["p4_port"]}])
                for i, client in enumerate(cfg["loadgen_clients"]):
                    table_entry_add("ingress::t_l2_forwarding", "dut1_client{}".format(i),
                            {"standard_metadata.ingress_port": cfg["dut2"],
                                "ethernet.dstAddr": "0x{}".format(client["loadgen_mac"].replace(":", ""))},
                            ["ingress::send", {"spec": client["p4_port"]}])
            elif cfg["forwarding_mode"] == "3":
                for i, server in enumerate(cfg["loadgen_servers"]):
                    table_entry_add("ingress::t_l3_forwarding", "dut0_server{}".format(i),
                            {"standard_metadata.ingress_port": cfg["dut1"],
                                "ipv4.dstAddr": server["loadgen_ip"]},
                            ["ingress::send", {"spec": server["p4_port"]}])
                for i, client in enumerate(cfg["loadgen_clients"]):
                    table_entry_add("ingress::t_l3_forwarding", "dut1_client{}".format(i),
                            {"standard_metadata.ingress_port": cfg["dut2"],
                                "ipv4.dstAddr": client["loadgen_ip"]},
                            ["ingress::send", {"spec": client["p4_port"]}])

            # dut -> +external host
            if cfg["ext_host"] != "":
                #TODO apply for all packets with p4sta header
                if cfg["dut_2_outgoing_stamp"] == "checked":
                    table_entry_add("ingress::t_extHost", "dut0_servers",
                            {"standard_metadata.ingress_port": cfg["dut1"]},
                            ["ingress::send_if_extHost", {"spec": "mg2"}])
                if cfg["dut_1_outgoing_stamp"] == "checked":
                    table_entry_add("ingress::t_extHost", "dut1_clients",
                            {"standard_metadata.ingress_port": cfg["dut2"]},
                            ["ingress::send_if_extHost", {"spec": "mg3"}])

            # Change MAC for packages to external host
            table_entry_add("egress::t_change_mac", "extHost",
                    {"standard_metadata.egress_port": cfg["ext_host"]},
                    ["egress::change_mac", {"dstAddr": "ff:ff:ff:ff:ff:ff"}])

            # Enable MAC command on physical ports if hardware stamping is activated
            EgCmdPrependEn = 0
            ports = self.port_lists()
            for token, i in zip(ports['real_ports'], ports['logical_ports']):
                if token.startswith("p"):
                    table_entry_add("egress::t_add_empty_nfp_mac_eg_cmd", token,
                            {"standard_metadata.egress_port": i},
                            ["egress::add_empty_nfp_mac_eg_cmd", {}])
                    EgCmdPrependEn |= 0xff << (8 * int(i))

            sshstr = "sudo /opt/netronome/bin/nfp-reg xpb:Nbi0IsldXpbMap.NbiTopXpbMap.MacGlbAdrMap.MacCsr.EgCmdPrependEn0Lo={0}; sudo /opt/netronome/bin/nfp-reg xpb:Nbi0IsldXpbMap.NbiTopXpbMap.MacGlbAdrMap.MacCsr.EgCmdPrependEn0Hi={1}".format(hex(EgCmdPrependEn & 0xffffffff), hex(EgCmdPrependEn >> 32 & 0xffffffff))
            self.execute_ssh(cfg, sshstr)

            # Timestamp on dut ports
            protos = []
            if cfg["stamp_tcp"] == "checked":
                protos.append(["tcp", "0x06"])
            if cfg["stamp_udp"] == "checked":
                protos.append(["udp", "0x11"])

            if cfg["dut_2_outgoing_stamp"] == "checked":
                table_entry_add("ingress::t_stamped_throughput_ingress", "dut1",
                        {"standard_metadata.ingress_port": cfg["dut1"]},
                        ["ingress::c_stamped_throughput_ingress_count", {"index": CNTR_DUT1}])
                for proto in protos:
                    table_entry_add("ingress::t_timestamp2", "dut1_{}".format(proto[0]),
                            {"standard_metadata.ingress_port": cfg["dut1"],
                                    "ipv4.protocol": proto[1]},
                            ["ingress::timestamp2_{0}".format(proto[0]), {}])
                    table_entry_add("egress::t_timestamp1", "dut2_{}".format(proto[0]),
                            {"standard_metadata.egress_port": cfg["dut2"],
                                    "ipv4.protocol": proto[1]},
                            ["egress::timestamp1_{0}_mac".format(proto[0]), {}])
                    table_entry_add("egress::t_stamped_throughput_egress", "dut2_{}".format(proto[0]),
                            {"standard_metadata.egress_port": cfg["dut2"],
                                    "ipv4.protocol": proto[1]},
                            ["egress::c_stamped_throughput_egress_count", {"index": CNTR_DUT2}])

            if cfg["dut_1_outgoing_stamp"] == "checked" and cfg["dut1"] != cfg["dut2"]:
                table_entry_add("ingress::t_stamped_throughput_ingress", "dut2",
                        {"standard_metadata.ingress_port": cfg["dut2"]},
                        ["ingress::c_stamped_throughput_ingress_count", {"index": CNTR_DUT2}])
                for proto in protos:
                    table_entry_add("ingress::t_timestamp2", "dut2_{}".format(proto[0]),
                            {"standard_metadata.ingress_port": cfg["dut2"],
                                    "ipv4.protocol": proto[1]},
                            ["ingress::timestamp2_{0}".format(proto[0]), {}])
                    table_entry_add("egress::t_timestamp1", "dut1_{}".format(proto[0]),
                            {"standard_metadata.egress_port": cfg["dut1"],
                                    "ipv4.protocol": proto[1]},
                            ["egress::timestamp1_{0}_mac".format(proto[0]), {}])
                    table_entry_add("egress::t_stamped_throughput_egress", "dut1_{}".format(proto[0]),
                            {"standard_metadata.egress_port": cfg["dut1"],
                                    "ipv4.protocol": proto[1]},
                            ["egress::c_stamped_throughput_egress_count", {"index": CNTR_DUT1}])

            # Measure throughput
            for g in ["ingress", "egress"]:
                table_entry_add("{0}::t_throughput_{0}".format(g), "dut1",
                        {"standard_metadata.{0}_port".format(g): cfg["dut1"]},
                        ["{0}::c_throughput_{0}_count".format(g), {"index": CNTR_DUT1}])
                table_entry_add("{0}::t_throughput_{0}".format(g), "dut2",
                        {"standard_metadata.{0}_port".format(g): cfg["dut2"]},
                        ["{0}::c_throughput_{0}_count".format(g), {"index": CNTR_DUT2}])
                i = CNTR_SRV
                for host in (cfg["loadgen_servers"] + cfg["loadgen_clients"]):
                    table_entry_add("{0}::t_throughput_{0}".format(g), "lg{}".format(i - CNTR_SRV),
                            {"standard_metadata.{0}_port".format(g): host["p4_port"]},
                            ["{0}::c_throughput_{0}_count".format(g), {"index": i}])
                    i = i + 1
        except:
            return traceback.format_exc()
        print("DEPLOY FINISHED AT NETRONOME")

    def read_p4_device(self, cfg):
        rte_client = self._get_rte_client(cfg)

        try:
            registers = {r.name: r for r in rte_client.register_list_all()}
            counters = {c.name: c for c in rte_client.p4_counter_list_all()}
        except:
            registers = {}
            counters = {}

        def read_reg(reg):
            try:
                ret = rte_client.register_retrieve(RegisterArrayArg(reg_id=registers[reg].id))
                return dict(enumerate([int(val, 16) for val in ret]))
            except:
                return {}

        def read_cnt(cnt):
            try:
                pck = rte_client.p4_counter_retrieve(counters[cnt + "_packets"].id)
                byt = rte_client.p4_counter_retrieve(counters[cnt + "_bytes"].id)
                pck_dict = dict(enumerate([i[0] for i in struct.iter_unpack('Q', pck.data)]))
                byt_dict = dict(enumerate([i[0] for i in struct.iter_unpack('Q', byt.data)]))
                return [pck_dict, byt_dict]
            except:
                return [{}, {}]

        cfg["total_deltas"] = read_reg("r_delta_sum").get(0, -1)
        cfg["delta_counter"] = read_reg("r_delta_count").get(0, -1)
        cfg["min_delta"] = read_reg("r_delta_min").get(0, -1)
        cfg["max_delta"] = read_reg("r_delta_max").get(0, -1)

        c_throughput_ingress = read_cnt("c_throughput_ingress")
        c_throughput_egress = read_cnt("c_throughput_egress")
        c_stamped_throughput_ingress = read_cnt("c_stamped_throughput_ingress")
        c_stamped_throughput_egress = read_cnt("c_stamped_throughput_egress")

        cfg["dut1_num_ingress_packets"] = c_throughput_ingress[0].get(CNTR_DUT1, -1)
        cfg["dut1_num_ingress_bytes"] = c_throughput_ingress[1].get(CNTR_DUT1, -1)
        cfg["dut1_num_egress_packets"] = c_throughput_egress[0].get(CNTR_DUT1, -1)
        cfg["dut1_num_egress_bytes"] = c_throughput_egress[1].get(CNTR_DUT1, -1)
        cfg["dut1_num_ingress_stamped_packets"] = c_stamped_throughput_ingress[0].get(CNTR_DUT1, -1)
        cfg["dut1_num_ingress_stamped_bytes"] = c_stamped_throughput_ingress[1].get(CNTR_DUT1, -1)
        cfg["dut1_num_egress_stamped_packets"] = c_stamped_throughput_egress[0].get(CNTR_DUT1, -1)
        cfg["dut1_num_egress_stamped_bytes"] = c_stamped_throughput_egress[1].get(CNTR_DUT1, -1)
        cfg["dut2_num_ingress_packets"] = c_throughput_ingress[0].get(CNTR_DUT2, -1)
        cfg["dut2_num_ingress_bytes"] = c_throughput_ingress[1].get(CNTR_DUT2, -1)
        cfg["dut2_num_egress_packets"] = c_throughput_egress[0].get(CNTR_DUT2, -1)
        cfg["dut2_num_egress_bytes"] = c_throughput_egress[1].get(CNTR_DUT2, -1)
        cfg["dut2_num_ingress_stamped_packets"] = c_stamped_throughput_ingress[0].get(CNTR_DUT2, -1)
        cfg["dut2_num_ingress_stamped_bytes"] = c_stamped_throughput_ingress[1].get(CNTR_DUT2, -1)
        cfg["dut2_num_egress_stamped_packets"] = c_stamped_throughput_egress[0].get(CNTR_DUT2, -1)
        cfg["dut2_num_egress_stamped_bytes"] = c_stamped_throughput_egress[1].get(CNTR_DUT2, -1)

        i = CNTR_SRV
        for host in (cfg["loadgen_servers"] + cfg["loadgen_clients"]):
            host["num_ingress_packets"] = c_throughput_ingress[0].get(i, -1)
            host["num_ingress_bytes"] = c_throughput_ingress[1].get(i, -1)
            host["num_egress_packets"] = c_throughput_egress[0].get(i, -1)
            host["num_egress_bytes"] = c_throughput_egress[1].get(i, -1)
            host["num_ingress_stamped_packets"] = c_stamped_throughput_ingress[0].get(i, -1)
            host["num_ingress_stamped_bytes"] = c_stamped_throughput_ingress[1].get(i, -1)
            host["num_egress_stamped_packets"] = c_stamped_throughput_egress[0].get(i, -1)
            host["num_egress_stamped_bytes"] = c_stamped_throughput_egress[1].get(i, -1)
            i = i + 1

        return cfg

    def visualization(self, cfg):
        return "<p>Unfortunately there is <b>no</b> visualization html file provided by the selected p4 device.</p>"

    def p4_dev_status(self, cfg):
        try:
            rte_client = self._get_rte_client(cfg)
            status = rte_client.design_load_status()
            if status.is_loaded:
                print("Netronome : device status is: is_loaded==True")
                print(status)
                uptime = status.uptime
                try:
                    uptime = int(uptime)
                    if uptime >= 3600:
                        formatted_uptime = str(int(uptime/3600)) + "h " + str(int((uptime%3600) / 60)) + "min " + str(uptime % 60) + "s"
                    elif uptime >= 60:
                        formatted_uptime = str(int(uptime/60)) + "min " + str(uptime%60) + "s"
                    else:
                        formatted_uptime = str(uptime) + "s"
                except:
                    formatted_uptime = uptime
                dev_status = "{} {} ({}) for {}".format(status.uuid, status.frontend_source, status.frontend_build_date, formatted_uptime)

                n = 0
                for table in rte_client.table_list_all():
                    n = n + len(rte_client.table_retrieve(table.tbl_id))

                return ["Number of table rules: {}".format(n)], status.is_loaded, dev_status
            else:
                print("Netronome: device status: is_loaded==False")
                print(status)
        except:
            pass
        return [], False, "not running (starting may take a while)"

    # starts specific p4 software on device
    def start_p4_dev_software(self, cfg):
        rte_client = self._get_rte_client(cfg)

        nfpfw = open(cfg["nfpfw"], "rb").read()
        pif_design_json = open(cfg["pif_design_json"], "rb").read()
        # May fail if nfp-sdk6-rte.service was just started. Workaround: load design with CLI once
        ret = rte_client.design_load(DesignLoadArgs(nfpfw, pif_design_json)) #this takes 30-40 seconds
        if ret.value != 0:
            print("err")
            raise RteError(ret.reason + "\nTry loading design with CLI once.")

        # Set CSR for timestamp format
        sshstr = "sudo /opt/netronome/bin/nfp-reg xpb:Nbi0IsldXpbMap.NbiTopXpbMap.MacGlbAdrMap.MacCsr.MacSysSupCtrl.TimeStampFrc=" + ("0x1" if TIMESTAMP_FRC else "0x0")
        self.execute_ssh(cfg, sshstr)

    def stop_p4_dev_software(self, cfg):
        rte_client = self._get_rte_client(cfg)
        rte_client.design_unload()

    # reset registers of p4 device
    def reset_p4_registers(self, cfg):
        rte_client = self._get_rte_client(cfg)
        rte_client.p4_counter_clear_all()
        registers_to_clear = ["r_delta_sum", "r_delta_count", "r_delta_max", "r_delta_min", "r_extHost_count"]
        for register in rte_client.register_list_all():
            if register.name in registers_to_clear:
                rte_client.register_clear(RegisterArrayArg(reg_id=register.id))

    def get_p4_dev_startup_log(self, cfg):
        return ["For this target is no log available."]

    def check_if_p4_compiled(self, cfg):
        try:
            for f in [[cfg["nfpfw"], b"ELF 64-bit LSB relocatable, *unknown arch 0x6000* version 1 (SYSV), not stripped\n"],
                    [cfg["pif_design_json"], b"ASCII text\n"]]:
                res = subprocess.run(["file", "-E", "-b", f[0]], stdout=subprocess.PIPE)
                if res.returncode != 0:
                    return False, res.stdout.decode('utf-8')
                if res.stdout != f[1]:
                    return False, "{} is wrong format: '{}'".format(f[0], res.stdout.decode('utf-8'))
            return True, "Firmware files found and format correct"
        except Exception as e:
            return False, str(e)
