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

# parent class for individual load generator implementation
# every method should be overwritten by specific loadgen methods
import os
import P4STA_utils


class AbstractLoadgenerator:
    def __init__(self, loadgen_cfg):
        self.loadgen_cfg = loadgen_cfg

    def get_name(self):
        return "[Loadgenerator Template]"

    def setRealPath(self, path):
        self.realPath = path

    def run_loadgens(self, file_id, duration, l4_selected, packt_size_mtu,
                     results_path, loadgen_rate_limit, loadgen_flows,
                     loadgen_server_groups):
        return ["Sure you selected a load generator?"], "", True, "", "", \
               "", 0, 0, self.empty_plot()

    def process_loadgen_data(self, file_id, results_path):
        to_plot = self.empty_plot()

    # returns "empty" to_plot dict
    # can be called by inherited class if implemented type of loadgen
    # is not able to measure metrics like RTT
    def empty_plot(self):
        to_plot = {"mbits": {}, "rtt": {}, "packetloss": {}}
        to_plot["mbits"] = {"value_list_input": [0, 0, 0],
                            "index_list": [0, 1, 2],
                            "titel": "no throughput data available",
                            "x_label": "t[s]", "y_label": "Speed [Mbit/s]",
                            "filename": "loadgen_1", "adjust_unit": False,
                            "adjust_y_ax": False}

        to_plot["rtt"] = {"value_list_input": [0, 0, 0],
                          "index_list": [0, 1, 2],
                          "titel": "no RTT data available", "x_label": "t[s]",
                          "y_label": "RTT [microseconds]",
                          "filename": "loadgen_2", "adjust_unit": False,
                          "adjust_y_ax": False}

        to_plot["packetloss"] = {"value_list_input": [0, 0, 0],
                                 "index_list": [0, 1, 2],
                                 "titel": "no packetloss data available",
                                 "x_label": "t[s]",
                                 "y_label": "Packetloss [packets]",
                                 "filename": "loadgen_3", "adjust_unit": False,
                                 "adjust_y_ax": False}
        return to_plot

    def get_server_install_script(self, list_of_server):
        lst = []
        lst.append('echo "====================================="')
        lst.append('echo "not implemented for this Load generator"')
        lst.append('echo "====================================="')
        return lst

    # load generators threads
    def loadgen_status_overview(self, host, results, index):
        def check_iface(user, ip, iface, namespace=""):
            ipv4, mac, prefix, up_state, iface_found = \
                P4STA_utils.fetch_interface(user, ip, iface, namespace)
            if ipv4 == "" or ipv4 == []:
                ipv4 = "n/a"
            if mac == "" or mac == []:
                mac = "device not found"
            return ipv4, mac, prefix, up_state

        def check_namespaces(user, ip):
            namespaces = P4STA_utils.execute_ssh(user, ip, "ip netns list")
            answer = []
            for ns in namespaces:
                if ns != "":
                    ns_name = ns.split(" ")[0]
                    answer.append([str(ns)] + P4STA_utils.execute_ssh(
                        user, ip, "sudo ip netns exec " + str(
                            ns_name) + " ifconfig"))
            return answer

        res = {}
        res["ssh_ping"] = (
                os.system("timeout 1 ping " + host["ssh_ip"] + " -c 1") == 0)
        if res["ssh_ping"]:
            if "namespace_id" in host:
                res["fetched_ipv4"], res["fetched_mac"], \
                    res["fetched_prefix"], res["up_state"] = check_iface(
                    host['ssh_user'], host['ssh_ip'], host['loadgen_iface'],
                    host["namespace_id"])
            else:
                res["fetched_ipv4"], res["fetched_mac"], \
                    res["fetched_prefix"], res["up_state"] = check_iface(
                    host['ssh_user'], host['ssh_ip'],
                    host['loadgen_iface'], "")

            res["sudo_rights"], list_of_path_possibilities = \
                P4STA_utils.check_sudo(
                    host['ssh_user'], host['ssh_ip'], dynamic_mode=True)
            print("Loadgen sudo path possibilities:")
            print(list_of_path_possibilities)
            res["needed_sudos_to_add"] = P4STA_utils.check_needed_sudos(
                {"sudo_rights": res["sudo_rights"]},
                self.loadgen_cfg["status_check"]["needed_sudos_to_add"],
                dynamic_mode_inp=list_of_path_possibilities)
            res["ip_routes"] = P4STA_utils.execute_ssh(
                host['ssh_user'], host['ssh_ip'], "ip route")
            res["namespaces"] = check_namespaces(
                host['ssh_user'], host['ssh_ip'])

        else:
            res["sudo_rights"] = ["not reachable"]
            res["needed_sudos_to_add"] = []
            res["fetched_ipv4"], res["fetched_mac"] = ("", "")
            res["fetched_prefix"], res["up_state"] = ("", "down")
            res["ip_routes"] = []
            res["namespaces"] = []
        results[index] = res
