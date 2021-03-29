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

import json
import os
import re
import subprocess
import traceback
from pathlib import Path


def set_project_path(path):
    global project_path
    project_path = path


def read_current_cfg(name="config.json"):
    path = os.path.join(project_path, "data", name)
    if not Path(path).is_file():
        return None

    updated_to_new_style = False

    with open(path, "r") as f:
        cfg = json.load(f)
        # change old style config into new one
        # allows compatibility to old configs
        if "p4_dev_ssh" in cfg and "stamper_ssh" not in cfg:
            cfg["stamper_ssh"] = cfg["p4_dev_ssh"]
            del cfg["p4_dev_ssh"]
            updated_to_new_style = True
        if "p4_dev_user" in cfg and "stamper_user" not in cfg:
            cfg["stamper_user"] = cfg["p4_dev_user"]
            del cfg["p4_dev_user"]
            updated_to_new_style = True
    # only update to new style if config.json - otherwise date overwritten
    if updated_to_new_style and name == "config.json":
        write_config(cfg)

    return cfg


def get_results_path(id):
    return os.path.join(project_path, "results", str(id))


def read_result_cfg(id):
    path = os.path.join(get_results_path(id), "config_"+str(id)+".json")
    if Path(path).is_file():
        with open(path, "r") as f:
            cfg = json.load(f)
            return cfg
    else:
        return


def write_config(cfg, file_name="config.json"):
    with open(project_path + "/data/"+file_name, "w") as write_json:
        json.dump(cfg, write_json, indent=2, sort_keys=True)


def execute_ssh(user, ip_address, arg):
    input = ["ssh", "-o ConnectTimeout=5", "-o BatchMode=yes",
             "-o StrictHostKeyChecking=no", user + "@" + ip_address, arg]
    res = subprocess.run(input, stdout=subprocess.PIPE).stdout
    return res.decode().split("\n")


# Logging


def log_error(error):
    print_msg = "\033[1;31m"
    print_msg += "-------------------- P4STA ERROR -------------------- \n"

    if isinstance(error, str):
        print_msg += error
    elif isinstance(error, tuple):
        print_msg += ''.join(error)
    else:
        print_msg += ("unknown error type: " + str(type(error)))
        print_msg += str(error)
    print_msg += "\n-----------------------------------------------------"
    print_msg += "\x1b[0m"

    print(print_msg)


# Sudo checking


def check_needed_sudos(host, needed_sudos, dynamic_mode_inp=[]):
    to_add = []
    for needed in needed_sudos:
        found = False
        if len(dynamic_mode_inp) > 0:
            found_in_path_str = False
            # is the needed sudo one of the possible paths?
            for paths_str in dynamic_mode_inp:
                if paths_str.find(needed) > -1:
                    found_in_path_str = True
                    break
            # is the line in visudo one of the possible paths?
            for right in host["sudo_rights"]:
                prog_name_inx = right.find("/")
                if prog_name_inx > -1:
                    for paths_str in dynamic_mode_inp:
                        if paths_str.find(right[prog_name_inx:]) > -1 \
                                and found_in_path_str:
                            found = True
                            break

        # not found => maybe dynamic failed, try old method (more false neg)
        if len(dynamic_mode_inp) == 0 or not found:
            for right in host["sudo_rights"]:
                if right.endswith("NOPASSWD: ALL"):
                    return []
                if right.find(needed) > -1:
                    found = True
        if not found:
            to_add.append(needed)
    return to_add


# dynamic_mode returns a second variable = list of strings of possibilities
def check_sudo(user, ip_address, dynamic_mode=False):
    # filters list and returns list of strings containing li
    def filter_list(li, to_check):
        return_results = []
        for r in li:
            if r.find(to_check) > -1:
                return_results.append(r)
        return return_results

    visudo_results = filter_list(
        execute_ssh(user, ip_address, "sudo -l"), "NOPASSWD")
    dyn_ret = []
    if dynamic_mode:
        for line in visudo_results:
            last = line.rfind("/")
            if last > -1:
                # e.g. = "ip" or "ethtool" or ..
                prog_name = line[line.rfind("/")+1:]
                ssh_res = execute_ssh(user, ip_address, "whereis " + prog_name)
                if len(ssh_res[0]) > len(prog_name):
                    # cut prog name at beginning of str("ip: /bin/ip /sbin/ip")
                    if ssh_res[0].find(prog_name + ":") == 0:
                        dyn_ret.append(ssh_res[0][len(prog_name)+2:])
                    # or just check if its in string
                    elif ssh_res[0].find(prog_name) > -1:
                        dyn_ret.append(ssh_res[0])
    if len(visudo_results) > 1:
        if dynamic_mode:
            return visudo_results, dyn_ret
        else:
            return visudo_results
    else:
        return ["Error checking sudo status."]


