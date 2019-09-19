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

# parent class for individual target implementation
# every method should be overwritten by specific target methods

import os
import subprocess

class AbstractTarget:
    def __init__(self, target_cfg):
        self.target_cfg = target_cfg
        self.speed_list = ["1G", "10G", "25G", "40G"]  # speedlist if no new one will be defined in child class

    def setRealPath(self, path):
        self.realPath = path

    def getFullTemplatePath(self):
        return os.path.join(self.realPath, self.target_cfg["cfg_template"])

    # for stamper target specific configuration inputs (e.g. FEC)
    def stamper_specific_config(self, cfg):
        pass

    # returns a dict["real_ports"] and ["logical_ports"]
    def port_lists(self):
        temp = {"real_ports": [], "logical_ports": []}
        for i in range(0, 100):
            temp["real_ports"].append(str(i))
            temp["logical_ports"].append(str(i))
        return temp

    # deploy config file (table entries) to p4 device
    def deploy(self):
        pass

    # if not overwritten = everything is zero
    def read_p4_device(self, cfg):
        cfg["total_deltas"] = cfg["delta_counter"] = cfg["min_delta"] = cfg["max_delta"] = 0
        for n in ["dut1", "dut2", "ext_num"]:
            cfg[n + "_num_ingress_packets"] = cfg[n + "_num_ingress_bytes"] = 0
            cfg[n + "_num_egress_packets"] = cfg[n + "_num_egress_bytes"] = 0
        i = 9
        for host in (cfg["loadgen_servers"] + cfg["loadgen_clients"]):
            host["num_ingress_packets"] = host["num_ingress_bytes"] = 0
            host["num_egress_packets"] = host["num_egress_bytes"] = 0
            i = i + 3
        cfg["packet_loss_1"] = cfg["packet_loss_2"] = 0

        return cfg

    def visualization(self, cfg):
        return "<p>Unfortunately there is <b>no</b> visualization html file provided by the selected p4 device.</p>" \
               "<p>Are you sure you selected the right device?</p>"

    def p4_dev_status(self, cfg):
        return ["No portmanager available", "Are you sure you selected a target before?"], False, "no target selected!"

    # starts specific p4 software on device
    def start_p4_dev_software(self, cfg):
        pass

    def stop_p4_dev_software(self, cfg):
        pass

    # reset registers of p4 device
    def reset_p4_registers(self, cfg):
        pass

    def get_p4_dev_startup_log(self, cfg):
        return ["For this target is no log available."]

    def check_if_p4_compiled(self, cfg):
        return False, "Can not check if P4 program is compiled."

    def execute_ssh(self, cfg, arg):
        input = ["ssh", cfg["p4_dev_user"] + "@" + cfg["p4_dev_ssh"], arg]
        res = subprocess.Popen(input, stdout=subprocess.PIPE).stdout
        return res.read().decode().split("\n")
