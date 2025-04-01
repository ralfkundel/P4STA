# Copyright 2025-present Fridolin Siegmund, Ralf Kundel
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

import json
import os
import sys
import traceback

from scapy.all import *
from scapy.contrib import gtp
from scapy_patches.ppp import PPPoE, PPP  # Needed due to https://github.com/secdev/scapy/commit/3e6900776698cd5472c5405294414d5b672a3f18

dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir_path)
p4sta_root_dir_path = os.path.abspath(os.path.join(dir_path, "..",".."))
wedge100b65_dir = os.path.abspath(os.path.join(p4sta_root_dir_path, 'stamper_targets', 'Wedge100B65'))
sys.path.append(wedge100b65_dir)

import bfrt_grpc.grpc_interface as grpc_interface


class TofinoPacketGenerator():
    def __init__(self, libcfg, logger): #tofino_stamper_obj=None
        # libcfg e.g.: 
        # {
        #   "ssh_ip": "172.16.5.21", 
        #   "generator_ports": [68, 196, 324, 452],
        #   "egress_ports": [412,0,0,415]  same length als generation ports! 0 for blocking l1 forwarding
        #   "egress_mcast_groups_map": [[1,2,3,4], [], [], []]    duplicate the packets egressing on the first DUT port to port 1,2,3,4, other DUT ports no replication
        #   "use_gen_port_map": [True, True, True, False],        use generation ports 1,2,3 but not 4
        #   "mcast_duplication_multis": [1,1,1,1],                no extra duplication with 1, just duplication to the egress group in egress_mcast_group_maps
        #   "p4_program": "compiled_p4_name",
        #   "tofino_generation": "1",
        #   "sniff_points": [                                     Type 1: before DUT    Type 2: after DUT
        #       {"type": 1, "duplicate_to_p4_ports": [320]},      => not supported right now
        #       {"type": 2, "duplicate_to_p4_ports": [320]}       => not supported right now
        #    ]
        #   ".."
        # }
        self.abort = False
        if len(libcfg["generator_ports"]) != len(libcfg["egress_ports"]):
            self.abort = True
            raise Exception("Length of generator_ports and egress_ports list must be the same.")
        self.libcfg = libcfg
        self.open_connection = None
        self.no_teardown = False
        self.logger = logger

    def set_connection(self):
        interface = grpc_interface.TofinoInterface(self.libcfg["ssh_ip"], 0, self.logger)
        interface.bind_p4_name(self.libcfg["p4_program"])
        self.open_connection = interface
        
        return interface
        
    def get_simple_tcp_packet(self, dst_mac="ff:ff:ff:ff:ff:ff", dst_ip="1.2.3.4", size=1400):
        hdr = Ether(dst=dst_mac)/IP(dst=dst_ip)/TCP(sport=4242, dport=4242, flags="PA")
        hdr.show()
        pkt = hdr/Padding(bytes('\x00' * (size - len(hdr)), 'utf-8'))
        return pkt

    def get_timer(self, rate_mbps, packet_size):
        rate_bytes_per_sec = rate_mbps * 10**6 / 8
        rate_pps = rate_bytes_per_sec / packet_size 
        timer = round(10**9/rate_pps) # 1 second in ns / rate_pps
        exp_mbps = (packet_size*rate_pps) / 10**6 * 8
        exp_mbps_2 = packet_size*8000/timer
        
        self.logger.debug("rate_mbps = " + str(rate_mbps))
        self.logger.debug("rate_bytes_per_sec = " + str(rate_bytes_per_sec))
        self.logger.debug("rate_pps = " + str(rate_pps))
        self.logger.debug("timer = " + str(timer))
        self.logger.debug("Expected Bitrate: " + str(exp_mbps) + " Mbps")
        self.logger.debug("Expected Bitrate 2: " + str(exp_mbps_2) + " Mbps")

        return timer

    def start_packet_generation(self, packet_list=[], tofino_grpc_obj=None):
        t_action="trigger_timer_periodic"

        if self.abort:
            self.logger.warning("Aborting packet generation.")
            return None

        if len(packet_list) != len(self.libcfg["generator_ports"]):
            self.logger.warning("Passed argument packet_list must contain the same amount of packets as generator ports - one per port in the same order.")
            return None
        
        if tofino_grpc_obj != None:
            self.open_connection = tofino_grpc_obj
            self.no_teardown = True

        if self.open_connection != None:
            self.logger.debug("Reusing open gRPC connection")

            if "tables" in self.open_connection.bfruntime_info:
                self.logger.warning("key tables found in bfruntime_info")
                interface = self.open_connection
            else:
                try:
                    self.logger.warning("key tables not found in bfruntime_info, teardown and recreate gRPC connection ... ")
                    self.open_connection.teardown()
                    interface = self.set_connection()
                except:
                    self.logger.error(traceback.format_exc())

        else:
            interface = self.set_connection()
        
        interface.delete_table("pipe.SwitchIngress.t_l1_forwarding_generation")
        interface.delete_table("pipe.SwitchIngress.t_duplicate_sniff_1")
        interface.delete_table("pipe.SwitchIngress.t_duplicate_sniff_2")

        for indx, port in enumerate(self.libcfg["generator_ports"]):
            port_enb = self.libcfg["use_gen_port_map"][indx]
            interface.add_to_table(
                table_name="tf" + self.libcfg["tofino_generation"] + ".pktgen.port_cfg", 
                keys=[["dev_port", int(port)]],
                datas=[["pktgen_enable", port_enb]],
                mod=True
            )  
            self.logger.info("Tofino Packet Generator: port " + str(port) + " enabled")


        buffer_offset = 0
        for packet in packet_list:
            if packet != None:     
                try:
                    interface.add_to_table(
                        table_name="tf" + self.libcfg["tofino_generation"] + ".pktgen.pkt_buffer", 
                        keys=[["pkt_buffer_offset", buffer_offset], ["pkt_buffer_size", len(packet["scapy_packet"])]],
                        datas=[["buffer", bytearray(bytes(packet["scapy_packet"]))]],
                        mod=True
                    )
                    packet["buffer_offset"] = buffer_offset
                    # now set buffer_offset for next packet, align buffer with 16 byte steps
                    if 16 % len(packet["scapy_packet"]) == 0:
                        add = 0
                    else:
                        add = 16 - (len(packet["scapy_packet"])%16)
                    buffer_offset = buffer_offset + len(packet["scapy_packet"]) + add
                    self.logger.info("Tofino Packet Generator: buffer configured")
                except Exception as e:
                    self.logger.error(traceback.format_exc()) 


        # preconfig for additional ports for egress duplication multicast groups
        DEBUG_disable_mcast = False

        start_group = 100 
        self.libcfg["mcast_grp_ids"] = [0,0,0,0]
        mcast_inp = []
        try:
            with open("mcast_grps_deployment.json", "r") as f:
                mcast_inp = json.load(f)
        except:
            self.logger.error(traceback.format_exc())

        # find latest mcast node ID
        node_ids = []
        for inp in mcast_inp:
            try:
                node_ids.append(int(inp["node_id"]))
            except:
                self.logger.error(traceback.format_exc())

        node_id = max(node_ids) + 1

        # workaround because the last node id from deploy() is not known here
        # clear all mcast grps and restore again from json
        interface.clear_multicast_groups()

        # not needed anymore # node_id = 4 # seems like max 19 mcast nodes possible
        for indx, port in enumerate(self.libcfg["generator_ports"]):
            try:
                packet = packet_list[indx]
                eg_port = self.libcfg["egress_ports"][indx]
                mcast_multi = self.libcfg["mcast_duplication_multis"][indx]

                # prepare multicasting groups for duplication to additional ports
                # "egress_mcast_groups_map": [[1,2,3,4], [], [], []] # p4 ports!
                if "egress_mcast_groups_map" in self.libcfg and len(self.libcfg["egress_mcast_groups_map"]) > 0:
                    p4_ports = self.libcfg["egress_mcast_groups_map"][indx]
                    if not DEBUG_disable_mcast:
                        # apply mcast multiplicator
                        multiplicated_p4_ports = p4_ports
                        if mcast_multi > 1:
                            multiplicated_p4_ports = []
                            for i in range(mcast_multi):
                                multiplicated_p4_ports.extend(p4_ports)
                                # add eg_port only for multiplication, not in first round as the original packet egresses there
                                if i > 0:
                                    multiplicated_p4_ports.append(eg_port)

                        for p4_port in multiplicated_p4_ports:
                            self.logger.debug("Adding P4 Port " + str(p4_port) + " to mcast group " + str(start_group))
                            cfg = {"node_id": node_id, "group_id": start_group, "port": int(p4_port)}
                            mcast_inp.append(cfg)
                            node_id += 1

                        self.libcfg["mcast_grp_ids"][indx] = int(start_group)
                        start_group += 1

                if eg_port > 0 and "app_id" in packet:
                    grp = self.libcfg["mcast_grp_ids"][indx]

                    interface.add_to_table(table_name="pipe.SwitchIngress.t_l1_forwarding_generation",
                        keys=[["ig_intr_md.ingress_port", int(port)], ["hdr.pkg_gen_timer.app_id", packet["app_id"]]],
                        datas=[["egress_port", eg_port]],
                        action="SwitchIngress.send")
                    self.logger.debug("Added pipe.SwitchIngress.t_l1_forwarding_generation => ingress_port " + str(port) + " => " + "eg_port " + str(eg_port))

                    t_duplicate_to_dut = "pipe.SwitchIngress.t_duplicate_to_dut"
                    interface.add_to_table(
                        t_duplicate_to_dut,
                        [["ig_intr_tm_md.ucast_egress_port", int(eg_port)]],
                        [["group", int(grp)]],
                        "SwitchIngress.duplicate_to_dut",
                    )
                    self.logger.debug("Added pipe.SwitchIngress.t_duplicate_to_dut => ucast_egress_port " + str(eg_port) + " => " + "group " + str(grp))

            except Exception as e:
                self.logger.error(traceback.format_exc())

        ## monitoring points, duplicate packet as it is 
        # TODO: does not work in current state
        # (TODO: for now packets to ext host port are always striped of lower layers and added UDP due to prepare_ext_host p4 tables matching on egress port)
        # TYPE 1: duplicate of ingressing to DUT     TYPE 2: duplicate after egressing DUT
        # e.g. sniff_points = [{"type": 1, "duplicate_to_p4_ports": [123]}, {"type": 2, "duplicate_to_p4_ports": [123]}]

        for point in self.libcfg["sniff_points"]:
            for p4_port in point["duplicate_to_p4_ports"]:
                cfg = {"node_id": node_id, "group_id": start_group, "port": int(p4_port)}
                mcast_inp.append(cfg)
                for indx, port in enumerate(self.libcfg["generator_ports"]):
                    eg_port = self.libcfg["egress_ports"][indx]

                    if "type" in point and point["type"] == 2:
                        interface.add_to_table(table_name="pipe.SwitchIngress.t_duplicate_sniff_2",
                            keys=[["ig_intr_md.ingress_port", int(eg_port)]], # fine with egress ports as all DUT ports are duplicated
                            datas=[["group", int(start_group)]], 
                            action="SwitchIngress.duplicate_to_dut"
                        ) # misleading action name as it is reused for sniffing

                        self.logger.debug("Added pipe.SwitchIngress.t_duplicate_sniff_2 => ingress_port " + str(eg_port) + " => " + "mcast grp " + str(start_group))

                    elif "type" in point and point["type"] == 1:
                        t_duplicate_to_dut = "pipe.SwitchIngress.t_duplicate_sniff_1"
                        interface.add_to_table(
                            t_duplicate_to_dut,
                            [["ig_intr_tm_md.ucast_egress_port", int(eg_port)]],
                            [["group", int(start_group)]],
                            "SwitchIngress.duplicate_to_dut",
                        )
                        self.logger.debug("Added pipe.SwitchIngress.t_duplicate_sniff_1 => egress_port " + str(eg_port) + " => " + "mcast group " + str(start_group))

                node_id += 1
                start_group += 1



        interface.set_multicast_groups(mcast_inp)

        for indx, port in enumerate(self.libcfg["generator_ports"]): 
            try:
                if True: #len(packet_list) < indx: # was "<" not "<="
                    packet = packet_list[indx]
                    timer = self.get_timer(packet["rate_mbps"], len(packet["scapy_packet"]))
                    if self.libcfg["tofino_generation"] == '1':
                        interface.add_to_table(table_name="tf1.pktgen.app_cfg", 
                        keys=[["app_id", packet["app_id"]]],
                        datas=[     
                            ["timer_nanosec", timer],
                            ["app_enable", True],
                            ["pkt_len", len(packet["scapy_packet"])],
                            ["pkt_buffer_offset", packet["buffer_offset"]],
                            ["pipe_local_source_port", int(port) & 0x7f ],  # remove pipe id from port
                            ["increment_source_port", False],
                            ["batch_count_cfg", 0],                         # single batch
                            ["packets_per_batch_cfg", 0],                   # burst-len - 1 -> packets per batch
                            ["ibg", 0],                                     # inter-batch-gap in ns
                            ["ibg_jitter", 0],                              # inter-batch-jitter in ns
                            ["ipg", 0],                                     # inter-packet-gap in ns
                            ["ipg_jitter", 0],                              # inter-packet-jitter in ns
                            ["batch_counter", 0],
                            ["pkt_counter", 0],
                            ["trigger_counter", 0]
                            ],
                        action=t_action, mod = True)  
                    else:
                        interface.add_to_table(table_name="tf2.pktgen.app_cfg", 
                        keys=[["app_id", packet["app_id"]]],
                        datas=[     
                            ["timer_nanosec", timer],
                            ["app_enable", True],
                            ["pkt_len", len(packet["scapy_packet"])],
                            ["pkt_buffer_offset", packet["buffer_offset"]],
                            ["pipe_local_source_port", int(port) & 0x7f],  
                            ["batch_count_cfg", 0],
                            ["packets_per_batch_cfg", 0],
                            ['assigned_chnl_id', 6]
                            ],
                        action=t_action, mod=True)  
                    self.logger.info("Tofino Packet Generator: start gen with " + str(packet["app_id"]) + " - Type: " + t_action + " from port " + str(port) + " buffer_offset= " + str(packet["buffer_offset"]) + " with " + str(packet["rate_mbps"]) + " mbps" )

            except Exception as e:
                self.logger.error(traceback.format_exc())

        return self.open_connection


    def stop_packet_generation(self, packets, force=False, tofino_grpc_obj=None):
        t_action="trigger_timer_periodic"

        if tofino_grpc_obj != None:
            self.open_connection = tofino_grpc_obj

        if self.open_connection == None:
            self.open_connection = self.set_connection()

        for packet in packets:
            try:
                self.open_connection.add_to_table(
                    table_name="tf"+self.libcfg["tofino_generation"]+".pktgen.app_cfg", 
                    keys=[["app_id", packet["app_id"]]],
                    datas=[["app_enable",False]],
                    action=t_action, 
                    mod=True
                )  
                self.logger.debug("Tofino Packet Generator: stopped app_id " + str(packet["app_id"]))

                self.open_connection.delete_table("pipe.SwitchIngress.t_l1_forwarding_generation")

            except Exception as e:
                self.logger.error(traceback.format_exc()) 
        
        for pktgen_port in self.libcfg["generator_ports"]:
            try:
                self.open_connection.add_to_table(table_name="tf"+self.libcfg["tofino_generation"]+".pktgen.port_cfg", 
                                    keys=[["dev_port", int(pktgen_port)]],
                                    datas=[["pktgen_enable", False]], 
                                    mod= True)  
                self.logger.debug("Tofino Packet Generator: port " + str(pktgen_port) + " disabled")
            except Exception as e:
                self.logger.error(traceback.format_exc())
        # when stopping packet gen only close connection when no open connection was passed as param
        if self.open_connection and not self.no_teardown:
            self.logger.debug("Tofino Packet Generator: teardown")
            self.open_connection.teardown()

        self.open_connection = None

        return None



