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
import os
import time
import subprocess

import P4STA_utils

from abstract_extHost import AbstractExtHost

dir_path = os.path.dirname(os.path.realpath(__file__))


class ExtHostImpl(AbstractExtHost):
    def __init__(self, host_cfg):
        super().__init__(host_cfg)
        print("init ext Host dpdk")

    def start_external(self, file_id, multi=1, tsmax=(2 ** 32 - 1)):
        self.cfg = P4STA_utils.read_current_cfg()

        cmd = "cd /home/" + self.cfg[
            "ext_host_user"] + "/p4sta/externalHost/dpdkExtHost/; touch " \
                               "receiver_stop; sleep 0.5; rm receiver_stop; " \
                               "sudo build/receiver 0"
        if self.cfg["selected_target"] == "bmv2":  # if mininet
            # load vfio module
            cmd = "sudo rmmod vfio-pci; sudo rmmod vfio_iommu_type1; " \
                  "sudo rmmod vfio; sudo modprobe vfio-pci; " + cmd
            cmd += " --vdev=eth_af_packet42,iface=" + self.cfg[
                "ext_host_if"] + ",blocksz=4096,framesz=2048,framecnt=512," \
                                 "qpairs=1,qdisc_bypass=0"
        cmd += " -- --name " + file_id + " > foo.out 2> foo.err < /dev/null &"
        print(cmd)
        res = P4STA_utils.execute_ssh(self.cfg["ext_host_user"],
                                      self.cfg["ext_host_ssh"], cmd)
        print("started DPDK-based external host")
        print(res)
        errors = ()
        return errors

    def stop_external(self, file_id):
        self.cfg = P4STA_utils.read_current_cfg()
        input = ["ssh",
                 self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"],
                 "cd /home/" + self.cfg[
                     "ext_host_user"] + "/p4sta/externalHost/dpdkExtHost/; "
                                        "touch receiver_stop"]
        res = subprocess.run(input).stdout
        print(res)
        input = ["ssh", "-o ConnectTimeout=5",
                 self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"],
                 "cd /home/" + self.cfg[
                     "ext_host_user"] + "/p4sta/externalHost/dpdkExtHost/; "
                                        "./check_extH_status.sh; exit"]
        c = 0
        while True:  # wait until exthost stopped
            time.sleep(1)
            c = c + 1
            res = subprocess.run(input, stdout=subprocess.PIPE).stdout
            result = res.decode()
            if result.find("1") > -1 or c > 59:
                # if 1 is found by check_extH_status.sh at external host,
                # receiver has finished saving csv files
                break
        subprocess.run(["scp", self.cfg["ext_host_user"] + "@" + self.cfg[
            "ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] +
                        "/p4sta/externalHost/dpdkExtHost/raw_packet_counter_"
                        + file_id + ".csv",
                        P4STA_utils.get_results_path(file_id)])
        subprocess.run(["scp", self.cfg["ext_host_user"] + "@" + self.cfg[
            "ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] +
                        "/p4sta/externalHost/dpdkExtHost/packet_sizes_" +
                        file_id + ".csv",
                        P4STA_utils.get_results_path(file_id)])
        subprocess.run(["scp", self.cfg["ext_host_user"] + "@" + self.cfg[
            "ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] +
                        "/p4sta/externalHost/dpdkExtHost/timestamp1_list_" +
                        file_id + ".csv",
                        P4STA_utils.get_results_path(file_id)])
        subprocess.run(["scp", self.cfg["ext_host_user"] + "@" + self.cfg[
            "ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] +
                        "/p4sta/externalHost/dpdkExtHost/timestamp2_list_" +
                        file_id + ".csv",
                        P4STA_utils.get_results_path(file_id)])
        time.sleep(1)
        P4STA_utils.execute_ssh(self.cfg["ext_host_user"],
                                self.cfg["ext_host_ssh"],
                                "cd /home/" + self.cfg["ext_host_user"] +
                                "/p4sta/externalHost/dpdkExtHost/; rm *.csv")
        return True

    def get_server_install_script(self, user_name, ip):
        add_sudo_rights_str = "current_user=$USER\nadd_sudo_rights() {\n  " \
            "current_user=$USER\n  if " \
            "(sudo -l | grep -q '(ALL : ALL) NOPASSWD: '$1); then\n    " \
            "echo 'visudo entry " \
            "already exists';\n  else\n    sleep 0.1\n    " \
            "echo $current_user' ALL=(ALL:ALL) " \
            "NOPASSWD:'$1 | sudo EDITOR='tee -a' visudo;\n  fi\n}\n"

        with open(dir_path + "/scripts/install_dpdk_sudo.sh", "w") as f:
            f.write(add_sudo_rights_str)
            f.write('printf "\nAdding the following entries to visudo '
                    'at ***External Host***:\n"\n')
            for sudo in self.host_cfg["status_check"]["needed_sudos_to_add"]:
                # e.g. sudo =
                # "/p4sta/externalHost/python/pythonRawSocketExtHost.py" case
                # => pasta dir at loadgen is always in home/user/p4sta
                if sudo.find("/p4sta/externalHost/") > -1:
                    f.write("add_sudo_rights /home/" + user_name + sudo + "\n")
                else:
                    f.write("add_sudo_rights $(which " + sudo + ")\n")
            f.write("\n")
        os.chmod(dir_path + "/scripts/install_dpdk_sudo.sh", 0o775)

        lst = []
        lst.append('echo "====================================="')
        lst.append('echo "Installing DPDK External Host on ' + ip + '"')
        lst.append('echo "====================================="')
        lst.append(
            'if ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
            user_name + '@' + ip + ' "echo \'ssh to ' + ip +
            ' ***worked***\';"; [ $? -eq 255 ]; then')

        lst.append('  echo "====================================="')
        lst.append('  echo "\033[0;31m ERROR: Failed to connect to DPDK '
                   'external host server \033[0m"')
        lst.append('  echo "====================================="')

        lst.append('else')

        lst.append('  cd ' + self.realPath + '/')

        lst.append('  ssh  -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
                   user_name + '@' + ip + ' " mkdir -p /home/' +
                   user_name + '/p4sta/externalHost/dpdkExtHost/;"')
        lst.append('  scp scripts/install_dpdk_ext_host.sh ' + user_name +
                   '@' + ip + ':/home/' + user_name +
                   '/p4sta/externalHost/dpdkExtHost/')
        lst.append('  scp scripts/check_extH_status.sh ' + user_name + '@' +
                   ip + ':/home/' + user_name +
                   '/p4sta/externalHost/dpdkExtHost/')
        lst.append('  scp scripts/install_dpdk_sudo.sh ' + user_name +
                   '@' + ip + ':/home/' + user_name +
                   '/p4sta/externalHost/dpdkExtHost/')
        lst.append('  scp -r src/* ' + user_name + '@' + ip + ':/home/' +
                   user_name + '/p4sta/externalHost/dpdkExtHost/')
        lst.append('  ssh  -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
                   user_name + '@' + ip + ' "cd /home/' + user_name +
                   '/p4sta/externalHost/dpdkExtHost; chmod +x '
                   'install_dpdk_ext_host.sh install_dpdk_sudo.sh;"')
        lst.append('  ssh  -t -o ConnectTimeout=2 -o StrictHostKeyChecking=no '
                   + user_name + '@' + ip + ' "cd /home/' + user_name +
                   '/p4sta/externalHost/dpdkExtHost; '
                   './install_dpdk_ext_host.sh; ./install_dpdk_sudo.sh;"')

        lst.append('fi')
        return lst

    def ext_host_status_overview(self, results, index, cfg):
        super(ExtHostImpl, self).ext_host_status_overview(results, index, cfg)
        if results[index]["ext_host_ssh_ping"]:
            results[index][
                "ext_host_needed_sudos_to_add"] = P4STA_utils.\
                check_needed_sudos(
                {"sudo_rights": results[index]["ext_host_sudo_rights"]},
                ["/usr/bin/pkill", "/usr/bin/killall", "/sbin/rmmod",
                 "/sbin/modprobe", "/home/" + cfg["ext_host_user"] +
                 "/p4sta/externalHost/dpdkExtHost/build/receiver"],
                dynamic_mode_inp=results[index]["list_of_path_possibilities"])
            try:
                answer = P4STA_utils.execute_ssh(
                    cfg["ext_host_user"], cfg["ext_host_ssh"],
                    "[ -d '/home/" + cfg["ext_host_user"] +
                    "/p4sta/externalHost/dpdkExtHost/dpdk-19.11/build' ] "
                    "&& echo '1'")
                print(answer)
                if answer[0] == "1":
                    results[index]["custom_checks"] = [
                        [True, "DPDK", "is installed"]]
                else:
                    results[index]["custom_checks"] = [
                        [False, "DPDK", "no installation found"]]
            except Exception:
                results[index]["custom_checks"] = [
                    [False, "DPDK", "An error occured while checking "
                                    "the DPDK installation path"]]
            try:
                answer = P4STA_utils.execute_ssh(
                    cfg["ext_host_user"], cfg["ext_host_ssh"],
                    "cat /sys/kernel/mm/hugepages/hugepages-2048kB/"
                    "nr_hugepages")
                try:
                    num = int(answer[0])
                    if num < 500:
                        results[index]["custom_checks"].append(
                            [False, "DPDK Hugepages",
                             "The number of configured hugepages(" + str(
                                 num) + ") is too low or zero!"])
                    else:
                        results[index]["custom_checks"].append(
                            [True, "DPDK Hugepages",
                             "The number of configured hugepages is " + str(
                                 num) + "!"])
                except Exception:
                    results[index]["custom_checks"].append(
                        [False, "DPDK Hugepages",
                         "An error occured while checking the hugepages: " +
                         answer])

            except Exception:
                results[index]["custom_checks"].append(
                    [False, "DPDK Hugepages", "ERROR"])