# Interface fetching
def fetch_interface(ssh_user, ssh_ip, iface, namespace=""):
    try:
        lines = subprocess.run(
            [project_path + "/core/scripts/fetch.sh", ssh_user, ssh_ip, iface,
             namespace], stdout=subprocess.PIPE).stdout.decode(
            "utf-8").split("\n")
        mac_line = ""
        ipv4_line = ""
        for li in range(0, len(lines)):
            if lines[li].find(iface) > -1:
                try:
                    for i in range(0, 10):
                        if lines[li + i].find("ether") > -1 \
                                or lines[li + i].find("HWaddr") > -1:
                            mac_line = lines[li + i]
                            break
                except Exception:
                    mac_line = ""
                try:
                    for i in range(0, 10):
                        found = lines[li + i].find("inet ")
                        # ifconfig diff vers, sometimes Bcast or broadcast
                        if found > -1:
                            if lines[li + i].find(
                                    "Bcast") < lines[li + i].find("broadcast"):
                                bcast = lines[li + i].find("broadcast")
                            else:
                                bcast = lines[li + i].find("Bcast")
                            if lines[li + i].find(
                                    "netmask") < lines[li + i].find("Mask"):
                                nm = lines[li + i].find("Mask")
                            else:
                                nm = lines[li + i].find("netmask")
                            # broadcast and netmask in diff versions swapped
                            if nm < bcast:
                                stop = nm
                                nm_line = lines[li + i][nm:bcast]
                            else:
                                stop = bcast
                                nm_line = lines[li + i][nm:]

                            ipv4_line = lines[li + i][found:stop]
                            break
                except Exception:
                    ipv4_line = nm_line = ""
                break

        re_mac = re.compile('([0-9a-f]{2}(?::[0-9a-f]{2}){5})', re.IGNORECASE)
        re_ipv4 = re.compile(r'[0-9]+(?:\.[0-9]+){3}')

        mac = re.findall(re_mac, mac_line)
        if isinstance(mac, list) and len(mac) > 0:
            mac = mac[0]
        else:
            mac = ""
        ipv4 = re.findall(re_ipv4, ipv4_line)
        if isinstance(ipv4, list) and len(ipv4) > 0:
            ipv4 = ipv4[0]
        else:
            ipv4 = ""
        prefix = ""
        try:
            netmask = re.findall(re_ipv4, nm_line)[0]
            prefix = "/" + str(sum(bin(int(x)).count(
                '1') for x in netmask.split('.')))
        except Exception:
            prefix = ""

    except Exception as e:
        log_error("CORE EXCEPTION: " + str(traceback.format_exc()))
        ipv4 = mac = "fetch error"

    # check if iface is up
    iface_found = False
    try:
        if namespace == "":
            up_state = execute_ssh(
                ssh_user, ssh_ip, 'ifconfig | grep "' + iface+'"')[0]
        else:
            up_state = execute_ssh(
                ssh_user, ssh_ip, 'sudo ip netns exec ' + str(
                    namespace) + ' ifconfig | grep "' + iface + '"')[0]
        if len(up_state) > 0:
            up_state = "up"
            iface_found = True
        else:
            up_state = "down"
            found = execute_ssh(
                ssh_user, ssh_ip, 'ifconfig -a | grep "' + iface + '"')[0]
            if len(found) > 0:
                iface_found = True
    except Exception:
        up_state = "error"

    return ipv4, mac, prefix, up_state, iface_found


# RPC tools:


def flt(x):
    if isinstance(x, dict):
        return flt_dict(x)
    elif isinstance(x, list):
        return flt_lst(x)
    elif isinstance(x, tuple):
        return flt_tuple(x)
    else:
        return x


def flt_dict(cfg):
    new = {}
    for k, v in cfg.items():
        new[k] = flt(v)
    return new


def flt_lst(lst):
    ls = []
    for e in lst:
        ls.append(flt(e))
    return ls


def flt_tuple(tpl):
    new = ()
    for e in tpl:
        new = new + (flt(e),)
    return new
