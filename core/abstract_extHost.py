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
import P4STA_utils

class AbstractExtHost:
    def __init__(self, host_cfg):
        self.host_cfg = host_cfg
        print("init abstract ext Host:")
        print(host_cfg)

    def setRealPath(self, path):
        self.realPath = path

    def start_external(self, file_id):
        return

    def stop_external(self, file_id):
        return

    def get_server_install_script(self, user_name, ip):
        lst = []
        lst.append('echo "====================================="')
        lst.append('echo "not implemented for this external host"')
        lst.append('echo "====================================="')
        return lst

    def ext_host_status_overview(self, results, index, cfg):
        def check_iface(user, ip, iface, namespace=""):
            ipv4, mac, prefix, up_state, iface_found = P4STA_utils.fetch_interface(user, ip, iface, namespace)
            if ipv4 == "" or ipv4 == []:
                ipv4 = "n/a"
            if mac == "" or mac == []:
                mac = "device not found"
            return ipv4, mac, prefix, up_state
        res = {"ext_host_ssh_ping": (os.system("timeout 1 ping " + cfg["ext_host_ssh"] + " -c 1") == 0)}
        if res["ext_host_ssh_ping"]:
            res["ext_host_sudo_rights"], list_of_path_possibilities = P4STA_utils.check_sudo(cfg["ext_host_user"], cfg["ext_host_ssh"], dynamic_mode=True)
            print("Ext Host sudo path possibilities:")
            print(list_of_path_possibilities)
            res["list_of_path_possibilities"] = list_of_path_possibilities
            res["ext_host_fetched_ipv4"], res["ext_host_fetched_mac"], res["ext_host_fetched_prefix"], res["ext_host_up_state"] = check_iface(cfg["ext_host_user"], cfg["ext_host_ssh"], cfg["ext_host_if"])

            # store in results list (no return possible for a thread)
            results[index] = res
