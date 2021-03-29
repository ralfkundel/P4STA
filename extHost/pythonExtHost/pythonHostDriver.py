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
import time
import subprocess
import P4STA_utils

from abstract_extHost import AbstractExtHost

dir_path = os.path.dirname(os.path.realpath(__file__))


class ExtHostImpl(AbstractExtHost):
    def __init__(self, host_cfg):
        super().__init__(host_cfg)
        print("init Python Ext Host")

    def start_external(self, file_id, multi=1, tsmax=(2 ** 32 - 1)):
        self.cfg = P4STA_utils.read_current_cfg()

        ext_py_dir = self.host_cfg["real_path"]
        errors = ()

        # check pip3 modules
        answer = P4STA_utils.execute_ssh(
            self.cfg["ext_host_user"],
            self.cfg["ext_host_ssh"],
            "python3 -c 'import pkgutil; print(1 if pkgutil.find_loader"
            "(\"setproctitle\") else 0)'")
        if answer[0] == "0":
            errors = errors + (
                "Python Module 'setproctitle' not found at external host -> "
                "'pip3 install setproctitle'",)
            return errors

        answer = P4STA_utils.execute_ssh(
            self.cfg["ext_host_user"],
            self.cfg["ext_host_ssh"],
            "mkdir -p /home/" + self.cfg["ext_host_user"] +
            "/p4sta/externalHost/python; "
            "sudo killall external_host_python_receiver")

        input = ["scp", ext_py_dir + "/pythonRawSocketExtHost.py",
                 self.cfg["ext_host_user"] + "@" + self.cfg[
                     "ext_host_ssh"] + ":/home/" + self.cfg[
                     "ext_host_user"] + "/p4sta/externalHost/python"]
        res = subprocess.run(input, stdout=subprocess.PIPE, timeout=3).stdout

        input = ["scp", ext_py_dir + "/check_extH_status.sh",
                 self.cfg["ext_host_user"] + "@" + self.cfg[
                     "ext_host_ssh"] + ":/home/" + self.cfg[
                     "ext_host_user"] + "/p4sta/externalHost/python"]
        res = subprocess.run(input, stdout=subprocess.PIPE, timeout=3).stdout

        args = "chmod +x /home/" + self.cfg["ext_host_user"] + \
               "/p4sta/externalHost/python/pythonRawSocketExtHost.py; " \
               "chmod +x /home/" + self.cfg["ext_host_user"] + \
               "/p4sta/externalHost/python/check_extH_status.sh;" \
               " rm -f /home/" + self.cfg["ext_host_user"] + \
               "/p4sta/externalHost/python/pythonRawSocketExtHost.log"
        print(args)
        res = P4STA_utils.execute_ssh(self.cfg["ext_host_user"],
                                      self.cfg["ext_host_ssh"], args)

        print("now start python extHost")
        call = "sudo ./pythonRawSocketExtHost.py --name " + file_id + \
               " --interface " + self.cfg["ext_host_if"] + " --multi " + str(
                   multi) + " --tsmax " + str(tsmax)
        args = "cd /home/" + self.cfg["ext_host_user"] + \
               "/p4sta/externalHost/python/; nohup " + call + \
               " > foo.out 2> foo.err < /dev/null &"
        print(args)
        res = P4STA_utils.execute_ssh(self.cfg["ext_host_user"],
                                      self.cfg["ext_host_ssh"], args)

        time.sleep(2)  # wait for the ext-host to succeed/fail
        # check if interface is not found or other crash
        input = ["ssh",
                 self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"],
                 "cd /home/" + self.cfg["ext_host_user"] +
                 "/p4sta/externalHost/python; cat pythonRawSocketExtHost.log; "
                 "exit"]
        res = subprocess.run(input, stdout=subprocess.PIPE, timeout=3).stdout
        result = res.decode("utf-8")

        if result.find("Errno 19") > -1:
            errors = errors + ("Interface " + str(self.cfg["ext_host_if"]) +
                               " not found at external host: " + result,)
        elif result.find("Exception") > -1:
            errors = errors + ("An exception occurred: " + result,)
        elif result.find("Started") == -1:
            errors = errors + ("Ext host not started properly",)

        return errors

    def stop_external(self, file_id):
        self.cfg = P4STA_utils.read_current_cfg()
        P4STA_utils.execute_ssh(self.cfg["ext_host_user"],
                                self.cfg["ext_host_ssh"],
                                "sudo killall external_host_python_receiver")
        input = ["ssh", "-o ConnectTimeout=5",
                 self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"],
                 "cd /home/" + self.cfg["ext_host_user"] +
                 "/p4sta/externalHost/python; ./check_extH_status.sh; exit"]
        time.sleep(0.2)
        c = 0
        while True:  # wait until exthost stopped
            time.sleep(0.3)
            c = c + 1
            res = subprocess.run(input, stdout=subprocess.PIPE).stdout
            result = res.decode()
            if result.find("1") > -1 or c > 59:
                # if 1 is found by check_extH_status.sh at external host
                # external Host has finished saving csv files
                break
        subprocess.run(["scp", self.cfg["ext_host_user"] + "@" + self.cfg[
            "ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] +
                        "/p4sta/externalHost/python/raw_packet_counter_" +
                        file_id + ".csv",
                        P4STA_utils.get_results_path(file_id)])
        subprocess.run(["scp", self.cfg["ext_host_user"] + "@" + self.cfg[
            "ext_host_ssh"] + ":/home/" + self.cfg[
                            "ext_host_user"] +
                        "/p4sta/externalHost/python/packet_sizes_" +
                        file_id + ".csv",
                        P4STA_utils.get_results_path(file_id)])
        subprocess.run(["scp", self.cfg["ext_host_user"] + "@" + self.cfg[
            "ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] +
                        "/p4sta/externalHost/python/timestamp1_list_" +
                        file_id + ".csv",
                        P4STA_utils.get_results_path(file_id)])
        subprocess.run(["scp", self.cfg["ext_host_user"] + "@" + self.cfg[
            "ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] +
                        "/p4sta/externalHost/python/timestamp2_list_" +
                        file_id + ".csv",
                        P4STA_utils.get_results_path(file_id)])

        P4STA_utils.execute_ssh(self.cfg["ext_host_user"],
                                self.cfg["ext_host_ssh"],
                                "cd /home/" + self.cfg["ext_host_user"] +
                                "/p4sta/externalHost/python; rm *.csv")

        return True

    def get_server_install_script(self, user_name, ip):
        add_sudo_rights_str = "current_user=$USER\nadd_sudo_rights() {\n  " \
            "current_user=$USER\n  if " \
            "(sudo -l | grep -q '(ALL : ALL) NOPASSWD: '$1); then\n    " \
            "echo 'visudo entry " \
            "already exists';\n  else\n    sleep 0.1\n    " \
            "echo $current_user' ALL=(ALL:ALL) " \
            "NOPASSWD:'$1 | sudo EDITOR='tee -a' visudo;\n  fi\n}\n"

        with open(dir_path + "/scripts/install_python_sudo.sh", "w") as f:
            f.write(add_sudo_rights_str)
            f.write(
                'printf "\nAdding the following entries to '
                'visudo at ***External Host***:\n"\n')
            for sudo in self.host_cfg["status_check"]["needed_sudos_to_add"]:
                # e.g. sudo =
                # "/p4sta/externalHost/python/pythonRawSocketExtHost.py" case
                # => pasta dir at loadgen is always in home/user/p4sta
                if sudo.find("/p4sta/externalHost/") > -1:
                    f.write("add_sudo_rights /home/" + user_name + sudo + "\n")
                else:
                    f.write("add_sudo_rights $(which " + sudo + ")\n")
            f.write("\n")
        os.chmod(dir_path + "/scripts/install_python_sudo.sh", 0o775)

        lst = []
        lst.append('echo "====================================="')
        lst.append('echo "Installing Python External Host on ' + ip + '"')
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

        lst.append(
            '  ssh  -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
            user_name + '@' + ip + ' " mkdir -p /home/' + user_name +
            '/p4sta/externalHost/python/;"')
        lst.append(
            '  scp install_python_sudo.sh ' + user_name + '@' + ip +
            ':/home/' + user_name + '/p4sta/externalHost/python/')
        lst.append(
            '  ssh  -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
            user_name + '@' + ip + ' "cd /home/' + user_name +
            '/p4sta/externalHost/python; chmod +x install_python_sudo.sh;"')
        lst.append(
            '  ssh  -t -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
            user_name + '@' + ip + ' "cd /home/' + user_name +
            '/p4sta/externalHost/python; ./install_python_sudo.sh;"')
        lst.append(
            '  ssh  -t -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
            user_name + '@' + ip +
            ' "sudo apt update; sudo apt install -y python3-pip"')
        for version in self.host_cfg["python_dependencies"]:
            for module in version["modules"]:
                pip_str = "pip" + version[
                    "python_version"] + " install " + module
                lst.append('  ssh  -t -o ConnectTimeout=2 -o '
                           'StrictHostKeyChecking=no ' + user_name + '@' +
                           ip + ' "' + pip_str + '"')

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
            try:
                answer = P4STA_utils.\
                    execute_ssh(cfg["ext_host_user"], cfg["ext_host_ssh"],
                                "python3 -c 'import pkgutil; "
                                "print(1 if pkgutil.find_loader"
                                "(\"setproctitle\") else 0)'")
                if answer[0] == "1":
                    results[index]["custom_checks"] = [
                        [True, "module setproctitle", "is installed"]]
                else:
                    results[index]["custom_checks"] = [
                        [False, "module setproctitle", "is not installed"]]
            except Exception:
                results[index]["custom_checks"] = [
                    [False, "module setproctitle", "error checking"]]
