#!/usr/bin/env python3

# Copyright 2020-present Ralf Kundel, Fridolin Siegmund
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
import subprocess
import sys
import traceback

from abstract_target import AbstractTarget

import P4STA_utils

dir_path = os.path.dirname(os.path.realpath(__file__))

sys.path.append(dir_path + "/thrift")
import bmv2_thrift_py3 as bmv2_thrift

project_path = dir_path[0:dir_path.find("/stamper_targets")]


class TargetImpl(AbstractTarget):

    def __init__(self, target_cfg):
        super().__init__(target_cfg)
        self.speed_list = ["n/a"]

    def deploy_stamper_thrift(self, cfg):
        all_dut_dst_p4_ports = self.get_all_dut_dst_p4_ports(cfg)
        error_msg = ""
        try:
            thr = bmv2_thrift.Bmv2Thrift(cfg["p4_dev_ssh"], dir_path + "/data/" + cfg["program"] + ".json")

            thr.clear_all_tables()
            thr.clear_all_mcast_grps()
            print("All tables and mcast groups cleared.")

            last_group_id = 0
            node = 0
            for loadgen_group in cfg["loadgen_groups"]:
                last_group_id = int(loadgen_group["group"])
                group_hdl = thr.create_mcast_grp(last_group_id)
                for host in loadgen_group["loadgens"]:
                    thr.create_mc_node(node, host["p4_port"])
                    thr.associate_mc_node(group_hdl, node)
                    print("Loadgen Group " + str(last_group_id) + " Host " + host["loadgen_ip"] + " connected to P4-Port " + host["p4_port"] + " added to Mcast Grp " + str(group_hdl))
                    node = node + 1

            last_group_id = last_group_id + 1

            # multicast groups for external host, because of bmv2 the original receiver needs to be included
            for loadgen_group in cfg["loadgen_groups"]:
                for host in loadgen_group["loadgens"]:
                    host["mcast_grp"] = str(last_group_id)
                    group_hdl = thr.create_mcast_grp(last_group_id)
                    print("Create Mcast Grp " + str(last_group_id) + " for Loadgen " + host["loadgen_ip"] + " and ext host")
                    thr.create_mc_node(node, cfg["ext_host"])
                    thr.associate_mc_node(group_hdl, node)
                    node = node + 1
                    thr.create_mc_node(node, host["p4_port"])
                    thr.associate_mc_node(group_hdl, node)
                    node = node + 1
                    last_group_id = last_group_id + 1

            if cfg['forwarding_mode'] == "1":
                for loadgen_group in cfg["loadgen_groups"]:
                    first_host = loadgen_group["loadgens"][0]
                    for dut in cfg["dut_ports"]:
                        if dut["id"] == loadgen_group["group"] and dut["use_port"] == "checked":
                            error_msg += thr.table_add("ingress.t_l1_forwarding", "ingress.send", matches=[dut["p4_port"]], action_parameters=[first_host["p4_port"]])
            else:
                for dut in cfg["dut_ports"]:
                    if dut["use_port"] == "checked":
                        error_msg += thr.table_add("ingress.t_l1_forwarding", "ingress.no_op", matches=[dut["p4_port"]])

            error_msg += thr.table_add("ingress.t_l1_forwarding", "ingress.no_op", matches=[cfg["ext_host"]])

            # Send ingoing from Group 1 to DUT1, Group 2 to DUT2 ...
            for loadgen_group in cfg["loadgen_groups"]:
                for dut in cfg["dut_ports"]:
                    if int(dut["id"]) == int(loadgen_group["group"]) and dut["use_port"] == "checked":
                        for host in loadgen_group["loadgens"]:
                            error_msg += thr.table_add("ingress.t_l1_forwarding", "ingress.send", matches=[host["p4_port"]], action_parameters=[dut["p4_port"]])
                        break

            if int(cfg['forwarding_mode']) >= 2:
                # MC l2 group
                print("set table entries for l2 forwarding")

                for loadgen_group in cfg["loadgen_groups"]:
                    for dut in cfg["dut_ports"]:
                        if int(dut["id"]) == int(loadgen_group["group"]) and dut["use_port"] == "checked":
                            error_msg += thr.table_add("ingress.t_l2_forwarding", "ingress.send_to_mc_grp", matches=[dut["p4_port"], "281474976710655"], action_parameters=[str(loadgen_group["group"])])
                            for host in loadgen_group["loadgens"]:
                                error_msg += thr.table_add("ingress.t_l2_forwarding", "ingress.send", matches=[dut["p4_port"], "0x" + host['loadgen_mac'].replace(":", "")], action_parameters=[host["p4_port"]])
                            break

            if cfg['forwarding_mode'] == "3":
                print("create table entries for l3 forwarding")
                # IPv4 forwarding
                for loadgen_group in cfg["loadgen_groups"]:
                    for dut in cfg["dut_ports"]:
                        if int(dut["id"]) == int(loadgen_group["group"]) and dut["use_port"] == "checked":
                            for host in loadgen_group["loadgens"]:
                                error_msg += thr.table_add("ingress.t_l3_forwarding", "ingress.send", matches=[dut["p4_port"], host["loadgen_ip"]], action_parameters=[host["p4_port"]])
                            break

            error_msg += thr.table_add("egress.broadcast_mac", "egress.change_mac", matches=[cfg["ext_host"]], action_parameters=["281474976710655"])  # 281474976710655 = 0xffffffffffff

            if cfg["stamp_tcp"] == "checked":
                offsets_start = ["5", "8"]
                offsets_end = ["9", "12"]
                for i in range(0, 2):
                    flow_direction = 0
                    # actually for multicast threshold each flow gets an own counter
                    # BUT now with multiple loadgens this is not possible anymore
                    # => count all as one flow for multicast threshold
                    for dut in cfg["dut_ports"]:
                        if dut["stamp_outgoing"] == "checked" and dut["use_port"] == "checked":
                            error_msg += thr.table_add("ingress.t_add_timestamp_header_tcp", "ingress.add_timestamp_header_tcp", matches=[offsets_start[i], dut["p4_port"]], action_parameters=[str(flow_direction)])
                    for p4_port_flow_dst in all_dut_dst_p4_ports:
                        error_msg += thr.table_add("ingress.t_timestamp2_tcp", "ingress.add_timestamp2", matches=[offsets_end[i], "3856", p4_port_flow_dst], action_parameters=[str(int(cfg["multicast"]) - 1), str(flow_direction)])

            for loadgen_group in cfg["loadgen_groups"]:
                for dut in cfg["dut_ports"]:
                    if int(dut["id"]) == int(loadgen_group["group"]) and dut["use_port"] == "checked":
                        if dut["stamp_outgoing"] == "checked" and cfg["ext_host"] != "":
                            for host in loadgen_group["loadgens"]:
                                error_msg += thr.table_add("ingress.t_multicast", "ingress.send_to_mc_grp", matches=[host["p4_port"]], action_parameters=[host["mcast_grp"]])

            ### UDP
            if cfg["stamp_udp"] == "checked":
                flow_direction = 0
                # actually for multicast threshold each flow gets an own counter
                # BUT now with multiple loadgens this is not possible anymore
                # => count all as one flow for multicast threshold
                for dut in cfg["dut_ports"]:
                    if dut["stamp_outgoing"] == "checked" and dut["use_port"] == "checked":
                        error_msg += thr.table_add("ingress.t_add_timestamp_header_udp", "ingress.add_timestamp_header_udp", matches=[dut["p4_port"]], action_parameters=[str(flow_direction)])
                for p4_port_flow_dst in all_dut_dst_p4_ports:
                    error_msg += thr.table_add("ingress.timestamp2_udp", "ingress.add_timestamp2", matches=["3856", p4_port_flow_dst], action_parameters=[str(int(cfg["multicast"]) - 1), str(flow_direction)])

            # workaround because if only count_stamped_egress() is called with if cond, it gets executed always ...
            error_msg += thr.table_add("egress.t_count_stamped_egress", "egress.count_stamped_egress", matches=["3856"])

        except:
            err = traceback.format_exc()
            print(err)
            error_msg += err

        finally:
            return error_msg

    def port_lists(self):
        temp = {"real_ports": [], "logical_ports": []}
        for i in range(0, 100):
            temp["real_ports"].append(str(i))
            temp["logical_ports"].append(str(i)) # = p4 ports
        return temp

    # deploy config file (table entries) again to p4 device (in case of changes)
    def deploy(self, cfg):
        error_msg = ""
        try:
            print("\n########## DEPLOY BMV2 ##########\n")
            print(cfg)
            error_msg = self.deploy_stamper_thrift(cfg)
            print("\n########## DEPLOY FINISHED ##########\n")
        except:
            err = traceback.format_exc()
            print(err)
            error_msg += str(err)
        finally:
            return error_msg

    def read_p4_device(self, cfg):
        thr = bmv2_thrift.Bmv2Thrift(cfg["p4_dev_ssh"], dir_path + "/data/" + cfg["program"] + ".json")

        def error_cfg():
            for key in ["total_deltas", "delta_counter", "min_delta", "max_delta"]:
                cfg[key] = -1
            for dut in cfg["dut_ports"]:
                if dut["use_port"] == "checked":
                    for direction in ["ingress", "egress", "ingress_stamped", "egress_stamped"]:
                        dut["num_" + direction + "_packets"] = dut["num_" + direction + "_bytes"] = -1

            for loadgen_grp in cfg["loadgen_groups"]:
                if loadgen_grp["use_group"] == "checked":
                    for host in loadgen_grp["loadgens"]:
                        for direction in ["ingress", "egress", "ingress_stamped", "egress_stamped"]:
                            host["num_" + direction + "_packets"] = host["num_" + direction + "_bytes"] = -1

        def read_counter_port(cfg, port_name, port):
            port = int(port)
            counter_results = thr.standard_client.bm_counter_read(0, "ingress.ingress_counter", port)
            cfg[port_name + "num_ingress_packets"] = counter_results.packets
            cfg[port_name + "num_ingress_bytes"] = counter_results.bytes

            counter_results = thr.standard_client.bm_counter_read(0, "ingress.ingress_stamped_counter", port)
            cfg[port_name + "num_ingress_stamped_packets"] = counter_results.packets
            cfg[port_name + "num_ingress_stamped_bytes"] = counter_results.bytes

            counter_results = thr.standard_client.bm_counter_read(0, "egress.egress_counter", port)
            cfg[port_name + "num_egress_packets"] = counter_results.packets
            cfg[port_name + "num_egress_bytes"] = counter_results.bytes

            counter_results = thr.standard_client.bm_counter_read(0, "egress.egress_stamped_counter", port)
            cfg[port_name + "num_egress_stamped_packets"] = counter_results.packets
            cfg[port_name + "num_egress_stamped_bytes"] = counter_results.bytes

        try:
            for dut in cfg["dut_ports"]:
                if dut["use_port"] == "checked":
                    read_counter_port(dut, "", dut["p4_port"])

            for loadgen_grp in cfg["loadgen_groups"]:
                if loadgen_grp["use_group"] == "checked":
                    for host in loadgen_grp["loadgens"]:
                        read_counter_port(host, "", host["p4_port"])

            read_counter_port(cfg, "ext_host_", cfg["ext_host"])

            time_average = thr.standard_client.bm_register_read_all(0, "ingress.time_average")
            cfg["total_deltas"] = time_average[0] * 1000  # bmv2 is in microseconds but nanoseconds are expected
            cfg["delta_counter"] = time_average[1]
            time_delta_min_max = thr.standard_client.bm_register_read_all(0, "ingress.time_delta_min_max")
            cfg["min_delta"] = time_delta_min_max[0] * 1000
            cfg["max_delta"] = time_delta_min_max[1] * 1000

            print("Read counter and registers finished.")

        except:
            print("\n######\nError in BMV2 read_p4_device")
            print(traceback.format_exc())
            error_cfg()
        print(cfg)
        return cfg

    def get_pid(self, cfg):
        lines = subprocess.run([self.realPath + "/scripts/mn_status.sh", cfg["p4_dev_user"], cfg["p4_dev_ssh"]], stdout=subprocess.PIPE).stdout.decode("utf-8").split("\n")
        print(self.realPath)
        print(lines)
        try:
            if int(lines[0]) > 0:
                pid = int(lines[0])
            else:
                pid = 0
        except:
            pid = 0
        return pid

    def p4_dev_status(self, cfg):
        pid = self.get_pid(cfg)
        print(pid)
        if pid > 0:
            dev_status = "Yes! PID: " + str(pid)
            running = True
            try:
                lines_pm = P4STA_utils.execute_ssh(cfg["p4_dev_user"], cfg["p4_dev_ssh"], "cat /home/" + cfg["p4_dev_user"] + "/p4sta/stamper/bmv2/data/mn.log")
            except:
                lines_pm = ["Error while reading mininet output"]
        else:
            dev_status = "not running"
            running = False
            lines_pm = ["No portmanager available",
                        "Are you sure you selected a target before?"]

        return lines_pm, running, dev_status

    # starts specific p4 software on device
    def start_p4_dev_software(self, cfg):
        try:
            input = "ip route get " + cfg["p4_dev_ssh"]
            output = subprocess.run(input, stdout=subprocess.PIPE, shell=True).stdout.decode("utf-8").replace("\n", "").split(" ")
            route_iface = output[output.index("dev")+1]
            # Assumes that all bmv2 management SSH IPs are in /24 subnet, should be 10.99.66.0/24
            ip_splitted = cfg["ext_host_ssh"].split(".")
            subprocess.run("sudo ip route add " + ".".join(ip_splitted[:3]) + ".0/24 via " + cfg["p4_dev_ssh"] + " dev " + route_iface, stdout=subprocess.PIPE, shell=True)
        except:
            print(traceback.format_exc())
            print("ERROR: Adding ip route to bmv2 server failed. Mininet hosts could not be reachable.")

        lines_check = P4STA_utils.execute_ssh(cfg["p4_dev_user"], cfg["p4_dev_ssh"], "cat " + cfg["bmv2_dir"] + "/LICENSE")
        if len(lines_check) > 100:
            subprocess.run([self.realPath + "/scripts/start_mininet.sh", "/home/"+cfg["p4_dev_user"]+"/p4sta/stamper/bmv2/scripts/netgen.py", cfg["p4_dev_user"], cfg["p4_dev_ssh"], project_path])
        else:
            print("BMV2 DIR NOT FOUND AT BMV2 TARGET: " + str(cfg["bmv2_dir"]))
            return "BMV2 DIR NOT FOUND AT BMV2 TARGET: " + str(cfg["bmv2_dir"])

    def stop_p4_dev_software(self, cfg):
        subprocess.run([self.realPath + "/scripts/stop_mininet.sh", cfg["p4_dev_user"], cfg["p4_dev_ssh"]])

    # reset registers of p4 device
    def reset_p4_registers(self, cfg):
        thr = bmv2_thrift.Bmv2Thrift(cfg["p4_dev_ssh"], dir_path + "/data/" + cfg["program"] + ".json")

        thr.standard_client.bm_counter_reset_all(0, "ingress.ingress_counter")
        thr.standard_client.bm_counter_reset_all(0, "ingress.ingress_stamped_counter")
        thr.standard_client.bm_counter_reset_all(0, "egress.egress_counter")
        thr.standard_client.bm_counter_reset_all(0, "egress.egress_stamped_counter")

        thr.standard_client.bm_register_reset(0, "ingress.time_average")
        thr.standard_client.bm_register_reset(0, "ingress.time_delta_min_max")

        print("Reset counters and registers finsihed")

    def check_if_p4_compiled(self, cfg):
        all_files = P4STA_utils.execute_ssh(cfg["p4_dev_user"], cfg["p4_dev_ssh"], "ls /home/" + cfg["p4_dev_user"] + "/p4sta/stamper/bmv2/data")
        found_jsons = []

        for item in all_files:
            if item.endswith("json") and item.find(cfg["program"]) > -1:
                found_jsons.append(item)
        if len(found_jsons) > 0:
            return True, "Found compiled " + " ".join(found_jsons) + " in /home/" + cfg["p4_dev_user"] + "/p4sta/stamper/bmv2/data"
        else:
            return False, "No compiled " + cfg["program"] + ".json found in /home/" + cfg["p4_dev_user"] + "/p4sta/stamper/bmv2/data"

    def get_server_install_script(self, user_name, ip, target_specific_dict={}):
        lst = []
        lst.append('echo "====================================="')
        lst.append('echo "Installing P4-BMv2 stamper target on '+ip+'"')
        lst.append('echo "====================================="')
        lst.append('if ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no '+user_name+'@'+ip+' "echo \'ssh to '+ip+' ***worked***\';"; [ $? -eq 255 ]; then')
        
        lst.append('  echo "====================================="')
        lst.append('  echo "\033[0;31m ERROR: Failed to connect to BMv2 server \033[0m"')
        lst.append('  echo "====================================="')

        lst.append('else')
        lst.append('  echo "START: Copying bmv2 files on remote server:"')
        
        lst.append('  cd '+ self.realPath)
        lst.append('  ssh  -o ConnectTimeout=2 -o StrictHostKeyChecking=no '+user_name+'@'+ip+' " mkdir -p /home/'+user_name+'/p4sta/stamper/bmv2;"')
        lst.append('  scp -r data/ ' + user_name + '@' + ip + ':/home/'+user_name+'/p4sta/stamper/bmv2/' )
        lst.append('  scp -r scripts/ ' + user_name + '@' + ip + ':/home/'+user_name+'/p4sta/stamper/bmv2/' )
        lst.append('  scp -r p4_src/ ' + user_name + '@' + ip + ':/home/'+user_name+'/p4sta/stamper/bmv2/' )
        lst.append('  echo "START: Setting up the required chmod rights at the machine, running bmv2:"')
        lst.append('  ssh -t -o ConnectTimeout=2 -o StrictHostKeyChecking=no '+user_name+'@'+ip+' "cd /home/'+user_name+'/p4sta/stamper/bmv2/scripts; chmod +x netgen.py return_ingress.py compile.sh install_bmv2.sh; ./install_bmv2.sh"') # start_mininet.sh stop_mininet.sh mn_status.sh
        lst.append('  ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no '+user_name+'@'+ip+' "sudo apt update; sudo apt install -y python-pip; pip install setproctitle"')
        lst.append('  echo "FINISHED setting up bmv2"')
        lst.append('  echo "====================================="')
        lst.append('  echo "\033[1;33m WARNING: BMv2 must be installed manually \033[0m"')
        lst.append('  echo "====================================="')

        lst.append('fi')
        return lst

    def stamper_status_overview(self, results, index, cfg):
        super(TargetImpl, self).stamper_status_overview(results, index, cfg)
        try:
            answer = P4STA_utils.execute_ssh(cfg["p4_dev_user"], cfg["p4_dev_ssh"], "cat /proc/sys/net/ipv4/ip_forward")
            if answer[0] == "0":
                results[index]["custom_checks"] = [[False, "IPv4 forwarding", "0 (disabled)"]]
            elif answer[0] == "1":
                results[index]["custom_checks"] = [[True, "IPv4 forwarding", "1 (enabled)"]]
            else:
                results[index]["custom_checks"] = [[False, "IPv4 forwarding", "error"]]
        except:
            print(traceback.format_exc())
