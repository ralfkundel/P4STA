# Copyright 2019-present Ralf Kundel, Fridolin Siegmund
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

import ipaddress
import os
import subprocess
import sys
import time
import traceback

from tabulate import tabulate

dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir_path)
project_path = dir_path[0:dir_path.find("/stamper_targets")]
sys.path.append(project_path + "/core")
try:
    from abstract_target import AbstractTarget
    import P4STA_utils

    import bfrt_grpc.grpc_interface as grpc_interface
    import pd_fixed_api
except Exception:
    pass


class TargetImpl(AbstractTarget):

    def __init__(self, target_cfg):
        super().__init__(target_cfg)
        self.speed_list = ["10G", "25G", "40G", "50G", "100G"]

    def get_sde(self, cfg):
        try:
            if "sde" in cfg and len(cfg["sde"]) > 0:
                return cfg["sde"]
            else:
                raise Exception
        except Exception:
            return "/opt/bf-sde-9.3.0"

    def port_lists(self):
        temp = {}
        real_ports = []  # stores all real port name possibilities
        nr_ports = self.target_cfg["nr_ports"]
        for i in range(1, nr_ports + 1):
            for z in range(0, 4):
                real_ports.append(str(i) + "/" + str(z))
        real_ports.append("bf_pci0")
        if "p4_ports" in self.target_cfg:
            logical_ports = self.target_cfg["p4_ports"]
        else:
            P4STA_utils.log_error(
                "Error reading key 'p4_ports' from target_config.json")
            logical_ports = [-1 for i in range(nr_ports * 4 + 1)]
        temp["real_ports"] = real_ports
        temp["logical_ports"] = logical_ports

        return temp

    # returns list of stamper ports which are used
    def get_used_ports_list(self, cfg):
        cntr_port_list = []
        for dut in cfg["dut_ports"]:
            if dut["use_port"] == "checked":
                cntr_port_list.append(dut["p4_port"])
        cntr_port_list.append(cfg["ext_host"])

        for loadgen_grp in cfg["loadgen_groups"]:
            for host in loadgen_grp["loadgens"]:
                cntr_port_list.append(host["p4_port"])
        cntr_port_list = list(map(int, cntr_port_list))  # convert str to int
        return cntr_port_list

    def deploy(self, cfg):
        try:
            # client id is chosen randomly by TofinoInterface
            interface = grpc_interface.TofinoInterface(cfg["stamper_ssh"],
                                                       device_id=0)

            if type(interface) == str:  # error case
                interface = grpc_interface.TofinoInterface(cfg["stamper_ssh"],
                                                           device_id=0)
                if type(interface) == str:
                    total_error = interface.replace("\n", "")
                else:
                    total_error = ""
            else:
                total_error = ""

            if len(total_error) < 2:
                total_error = interface.bind_p4_name(cfg["program"])

        except Exception:
            total_error = total_error + str(traceback.format_exc()).replace(
                "\n", "")

        if len(total_error) < 2 and interface is not None:
            try:
                interface.delete_ports()
                interface.clear_multicast_groups()

                ignore_list = ["multi_counter_register", "ingress_counter",
                               "egress_counter", "ingress_stamped_counter",
                               "egress_stamped_counter",
                               "pipe.SwitchIngress.delta_register",
                               "pipe.SwitchIngress.delta_register_high",
                               "pipe.SwitchIngress.delta_register_pkts",
                               "pipe.SwitchIngress.min_register",
                               "pipe.SwitchIngress.max_register"]
                interface.clear_all_tables(ignore_list)

                hosts = []
                for loadgen_grp in cfg["loadgen_groups"]:
                    for host in loadgen_grp["loadgens"]:
                        if host["p4_port"] != "320":
                            hosts.append(host)

                for dut in cfg["dut_ports"]:
                    if dut["use_port"] == "checked":
                        hosts.append(dut)

                if cfg["ext_host_real"] != "bf_pci0" and cfg[
                        "ext_host"] != "320":
                    hosts.append({"p4_port": cfg["ext_host"],
                                  "real_port": cfg["ext_host_real"],
                                  "speed": cfg["ext_host_speed"],
                                  "fec": cfg["ext_host_fec"],
                                  "an": cfg["ext_host_an"]})
                interface.set_ports(hosts)

                self.deploy_tables(cfg, interface)

                mcast_inp = [{"node_id": 1, "group_id": 1,
                              "port": int(cfg["ext_host"])}]
                node_id = 2
                # add to group with own group id +1
                # (because ext host already blocks ID 1)
                for loadgen_grp in cfg["loadgen_groups"]:
                    for host in loadgen_grp["loadgens"]:
                        mcast_inp.append({"node_id": node_id,
                                          "group_id": loadgen_grp["group"] + 1,
                                          "port": int(host["p4_port"])})
                        node_id = node_id + 1

                # same DUT port in group for duplication feature
                start_group = 50
                for dut in cfg["dut_ports"]:
                    if "dataplane_duplication" in dut and dut[
                        "dataplane_duplication"].isdigit() and int(
                            dut["dataplane_duplication"]) > 0:
                        try:
                            duplication_scale = int(
                                dut["dataplane_duplication"])
                            if duplication_scale < 0:
                                raise ValueError
                        except ValueError:
                            P4STA_utils.log_error(
                                "Input Dataplane Duplication for DUT port "
                                + str(dut["real_port"]) +
                                " is not a valid number - "
                                "no duplication activated.")
                            duplication_scale = 0
                        for i in range(duplication_scale):
                            mcast_inp.append({"node_id": node_id,
                                              "group_id": start_group + dut[
                                                  "id"],
                                              "port": int(dut["p4_port"])})
                            node_id = node_id + 1

                interface.set_multicast_groups(mcast_inp)
            except Exception:
                total_error = total_error + str(
                    traceback.format_exc()).replace("\n", "")
            finally:
                interface.teardown()

            # set traffic shaping
            thrift = pd_fixed_api.PDFixedConnect(cfg["stamper_ssh"])

            def set_shape(host, key=""):
                try:
                    if key + "shape" in host and host[key + "shape"] != "":
                        if (type(host[key + "p4_port"]) == str and host[
                            key + "p4_port"].isdigit()) or type(
                                host[key + "p4_port"] == int):
                            if (type(host[key + "shape"]) == str and host[
                                key + "shape"].isdigit()) or type(
                                    host[key + "shape"] == int):
                                if int(host[key + "shape"]) == 0:
                                    thrift.disable_port_shaping(
                                        int(host[key + "p4_port"]))
                                elif 2147483647 > int(host[key + "shape"]) > 0:
                                    # set in kbit/s
                                    thrift.set_port_shaping_rate(
                                        int(host[key + "p4_port"]),
                                        int(host[key + "shape"]) * 1000)
                                    thrift.enable_port_shaping(
                                        int(host[key + "p4_port"]))
                                    print("Limit port " + str(
                                        host[key + "p4_port"]) + " to " + str(
                                        host[key + "shape"]) +
                                          " Mbit/s outgoing (from stamper).")
                                else:
                                    raise Exception(
                                        "wrong limit (" + str(host[key +
                                                                   "shape"]) +
                                        ") for p4_port: " + str(host[key +
                                                                "p4_port"]) +
                                        ". Allowed from 0 (disable) to "
                                        "2147483646")
                            else:
                                raise Exception("wrong type for shape: " + str(
                                    host[key + "shape"]))
                        else:
                            raise Exception("wrong type for p4_port: " + str(
                                host[key + "p4_port"]))
                except Exception:
                    print(traceback.format_exc())

            if thrift.error:
                total_error = total_error + "\n" + thrift.error_message
            else:
                for loadgen_grp in cfg["loadgen_groups"]:
                    for host in loadgen_grp["loadgens"]:
                        set_shape(host)

                for dut in cfg["dut_ports"]:
                    set_shape(dut)

                cfg["ext_host_p4_port"] = cfg["ext_host"]
                set_shape(cfg, key="ext_host_")

                print("Set port shaping finished.")
        if total_error is not "":
            return total_error

    def deploy_tables(self, cfg, interface):
        def mac_str_to_int(mac_str):
            return int("".join(mac_str.split(":")), 16)

        all_dut_dst_p4_ports = self.get_all_dut_dst_p4_ports(cfg)

        try:
            ###################
            # t_l1_forwarding #
            ###################
            t_l1_forwarding = "pipe.SwitchIngress.t_l1_forwarding"
            if cfg['forwarding_mode'] == "1":
                try:
                    for dut in cfg["dut_ports"]:
                        if dut["use_port"] == "checked":
                            for loadgen_grp in cfg["loadgen_groups"]:
                                if loadgen_grp["group"] == dut["id"] \
                                        and len(loadgen_grp["loadgens"]) > 0:
                                    interface.add_to_table(
                                        t_l1_forwarding, [
                                            ["ig_intr_md.ingress_port",
                                                int(dut["p4_port"])]
                                        ], [
                                            ["egress_port",
                                                int(loadgen_grp[
                                                    "loadgens"][0]["p4_port"])]
                                        ],
                                        "SwitchIngress.send"
                                    )
                                    break
                except Exception as e:
                    # probably because no host in group 2
                    print(traceback.format_exc())

            for loadgen_grp in cfg["loadgen_groups"]:
                for dut in cfg["dut_ports"]:
                    if loadgen_grp["group"] == dut["id"] \
                            and dut["use_port"] == "checked":
                        for host in loadgen_grp["loadgens"]:
                            interface.add_to_table(t_l1_forwarding,
                                                   [["ig_intr_md.ingress_port",
                                                     int(host["p4_port"])]],
                                                   [["egress_port",
                                                     int(dut["p4_port"])]],
                                                   "SwitchIngress.send")
        except Exception:
            print(traceback.format_exc())

        try:
            ###################
            # t_l2_forwarding #
            ###################
            if int(cfg['forwarding_mode']) >= 2:
                t_l2_forwarding = "pipe.SwitchIngress.t_l2_forwarding"

                for dut in cfg["dut_ports"]:
                    if dut["use_port"] == "checked":
                        interface.add_to_table(t_l2_forwarding, [
                            ["ig_intr_md.ingress_port", int(dut["p4_port"])],
                            ["hdr.ethernet.dstAddr",
                             mac_str_to_int("ff:ff:ff:ff:ff:ff")]],
                                               [["group", dut["id"] + 1]],
                                               "SwitchIngress.send_to_mc_group"
                                               )

                print("create table entries for l2 forwarding")

                for loadgen_grp in cfg["loadgen_groups"]:
                    for dut in cfg["dut_ports"]:
                        if loadgen_grp["group"] == dut["id"] \
                                and dut["use_port"] == "checked":
                            for host in loadgen_grp["loadgens"]:
                                interface.add_to_table(
                                    t_l2_forwarding, [
                                        ["ig_intr_md.ingress_port",
                                         int(dut["p4_port"])],
                                        ["hdr.ethernet.dstAddr",
                                         mac_str_to_int(host["loadgen_mac"])]
                                    ],
                                    [
                                        ["egress_port",
                                         int(host["p4_port"])]
                                    ],
                                    "SwitchIngress.send")
        except Exception as e:
            print(traceback.format_exc())

        try:
            ###################
            # t_l3_forwarding #
            ###################
            if cfg['forwarding_mode'] == "3":
                print("create table entries for l3 forwarding")
                t_l3_forwarding = "pipe.SwitchIngress.t_l3_forwarding"

                for loadgen_grp in cfg["loadgen_groups"]:
                    for dut in cfg["dut_ports"]:
                        if loadgen_grp["group"] == dut["id"] \
                                and dut["use_port"] == "checked":
                            for host in loadgen_grp["loadgens"]:
                                interface.add_to_table(
                                    t_l3_forwarding,
                                    [
                                        ["ig_intr_md.ingress_port",
                                            int(dut["p4_port"])],
                                        ["hdr.ipv4.dstAddr",
                                            int(ipaddress.IPv4Address(
                                              host["loadgen_ip"]))]
                                    ],
                                    [
                                        ["egress_port",
                                         int(host["p4_port"])]
                                    ],
                                    "SwitchIngress.send")
        except Exception:
            print(traceback.format_exc())

        try:
            #############################
            # t_add_empty_timestamp_tcp #
            #############################
            t_add_empty_timestamp_tcp = "pipe.SwitchIngress." \
                                        "t_add_empty_timestamp_tcp"

            for dut in cfg["dut_ports"]:
                if dut["use_port"] == "checked" and dut[
                    "stamp_outgoing"] == "checked" \
                        and cfg["stamp_tcp"] == "checked":
                    interface.add_to_table(t_add_empty_timestamp_tcp,
                                           [["hdr.tcp.dataOffset", 5],
                                            ["ig_intr_tm_md.ucast_egress_port",
                                             int(dut["p4_port"])]], [],
                                           "SwitchIngress."
                                           "add_timestamp_header_tcp")
                    interface.add_to_table(t_add_empty_timestamp_tcp,
                                           [["hdr.tcp.dataOffset", 8],
                                            ["ig_intr_tm_md.ucast_egress_port",
                                             int(dut["p4_port"])]], [],
                                           "SwitchIngress."
                                           "add_timestamp_header_tcp")

        except Exception as e:
            print(traceback.format_exc())

        try:
            #############################
            # broadcast_mac             #
            #############################
            t_broadcast_mac = "pipe.SwitchEgress.broadcast_mac"
            interface.add_to_table(t_broadcast_mac, [
                ["eg_intr_md.egress_port", int(cfg["ext_host"])]],
                                   [["dst", 0xffffffffffff]],
                                   "SwitchEgress.change_mac")
        except Exception as e:
            print(traceback.format_exc())

        try:
            #############################
            # t_timestamp2_tcp          #
            #############################

            if cfg["stamp_tcp"] == "checked":
                t_timestamp2_tcp = "pipe.SwitchIngress.t_timestamp2_tcp"
                for p4_port_flow_dst in all_dut_dst_p4_ports:
                    interface.add_to_table(t_timestamp2_tcp,
                                           [["hdr.tcp.dataOffset", 0x9], [
                                               "hdr.tcp_options_128bit_custom."
                                               "myType",
                                               0x0f10],
                                            ["ig_intr_md.ingress_port",
                                             int(p4_port_flow_dst)]], [
                                               ["threshold",
                                                int(cfg["multicast"]) - 1]],
                                           "SwitchIngress.add_timestamp2_tcp")
                    interface.add_to_table(t_timestamp2_tcp,
                                           [["hdr.tcp.dataOffset", 0xc], [
                                               "hdr.tcp_options_128bit_custom."
                                               "myType",
                                               0x0f10],
                                            ["ig_intr_md.ingress_port",
                                             int(p4_port_flow_dst)]], [
                                               ["threshold",
                                                int(cfg["multicast"]) - 1]],
                                           "SwitchIngress.add_timestamp2_tcp")
        except Exception as e:
            print(traceback.format_exc())

        try:
            ##################################################
            # t_add_empty_timestamp_udp & t_timestamp2_udp   #
            ##################################################
            if cfg["stamp_udp"] == "checked":
                t_add_empty_timestamp_udp = "pipe.SwitchIngress." \
                                            "t_add_empty_timestamp_udp"
                t_timestamp2_udp = "pipe.SwitchIngress.t_timestamp2_udp"

                for dut in cfg["dut_ports"]:
                    if dut["stamp_outgoing"] == "checked" \
                            and dut["use_port"] == "checked":
                        interface.add_to_table(t_add_empty_timestamp_udp,
                                               [[
                                                    "ig_intr_tm_md."
                                                    "ucast_egress_port",
                                                    int(dut["p4_port"])]], [],
                                               "SwitchIngress."
                                               "add_timestamp_header_udp")

                for p4_port_flow_dst in all_dut_dst_p4_ports:
                    interface.add_to_table(t_timestamp2_udp,
                                           [[
                                                "hdr.tcp_options_"
                                                "128bit_custom.myType",
                                                0x0f10],
                                            ["ig_intr_md.ingress_port",
                                             int(p4_port_flow_dst)]],
                                           [["threshold",
                                             int(cfg["multicast"]) - 1]],
                                           "SwitchIngress.add_timestamp2_udp")
        except Exception:
            print(traceback.format_exc())

        try:
            #############################
            #    for external host      #
            #############################
            # to ensure that the external host can't send packets into stamper
            t_l1_forwarding = "pipe.SwitchIngress.t_l1_forwarding"
            interface.add_to_table(t_l1_forwarding, [
                ["ig_intr_md.ingress_port", int(cfg["ext_host"])]], [],
                                   "SwitchIngress.no_op")
        except Exception as e:
            print(traceback.format_exc())

        try:
            #############################
            #    dataplane duplication  #
            #############################
            t_duplicate_to_dut = "pipe.SwitchIngress.t_duplicate_to_dut"
            t_mark_duplicate = "pipe.SwitchEgress.t_mark_duplicate"

            for dut in cfg["dut_ports"]:
                if "dataplane_duplication" in dut and dut[
                    "dataplane_duplication"].isdigit() and int(
                        dut["dataplane_duplication"]) > 0 \
                        and dut["use_port"] == "checked":
                    interface.add_to_table(t_duplicate_to_dut,
                                           [["ig_intr_tm_md.ucast_egress_port",
                                             int(dut["p4_port"])]],
                                           [["group", 50 + dut["id"]]],
                                           "SwitchIngress.duplicate_to_dut")
                    interface.add_to_table(t_mark_duplicate,
                                           [["eg_intr_md.egress_port",
                                             int(dut["p4_port"])]], [],
                                           "SwitchEgress.change_empty_field")
        except Exception as e:
            print(traceback.format_exc())

    def read_stamperice(self, cfg):
        def get_at_index(list, index):
            try:
                if type(index) == str and index.isdigit():
                    return list[int(index)]
                elif type(index) == int:
                    return list[index]
                else:
                    raise ValueError
            except Exception:
                return 0

        interface = grpc_interface.TofinoInterface(cfg["stamper_ssh"], 0)
        if type(interface) == str:
            return
        interface.bind_p4_name(cfg["program"])
        try:
            cntr_port_list = self.get_used_ports_list(cfg)
            before = time.time()

            ingress_counter = "pipe.SwitchIngress.ingress_counter"
            all_ingress_counter = interface.read_counter(
                ingress_counter, port_list=cntr_port_list)

            ingress_stamped_counter = "pipe.SwitchIngress." \
                                      "ingress_stamped_counter"
            all_ingress_stamped_counter = interface.read_counter(
                ingress_stamped_counter, port_list=cntr_port_list)

            egress_counter = "pipe.SwitchEgress.egress_counter"
            all_egress_counter = interface.read_counter(
                egress_counter, port_list=cntr_port_list)

            egress_stamped_counter = "pipe.SwitchEgress.egress_stamped_counter"
            all_egress_stamped_counter = interface.read_counter(
                egress_stamped_counter, port_list=cntr_port_list)

            print("Retrieving the counters took " + str(
                time.time() - before) + " seconds.")

            #############################
            #      register read        #
            #############################
            high_read = interface.read_register(
                "pipe.SwitchIngress.delta_register_high")
            print("delta_register_high: " + str(high_read))
            low_read = max(high_read)
            overflow = 0
            try:
                overflow = min([x for x in high_read
                                if ((x > 0) and (x != low_read))])
            except Exception:
                overflow = 0
            total_deltas = (overflow << 32) + low_read

            delta_counter = sum(interface.read_register(
                "pipe.SwitchIngress.delta_register_pkts"))

            cleared_min = [i for i in interface.read_register(
                "pipe.SwitchIngress.min_register") if i > 0]
            if len(cleared_min) > 0:
                min_delta = min(cleared_min)
            else:
                min_delta = 0

            max_delta = max(
                interface.read_register("pipe.SwitchIngress.max_register"))

            print("total deltas:" + str(total_deltas))
            print("delta counter:" + str(delta_counter))
            if delta_counter > 0:
                print("delta per packet:" + str(
                    total_deltas / delta_counter) + "ns")
            print("min_delta:" + str(min_delta))
            print("max_delta:" + str(max_delta))

            cfg["total_deltas"] = total_deltas
            cfg["delta_counter"] = delta_counter
            cfg["min_delta"] = min_delta
            cfg["max_delta"] = max_delta

            for dut in cfg["dut_ports"]:
                dut["num_ingress_packets"], dut[
                    "num_ingress_bytes"] = get_at_index(all_ingress_counter,
                                                        dut["p4_port"])
                dut["num_egress_packets"], dut[
                    "num_egress_bytes"] = get_at_index(all_egress_counter,
                                                       dut["p4_port"])
                dut["num_ingress_stamped_packets"], dut[
                    "num_ingress_stamped_bytes"] = get_at_index(
                    all_ingress_stamped_counter, dut["p4_port"])
                dut["num_egress_stamped_packets"], dut[
                    "num_egress_stamped_bytes"] = get_at_index(
                    all_egress_stamped_counter, dut["p4_port"])

            for loadgen_grp in cfg["loadgen_groups"]:
                for host in loadgen_grp["loadgens"]:
                    host["num_ingress_packets"], host[
                        "num_ingress_bytes"] = get_at_index(
                        all_ingress_counter, host["p4_port"])
                    host["num_egress_packets"], host[
                        "num_egress_bytes"] = get_at_index(all_egress_counter,
                                                           host["p4_port"])
                    host["num_ingress_stamped_packets"], host[
                        "num_ingress_stamped_bytes"] = get_at_index(
                        all_ingress_stamped_counter, host["p4_port"])
                    host["num_egress_stamped_packets"], host[
                        "num_egress_stamped_bytes"] = get_at_index(
                        all_egress_stamped_counter, host["p4_port"])

            cfg["ext_host_" + "num_ingress_packets"], cfg[
                "ext_host_" + "num_ingress_bytes"] = get_at_index(
                all_ingress_counter, cfg["ext_host"])
            cfg["ext_host_" + "num_ingress_stamped_packets"], cfg[
                "ext_host_" + "num_ingress_stamped_bytes"] = get_at_index(
                all_ingress_stamped_counter, cfg["ext_host"])
            cfg["ext_host_" + "num_egress_packets"], cfg[
                "ext_host_" + "num_egress_bytes"] = get_at_index(
                all_egress_counter, cfg["ext_host"])
            cfg["ext_host_" + "num_egress_stamped_packets"], cfg[
                "ext_host_" + "num_egress_stamped_bytes"] = get_at_index(
                all_egress_stamped_counter, cfg["ext_host"])

        except Exception:
            print(traceback.format_exc())

        finally:
            interface.teardown()

        return cfg

    def stamper_status(self, cfg):
        lines = subprocess.run(
            [dir_path + "/scripts/switchd_status.sh", cfg["stamper_user"],
             cfg["stamper_ssh"]], stdout=subprocess.PIPE).stdout.decode(
            "utf-8").split("\n")

        try:
            if len(lines) > 0 and lines[0].isdigit() and int(lines[0]) > 0:
                dev_status = "Yes! PID: " + str(lines[0])
                try:
                    start = lines[2].find("/p4/targets/tofino/") + 19
                    end = lines[2].find(".conf")
                    parsed_prog = lines[2][start:end]
                    if parsed_prog == cfg["program"]:
                        dev_status = dev_status + " | " + parsed_prog
                    else:
                        dev_status = dev_status + \
                                     ' | <span style="color:red">' + \
                                     parsed_prog + ' (does not match ' \
                                                   'configured program)</span>'
                except Exception:
                    dev_status = dev_status + \
                                 " | error parsing currently " \
                                 "loaded program on p4 device."
                running = True

                interface = grpc_interface.TofinoInterface(cfg["stamper_ssh"],
                                                           0)
                try:
                    interface.bind_p4_name(cfg["program"])

                    # returns list of dictionaries with port status
                    port_status_list = interface.read_port_status()

                    rows = [
                        ["Port", "Status", "Enb", "Speed", "AN SET", "FEC"],
                        ["----", "------", "----", "-----", "-------", "----"]]
                    enb_rows = []
                    dis_rows = []
                    for port_status in port_status_list:
                        if port_status["$PORT_UP"].bool_val:
                            up = "_UP_"
                        else:
                            up = "DOWN"
                        an_status = port_status["$AUTO_NEGOTIATION"]
                        if an_status.str_val == "PM_AN_FORCE_ENABLE":
                            an_set = "__ON___"
                        elif an_status.str_val == "PM_AN_FORCE_DISABLE":
                            an_set = "__OFF__"
                        elif an_status.str_val == "PM_AN_DEFAULT":
                            an_set = "DEFAULT"
                        else:
                            an_set = "UNKNOWN"

                        if port_status["$PORT_ENABLE"].bool_val:
                            enb_rows.append(
                                [port_status["$PORT_NAME"].str_val, up,
                                 str(port_status["$PORT_ENABLE"].bool_val),
                                 port_status["$SPEED"].str_val.split("_")[-1],
                                 an_set,
                                 port_status["$FEC"].str_val.split("_")[-1]])
                        else:
                            dis_rows.append(
                                [port_status["$PORT_NAME"].str_val, up,
                                 str(port_status["$PORT_ENABLE"].bool_val),
                                 port_status["$SPEED"].str_val.split("_")[-1],
                                 an_set,
                                 port_status["$FEC"].str_val.split("_")[-1]])
                    if len(dis_rows) != 0:
                        rows.append(["ENABLED PORTS:"])
                    rows.extend(enb_rows)
                    if len(enb_rows) == 0:
                        rows.append(["---", "---", "---", "---", "---", "---"])
                    # only if nothing is enabled disabled rows are returned
                    # by grpc tofino call
                    if len(dis_rows) != 0:
                        rows.append(["DISABLED PORTS:"])
                        rows.extend(dis_rows)
                    lines_pm = tabulate(rows).split("\n")
                except Exception:
                    error = traceback.format_exc()
                    print(error)
                    lines_pm = ["Error retrieving port status from tofino."]
                    lines_pm.extend(traceback.format_exc().split("\n"))
                finally:
                    interface.teardown()
            else:
                dev_status = "not running"
                running = False
                lines_pm = ["Port-manager not available"]
        except Exception:
            print(traceback.format_exc())
            dev_status = "not running"
            running = False
            lines_pm = ["Port-manager not available"]

        return lines_pm, running, dev_status

    def start_stamper_software(self, cfg):
        script_dir = dir_path + "/scripts/run_switchd.sh"
        output_sub = subprocess.run(
            [dir_path + "/scripts/start_switchd.sh", cfg["stamper_ssh"],
             cfg["stamper_user"], self.get_sde(cfg), cfg["program"],
             script_dir], stdout=subprocess.PIPE)
        print("started stamper dev software - sleep 15 sec until grpc is up")
        time.sleep(15)
        print("grpc ports of tofino should be up now")
        print(output_sub)

    def get_stamper_startup_log(self, cfg):
        result = self.execute_ssh(
            cfg,
            'cd p4sta; echo "Last modified:"; stat -c %y "startup.log"; '
            'echo "Modified by: "; stat -c %U "startup.log"; cat startup.log')

        results = []
        for r in result:
            if r.find("|") == -1:
                results.append(r)

        return results

    def stop_stamper_software(self, cfg):
        output_sub = subprocess.run(
            [dir_path + "/scripts/stop_switchd.sh", cfg["stamper_ssh"],
             cfg["stamper_user"]], stdout=subprocess.PIPE)

    def reset_p4_registers(self, cfg):
        interface = grpc_interface.TofinoInterface(cfg["stamper_ssh"],
                                                   device_id=0)
        if type(interface) == str:
            print("error resetting registers ..")
            print(interface)
            return interface
        interface.bind_p4_name(cfg["program"])
        try:
            # clear counters
            cntr_port_list = self.get_used_ports_list(cfg)
            for name in ["Ingress.ingress_counter",
                         "Ingress.ingress_stamped_counter",
                         "Egress.egress_counter",
                         "Egress.egress_stamped_counter"]:
                print("CLEAR COUNTER: " + "pipe.Switch" + name)
                try:
                    interface.clear_indirect_counter("pipe.Switch" + name,
                                                     id_list=cntr_port_list)
                except Exception:
                    P4STA_utils.log_error(traceback.format_exc())

            # clear indirect registers
            for name in ["delta_register", "min_register", "max_register",
                         "delta_register_high", "delta_register_pkts",
                         "multi_counter_register"]:
                print("CLEAR REGISTER: " + name)
                try:
                    interface.clear_register("pipe.SwitchIngress." + name)
                except Exception:
                    P4STA_utils.log_error(traceback.format_exc())
        except Exception:
            P4STA_utils.log_error(traceback.format_exc())
        finally:
            interface.teardown()

    def check_if_p4_compiled(self, cfg):
        arg = "[ -d '" + self.get_sde(cfg) + "/build/p4-build/" + cfg[
            "program"] + "' ] && echo 'y'; exit"
        answer = self.execute_ssh(cfg, arg)

        if answer[0] != "y":
            return False, cfg["program"] + " not compiled: " + cfg[
                "sde"] + "/build/p4-build/" + cfg["program"] + "/ not found."
        else:
            return True, cfg["program"] + " is compiled: " + cfg[
                "sde"] + "/build/p4-build/" + cfg["program"] + "/ found."

    def needed_dynamic_sudos(self, cfg):
        return [cfg["sde"] + "/run_switchd.sh"]

    # target_specific_dict contains input fields from /setup_devices/
    # => here SDE path
    def get_server_install_script(self, user_name, ip,
                                  target_specific_dict={}):
        print("INSTALLING TOFINO STAMPER TARGET:")
        print(target_specific_dict)
        sde_path = ""
        if "sde" in target_specific_dict and len(
                target_specific_dict["sde"]) > 1:
            sde_path = target_specific_dict["sde"]
        else:
            lines = P4STA_utils.execute_ssh(user_name, ip, "cat $HOME/.bashrc")
            for line in lines:
                if line.find("export SDE_INSTALL") > -1:
                    lrep = line.replace("\n", "")
                    start = lrep.find("=") + 1
                    sde_path = lrep[start:]
                    print("/**************************/")
                    print(
                        "Found $SDE_INSTALL at target " + ip +
                        " = " + sde_path)
                    print("/**************************/")
            if sde_path == "":
                print(
                    "\033[1;33m/**********************************"
                    "****************************/")
                print(
                    "WARNING: SDE Path not found on Tofino, using "
                    "/opt/bf-sde-9.3.0")
                print(
                    "/*********************************************"
                    "*****************/\033[0m")
                sde_path = "/opt/bf-sde-9.3.0"

        # create install_tofino.sh
        add_sudo_rights_str = "#!/bin/bash\nadd_sudo_rights() {\ncurrent_" \
                              "user=$USER\n  if (sudo -l | grep -q " \
                              "'(ALL : ALL) SETENV: NOPASSWD: '$1); then\n  " \
                              "  echo 'visudo entry already exists';" \
                              "\n  else\n    sleep 0.1\n    echo " \
                              "$current_user' ALL=(ALL:ALL) NOPASSWD:" \
                              "SETENV:'$1 | " \
                              "sudo EDITOR='tee -a' visudo; \n  fi\n}\n"

        with open(dir_path + "/scripts/install_tofino.sh", "w") as f:
            f.write(add_sudo_rights_str)
            for sudo in self.target_cfg["status_check"]["needed_sudos_to_add"]:
                if sudo.find("run_switchd.sh") > -1:
                    f.write(
                        "add_sudo_rights " + sde_path + "/run_switchd.sh\n")
                else:
                    f.write("add_sudo_rights $(which " + sudo + ")\n")
        os.chmod(dir_path + "/scripts/install_tofino.sh", 0o775)

        lst = []
        lst.append('echo "====================================="')
        lst.append(
            'echo "Installing Barefoot Tofino stamper target on ' + ip + '"')
        lst.append('echo "====================================="')

        lst.append('echo "START: Copying Tofino files on remote server:"')
        lst.append('cd ' + dir_path + "/scripts")

        lst.append('if ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no '
                   + user_name + '@' + ip + ' "echo \'ssh to ' + ip
                   + ' ***worked***\';"; [ $? -eq 255 ]; then')

        lst.append('  echo "====================================="')
        lst.append('  echo "\033[0;31m ERROR: Failed to connect to Stamper '
                   'server with IP: ' + ip + ' \033[0m"')
        lst.append('  echo "====================================="')

        lst.append('else')
        lst.append(
            '  chmod +x stop_switchd.sh start_switchd.sh switchd_status.sh')
        lst.append('  ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no '
                   + user_name + '@' + ip + ' \"echo "SSH to stamper device **'
                                            '*__worked__***\"; mkdir -p /home/'
                   + user_name + '/p4sta/stamper/tofino1/"')

        lst.append("   echo ")

        lst.append('  scp install_tofino.sh ' + user_name + '@' + ip +
                   ':/home/' + user_name + '/p4sta/stamper/tofino1/')
        lst.append('  ssh  -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
                   user_name + '@' + ip + ' "cd /home/' + user_name +
                   '/p4sta/stamper/tofino1/; chmod +x install_tofino.sh;"')
        lst.append('  ssh  -t -o ConnectTimeout=2 -o StrictHostKeyChecking=no '
                   + user_name + '@' + ip + ' "cd /home/' + user_name +
                   '/p4sta/stamper/tofino1; ./install_tofino.sh ' + ';"')

        lst.append('  echo "Downloading bfruntime.proto from Tofino Target"')
        # important to use dir_path because THIS file is stored
        # there but target could be other tofino
        lst.append('  cd ' + dir_path + '/bfrt_grpc')
        lst.append('  scp ' + user_name + '@' + ip + ':' + sde_path +
                   '/install/share/bf_rt_shared/proto/bfruntime.proto proto/ ')
        lst.append('  echo "Building python3 stub at management server from '
                   'bfruntime.proto for Tofino Target"')
        lst.append('  source ../../../pastaenv/bin/activate; python3 -m '
                   'grpc_tools.protoc -I ./proto --python_out=. '
                   '--grpc_python_out=. ./proto/bfruntime.proto; deactivate')

        lst.append('  echo "FINISHED setting up Barefoot Tofino target"')
        lst.append('  echo "====================================="')
        lst.append('  echo "\033[0;31m IMPORTANT NOTE: P4 source code must be '
                   'compiled manually on Tofino after compiling Intel/Barefoot'
                   ' SDE\033[0m"')
        lst.append('  echo "====================================="')
        lst.append('  echo ""')
        lst.append('  echo "====================================="')
        lst.append('  echo "\033[0;31m IMPORTANT NOTE: Please stop the install'
                   '.sh script in the CLI and restart P4STA with ./run.sh in o'
                   'rder to load the freshly compiled grpc files correctly. '
                   '\033[0m"')
        lst.append('  echo "====================================="')
        lst.append('fi')

        return lst
