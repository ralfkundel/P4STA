
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
import numpy as np
import os
import sys
import threading
import time
import traceback

dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir_path)
from abstract_loadgenerator import AbstractLoadgenerator
from pktgen import TofinoPacketGenerator
import P4STA_utils

class LoadGeneratorImpl(AbstractLoadgenerator):
    def __init__(self, loadgen_cfg, logger):
        super().__init__(loadgen_cfg, logger)
        self.directory = os.path.dirname(os.path.realpath(__file__))

        cfg = P4STA_utils.read_current_cfg()
        self.cfg = P4STA_utils.read_current_cfg()
        try:
            stamper_cfg = loadgen_cfg["current_stamper_cfg"]
            dut_ports = [dut["p4_port"] for dut in cfg["dut_ports"]]
            # if e.g. only 2 dut ports are used, fill with 0 as dut port so each generator port matches a dut port
            while len(dut_ports) < len(stamper_cfg["packet_generator_ports"]):
                dut_ports.append(0)
            
            lib_cfg = {
                "ssh_ip": cfg["stamper_ssh"], 
                "generator_ports": stamper_cfg["packet_generator_ports"], 
                "egress_ports": dut_ports,
                "egress_mcast_groups_map": [[], [], [], []],
                "use_gen_port_map": [False, False, False, False], # is updated when running
                "mcast_duplication_multis": [1,1,1,1],        # is updated when running
                "p4_program": cfg["program"],
                "tofino_generation": str(stamper_cfg["tofino_generation"]),
                "sniff_points": []
                    # not working in current state
                    # {"type": 1, "duplicate_to_p4_ports": [44]},
                    # {"type": 2, "duplicate_to_p4_ports": [44]}
            }
        except KeyError as e:
            self.logger.warning("KeyError ("+str(e)+")for Tofino Integrated Packet Generator - unable to configure Tofino generation. Trying fallback to default values: TOFINO 1.")
            self.logger.debug(traceback.format_exc())
            lib_cfg = {
                "ssh_ip": cfg["stamper_ssh"], 
                "generator_ports": [],
                "egress_ports": [dut["p4_port"] for dut in cfg["dut_ports"]],
                "egress_mcast_groups_map": [[], [], [], []],
                "use_gen_port_map": [True, True, True, True],
                "mcast_duplication_multis": [1,1,1,1],
                "p4_program": cfg["program"],
                "tofino_generation": "1",
                "sniff_points": []
                    # {"type": 1, "duplicate_to_p4_ports": []},
                    # {"type": 2, "duplicate_to_p4_ports": []}
            }

        try:
            self.lib = TofinoPacketGenerator(lib_cfg, self.logger)
        except:
            self.logger.error(traceback.format_exc())
            self.lib = None

    def get_name(self):
        return "Tofino Packet Generator"

    def run_loadgens(self, file_id, duration, l4_selected, packet_size_mtu,
                     results_path, loadgen_rate_limit, loadgen_flows,
                     loadgen_server_groups, loadgen_cfg):

        self.logger.debug("loadgen_cfg: " + str(loadgen_cfg))
        
        if loadgen_cfg != None and "tofino_grpc_obj" in loadgen_cfg:
            tofino_grpc_obj = loadgen_cfg["tofino_grpc_obj"]
            # in current state connection is always new established (in set_connection())
            tofino_grpc_obj.teardown()
        else:
            tofino_grpc_obj = None
            self.logger.debug("#core IntegratedGeneration.py run_loadgens(): tofino_grpc_obj is None - creating...")

        # parse current scapy packets
        py_packets = self.exec_py_str(self.read_python_packet_code())

        packet_list = []#[None, None, None, None]
        self.lib.libcfg["mcast_duplication_multis"] = []
        indx = -1
        for gen_port in loadgen_cfg["gen_ports"]:
            indx += 1
            self.lib.libcfg["use_gen_port_map"][indx] = gen_port["use_port"]
            scapy_packet = py_packets[gen_port["selected_packet"]]
            #packet_list[indx] = {
            packet_list.append({
                "scapy_packet": scapy_packet,
                "app_id": indx+1, # start at app 1 (periodic timer)
                "rate_mbps": int(gen_port["rate_mbps"])
            })
            # duplicate packets to additional ports
            additional_port_p4_ports = []
            for port_id in gen_port["duplicate_to_additional_port_ids"]:
                for port in self.cfg["additional_ports"]:
                    if port["id"] == port_id:
                        additional_port_p4_ports.append(port["p4_port"])
                        break
            self.lib.libcfg["egress_mcast_groups_map"][indx] = additional_port_p4_ports

            # set duplication multiplicators => 1 means no extra duplication here. Just the normal multicast egress ports
            multi = gen_port["mcast_duplication_multi"]
            if multi is None or multi == "":
                self.lib.libcfg["mcast_duplication_multis"].append(1)
            elif (type(multi) == str and multi.isnumeric()) or type(multi) == int:
                m = int(multi)
                # default is 1, no additional duplication
                if m < 1:
                    m = 1
                self.lib.libcfg["mcast_duplication_multis"].append(m)


        tofino_grpc_obj = self.lib.set_connection()
        tofino_grpc_obj = self.lib.start_packet_generation(packet_list, tofino_grpc_obj)

        self.logger.info("Started packet generation ..")

        def wait_and_stop_thread(duration, packet_list, tofino_grpc_obj):
            for i in range(1,duration+1):
                self.logger.info("Run sec " + str(i))
                time.sleep(1)

            self.lib.stop_packet_generation(packet_list, tofino_grpc_obj)
            self.logger.info("Stopped packet generation")

        # non-blocking loadgen run so django can serve other requests such as metrics queries
        thread = threading.Thread(target=wait_and_stop_thread, args=(duration, packet_list, tofino_grpc_obj))
        thread.start()

        # return grpc object as live display of throughput in django views requires the open connection
        return {"tofino_grpc_obj": tofino_grpc_obj}
    
    
    def process_loadgen_data(self, file_id, results_path):
        with open("results/" + str(
            file_id) + "/logfile.json", "r") as json_file:
            data = json.load(json_file)
        output = ""
        error = False
        to_plot = {}
        egress_port_list = []

        for i in range(len(data)):
            egress_port = data[i]['egress_port']
            egress_port_list.append(egress_port)
            bit_rate_list = data[i]['bit_rate_list']
            packet_rate_list = data[i]['packet_rate_list']
            total_interval_mbits = [x / 1000000 for x in bit_rate_list]
            total_interval_kpps = [x/1000 for x in packet_rate_list]

            to_plot["mbits_"+str(i)] = {"value_list_input": total_interval_mbits,
                        "index_list": np.arange(1, len(total_interval_mbits) + 1),
                        "titel": f"Bit Rate at Egress Port {egress_port}",
                        "x_label": "t[s]",
                        "y_label": "Speed [Mbit/s]",
                        "filename": f"loadgen_{i+1}_1", 
                        "adjust_unit": False, 
                        "adjust_y_ax": True}
            
            to_plot["kpps_"+str(i)] = {"value_list_input": total_interval_kpps,
                        "index_list": np.arange(1, len(total_interval_kpps) + 1),
                        "titel": f"Packet Rate at Egress Port {egress_port}",
                        "x_label": "t[s]",
                        "y_label": "Packet Rate [kpps]",
                        "filename": f"loadgen_{i+1}_2", 
                        "adjust_unit": False, 
                        "adjust_y_ax": True}
                
        return output, error, to_plot, egress_port_list
    

    #
    # 
    #  Functions only for integrated generation, not abstract loadgen API compliant
    #
    #
    def save_python_packet_code(self, py_str):
        with open(dir_path + "/scapy_code.py", "w+") as f:
            f.write(py_str)

    def read_python_packet_code(self):
        try:
            with open(dir_path + "/scapy_code.py", "r") as f:
                return f.read()
        except FileNotFoundError:
            self.logger.info("scapy_code.py not found - using template.py")
            return self.read_python_packet_code_template()
        except:
            self.logger.error(traceback.format_exc())
            return str(traceback.format_exc())
        
    def read_python_packet_code_template(self):
        try:
            with open(dir_path + "/template.py", "r") as f:
                return f.read()
        except:
            self.logger.error(traceback.format_exc())
            return str(traceback.format_exc())
        
    def exec_py_str(self, py_str):
        imports_str = "from scapy.all import *\nfrom scapy.contrib import gtp\nfrom scapy_patches.ppp import PPPoE, PPP"


        self.logger.debug("----- START EXEC -----")
        self.logger.debug("INPUT ===>")
        self.logger.debug(repr(py_str))

        scope = {}
        py_code = imports_str + py_str
        exec(py_code, scope)
        packets = scope["packets"]
        
        self.logger.debug("----- END EXEC -----")
        self.logger.debug("Got packets dictionary from WebGUI: " + str(packets))

        return packets