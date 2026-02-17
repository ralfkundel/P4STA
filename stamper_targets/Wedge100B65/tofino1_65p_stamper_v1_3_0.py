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
import json
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
except Exception as e:
    # no logger obj available outside of class
    print(traceback.format_exc())


class TargetImpl(AbstractTarget):

    def __init__(self, target_cfg, logger):
        super().__init__(target_cfg, logger)
        self.port_mapping = None

    def get_sde(self, cfg):
        try:
            if "sde" in cfg and len(cfg["sde"]) > 0:
                return cfg["sde"]
            else:
                raise Exception
        except Exception:
            return "/opt/bf-sde-9.13.0"

    def get_port_mapping(self, ssh_ip, data_plane_program_name, tofino_grpc_obj):
        if self.port_mapping is None:
            try:
                if tofino_grpc_obj != None and tofino_grpc_obj.p4_connected:
                    self.logger.info("Open P4 connection reused")
                    interface = tofino_grpc_obj
                else:
                    interface = grpc_interface.TofinoInterface(ssh_ip, 0, self.logger)
                    interface.bind_p4_name(data_plane_program_name)
                if not interface.connection_established and interface.p4_connected:
                    interface.teardown()
                    return None # case where run_switchd is not running correctly
                self.port_mapping = interface.get_port_mapping()
                if "static_ports" in self.target_cfg:
                    for port_name in self.target_cfg["static_ports"]:
                        internal_port_id = self.target_cfg["static_ports"][port_name]
                        self.port_mapping[port_name] = internal_port_id
            except Exception:
                self.logger.error(traceback.format_exc())
            finally:
                if interface is not None:
                    interface.teardown()
        return self.port_mapping

    def update_portmapping(self, cfg, tofino_grpc_obj=None):
        port_map = self.get_port_mapping(cfg["stamper_ssh"], cfg["program"], tofino_grpc_obj)

        if port_map is None:
            return cfg

        # 1 dut ports
        for dut_port in cfg["dut_ports"]:
            # real port can be e 1/0, 1/2.. for breakout and 1/0 for full, but also 1/- for full
            port = dut_port["real_port"].replace("-", "0")
            if port in port_map:
                dut_port["p4_port"] = port_map[port]

        # 2 loadgen ports
        for loadgen_group in cfg["loadgen_groups"]:
            for loadgen in loadgen_group["loadgens"]:
                # real port can be e 1/0, 1/2.. for breakout and 1/0 for full, but also 1/- for full
                port = loadgen["real_port"].replace("-", "0")
                if port in port_map:
                    loadgen["p4_port"] = port_map[port]

        # 3 ext host
        if cfg["ext_host_real"] in port_map:
            cfg["ext_host"] = port_map[cfg["ext_host_real"]]

        # 4 additional ports
        if "additional_ports" in cfg:
            for port in cfg["additional_ports"]:
                # real port can be e 1/0, 1/2.. for breakout and 1/0 for full, but also 1/- for full
                real_port = port["real_port"].replace("-", "0")
                if real_port in port_map:
                    port["p4_port"] = port_map[real_port]

        return cfg

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

    def deploy(self, cfg, tofino_grpc_obj=None):
        try:
            if tofino_grpc_obj != None and tofino_grpc_obj.connection_established and tofino_grpc_obj.p4_connected:
                self.logger.debug("reuse open connection in passed tofino_grpc_obj")
                interface = tofino_grpc_obj
            else:
                # client id is chosen randomly by TofinoInterface
                interface = grpc_interface.TofinoInterface(cfg["stamper_ssh"], 0, self.logger)

                if type(interface) == str:  # error case
                    interface = grpc_interface.TofinoInterface(cfg["stamper_ssh"], 0, self.logger)
                    if type(interface) == str:
                        total_error = interface.replace("\n", "")
                    else:
                        total_error = ""
                else:
                    total_error = ""

                if len(total_error) < 2:
                    total_error = interface.bind_p4_name(cfg["program"])

        except Exception:
            total_error = total_error + str(traceback.format_exc()).replace("\n", "")

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
                               "pipe.SwitchIngress.delta_register_pkts_high",
                               "pipe.SwitchIngress.min_register",
                               "pipe.SwitchIngress.max_register",
                               "pipe.snapshot.ingress_data",
                               "pipe.snapshot.ingress_liveness",
                               "pipe.snapshot.egress_data",
                               "pipe.snapshot.egress_liveness",
                               "tbl_dbg_counter"
                               ]
                interface.clear_all_tables(ignore_list)

                ignore_ports = ["320"]
                if "packet_generator_ports" in self.target_cfg:
                    ignore_ports.extend(self.target_cfg["packet_generator_ports"])
                hosts = []
                for loadgen_grp in cfg["loadgen_groups"]:
                    for host in loadgen_grp["loadgens"]:
                        if host["p4_port"] not in ignore_ports:
                            hosts.append(host)

                for dut in cfg["dut_ports"]:
                    if dut["use_port"] == "checked":
                        hosts.append(dut)

                self.logger.debug(self.target_cfg)

                if cfg["ext_host_real"] != "bf_pci0" and cfg["ext_host"] != "320":
                    hosts.append({"p4_port": cfg["ext_host"],
                                  "real_port": cfg["ext_host_real"],
                                  "speed": cfg["ext_host_speed"],
                                  "fec": cfg["ext_host_fec"],
                                  "an": cfg["ext_host_an"]})
                    
                if "additional_ports" in cfg:
                    for port in cfg["additional_ports"]:
                        found = False
                        for host in hosts:
                            if host["real_port"] == port["real_port"]:
                                found = True
                        if not found:
                            hosts.append(port)

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
                            self.logger.error(
                                "Input Dataplane Duplication for DUT port "
                                + str(dut["real_port"]) +
                                " is not a valid number - " +
                                "no duplication activated.")
                            duplication_scale = 0
                        for i in range(duplication_scale):
                            mcast_inp.append({"node_id": node_id,
                                              "group_id": start_group + dut["id"],
                                              "port": int(dut["p4_port"])})
                            node_id = node_id + 1

                # workaround for additional ports multicasting
                with open("mcast_grps_deployment.json", "w+") as f:
                    json.dump(mcast_inp, f)

                interface.set_multicast_groups(mcast_inp)
            except Exception:
                total_error = total_error + str(
                    traceback.format_exc()).replace("\n", "")
            finally:
                interface.teardown()

            # set traffic shaping
            thrift = pd_fixed_api.PDFixedConnect(cfg["stamper_ssh"], self.logger)

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
                                    self.logger.info("Limit port " + str(
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
                    self.logger.error(traceback.format_exc())

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

                self.logger.debug("Set port shaping finished.")
        if total_error != "":
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
                    self.logger.error(traceback.format_exc())

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
            self.logger.error(traceback.format_exc())

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

                self.logger.debug("create table entries for l2 forwarding")

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
            self.logger.error(traceback.format_exc())

        try:
            ###################
            # t_l3_forwarding #
            ###################
            if cfg['forwarding_mode'] == "3":
                self.logger.debug("create table entries for l3 forwarding")
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
            self.logger.error(traceback.format_exc())

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

            if "additional_ports" in cfg:
                for add_port in cfg["additional_ports"]:
                    interface.add_to_table(t_add_empty_timestamp_tcp,
                                            [["hdr.tcp.dataOffset", 5],
                                            ["ig_intr_tm_md.ucast_egress_port",
                                                int(add_port["p4_port"])]], [],
                                            "SwitchIngress."
                                            "add_timestamp_header_tcp")
                    interface.add_to_table(t_add_empty_timestamp_tcp,
                                            [["hdr.tcp.dataOffset", 8],
                                            ["ig_intr_tm_md.ucast_egress_port",
                                                int(add_port["p4_port"])]], [],
                                            "SwitchIngress."
                                            "add_timestamp_header_tcp")

        except Exception as e:
            self.logger.error(traceback.format_exc())


        ##################################################################
        # Add table entries for sending tstamp1 packets to external host #
        ##################################################################
        if "second_ext_host_ssh" in cfg:
            DUPLICATE_WITH_FIRST_TSTAMP = True
        else:
            DUPLICATE_WITH_FIRST_TSTAMP = False
        try:
            if DUPLICATE_WITH_FIRST_TSTAMP:
                # table name may misleading, can be used for any mc group
                t_duplicate_to_dut = "pipe.SwitchIngress.t_duplicate_to_dut"

                dut_egress_ports_to_use = []

                for loadgen_grp in cfg["loadgen_groups"]:
                    for dut in cfg["dut_ports"]:
                        if loadgen_grp["group"] == dut["id"] and dut["use_port"] == "checked":
                            for host in loadgen_grp["loadgens"]:
                                port = int(dut["p4_port"])
                                if port not in dut_egress_ports_to_use:
                                    dut_egress_ports_to_use.append(int(dut["p4_port"]))
                for eg_port in dut_egress_ports_to_use:
                    # TODO: for now th same mcast group is used => only support for the same ext host
                    interface.add_to_table(t_duplicate_to_dut,
                                        [["ig_intr_tm_md.ucast_egress_port", eg_port]],
                                        [["group", 1]], "SwitchIngress.duplicate_to_dut")
        except Exception as e:
            self.logger.error(traceback.format_exc())

        # also table entries in broadcast_mac for sending tstamp1 packets to ext host


        try:
            #############################
            #broadcast_mac             #
            #############################
            t_broadcast_mac = "pipe.SwitchEgress.broadcast_mac"
            t_broadcast_mac_gtp = "pipe.SwitchEgress.broadcast_mac_gtp"

            # find matching source IP to the Ext Host Interface IP
            # e.g. src=127... packets are dropped by Linux at Ext Host
            add = 0
            if len(cfg["ext_host_ip"].split(".")) == 4:
                last_block = cfg["ext_host_ip"].split(".")[3]
                if int(last_block) >= 254:
                    add = -1
                elif int(last_block) >= 1:
                    add = 1
            if add == 0:
                raise Exception("Could not find matching source IP for prepared ext host packets. Ext Host IP: " + str(cfg["ext_host_ip"]))
            
            v4_ext_h = int(ipaddress.IPv4Address(cfg["ext_host_ip"]))
            src_ip = v4_ext_h + add

            
            ### UDP
            try:
                interface.add_to_table(
                    t_broadcast_mac,
                    [
                        ["eg_intr_md.egress_port", int(cfg["ext_host"])],
                        ["hdr.ipv4.protocol", 17],  # UDP
                        ["hdr.tcp_options_128bit_custom.myType", 0x0f10]
                    ],
                    [
                        ["dst", mac_str_to_int(cfg["ext_host_mac"])],
                        ["dstip", int(ipaddress.IPv4Address(cfg["ext_host_ip"]))],
                        ["srcip", src_ip],
                        ["dstport", 41111]
                    ],
                    "SwitchEgress.prepare_exthost_packet_udp",
                )
            except:
                self.logger.error(traceback.format_exc())

            try:
                if(DUPLICATE_WITH_FIRST_TSTAMP):
                    interface.add_to_table(
                        t_broadcast_mac,
                        [
                            ["eg_intr_md.egress_port", int(cfg["ext_host"])],
                            ["hdr.ipv4.protocol", 17],  # UDP
                            ["hdr.tcp_options_128bit_custom.myType", 0x0f11] # Other type than tstamp2 ext host
                        ],
                        [
                            ["dst", mac_str_to_int(cfg["ext_host_mac"])],
                            ["dstip", int(ipaddress.IPv4Address(cfg["ext_host_ip"]))],
                            ["srcip", src_ip],
                            ["dstport", 41112] # Other port than tstamp2 ext host
                        ],
                        "SwitchEgress.prepare_exthost_packet_udp",
                    )
            except:
                self.logger.error(traceback.format_exc())

            try:
                interface.add_to_table(
                    t_broadcast_mac_gtp,
                    [
                        ["eg_intr_md.egress_port", int(cfg["ext_host"])],
                        ["hdr.outer_ipv4.protocol", 17],  # UDP
                        ["hdr.tcp_options_128bit_custom.myType", 0x0f10]
                    ],
                    [
                        ["dst", mac_str_to_int(cfg["ext_host_mac"])],
                        ["dstip", int(ipaddress.IPv4Address(cfg["ext_host_ip"]))],
                        ["srcip", src_ip],
                        ["dstport", 41111]
                    ],
                    "SwitchEgress.prepare_exthost_packet_udp",
                )
            except Exception as e:
                self.logger.warning("Deploying GTP table to Tofino error: If P4 not compiled for GTP ignore this warning: " + str(e))

            try:
                if(DUPLICATE_WITH_FIRST_TSTAMP):
                    interface.add_to_table(
                        t_broadcast_mac_gtp,
                        [
                            ["eg_intr_md.egress_port", int(cfg["ext_host"])],
                            ["hdr.outer_ipv4.protocol", 17],  # UDP
                            ["hdr.tcp_options_128bit_custom.myType", 0x0f11] # Other type than tstamp2 ext host
                        ],
                        [
                            ["dst", mac_str_to_int(cfg["ext_host_mac"])],
                            ["dstip", int(ipaddress.IPv4Address(cfg["ext_host_ip"]))],
                            ["srcip", src_ip],
                            ["dstport", 41112] # Other port than tstamp2 ext host
                        ],
                        "SwitchEgress.prepare_exthost_packet_udp",
                    ) 
            except:
                self.logger.error(traceback.format_exc())
                
            ### TCP
            try:
                interface.add_to_table(
                    t_broadcast_mac,
                    [
                        ["eg_intr_md.egress_port", int(cfg["ext_host"])],
                        ["hdr.ipv4.protocol", 6], # TCP
                        ["hdr.tcp_options_128bit_custom.myType", 0x0f10]
                    ],
                    [
                        ["dst", mac_str_to_int(cfg["ext_host_mac"])],
                        ["dstip", int(ipaddress.IPv4Address(cfg["ext_host_ip"]))],
                        ["srcip", src_ip],
                        ["dstport", 41111]
                    ],
                    "SwitchEgress.prepare_exthost_packet_tcp",
                )
            except:
                self.logger.error(traceback.format_exc())

            try:
                if(DUPLICATE_WITH_FIRST_TSTAMP):
                    interface.add_to_table(
                        t_broadcast_mac,
                        [
                            ["eg_intr_md.egress_port", int(cfg["ext_host"])],
                            ["hdr.ipv4.protocol", 6],  # TCP
                            ["hdr.tcp_options_128bit_custom.myType", 0x0f11] # Other type than tstamp2 ext host
                        ],
                        [
                            ["dst", mac_str_to_int(cfg["ext_host_mac"])],
                            ["dstip", int(ipaddress.IPv4Address(cfg["ext_host_ip"]))],
                            ["srcip", src_ip],
                            ["dstport", 41112] # Other port than tstamp2 ext host
                        ],
                        "SwitchEgress.prepare_exthost_packet_tcp",
                    )
            except:
                self.logger.error(traceback.format_exc())
            
            try:
                interface.add_to_table(
                    t_broadcast_mac_gtp,
                    [
                        ["eg_intr_md.egress_port", int(cfg["ext_host"])],
                        ["hdr.outer_ipv4.protocol", 6], # TCP
                        ["hdr.tcp_options_128bit_custom.myType", 0x0f10]
                    ],
                    [
                        ["dst", mac_str_to_int(cfg["ext_host_mac"])],
                        ["dstip", int(ipaddress.IPv4Address(cfg["ext_host_ip"]))],
                        ["srcip", src_ip],
                        ["dstport", 41111]
                    ],
                    "SwitchEgress.prepare_exthost_packet_tcp",
                )
            except Exception as e:
                self.logger.warning("Deploying GTP table to Tofino error: If P4 not compiled for GTP ignore this warning: " + str(e))

            try:
                if(DUPLICATE_WITH_FIRST_TSTAMP):
                    interface.add_to_table(
                        t_broadcast_mac_gtp,
                        [
                            ["eg_intr_md.egress_port", int(cfg["ext_host"])],
                            ["hdr.outer_ipv4.protocol", 6],  # UDP
                            ["hdr.tcp_options_128bit_custom.myType", 0x0f11] # Other type than tstamp2 ext host
                        ],
                        [
                            ["dst", mac_str_to_int(cfg["ext_host_mac"])],
                            ["dstip", int(ipaddress.IPv4Address(cfg["ext_host_ip"]))],
                            ["srcip", src_ip],
                            ["dstport", 41112] # Other port than tstamp2 ext host
                        ],
                        "SwitchEgress.prepare_exthost_packet_tcp",
                    ) 
            except:
                self.logger.error(traceback.format_exc())

            ### ICMP
            try:
                interface.add_to_table(
                    t_broadcast_mac,
                    [
                        ["eg_intr_md.egress_port", int(cfg["ext_host"])],
                        ["hdr.ipv4.protocol", 1], # ICMP
                        ["hdr.tcp_options_128bit_custom.myType", 0x0f10]
                    ],
                    [
                        ["dst", mac_str_to_int(cfg["ext_host_mac"])],
                        ["dstip", int(ipaddress.IPv4Address(cfg["ext_host_ip"]))],
                        ["srcip", src_ip],
                        ["dstport", 41111]
                    ],
                    "SwitchEgress.prepare_exthost_packet_tcp",
                )
                # no GTP table for ICMP
            except Exception as e:
                # only warning as exception occurs in GTP compiled P4 
                self.logger.warning("Deploying GTP table to Tofino error: If P4 not compiled for GTP ignore this warning: " + str(e))
            
            try:
                interface.add_to_table(
                    t_broadcast_mac,
                    [
                        ["eg_intr_md.egress_port", int(cfg["ext_host"])],
                        ["hdr.ipv4.protocol", 1], # ICMP
                        ["hdr.tcp_options_128bit_custom.myType", 0x0f11] # Other type than tstamp2 ext host
                    ],
                    [
                        ["dst", mac_str_to_int(cfg["ext_host_mac"])],
                        ["dstip", int(ipaddress.IPv4Address(cfg["ext_host_ip"]))],
                        ["srcip", src_ip],
                        ["dstport", 41112] # Other port than tstamp2 ext host
                    ],
                    "SwitchEgress.prepare_exthost_packet_tcp",
                )
                # no GTP table for ICMP
            except Exception as e:
                # only warning as exception occurs in GTP compiled P4 
                self.logger.warning("Deploying GTP table to Tofino error: If P4 not compiled for GTP ignore this warning: " + str(e))

        except Exception as e:
            self.logger.error(traceback.format_exc())

        try:
            #############################
            # t_timestamp2_tcp          #
            #############################

            if cfg["stamp_tcp"] == "checked":
                t_timestamp2_tcp = "pipe.SwitchIngress.t_timestamp2_tcp"
                for p4_port_flow_dst in all_dut_dst_p4_ports:
                    interface.add_to_table(
                        t_timestamp2_tcp,
                        [
                            ["hdr.tcp.dataOffset", 0x9],
                            ["hdr.tcp_options_128bit_custom." "myType", 0x0F10],
                            ["ig_intr_md.ingress_port", int(p4_port_flow_dst)],
                        ],
                        [["threshold", int(cfg["multicast"]) - 1]],
                        "SwitchIngress.add_timestamp2_tcp",
                    )
                    interface.add_to_table(
                        t_timestamp2_tcp,
                        [
                            ["hdr.tcp.dataOffset", 0xC],
                            ["hdr.tcp_options_128bit_custom." "myType", 0x0F10],
                            ["ig_intr_md.ingress_port", int(p4_port_flow_dst)],
                        ],
                        [["threshold", int(cfg["multicast"]) - 1]],
                        "SwitchIngress.add_timestamp2_tcp",
                    )

                
                # additional ports from GUI
                # all additional ports timestamp ingressing and egressing
                if "additional_ports" in cfg:
                    for add_port in cfg["additional_ports"]:
                        interface.add_to_table(
                            t_timestamp2_tcp,
                            [
                                ["hdr.tcp.dataOffset", 0x9],
                                ["hdr.tcp_options_128bit_custom." "myType", 0x0F10],
                                ["ig_intr_md.ingress_port", int(add_port["p4_port"])],
                            ],
                            [["threshold", int(cfg["multicast"]) - 1]],
                            "SwitchIngress.add_timestamp2_tcp",
                        )
                        interface.add_to_table(
                            t_timestamp2_tcp,
                            [
                                ["hdr.tcp.dataOffset", 0xC],
                                ["hdr.tcp_options_128bit_custom." "myType", 0x0F10],
                                ["ig_intr_md.ingress_port", int(add_port["p4_port"])],
                            ],
                            [["threshold", int(cfg["multicast"]) - 1]],
                            "SwitchIngress.add_timestamp2_tcp",
                        )



        except Exception as e:
            self.logger.error(traceback.format_exc())

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
                        interface.add_to_table(
                            t_add_empty_timestamp_udp,
                            [["ig_intr_tm_md.ucast_egress_port", int(dut["p4_port"])]],
                            [],
                            "SwitchIngress." "add_timestamp_header_udp",
                        )

                for p4_port_flow_dst in all_dut_dst_p4_ports:
                    interface.add_to_table(
                        t_timestamp2_udp,
                        [
                            ["hdr.tcp_options_128bit_custom.myType", 0x0F10],
                            ["ig_intr_md.ingress_port", int(p4_port_flow_dst)],
                        ],
                        [["threshold", int(cfg["multicast"]) - 1]],
                        "SwitchIngress.add_timestamp2_udp",
                    )
                    
                # additional ports from GUI
                # all additional ports timestamp ingressing and egressing
                if "additional_ports" in cfg:
                    for add_port in cfg["additional_ports"]:
                        interface.add_to_table(
                            t_add_empty_timestamp_udp,
                            [["ig_intr_tm_md.ucast_egress_port", int(add_port["p4_port"])]],
                            [],
                            "SwitchIngress." "add_timestamp_header_udp",
                        )

                        interface.add_to_table(
                            t_timestamp2_udp,
                            [
                                ["hdr.tcp_options_128bit_custom.myType", 0x0F10],
                                ["ig_intr_md.ingress_port", int(add_port["p4_port"])],
                            ],
                            [["threshold", int(cfg["multicast"]) - 1]],
                            "SwitchIngress.add_timestamp2_udp",
                        )
        except Exception:
            self.logger.error(traceback.format_exc())

        try:
            ##################################################
            #  ICMP tables, reuse timestamp2 from udp        #
            # t_add_empty_timestamp_udp & t_timestamp2_udp   #
            ##################################################
            # cfg = P4STA_utils.read_current_cfg()
            if cfg["selected_loadgen"] == "Tofino Packet Generator": # TODO also cfg["stamp_icmp"] == "checked":
                t_add_empty_timestamp_icmp = "pipe.SwitchIngress.t_add_empty_timestamp_icmp"
                t_timestamp2_udp = "pipe.SwitchIngress.t_timestamp2_udp"

                for dut in cfg["dut_ports"]:
                    if dut["stamp_outgoing"] == "checked" and dut["use_port"] == "checked":
                        interface.add_to_table(
                            t_add_empty_timestamp_icmp,
                            [
                                ["hdr.icmp.type", 0x8],
                                ["ig_intr_tm_md.ucast_egress_port", int(dut["p4_port"])]

                            ],
                            [],
                            "SwitchIngress.add_timestamp_header_icmp",
                        )
                # if stamp_udp is checked then this table entry is deployed already in the UDP section before
                if cfg["stamp_udp"] != "checked":
                    for p4_port_flow_dst in all_dut_dst_p4_ports:
                        interface.add_to_table(
                            t_timestamp2_udp,
                            [
                                ["hdr.tcp_options_128bit_custom.myType", 0x0F10],
                                ["ig_intr_md.ingress_port", int(p4_port_flow_dst)],
                            ],
                            [["threshold", int(cfg["multicast"]) - 1]],
                            "SwitchIngress.add_timestamp2_udp",
                        )

                  # additional ports from GUI
                # all additional ports timestamp ingressing and egressing
                if "additional_ports" in cfg:
                    for add_port in cfg["additional_ports"]:
                        interface.add_to_table(
                            t_add_empty_timestamp_icmp,
                            [
                                    ["hdr.icmp.type", 0x8],
                                    ["ig_intr_tm_md.ucast_egress_port", int(add_port["p4_port"])]

                            ],
                            [],
                            "SwitchIngress." "add_timestamp_header_icmp",
                        )
                        # if stamp_udp is checked then this table entry is deployed already in the UDP section before
                        if cfg["stamp_udp"] != "checked":
                            interface.add_to_table(
                                t_timestamp2_udp,
                                [
                                    ["hdr.tcp_options_128bit_custom.myType", 0x0F10],
                                    ["ig_intr_md.ingress_port", int(add_port["p4_port"])],
                                ],
                                [["threshold", int(cfg["multicast"]) - 1]],
                                "SwitchIngress.add_timestamp2_udp",
                            )


        except Exception:
            self.logger.error(traceback.format_exc())

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
            self.logger.error(traceback.format_exc())

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
            self.logger.error(traceback.format_exc())

    def read_stamperice(self, cfg, tofino_grpc_obj=None):
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

        if tofino_grpc_obj != None:
            self.logger.debug("use passed tofino grpc obj")
            # if tofino_grpc_obj.p4_program == "":
            #     self.logger.debug("No P4 programm binded. Bind " + str(cfg["p4_programm"]))
            #     interface.bind_p4_name(cfg["program"])
            if tofino_grpc_obj.connection_established and tofino_grpc_obj.p4_connected:
                interface = tofino_grpc_obj
        
        else:
            # Debugging: set own client ID
            interface = grpc_interface.TofinoInterface(cfg["stamper_ssh"], 0, self.logger, client_id=int(time.time()) % 100)
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

            self.logger.info("Retrieving the counters took " + str(
                time.time() - before) + " seconds.")

            #############################
            #      register read        #
            #############################
            # high_read eg = [0, 0, 1798348234, 0, 0, 0, 1, 0] => low_read is 1798.. and overflow is 1

            high_read = interface.read_register(
                "pipe.SwitchIngress.delta_register_high")
            self.logger.info("delta_register_high: " + str(high_read))

            # new approach
            if len(high_read) == 8:
                # 4 pipelines each high and low = 8
                old_low = high_read[0:4]
                high_delta = high_read[4:8]
                
                # sum is the same as bit shifting for each pipeline with the respective overflow and add
                low_read = sum(old_low)
                overflow = sum(high_delta)
                total_deltas = (overflow << 32) + low_read

            # legacy, as not sure if always list size 8
            else:
                low_read = max(high_read)
                overflow = 0
                try:
                    overflow = min([x for x in high_read if ((x > 0) and (x != low_read))])
                except Exception:
                    overflow = 0
                total_deltas = (overflow << 32) + low_read

            if False:
                delta_counter = sum(interface.read_register(
                    "pipe.SwitchIngress.delta_register_pkts"))
            # read two 32 bit delta_counters
            high_pkts_read = interface.read_register("pipe.SwitchIngress.delta_register_pkts_high")
            self.logger.info("delta_register_pkts_high: " + str(high_pkts_read))
                    
            # new approach
            if len(high_read) == 8:
                # 4 pipelines each high and low = 8
                old_low = high_pkts_read[0:4]
                high_pkts = high_pkts_read[4:8]
                
                # sum is the same as bit shifting for each pipeline with the respective overflow and add
                low_read = sum(old_low)
                overflow = sum(high_pkts)
                delta_counter = (overflow << 32) + low_read
            # old way, limited by 32 bit but still there
            else:
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

            self.logger.info("total deltas:" + str(total_deltas))
            self.logger.info("delta counter:" + str(delta_counter))
            if delta_counter > 0:
                self.logger.info("delta per packet:" + str(
                    total_deltas / delta_counter) + "ns")
            self.logger.info("min_delta:" + str(min_delta))
            self.logger.info("max_delta:" + str(max_delta))

            cfg["total_deltas"] = total_deltas
            cfg["delta_counter"] = delta_counter
            cfg["min_delta"] = min_delta
            cfg["max_delta"] = max_delta

            for dut in cfg["dut_ports"]:
                dut["num_ingress_packets"], dut[
                    "num_ingress_bytes"] = get_at_index(all_ingress_counter, dut["p4_port"])
                dut["num_egress_packets"], dut[
                    "num_egress_bytes"] = get_at_index(all_egress_counter, dut["p4_port"])
                dut["num_ingress_stamped_packets"], dut[
                    "num_ingress_stamped_bytes"] = get_at_index(all_ingress_stamped_counter, dut["p4_port"])
                dut["num_egress_stamped_packets"], dut[
                    "num_egress_stamped_bytes"] = get_at_index(all_egress_stamped_counter, dut["p4_port"])

            for loadgen_grp in cfg["loadgen_groups"]:
                for host in loadgen_grp["loadgens"]:
                    host["num_ingress_packets"], host[
                        "num_ingress_bytes"] = get_at_index(all_ingress_counter, host["p4_port"])
                    host["num_egress_packets"], host[
                        "num_egress_bytes"] = get_at_index(all_egress_counter, host["p4_port"])
                    host["num_ingress_stamped_packets"], host[
                        "num_ingress_stamped_bytes"] = get_at_index(all_ingress_stamped_counter, host["p4_port"])
                    host["num_egress_stamped_packets"], host[
                        "num_egress_stamped_bytes"] = get_at_index(all_egress_stamped_counter, host["p4_port"])

            cfg["ext_host_" + "num_ingress_packets"], cfg[
                "ext_host_" + "num_ingress_bytes"] = get_at_index(all_ingress_counter, cfg["ext_host"])
            cfg["ext_host_" + "num_ingress_stamped_packets"], cfg[
                "ext_host_" + "num_ingress_stamped_bytes"] = get_at_index(all_ingress_stamped_counter, cfg["ext_host"])
            cfg["ext_host_" + "num_egress_packets"], cfg[
                "ext_host_" + "num_egress_bytes"] = get_at_index(all_egress_counter, cfg["ext_host"])
            cfg["ext_host_" + "num_egress_stamped_packets"], cfg[
                "ext_host_" + "num_egress_stamped_bytes"] = get_at_index(all_egress_stamped_counter, cfg["ext_host"])

        except Exception:
            self.logger.error(traceback.format_exc())

        finally:
            interface.teardown()

        return cfg

    def stamper_status(self, cfg):
        lines = subprocess.run(
            [dir_path + "/scripts/switchd_status.sh", cfg["stamper_user"],
             cfg["stamper_ssh"]], stdout=subprocess.PIPE).stdout.decode(
            "utf-8").split("\n")
        self.logger.debug(str(lines))
        try:
            if len(lines) > 0 and lines[0].isdigit() and int(lines[0]) > 0:
                dev_status = "Yes! PID: " + str(lines[0])
                try:
                    start = lines[2].find("compile/") + 8
                    end = lines[2].find(".conf")
                    parsed_prog = lines[2][start:end]
                    if parsed_prog == cfg["program"]:
                        dev_status = dev_status + " | " + parsed_prog
                    else:
                        dev_status = dev_status + ' | <span style="color:red">' + parsed_prog + ' (does not match configured program)</span>'
                except Exception:
                    dev_status = dev_status + \
                                 " | error parsing currently " \
                                 "loaded program on p4 device."
                running = True

                interface = grpc_interface.TofinoInterface(cfg["stamper_ssh"], 0, self.logger)

                if not interface.connection_established:
                    interface.teardown()
                    return ["gRPC connection to Tofino failed, wait some time and retry."], False, "not running"
                
                try:
                    error = interface.bind_p4_name(cfg["program"])
                    if error != "":
                        return ["gRPC: Bind P4 Programm to Tofino failed, wait some time and retry."], True, "running"

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
                    self.logger.error(error)
                    lines_pm = ["Error retrieving port status from tofino."]
                    lines_pm.extend(traceback.format_exc().split("\n"))
                finally:
                    interface.teardown()
            else:
                dev_status = "not running"
                running = False
                lines_pm = ["Port-manager not available"]
        except Exception:
            self.logger.error(traceback.format_exc())
            dev_status = "not running"
            running = False
            lines_pm = ["Port-manager not available"]

        return lines_pm, running, dev_status

    def start_stamper_software(self, cfg):
        script_dir = dir_path + "/scripts/run_switchd.sh"
        user_name = cfg["stamper_user"]
        output_sub = subprocess.run(
            [dir_path + "/scripts/start_switchd.sh", cfg["stamper_ssh"],
             cfg["stamper_user"], self.get_sde(cfg),
             '/home/' + user_name + '/p4sta/stamper/tofino1/compile/' + cfg["program"] + '.conf',
             script_dir], stdout=subprocess.PIPE)
        self.logger.debug(output_sub)
        time.sleep(5)
        

        reachable = False
        for i in range(12):
            time.sleep(10)
            interface = grpc_interface.TofinoInterface(cfg["stamper_ssh"], 0, self.logger, print_errors=False)
            established = interface.connection_established
            self.logger.info("Probing gRPC connection to Tofino... Established: " + str(established))
            interface.teardown()
            if established:
                reachable = True
                break
                
        if reachable:
            self.logger.info("Tofino gRPC server reachable.")
        else:
            self.logger.warning("Tofino gRPC server not reachable after 2 minutes of probing.")
        

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
        interface = grpc_interface.TofinoInterface(cfg["stamper_ssh"], 0, self.logger)
        if type(interface) == str:
            self.logger.warning("error resetting registers ..")
            self.logger.warning(interface)
            return interface
        interface.bind_p4_name(cfg["program"])
        try:
            # clear counters
            cntr_port_list = self.get_used_ports_list(cfg)
            for name in ["Ingress.ingress_counter",
                         "Ingress.ingress_stamped_counter",
                         "Egress.egress_counter",
                         "Egress.egress_stamped_counter"]:
                self.logger.debug("CLEAR COUNTER: " + "pipe.Switch" + name)
                try:
                    interface.clear_indirect_counter("pipe.Switch" + name,
                                                     id_list=cntr_port_list)
                except Exception:
                    self.logger.error(traceback.format_exc())

            # clear indirect registers
            for name in ["delta_register", "min_register", "max_register",
                         "delta_register_high", "delta_register_pkts",
                         "delta_register_pkts_high", "multi_counter_register"]:
                self.logger.debug("CLEAR REGISTER: " + name)
                try:
                    interface.clear_register("pipe.SwitchIngress." + name)
                except Exception:
                    self.logger.error(traceback.format_exc())
        except Exception:
            self.logger.error(traceback.format_exc())
        finally:
            interface.teardown()

    def check_if_p4_compiled(self, cfg):
        user_name = cfg["stamper_user"]
        path = '/home/' + user_name + '/p4sta/stamper/tofino1/compile/' + cfg["program"] + '.conf'
        arg = "[ -f '" + path + "' ] && echo 'y'; exit"
        answer = self.execute_ssh(cfg, arg)

        if answer[0] != "y":
            return False, cfg["program"] + " not compiled: '" + path + "' not found."
        else:
            return True, cfg["program"] + " is compiled: '" + path + "' found."

    def needed_dynamic_sudos(self, cfg):
        return [cfg["sde"] + "/run_switchd.sh"]

    # target_specific_dict contains input fields from /setup_devices/
    # => here SDE path
    def get_server_install_script(self, user_name, ip, target_specific_dict={}):
        sde_path = ""
        if "sde" in target_specific_dict and len(target_specific_dict["sde"]) > 1:
            sde_path = target_specific_dict["sde"]
        else:
            lines = P4STA_utils.execute_ssh(user_name, ip, "cat $HOME/.bashrc")
            for line in lines:
                if line.find("export SDE_INSTALL") > -1:
                    lrep = line.replace("\n", "")
                    start = lrep.find("=") + 1
                    sde_path = lrep[start:]
                    self.logger.info("Found $SDE_INSTALL at tofino " + ip + " => " + sde_path)
            if sde_path == "":
                self.logger.warning("SDE Path not found on Tofino, using /opt/bf-sde-9.13.1")
                sde_path = "/opt/bf-sde-9.13.1"

        # create install_tofino.sh
        add_sudo_rights_str = "#!/bin/bash\n#AUTOGENERATED BY P4STA installer\nadd_sudo_rights() {\ncurrent_" \
                              "user=$USER\n  if (sudo -l | grep -q " \
                              "'(ALL : ALL) SETENV: NOPASSWD: '$1); then\n  " \
                              "  echo 'visudo entry already exists';" \
                              "\n  else\n    sleep 0.1\n    echo " \
                              "$current_user' ALL=(ALL:ALL) NOPASSWD:" \
                              "SETENV:'$1 | " \
                              "sudo EDITOR='tee -a' visudo; \n  fi\n}\n"
        
        p4c_flags = ""
        if "compile_flag" in target_specific_dict:
            if target_specific_dict["compile_flag"] == "NONE":
                pass
            elif target_specific_dict["compile_flag"] == "GTP_ENCAP":
                p4c_flags = "-D GTP_ENCAP"
            elif target_specific_dict["compile_flag"] == "PPPOE_ENCAP":
                p4c_flags = "-D PPPOE_ENCAP"
        if "p4c-flags" in target_specific_dict:
            if target_specific_dict["p4c-flags"] != "":
                p4c_flags = p4c_flags + " " + target_specific_dict["p4c-flags"]
        compile_p4_src = "export SDE_INSTALL=" + sde_path + "/install\n" \
                         "cd /home/" + user_name + "/p4sta/stamper/tofino1/\n" \
                         "mkdir -p compile\n" \
                         "$SDE_INSTALL/bin/bf-p4c -v "+ p4c_flags +" -o $PWD/compile/ tofino_stamper_v1_3_0.p4\n"

        with open(dir_path + "/scripts/install_tofino.sh", "w") as f:
            f.write(add_sudo_rights_str)
            for sudo in self.target_cfg["status_check"]["needed_sudos_to_add"]:
                if sudo.find("run_switchd.sh") > -1:
                    f.write("add_sudo_rights " + sde_path + "/run_switchd.sh\n")
                else:
                    f.write("add_sudo_rights $(which " + sudo + ")\n")
            f.write(compile_p4_src)
        os.chmod(dir_path + "/scripts/install_tofino.sh", 0o777)

        lst = []
        lst.append('echo "====================================="')
        lst.append('echo "Installing Barefoot Tofino stamper target on ' + ip + '"')
        lst.append('echo "P4 compile flag: ' + p4c_flags + '"')
        lst.append('echo "====================================="')

        lst.append('echo "START: Copying Tofino files on remote server:"')

        lst.append('if ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no '
                   + user_name + '@' + ip + ' "echo \'ssh to ' + ip + ' ***worked***\';"; [ $? -eq 255 ]; then')

        lst.append('  echo "====================================="')
        lst.append('  echo "\033[0;31m ERROR: Failed to connect to Stamper server with IP: ' + ip + ' \033[0m"')
        lst.append('  echo "====================================="')

        lst.append('else')

        lst.append('  cd ' + dir_path + "/scripts")
        lst.append('  chmod +x stop_switchd.sh start_switchd.sh switchd_status.sh')
        lst.append('  ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no '
                   + user_name + '@' + ip + ' \"echo "SSH to stamper device ***__worked__***\"; mkdir -p /home/' + user_name + '/p4sta/stamper/tofino1/"')

        lst.append("   echo ")

        lst.append('  scp ' + dir_path + '/p4_files/v1.3.0/header_tofino_stamper_v1_3_0.p4 ' + user_name + '@' + ip + ':/home/' + user_name + '/p4sta/stamper/tofino1/')
        lst.append('  scp ' + dir_path + '/p4_files/v1.3.0/tofino_stamper_v1_3_0.p4 ' + user_name + '@' + ip + ':/home/' + user_name + '/p4sta/stamper/tofino1/')

        lst.append('  scp install_tofino.sh ' + user_name + '@' + ip + ':/home/' + user_name + '/p4sta/stamper/tofino1/')
        lst.append('  ssh  -t -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
                   user_name + '@' + ip + ' "cd /home/' + user_name + '/p4sta/stamper/tofino1/; chmod +x install_tofino.sh; ./install_tofino.sh;"')

        lst.append('  echo "====================================="')
        lst.append('fi')

        return lst

    def get_live_metrics(self, cfg, tofino_grpc_obj=None):
        if tofino_grpc_obj == None:
            interface = grpc_interface.TofinoInterface(cfg["stamper_ssh"], 0, self.logger, print_errors=True)
            established = interface.connection_established
            interface.bind_p4_name(cfg["program"])
            self.logger.debug("Probing gRPC connection to Tofino... Established: " + str(established))
        else:
            interface = tofino_grpc_obj
            if tofino_grpc_obj.p4_program == "":
                interface.bind_p4_name(cfg["program"])
        live_metrics = []
        try:
            stats = interface.read_port_status(statistics=True)
            for port in stats:
                p_res = {}
                p_res["port"] = int(port["keys"][0][1].hex(), 16)
                p_res["tx_rate"] = int(port["$TX_RATE"].stream.hex(), 16) # which unit?
                p_res["rx_rate"] = int(port["$RX_RATE"].stream.hex(), 16)
                p_res["tx_pps"] = int(port["$TX_PPS"].stream.hex(), 16)
                p_res["rx_pps"] = int(port["$RX_PPS"].stream.hex(), 16)
                p_res["tx_avg_packet_size"] = round(p_res["tx_rate"] / p_res["tx_pps"], 2) if p_res["tx_pps"] > 0 else 0 # bit?
                p_res["rx_avg_packet_size"] = round(p_res["rx_rate"] / p_res["rx_pps"], 2) if p_res["rx_pps"] > 0 else 0 # bit?
                live_metrics.append(p_res)
        except:
            self.logger.warning(traceback.format_exc())
        finally:
            if tofino_grpc_obj == None:
                interface.teardown()
        return live_metrics

