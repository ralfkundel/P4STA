# Copyright 2019-2020-present Ralf Kundel, Fridolin Siegmund, Kadir Eryigit
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
import requests
import subprocess
import time
import P4STA_utils

from abstract_extHost import AbstractExtHost

dir_path = os.path.dirname(os.path.realpath(__file__))


class ExtHostImpl(AbstractExtHost):
    def __init__(self, host_cfg, logger):
        # dir name at the host the actual external host impl is running, .../p4sta_externalHost/ + self.path_on_exec_host
        super().__init__(host_cfg, "go", logger)

    def start_external(self, file_id, multi=1, tsmax=(2 ** 32 - 1)):
        self.cfg = P4STA_utils.read_current_cfg()

        ext_dir = self.host_cfg["real_path"]
        errors = ()

        answer = P4STA_utils.execute_ssh(
            self.cfg["ext_host_user"],
            self.cfg["ext_host_ssh"],
            "mkdir -p /home/" + self.cfg["ext_host_user"] +
            "/p4sta/externalHost/go; sudo killall extHostHTTPServer go") # TODO: kills all running go programms .. => only extHostHTTPServer?

        input = ["scp", ext_dir + "/goUdpSocketExtHost.go",
                 self.cfg["ext_host_user"] + "@" + self.cfg[
                     "ext_host_ssh"] + ":/home/" + self.cfg[
                     "ext_host_user"] + "/p4sta/externalHost/go"]
        self.logger.debug(input)
        res = subprocess.run(input, stdout=subprocess.PIPE, timeout=3).stdout
        self.logger.debug(res)
        
        input = ["scp", ext_dir + "/extHostHTTPServer.go",
                 self.cfg["ext_host_user"] + "@" + self.cfg[
                     "ext_host_ssh"] + ":/home/" + self.cfg[
                     "ext_host_user"] + "/p4sta/externalHost/go"]
        self.logger.debug(input)
        res = subprocess.run(input, stdout=subprocess.PIPE, timeout=3).stdout
        self.logger.debug(res)

        input = ["scp", ext_dir + "/check_extH_status.sh",
                 self.cfg["ext_host_user"] + "@" + self.cfg[
                     "ext_host_ssh"] + ":/home/" + self.cfg[
                     "ext_host_user"] + "/p4sta/externalHost/go"]
        self.logger.debug(input)
        res = subprocess.run(input, stdout=subprocess.PIPE, timeout=3).stdout
        self.logger.debug(res)

        args = "chmod +x /home/" + self.cfg["ext_host_user"] + \
               "/p4sta/externalHost/go/goUdpSocketExtHost.go; " \
               "chmod +x /home/" + self.cfg["ext_host_user"] + \
               "/p4sta/externalHost/go/check_extH_status.sh;" \
               " rm -f /home/" + self.cfg["ext_host_user"] + \
               "/p4sta/externalHost/go/golangUdpSocketExtHost.log"
        self.logger.debug(args)
        res = P4STA_utils.execute_ssh(self.cfg["ext_host_user"],
                                      self.cfg["ext_host_ssh"], args)

        self.logger.info("start golang extHost")

        call = "sudo /home/" + self.cfg["ext_host_user"] + \
               "/p4sta/externalHost/go/go/bin/go run extHostHTTPServer.go goUdpSocketExtHost.go --name " + file_id + \
               " --ip_port " + self.cfg["ext_host_ip"] + ":41111 --ip " + self.cfg["ext_host_ip"]  # + " --multi " + str(multi) + " --tsmax " + str(tsmax)
        args = "cd /home/" + self.cfg["ext_host_user"] + \
               "/p4sta/externalHost/go/; nohup " + call + \
               " > log.out 2> log.err < /dev/null &"
        self.logger.debug(args)
        res = P4STA_utils.execute_ssh(self.cfg["ext_host_user"],
                                      self.cfg["ext_host_ssh"], args)

        # time.sleep(2)  # wait for the ext-host to succeed/fail
        # # check if interface is not found or other crash
        # input = ["ssh",
        #          self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"],
        #          "cd /home/" + self.cfg["ext_host_user"] +
        #          "/p4sta/externalHost/go; cat golangUdpSocketExtHost.log; exit"]
       
        # res = subprocess.run(input, stdout=subprocess.PIPE, timeout=3).stdout
        # result = res.decode("utf-8")

        # TODO: adjust for golang, still python errors => not required with live view in webgui
        # if result.find("Errno 19") > -1:
        #     errors = errors + ("Interface " + str(self.cfg["ext_host_if"]) +
        #                        " not found at external host: " + result,)
        # elif result.find("Exception") > -1:
        #     errors = errors + ("An exception occurred: " + result,)
        # elif result.find("Started") == -1:
        #     errors = errors + ("Ext host not started properly",)

        return errors

    def stop_external(self, file_id):
        self.cfg = P4STA_utils.read_current_cfg()
        P4STA_utils.execute_ssh(self.cfg["ext_host_user"],
                                self.cfg["ext_host_ssh"],
                                "sudo pkill -15 go; sudo killall extHostHTTPServer") # send sigterm to allow writing of files in signal handler, TODO: kills all go applications
        input = ["ssh", "-o ConnectTimeout=5",
                 self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"],
                 "cd /home/" + self.cfg["ext_host_user"] +
                 "/p4sta/externalHost/go; ./check_extH_status.sh; exit"]
        time.sleep(0.2)
        c = 0
        while True:  # wait until exthost stopped
            time.sleep(1)
            c = c + 1
            res = subprocess.run(input, stdout=subprocess.PIPE).stdout
            result = res.decode()
            if result.find("1") > -1 or c > 600:
                # if 1 is found by check_extH_status.sh at external host
                # external Host has finished saving csv files
                break
        subprocess.run(["scp", self.cfg["ext_host_user"] + "@" + self.cfg[
            "ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] +
                        "/p4sta/externalHost/go/raw_packet_counter_" +
                        file_id + ".csv",
                        P4STA_utils.get_results_path(file_id)])
        subprocess.run(["scp", self.cfg["ext_host_user"] + "@" + self.cfg[
            "ext_host_ssh"] + ":/home/" + self.cfg[
                            "ext_host_user"] +
                        "/p4sta/externalHost/go/packet_sizes_" +
                        file_id + ".csv",
                        P4STA_utils.get_results_path(file_id)])
        subprocess.run(["scp", self.cfg["ext_host_user"] + "@" + self.cfg[
            "ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] +
                        "/p4sta/externalHost/go/timestamp1_list_" +
                        file_id + ".csv",
                        P4STA_utils.get_results_path(file_id)])
        subprocess.run(["scp", self.cfg["ext_host_user"] + "@" + self.cfg[
            "ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] +
                        "/p4sta/externalHost/go/timestamp2_list_" +
                        file_id + ".csv",
                        P4STA_utils.get_results_path(file_id)])

        P4STA_utils.execute_ssh(self.cfg["ext_host_user"],
                                self.cfg["ext_host_ssh"],
                                "cd /home/" + self.cfg["ext_host_user"] +
                                "/p4sta/externalHost/go; rm *.csv")

        return True

    def get_server_install_script(self, user_name, ip):
        add_sudo_rights_str = "current_user=$USER\nadd_sudo_rights() {\n  " \
            "current_user=$USER\n  if " \
            "(sudo -l | grep -q '(ALL : ALL) SETENV: NOPASSWD: '$1); then\n    " \
            "echo 'visudo entry already exists';\n  else\n    sleep 0.1\n    " \
            "echo $current_user' ALL=(ALL:ALL) " \
            "NOPASSWD:SETENV:'$1 | sudo EDITOR='tee -a' visudo;\n  fi\n}\n"

        with open(dir_path + "/scripts/install_go_sudo.sh", "w") as f:
            f.write(add_sudo_rights_str)

            f.write("sudo apt update\n\n")
            f.write("sudo apt install psmisc\n\n")

            f.write('printf "Adding the following entries to visudo at ***External Host***:"\n')
            for sudo in self.host_cfg["status_check"]["needed_sudos_to_add"]:
                # e.g. sudo =
                # "/p4sta/externalHost/go/golangUdpSocketExtHost.py" case
                # => pasta dir at loadgen is always in home/user/p4sta
                if sudo.find("/p4sta/externalHost/") > -1:
                    f.write("add_sudo_rights /home/" + user_name + sudo + "\n")
                else:
                    f.write("add_sudo_rights $(which " + sudo + ")\n")
            f.write("\n")
        os.chmod(dir_path + "/scripts/install_go_sudo.sh", 0o777)
        os.chmod(dir_path + "/scripts/check_install_go.sh", 0o777)

        lst = []
        lst.append('echo "====================================="')
        lst.append('echo "Installing GoLang External Host on ' + ip + '"')
        lst.append('echo "====================================="')
        lst.append(
            'if ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
            user_name + '@' + ip + ' "echo \'ssh to ' + ip +
            ' ***worked***\';"; [ $? -eq 255 ]; then')

        lst.append('  echo "====================================="')
        lst.append(
            '  echo "\033[0;31m ERROR: Failed to connect to server \033[0m"')
        lst.append('  echo "====================================="')

        lst.append('else')

        lst.append('  cd ' + self.realPath + '/scripts')

        # checking if go is installed in 

        lst.append(
            '  ssh  -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
            user_name + '@' + ip + ' " mkdir -p /home/' + user_name +
            '/p4sta/externalHost/go/;"')
        lst.append(
            '  scp install_go_sudo.sh ' + user_name + '@' + ip +
            ':/home/' + user_name + '/p4sta/externalHost/go/')
        lst.append(
            '  ssh  -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
            user_name + '@' + ip + ' "cd /home/' + user_name +
            '/p4sta/externalHost/go; chmod +x install_go_sudo.sh;"')
        lst.append(
            '  ssh  -t -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
            user_name + '@' + ip + ' "cd /home/' + user_name +
            '/p4sta/externalHost/go; ./install_go_sudo.sh;"')

        # copy check_install_go.sh and execute
        lst.append(
            '  scp check_install_go.sh ' + user_name + '@' + ip +
            ':/home/' + user_name + '/p4sta/externalHost/go/')
        lst.append(
            '  ssh  -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
            user_name + '@' + ip + ' "cd /home/' + user_name +
            '/p4sta/externalHost/go; chmod +x check_install_go.sh;"')
        lst.append(
            '  ssh  -t -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
            user_name + '@' + ip + ' "cd /home/' + user_name +
            '/p4sta/externalHost/go; ./check_install_go.sh;"')

        lst.append('fi')
        return lst

    def ext_host_status_overview(self, results, index, cfg):
        super(ExtHostImpl, self).ext_host_status_overview(results, index, cfg)

        if type(results[index]) == dict \
                and "ext_host_ssh_ping" in results[index] \
                and results[index]["ext_host_ssh_ping"]:
            results[index]["ext_host_needed_sudos_to_add"] = P4STA_utils.\
                check_needed_sudos(
                    {"sudo_rights": results[index]["ext_host_sudo_rights"]},
                    self.host_cfg["status_check"]["needed_sudos_to_add"],
                    dynamic_mode_inp=results[index]
                    ["list_of_path_possibilities"])
            
    def ext_host_live_status(self):
        cfg = P4STA_utils.read_current_cfg()

        base_url = "http://" + str(cfg["ext_host_ssh"]) + ":8888"
        try:
            run_state = requests.get(base_url + "/run_state").json()
        except requests.exceptions.ConnectionError:
            self.logger.warning("HTTP API of GoLangExtHost not reachable.")
            run_state = {}
        except Exception as e:
            self.logger.error(str(e))
            run_state = {}

        return run_state
