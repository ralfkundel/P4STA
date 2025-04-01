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
import P4STA_utils


class AbstractTarget:
    def __init__(self, target_cfg, logger):
        self.target_cfg = target_cfg
        self.logger = logger

    def setRealPath(self, path):
        self.realPath = path

    def getFullTemplatePath(self):
        return os.path.join(self.realPath, self.target_cfg["cfg_template"])

    # returns a dict["real_ports"] and ["logical_ports"]
    def port_lists(self):
        temp = {"real_ports": [], "logical_ports": []}
        for i in range(0, 400):
            temp["real_ports"].append(str(i))
            temp["logical_ports"].append(str(i))
        return temp

    # update port mapping from physical ports to (p4) pipeline port ID
    def update_portmapping(self, cfg):
        pass

    # deploy config file (table entries) to p4 device
    def deploy(self, cfg):
        pass

    def get_all_dut_dst_p4_ports(self, cfg, get_as_dict=False):
        all_dut_dst_p4_ports = []
        for dut in cfg["dut_ports"]:
            if dut["use_port"] == "checked":
                if dut["p4_port"] not in all_dut_dst_p4_ports:
                    if get_as_dict:
                        all_dut_dst_p4_ports.append(dut)
                    else:
                        all_dut_dst_p4_ports.append(dut["p4_port"])
                else:
                    self.logger.warning("Port " +
                          str(dut["p4_port"] + " seems to be configured to "
                                               "more than one DUT port, P4STA "
                                               "may not work properly."))

        return all_dut_dst_p4_ports

    # if not overwritten = everything is zero
    def read_stamperice(self, cfg):
        cfg["total_deltas"] = cfg["delta_counter"] = \
            cfg["min_delta"] = cfg["max_delta"] = 0
        for dut in cfg["dut_ports"]:
            dut["num_ingress_packets"] = 0
            dut["num_ingress_stamped_packets"] = 0
            dut["num_egress_packets"] = 0
            dut["num_egress_stamped_packets"] = 0
        for loadgen_grp in cfg["loadgen_groups"]:
            for host in loadgen_grp["loadgens"]:
                host["num_ingress_packets"] = host["num_ingress_bytes"] = 0
                host["num_egress_packets"] = host["num_egress_bytes"] = 0
        cfg["dut_stats"] = {}
        cfg["dut_stats"]["total_packetloss"] = 0
        cfg["dut_stats"]["total_num_egress_packets"] = 0
        cfg["dut_stats"]["total_packetloss_percent"] = 0
        cfg["dut_stats"]["total_packetloss_stamped"] = 0
        cfg["dut_stats"]["total_num_egress_stamped_packets"] = 0
        cfg["dut_stats"]["total_packetloss_stamped_percent"] = 0

        return cfg

    def stamper_status(self, cfg):
        return ["No portmanager available",
                "Are you sure you selected a target before?"], \
                False, "no target selected!"

    # starts specific p4 software on device
    def start_stamper_software(self, cfg):
        pass

    def stop_stamper_software(self, cfg):
        pass

    # reset registers of p4 device
    def reset_p4_registers(self, cfg):
        pass

    def get_stamper_startup_log(self, cfg):
        return ["For this target is no log available."]

    def check_if_p4_compiled(self, cfg):
        return False, "Can not check if P4 program is compiled."

    def execute_ssh(self, cfg, arg):
        # input = ["ssh", cfg["stamper_user"] + "@" + cfg["stamper_ssh"], arg]
        # res = subprocess.Popen(input, stdout=subprocess.PIPE).stdout
        # return res.read().decode().split("\n")
        return P4STA_utils.execute_ssh(
            cfg["stamper_user"], cfg["stamper_ssh"], arg)

    # returns list of strings with needed dynamic sudos for this target
    # in difference to fixed needed sudos defined in target_config.json this
    # checks for needed sudos which aren't clear for every use case
    def needed_dynamic_sudos(self, cfg):
        return []

    def get_server_install_script(self, user_name, ip, target_specific_dict={}):
        lst = []
        lst.append('echo "====================================="')
        lst.append('echo "not implemented for this Stamper device"')
        lst.append('echo "====================================="')
        return lst

    # thread method used in core.py status_overview()
    def stamper_status_overview(self, results, index, cfg):
        # instances inheriting from abstract_target could implement additional
        # checks in the following way:
        # res["custom_checks"] = [[True=green/False=red,
        # "ipv4_forwarding"(=label to check),
        # "=1"(=text indicating result of check)]]
        res = {}
        res["stamper_ssh_ping"] = (
                os.system(
                    "timeout 1 ping " + cfg["stamper_ssh"] + " -c 1") == 0)
        res["stamper_sudo_rights"], list_of_path_possibilities = \
            P4STA_utils.check_sudo(
                cfg["stamper_user"], cfg["stamper_ssh"], dynamic_mode=True)
        self.logger.debug("Target sudo path possibilities:")
        self.logger.debug(list_of_path_possibilities)

        if res["stamper_ssh_ping"]:
            res["stamper_compile_status_color"], res["p4_compile_status"] = \
                self.check_if_p4_compiled(cfg)
        else:
            res["stamper_compile_status_color"], res["p4_compile_status"] = (
                False, "P4-Stamper is not reachable at SSH IP!")
        # needed sudos = defined in target_config.json + dynamic sudos
        needed_sudos = self.target_cfg["status_check"]["needed_sudos_to_add"] \
            + self.needed_dynamic_sudos(cfg)
        res["stamper_needed_sudos_to_add"] = P4STA_utils.check_needed_sudos(
            {"sudo_rights": res["stamper_sudo_rights"]},
            needed_sudos,
            dynamic_mode_inp=list_of_path_possibilities)

        # store in results list (no return possible for a thread)
        results[index] = res
