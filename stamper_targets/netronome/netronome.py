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
import P4STA_utils
from thrift import Thrift
from thrift.transport import TSocket, TTransport, TZlibTransport
from thrift.protocol import TBinaryProtocol

from stamper_targets.netronome.sdk6_rte import RunTimeEnvironment
from stamper_targets.netronome.sdk6_rte.ttypes import DesignLoadArgs
from stamper_targets.netronome.sdk6_rte.ttypes import McastCfgEntry
from stamper_targets.netronome.sdk6_rte.ttypes import RegisterArrayArg
from stamper_targets.netronome.sdk6_rte.ttypes import TableEntry

TIMESTAMP_FRC = True

dir_path = os.path.dirname(os.path.realpath(__file__))


class RteError(Exception):
    pass


class TargetImpl(AbstractTarget):
    def __init__(self, target_cfg):
        super().__init__(target_cfg)
        self.speed_list = []

    def _get_rte_client(self, cfg):
        transport = TZlibTransport.TZlibTransport(
            TTransport.TBufferedTransport(
                TSocket.TSocket(cfg["stamper_ssh"], cfg["thrift_port"])))
        rte_client = RunTimeEnvironment.Client(
            TBinaryProtocol.TBinaryProtocol(transport))

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
            reg_id = list(filter(lambda r: r.name == "r_extHost_max",
                                 rte_client.register_list_all()))[0].id
            rte_client.register_field_set(RegisterArrayArg(reg_id=reg_id), 0,
                                          str(int(cfg["multicast"]) - 1))

            all_ports = []
            for loadgen_grp in cfg["loadgen_groups"]:
                all_ports.extend(
                    [int(host["p4_port"]) for host in loadgen_grp["loadgens"]])
            rte_client.mcast_config_set(
                McastCfgEntry(group_id=0, ports=all_ports))
            rte_client.mcast_config_set(
                McastCfgEntry(group_id=1, ports=all_ports))

            # create a mcast group consisting of loadgen_grp and ext host
            group = 2
            for loadgen_grp in cfg["loadgen_groups"]:
                ports = [int(host["p4_port"]) for host in
                         loadgen_grp["loadgens"]]
                ports.append(int(cfg["ext_host"]))
                loadgen_grp["mcast_grp"] = group
                group = group + 1
                print("Added ports " + str(ports) + " to mcast grp " + str(
                    loadgen_grp["mcast_grp"]))
                rte_client.mcast_config_set(
                    McastCfgEntry(group_id=loadgen_grp["mcast_grp"],
                                  ports=ports))

            def table_entry_add(table, rule_name, match, action):
                print(rule_name + ": " + table + " | match: " + str(
                    match) + " => " + str(action))
                match_json = "{{{0}}}".format(
                    ",".join(['"{0}":{{"value":"{1}"}}'.format(
                        k, v) for k, v in match.items()]))
                action_json = "{{{0}}}".format(
                    '"type":"{0}","data":{{{1}}}'.format(
                        action[0], ",".join(['"{0}":{{"value":"{1}"}}'.format(
                            k, v) for k, v in action[1].items()])))
                ret = rte_client.table_entry_add(tables[table].tbl_id,
                                                 TableEntry(
                                                     rule_name=rule_name,
                                                     match=match_json.encode(
                                                         'ascii'),
                                                     actions=action_json.
                                                     encode('ascii')))
                if ret.value != 0:
                    print("Raise Error in Netronome table_entry_add")
                    raise RteError(ret.reason)

            # loadgenerators -> dut
            for loadgen_grp in cfg["loadgen_groups"]:
                for dut in cfg["dut_ports"]:
                    if loadgen_grp["group"] == dut["id"] \
                            and dut["use_port"] == "checked":
                        for host in loadgen_grp["loadgens"]:
                            table_entry_add("ingress::t_l1_forwarding",
                                            "grp{}_loadgen{}_dut{}".format(
                                                loadgen_grp["group"],
                                                host["id"], dut["id"]),
                                            {"standard_metadata.ingress_port":
                                                host["p4_port"]},
                                            ["ingress::send",
                                             {"spec": dut["p4_port"]}])

            # dut -> server/clients (forwarding mode)
            # must be executed before t_lx_forwarding
            if int(cfg["forwarding_mode"]) >= 2:
                table_entry_add("ingress::t_bcast_forwarding", "bcast_mg1",
                                {"ethernet.dstAddr": "0xffffffffffff"},
                                ["ingress::send", {"spec": "mg1"}])

            if cfg["forwarding_mode"] == "1":
                for dut in cfg["dut_ports"]:
                    if dut["use_port"] == "checked":
                        for loadgen_grp in cfg["loadgen_groups"]:
                            if loadgen_grp["group"] == dut["id"] and len(
                                    loadgen_grp["loadgens"]) > 0:
                                table_entry_add(
                                    "ingress::t_l1_forwarding",
                                    "dut{}_grp{}_host{}".format(
                                                    dut["id"],
                                                    loadgen_grp["group"], 0),
                                    # host 0 because of L1 fw
                                    {
                                        "standard_metadata.ingress_port":
                                            dut["p4_port"]},
                                        [
                                            "ingress::send",
                                            {"spec": loadgen_grp["loadgens"]
                                                [0]["p4_port"]}
                                        ]
                                )
                                break

            elif cfg["forwarding_mode"] == "2":
                for loadgen_grp in cfg["loadgen_groups"]:
                    for dut in cfg["dut_ports"]:
                        if loadgen_grp["group"] == dut["id"] \
                                and dut["use_port"] == "checked":
                            for host in loadgen_grp["loadgens"]:
                                table_entry_add(
                                    "ingress::t_l2_forwarding",
                                    "dut{}_grp{}_host{}".format(
                                                    dut["id"],
                                                    loadgen_grp["group"],
                                                    host["id"]
                                    ),
                                    {
                                        "standard_metadata.ingress_port":
                                            dut["p4_port"],
                                        "ethernet.dstAddr": "0x{}".format(
                                            host["loadgen_mac"].replace(":",
                                                                        "")
                                            )
                                    },
                                    [
                                        "ingress::send",
                                        {"spec": host["p4_port"]}
                                    ]
                                )

            elif cfg["forwarding_mode"] == "3":

                for loadgen_grp in cfg["loadgen_groups"]:
                    for dut in cfg["dut_ports"]:
                        if loadgen_grp["group"] == dut["id"] \
                                and dut["use_port"] == "checked":
                            for host in loadgen_grp["loadgens"]:
                                table_entry_add(
                                    "ingress::t_l2_forwarding",
                                    "dut{}_grp{}_host{}".format(
                                                    dut["id"],
                                                    loadgen_grp["group"],
                                                    host["id"]
                                    ),
                                    {
                                        "standard_metadata.ingress_port": dut[
                                            "p4_port"],
                                        "ipv4.dstAddr": host["loadgen_ip"]
                                    },
                                    [
                                        "ingress::send",
                                        {"spec": host["p4_port"]}
                                    ]
                                )

            # dut -> +external host
            if cfg["ext_host"] != "":
                for loadgen_grp in cfg["loadgen_groups"]:
                    if loadgen_grp["use_group"] == "checked":
                        for dut in self.get_all_dut_dst_p4_ports(
                                cfg, get_as_dict=True):
                            if dut["id"] == loadgen_grp["group"]:
                                table_entry_add(
                                    "ingress::t_extHost",
                                    "dut{}_grp_".format(
                                        dut["id"], loadgen_grp["group"]),
                                    {
                                        "standard_metadata.ingress_port":
                                            dut["p4_port"]},
                                        [
                                            "ingress::send_if_extHost",
                                            {
                                                "spec": "mg{}".format(
                                                    loadgen_grp["mcast_grp"])
                                            }
                                        ])
                                break

            # Change MAC for packages to external host
            table_entry_add("egress::t_change_mac", "extHost",
                            {"standard_metadata.egress_port": cfg["ext_host"]},
                            ["egress::change_mac",
                             {"dstAddr": "ff:ff:ff:ff:ff:ff"}])

            # Enable MAC command on physical ports if
            # hardware stamping is activated
            EgCmdPrependEn = 0
            ports = self.port_lists()
            for token, i in zip(ports['real_ports'], ports['logical_ports']):
                if token.startswith("p"):
                    table_entry_add("egress::t_add_empty_nfp_mac_eg_cmd",
                                    token,
                                    {"standard_metadata.egress_port": i},
                                    ["egress::add_empty_nfp_mac_eg_cmd", {}])
                    EgCmdPrependEn |= 0xff << (8 * int(i))

            sshstr = "sudo /opt/netronome/bin/nfp-reg xpb:Nbi0IsldXpbMap." \
                     "NbiTopXpbMap.MacGlbAdrMap.MacCsr.EgCmdPrependEn0Lo=" \
                     "{0}; sudo /opt/netronome/bin/nfp-reg xpb:Nbi0IsldXp" \
                     "bMap.NbiTopXpbMap.MacGlbAdrMap.MacCsr.EgCmdPrependE" \
                     "n0Hi={1}".format(
                        hex(EgCmdPrependEn & 0xffffffff),
                        hex(EgCmdPrependEn >> 32 & 0xffffffff))
            self.execute_ssh(cfg, sshstr)

            # Timestamp on dut ports
            protos = []
            if cfg["stamp_tcp"] == "checked":
                protos.append(["tcp", "0x06"])
            if cfg["stamp_udp"] == "checked":
                protos.append(["udp", "0x11"])

            for dut in cfg["dut_ports"]:
                if dut["stamp_outgoing"] == "checked" \
                        and dut["use_port"] == "checked":
                    for proto in protos:
                        table_entry_add("egress::t_timestamp1",
                                        "dut{}_{}".format(dut["id"], proto[0]),
                                        {"standard_metadata.egress_port": dut[
                                            "p4_port"],
                                         "ipv4.protocol": proto[1]},
                                        ["egress::timestamp1_{0}_mac".format(
                                            proto[0]), {}])

                        table_entry_add("egress::t_stamped_throughput_egress",
                                        "dut{}_{}".format(dut["id"], proto[0]),
                                        {"standard_metadata.egress_port": dut[
                                            "p4_port"],
                                         "ipv4.protocol": proto[1]},
                                        [
                                            "egress::c_stamped"
                                            "_throughput_egress_count",
                                            {"index": dut["id"] - 1}])
            for dut in self.get_all_dut_dst_p4_ports(cfg, get_as_dict=True):
                table_entry_add("ingress::t_stamped_throughput_ingress",
                                "dut{}".format(str(dut["id"])),
                                {"standard_metadata.ingress_port": dut[
                                    "p4_port"]},
                                ["ingress::c_stamped_throughput_ingress_count",
                                 {"index": dut[
                                               "id"] - 1}])

                for proto in protos:
                    table_entry_add("ingress::t_timestamp2",
                                    "dut{}_{}".format(str(dut["id"]),
                                                      proto[0]),
                                    {"standard_metadata.ingress_port": dut[
                                        "p4_port"],
                                     "ipv4.protocol": proto[1]},
                                    ["ingress::timestamp2_{0}".format(
                                        proto[0]), {}])

            i = len(cfg["dut_ports"])
            for loadgen_grp in cfg["loadgen_groups"]:
                for host in loadgen_grp["loadgens"]:
                    for proto in protos:
                        table_entry_add("egress::t_stamped_throughput_egress",
                                        "host{}_{}_{}".format(host["id"],
                                                              loadgen_grp[
                                                                  "group"],
                                                              proto[0]),
                                        {"standard_metadata.egress_port": host[
                                            "p4_port"],
                                         "ipv4.protocol": proto[1]},
                                        [
                                            "egress::c_stamped_throughput"
                                            "_egress_count",
                                            {"index": i}])
                    i = i + 1

            for proto in protos:
                table_entry_add("egress::t_stamped_throughput_egress",
                                "ext_host_" + proto[1],
                                {"standard_metadata.egress_port": cfg[
                                    "ext_host"],
                                 "ipv4.protocol": proto[1]},
                                ["egress::c_stamped_throughput_egress_count",
                                 {"index": i}])

            # Measure throughput
            for g in ["ingress", "egress"]:
                for dut in cfg["dut_ports"]:
                    table_entry_add("{0}::t_throughput_{0}".format(g),
                                    "dut{}".format(dut["id"]),
                                    {"standard_metadata.{0}_port".format(
                                        g): dut["p4_port"]},
                                    ["{0}::c_throughput_{0}_count".format(g),
                                     {"index": dut["id"] - 1}])

                i = len(cfg["dut_ports"])
                for loadgen_grp in cfg["loadgen_groups"]:
                    for host in loadgen_grp["loadgens"]:
                        table_entry_add("{0}::t_throughput_{0}".format(g),
                                        "lg{}".format(
                                            i - (len(cfg["dut_ports"]) + 1)),
                                        {"standard_metadata.{0}_port".format(
                                            g): host["p4_port"]},
                                        ["{0}::c_throughput_{0}_count".format(
                                            g), {"index": i}])
                        i = i + 1

                # last index for ext host counter
                table_entry_add("{0}::t_throughput_{0}".format(g),
                                "lg{}".format(i - (len(cfg["dut_ports"]) + 1)),
                                {"standard_metadata.{0}_port".format(g): cfg[
                                    "ext_host"]},
                                ["{0}::c_throughput_{0}_count".format(g),
                                 {"index": i}])
        except Exception:
            return traceback.format_exc()
        print("DEPLOY FINISHED AT NETRONOME")

    def read_stamperice(self, cfg):
        rte_client = self._get_rte_client(cfg)

        try:
            registers = {r.name: r for r in rte_client.register_list_all()}
            counters = {c.name: c for c in rte_client.p4_counter_list_all()}
        except Exception:
            registers = {}
            counters = {}

        def read_reg(reg):
            try:
                ret = rte_client.register_retrieve(
                    RegisterArrayArg(reg_id=registers[reg].id))
                return dict(enumerate([int(val, 16) for val in ret]))
            except Exception:
                return {}

        def read_cnt(cnt):
            try:
                pck = rte_client.p4_counter_retrieve(
                    counters[cnt + "_packets"].id)
                byt = rte_client.p4_counter_retrieve(
                    counters[cnt + "_bytes"].id)
                pck_dict = dict(enumerate(
                    [i[0] for i in struct.iter_unpack('Q', pck.data)]))
                byt_dict = dict(enumerate(
                    [i[0] for i in struct.iter_unpack('Q', byt.data)]))
                return [pck_dict, byt_dict]
            except Exception:
                print(traceback.format_exc(()))
                return [{}, {}]

        cfg["total_deltas"] = read_reg("r_delta_sum").get(0, -1)
        cfg["delta_counter"] = read_reg("r_delta_count").get(0, -1)
        cfg["min_delta"] = read_reg("r_delta_min").get(0, -1)
        cfg["max_delta"] = read_reg("r_delta_max").get(0, -1)

        c_throughput_ingress = read_cnt("c_throughput_ingress")
        c_throughput_egress = read_cnt("c_throughput_egress")
        c_stamped_throughput_ingress = read_cnt("c_stamped_throughput_ingress")
        c_stamped_throughput_egress = read_cnt("c_stamped_throughput_egress")

        error_val = 0
        for dut in cfg["dut_ports"]:
            i = dut["id"] - 1
            dut["num_ingress_packets"] = c_throughput_ingress[0].get(i,
                                                                     error_val)
            dut["num_ingress_bytes"] = c_throughput_ingress[1].get(i,
                                                                   error_val)
            dut["num_egress_packets"] = c_throughput_egress[0].get(i,
                                                                   error_val)
            dut["num_egress_bytes"] = c_throughput_egress[1].get(i, error_val)
            dut["num_ingress_stamped_packets"] = c_stamped_throughput_ingress[
                0].get(i, error_val)
            dut["num_ingress_stamped_bytes"] = c_stamped_throughput_ingress[
                1].get(i, error_val)
            dut["num_egress_stamped_packets"] = c_stamped_throughput_egress[
                0].get(i, error_val)
            dut["num_egress_stamped_bytes"] = c_stamped_throughput_egress[
                1].get(i, error_val)

        i = len(cfg["dut_ports"])
        for loadgen_grp in cfg["loadgen_groups"]:
            for host in loadgen_grp["loadgens"]:
                host["num_ingress_packets"] = c_throughput_ingress[0].get(
                    i, error_val)
                host["num_ingress_bytes"] = c_throughput_ingress[1].get(
                    i, error_val)
                host["num_egress_packets"] = c_throughput_egress[0].get(
                    i, error_val)
                host["num_egress_bytes"] = c_throughput_egress[1].get(
                    i, error_val)
                host["num_ingress_stamped_packets"] = \
                    c_stamped_throughput_ingress[0].get(i, error_val)
                host["num_ingress_stamped_bytes"] = \
                    c_stamped_throughput_ingress[1].get(i, error_val)
                host["num_egress_stamped_packets"] = \
                    c_stamped_throughput_egress[0].get(i, error_val)
                host["num_egress_stamped_bytes"] = c_stamped_throughput_egress[
                    1].get(i, error_val)
                i = i + 1

        cfg["ext_host_" + "num_ingress_packets"] = 0
        cfg["ext_host_" + "num_ingress_bytes"] = 0
        cfg["ext_host_" + "num_ingress_stamped_packets"] = 0
        cfg["ext_host_" + "num_ingress_stamped_bytes"] = 0

        cfg["ext_host_" + "num_egress_packets"] = c_throughput_egress[0].get(
            i, error_val)
        cfg["ext_host_" + "num_egress_bytes"] = c_throughput_egress[1].get(
            i, error_val)

        cfg["ext_host_" + "num_egress_stamped_packets"] = \
            c_stamped_throughput_egress[0].get(i, error_val)
        cfg["ext_host_" + "num_egress_stamped_bytes"] = \
            c_stamped_throughput_egress[1].get(i, error_val)

        return cfg

    def stamper_status(self, cfg):
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
                        formatted_uptime = str(
                            int(uptime / 3600)) + "h " + str(
                            int((uptime % 3600) / 60)) + "min " + str(
                            uptime % 60) + "s"
                    elif uptime >= 60:
                        formatted_uptime = str(
                            int(uptime / 60)) + "min " + str(uptime % 60) + "s"
                    else:
                        formatted_uptime = str(uptime) + "s"
                except Exception:
                    formatted_uptime = uptime
                dev_status = "{} {} ({}) for {}".format(status.uuid,
                                                        status.frontend_source,
                                                        status.
                                                        frontend_build_date,
                                                        formatted_uptime)

                n = 0
                for table in rte_client.table_list_all():
                    n = n + len(rte_client.table_retrieve(table.tbl_id))

                return ["Number of table rules: {}".format(
                    n)], status.is_loaded, dev_status
            else:
                print("Netronome: device status: is_loaded==False")
                print(status)
        except Exception:
            pass
        return [], False, "not running (starting may take a while)"

    # starts specific p4 software on device
    def start_stamper_software(self, cfg):
        rte_client = self._get_rte_client(cfg)

        nfpfw = open(cfg["nfpfw"], "rb").read()
        pif_design_json = open(cfg["pif_design_json"], "rb").read()
        # May fail if nfp-sdk6-rte.service was just started.
        # Workaround: load design with CLI once
        ret = rte_client.design_load(
            DesignLoadArgs(nfpfw, pif_design_json))  # this takes 30-40 seconds
        if ret.value != 0:
            print("err")
            raise RteError(ret.reason + "\nTry loading design with CLI once.")

        # Set CSR for timestamp format
        sshstr = "sudo /opt/netronome/bin/nfp-reg xpb:Nbi0IsldXpbMap." \
                 "NbiTopXpbMap.MacGlbAdrMap.MacCsr.MacSysSupCtrl.Time" \
                 "StampFrc=" + ("0x1" if TIMESTAMP_FRC else "0x0")
        self.execute_ssh(cfg, sshstr)

    def stop_stamper_software(self, cfg):
        rte_client = self._get_rte_client(cfg)
        rte_client.design_unload()

    # reset registers of p4 device
    def reset_p4_registers(self, cfg):
        rte_client = self._get_rte_client(cfg)
        rte_client.p4_counter_clear_all()
        registers_to_clear = ["r_delta_sum", "r_delta_count", "r_delta_max",
                              "r_delta_min", "r_extHost_count"]
        for register in rte_client.register_list_all():
            if register.name in registers_to_clear:
                rte_client.register_clear(RegisterArrayArg(reg_id=register.id))

    def get_stamper_startup_log(self, cfg):
        return ["For this target is no log available."]

    def check_if_p4_compiled(self, cfg):
        try:
            for f in [[cfg["nfpfw"],
                       b"ELF 64-bit LSB relocatable, *unknown arch 0x6000*"
                       b" version 1 (SYSV), not stripped\n"],
                      [cfg["pif_design_json"], b"ASCII text\n"]]:
                res = subprocess.run(["file", "-E", "-b", f[0]],
                                     stdout=subprocess.PIPE)
                if res.returncode != 0:
                    return False, res.stdout.decode('utf-8')
                if res.stdout != f[1]:
                    return False, "{} is wrong format: '{}'".format(
                        f[0], res.stdout.decode('utf-8'))
            return True, "Firmware files found and format correct"
        except Exception as e:
            return False, str(e)

    def get_server_install_script(self, user_name, ip,
                                  target_specific_dict={}):
        add_sudo_rights_str = "#!/bin/bash\nadd_sudo_rights() {\n  current_" \
                              "user=$USER\n  if (sudo -l | grep -q " \
                              "'(ALL : ALL) NOPASSWD: '$1); then\n    echo " \
                              "'visudo entry already exists';\n  else\n" \
                              "    sleep 0.1\n    echo $current_user' ALL=(" \
                              "ALL:ALL) NOPASSWD:'$1 | sudo EDITOR='tee " \
                              "-a' visudo;\n  fi\n}\n"
        with open(dir_path + "/scripts/install_nfp.sh", "w") as f:
            f.write(add_sudo_rights_str)
            for sudo in self.target_cfg["status_check"]["needed_sudos_to_add"]:
                f.write("add_sudo_rights " + sudo + "\n")
        os.chmod(dir_path + "/scripts/install_nfp.sh", 0o775)

        lst = []
        lst.append('echo "====================================="')
        lst.append('echo "Installing Netronome SmartNIC stamper target on ' +
                   ip + '"')
        lst.append('echo "====================================="')

        lst.append(
            'if ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
            user_name + '@' + ip + ' "echo \'ssh to ' + ip +
            ' ***worked***\';"; [ $? -eq 255 ]; then')

        lst.append('  echo "====================================="')
        lst.append(
            '  echo "\033[0;31m ERROR: Failed to connect to Stamper server ' +
            ip + ' \033[0m"')
        lst.append('  echo "====================================="')

        lst.append('else')

        lst.append(
            '  ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
            user_name + '@' + ip + ' "mkdir -p p4sta/stamper/;"')
        lst.append('  cd ' + self.realPath + '/scripts')
        lst.append(
            '  scp install_nfp.sh ' + user_name + '@' + ip + ':/home/' +
            user_name + '/p4sta/stamper/')
        lst.append(
            '  ssh  -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
            user_name + '@' + ip +
            ' "cd p4sta/stamper/; chmod +x install_nfp.sh;"')
        lst.append(
            '  ssh  -t -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
            user_name + '@' + ip + ' "cd p4sta/stamper/; ./install_nfp.sh;"')
        lst.append(
            '  echo "FINISHED setting up Netronome smartNIC stamper target"')
        lst.append('  echo "====================================="')
        lst.append('  echo "\033[1;33m WARNING: Netronome SDE 6.1.0 must '
                   'be installed manually \033[0m"')
        lst.append('  echo "====================================="')

        lst.append('fi')

        return lst
