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
import threading


class AbstractExtHost:
    def __init__(self, host_cfg, dir_on_exec_host, logger):
        self.host_cfg = host_cfg
        self.dir_on_exec_host = dir_on_exec_host
        self.logger = logger

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
            ipv4, mac, prefix, up_state, iface_found = \
                P4STA_utils.fetch_interface(user, ip, iface, namespace)
            if ipv4 == "" or ipv4 == []:
                ipv4 = "n/a"
            if mac == "" or mac == []:
                mac = "device not found"
            return ipv4, mac, prefix, up_state
        res = {"ext_host_ssh_ping": (os.system(
            "timeout 1 ping " + cfg["ext_host_ssh"] + " -c 1") == 0)}
        if res["ext_host_ssh_ping"]:
            res["ext_host_sudo_rights"], list_of_path_possibilities = \
                P4STA_utils.check_sudo(
                    cfg["ext_host_user"], cfg["ext_host_ssh"],
                    dynamic_mode=True)
            self.logger.debug("Ext Host sudo path possibilities:")
            self.logger.debug(list_of_path_possibilities)
            res["list_of_path_possibilities"] = list_of_path_possibilities
            iface_status = check_iface(
                cfg["ext_host_user"], cfg["ext_host_ssh"], cfg["ext_host_if"])
            res["ext_host_fetched_ipv4"] = iface_status[0]
            res["ext_host_fetched_mac"] = iface_status[1]
            res["ext_host_fetched_prefix"] = iface_status[2]
            res["ext_host_up_state"] = iface_status[3]

            # store in results list (no return possible for a thread)
            results[index] = res

    # for all ext host the same (if log and error stored in log.out and log.err)
    def retrieve_current_logs(self, name_str_add=""):
        cfg = P4STA_utils.read_current_cfg()
        args_log = 'echo Last modified: $(stat -c "%y" /home/' + cfg["ext_host_user"] + '/p4sta/externalHost/' + self.dir_on_exec_host + '/log' + name_str_add + '.out); ' + 'cat /home/' + cfg["ext_host_user"] + '/p4sta/externalHost/' + self.dir_on_exec_host + '/log' + name_str_add + '.out'
        args_err = 'echo Last modified: $(stat -c "%y" /home/' + cfg["ext_host_user"] + '/p4sta/externalHost/' + self.dir_on_exec_host + '/log' + name_str_add + '.err); ' + 'cat /home/' + cfg["ext_host_user"] + '/p4sta/externalHost/' + self.dir_on_exec_host + '/log' + name_str_add + '.err'
        
        results = [None, None]
        def ssh_thread(args, res_indx):
            results[res_indx] = P4STA_utils.execute_ssh(cfg["ext_host_user"], cfg["ext_host_ssh"], args)

        # threading reduces the time from 0.8s to 0.4s
        t1 = threading.Thread(target = ssh_thread, args=(args_log, 0,))
        t2 = threading.Thread(target = ssh_thread, args=(args_err, 1,))

        t1.start()
        t2.start()

        t2.join()
        t1.join()

        res_log = results[0]
        res_err = results[1]

        # res = list of strings without \n
        # res_log = P4STA_utils.execute_ssh(cfg["ext_host_user"], cfg["ext_host_ssh"], args_log)
        # res_err = P4STA_utils.execute_ssh(cfg["ext_host_user"], cfg["ext_host_ssh"], args_err)

        # remove empty strings
        return (
            [x for x in res_log if x != ""],
            [x for x in res_err if x != ""]
            )
        