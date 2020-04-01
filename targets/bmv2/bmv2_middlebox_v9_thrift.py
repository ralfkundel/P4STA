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
import json
import sys
import time
import traceback
import subprocess
dir_path = os.path.dirname(os.path.realpath(__file__))
project_path = dir_path[0:dir_path.find("/targets")]
from abstract_target import AbstractTarget

print(os.path.dirname(os.path.abspath(__file__)))

sys.path.append(dir_path + "/thrift")
import bmv2_thrift_py3 as bmv2_thrift


class TargetImpl(AbstractTarget):

    def __init__(self, target_cfg):
        super().__init__(target_cfg)
        self.speed_list = ["n/a"]

    def deploy_stamper_thrift(self, cfg):
        error_msg = ""
        try:
            thr = bmv2_thrift.Bmv2Thrift(dir_path + "/data/" + cfg["program"] + ".json")

            thr.clear_all_tables()
            thr.clear_all_mcast_grps()
            print("All tables and mcast groups cleared.")
            # multicast grp for loadgen servers:
            group_hdl = thr.create_mcast_grp(1)
            node = 0
            for server in cfg["loadgen_servers"]:
                thr.create_mc_node(node, server["p4_port"])
                thr.associate_mc_node(group_hdl, node)
                node = node + 1

            # multicast grp for loadgen clients:
            group_hdl = thr.create_mcast_grp(2)
            for client in cfg["loadgen_clients"]:
                thr.create_mc_node(node, client["p4_port"])
                thr.associate_mc_node(group_hdl, node)
                node = node + 1

            # multicast groups for external host, because of bmv2 the original receiver needs to be included
            group = 3
            for host in cfg["loadgen_servers"] + cfg["loadgen_clients"]:
                host["mcast_grp"] = str(group)
                group_hdl = thr.create_mcast_grp(group)
                thr.create_mc_node(node, cfg["ext_host"])
                thr.associate_mc_node(group_hdl, node)
                node = node + 1
                thr.create_mc_node(node, host["p4_port"])
                thr.associate_mc_node(group_hdl, node)
                node = node + 1
                group = group + 1

            if cfg["dut_2_use_port"] == "unchecked":
                # create one group with all loadgens for ARP in case of one DUT port only
                group_hdl = thr.create_mcast_grp(99)
                for host in cfg["loadgen_servers"] + cfg["loadgen_clients"]:
                    thr.create_mc_node(node, host["p4_port"])
                    thr.associate_mc_node(group_hdl, node)
                    node = node + 1

            if cfg['forwarding_mode'] == "1":
                server = cfg["loadgen_servers"][0]
                client = cfg["loadgen_clients"][0]
                error_msg += thr.table_add("ingress.t_l1_forwarding", "ingress.send", matches=[cfg["dut1"]], action_parameters=[server["p4_port"]])
                error_msg += thr.table_add("ingress.t_l1_forwarding", "ingress.send", matches=[cfg["dut2"]], action_parameters=[client["p4_port"]])

            else:
                error_msg += thr.table_add("ingress.t_l1_forwarding", "ingress.no_op", matches=[cfg["dut1"]])
                if cfg["dut_2_use_port"] == "checked":
                    error_msg += thr.table_add("ingress.t_l1_forwarding", "ingress.no_op", matches=[cfg["dut2"]])

            error_msg += thr.table_add("ingress.t_l1_forwarding", "ingress.no_op", matches=[cfg["ext_host"]])

            for server in cfg["loadgen_servers"]:
                error_msg += thr.table_add("ingress.t_l1_forwarding", "ingress.send", matches=[server["p4_port"]], action_parameters=[cfg["dut1"]])

            for client in cfg["loadgen_clients"]:
                error_msg += thr.table_add("ingress.t_l1_forwarding", "ingress.send", matches=[client["p4_port"]], action_parameters=[cfg["dut2"]])

            if int(cfg['forwarding_mode']) >= 2:
                # MC l2 group
                print("set table entries for l2 forwarding")
                if cfg["dut_2_use_port"] == "checked":
                    error_msg += thr.table_add("ingress.t_l2_forwarding", "ingress.send_to_mc_grp", matches=[cfg["dut1"], "281474976710655"], action_parameters=["1"])
                    error_msg += thr.table_add("ingress.t_l2_forwarding", "ingress.send_to_mc_grp", matches=[cfg["dut2"], "281474976710655"], action_parameters=["2"])
                else:
                    error_msg += thr.table_add("ingress.t_l2_forwarding", "ingress.send_to_mc_grp", matches=[cfg["dut1"], "281474976710655"], action_parameters=["99"])

                for server in cfg["loadgen_servers"]:
                    error_msg += thr.table_add("ingress.t_l2_forwarding", "ingress.send", matches=[cfg["dut1"], "0x" + server['loadgen_mac'].replace(":", "")], action_parameters=[server["p4_port"]])

                for client in cfg["loadgen_clients"]:
                    error_msg += thr.table_add("ingress.t_l2_forwarding", "ingress.send", matches=[cfg["dut2"], "0x" + client['loadgen_mac'].replace(":", "")], action_parameters=[client["p4_port"]])

            if cfg['forwarding_mode'] == "3":
                print("create table entries for l3 forwarding")
                # IPv4 forwarding
                for server in cfg["loadgen_servers"]:
                    error_msg += thr.table_add("ingress.t_l3_forwarding", "ingress.send", matches=[cfg["dut1"], server["loadgen_ip"]], action_parameters=[server["p4_port"]])

                for client in cfg["loadgen_clients"]:
                    error_msg += thr.table_add("ingress.t_l3_forwarding", "ingress.send", matches=[cfg["dut2"], client["loadgen_ip"]], action_parameters=[client["p4_port"]])

            error_msg += thr.table_add("egress.broadcast_mac", "egress.change_mac", matches=[cfg["ext_host"]], action_parameters=["281474976710655"])  # int(0xffffffffffff, 16) = 281474976710655

            if cfg["stamp_tcp"] == "checked":
                offsets_start = ["5", "8"]
                offsets_end = ["9", "12"]
                for i in range(0, 2):
                    if cfg["dut_1_outgoing_stamp"] == "checked":
                        error_msg += thr.table_add("ingress.t_add_timestamp_header_tcp", "ingress.add_timestamp_header_tcp", matches=[offsets_start[i], cfg["dut1"]], action_parameters=["0"])
                        error_msg += thr.table_add("ingress.t_timestamp2_tcp", "ingress.add_timestamp2", matches=[offsets_end[i], "3856", cfg["dut2"]], action_parameters=[str(int(cfg["multicast"]) - 1), "0"])

                    if cfg["dut_2_outgoing_stamp"] == "checked":
                        error_msg += thr.table_add("ingress.t_add_timestamp_header_tcp", "ingress.add_timestamp_header_tcp", matches=[offsets_start[i], cfg["dut2"]], action_parameters=["1"])
                        error_msg += thr.table_add("ingress.t_timestamp2_tcp", "ingress.add_timestamp2", matches=[offsets_end[i], "3856", cfg["dut1"]], action_parameters=[str(int(cfg["multicast"]) - 1), "1"])

            if cfg["dut_1_outgoing_stamp"] == "checked" and cfg["ext_host"] != "":
                for client in cfg["loadgen_clients"]:
                    error_msg += thr.table_add("ingress.t_multicast", "ingress.send_to_mc_grp", matches=[client["p4_port"]], action_parameters=[client["mcast_grp"]])

            if cfg["dut_2_outgoing_stamp"] == "checked" and cfg["ext_host"] != "":
                for server in cfg["loadgen_servers"]:
                    error_msg += thr.table_add("ingress.t_multicast", "ingress.send_to_mc_grp", matches=[server["p4_port"]], action_parameters=[server["mcast_grp"]])

            ### UDP
            if cfg["stamp_udp"] == "checked":
                if cfg["dut_1_outgoing_stamp"] == "checked":
                    error_msg += thr.table_add("ingress.t_add_timestamp_header_udp", "ingress.add_timestamp_header_udp", matches=[cfg["dut1"]], action_parameters=["0"])
                    error_msg += thr.table_add("ingress.timestamp2_udp", "ingress.add_timestamp2", matches=["3856", cfg["dut2"]], action_parameters=[str(int(cfg["multicast"]) - 1), "0"])

                if cfg["dut_2_outgoing_stamp"] == "checked":
                    error_msg += thr.table_add("ingress.t_add_timestamp_header_udp", "ingress.add_timestamp_header_udp", matches=[cfg["dut2"]], action_parameters=["1"])
                    error_msg += thr.table_add("ingress.timestamp2_udp", "ingress.add_timestamp2", matches=["3856", cfg["dut1"]], action_parameters=[str(int(cfg["multicast"]) - 1), "2"])
            # workaround because if only count_stamped_egress() is called with if cond, it gets executed always ...
            error_msg += thr.table_add("egress.t_count_stamped_egress", "egress.count_stamped_egress", matches=["3856"])

        except:
            err = traceback.format_exc()
            print(err)
            error_msg += traceback.format_exc()

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
            error_msg = self.deploy_stamper_thrift(cfg)
            print("\n########## DEPLOY FINISHED ##########\n")
        except:
            error_msg += print(traceback.format_exc())
        finally:
            return error_msg

    # if not overwritten = everything is zero
    def read_p4_device(self, cfg):
        def error_cfg():
            for key in ["total_deltas", "delta_counter", "min_delta", "max_delta"]:
                cfg[key] = -1
            for key in ["dut1", "dut2", "ext_host"]:
                for direction in ["ingress", "egress"]:
                    cfg[key + "_num_" + direction + "_packets"] = cfg[key + "_num_" + direction + "_bytes"] = -1
            for host in (cfg["loadgen_servers"] + cfg["loadgen_clients"]):
                for direction in ["ingress", "egress"]:
                    host["num_" + direction + "_packets"] = host["num_" + direction + "_bytes"] = -1
            cfg["dut2_num_egress_stamped_packets"] = cfg["dut2_num_egress_stamped_bytes"] = cfg["dut1_num_ingress_stamped_packets"] = cfg["dut1_num_ingress_stamped_bytes"] = cfg["dut1_num_egress_stamped_packets"] = cfg["dut1_num_egress_stamped_bytes"] = cfg["dut2_num_ingress_stamped_packets"] = cfg["dut2_num_ingress_stamped_bytes"] = 0

        # generating the input for the bmv2 cli
        in_c = "counter_read ingress.ingress_counter "
        in_stamped_c = "counter_read ingress.ingress_stamped_counter "
        out_c = "counter_read egress.egress_counter "
        out_stamped_c = "counter_read egress.egress_stamped_counter "
        cli_input = "register_read ingress.time_average 0\nregister_read ingress.time_average 1\nregister_read ingress.time_delta_min_max 0\nregister_read ingress.time_delta_min_max 1\n"
        for host in ["dut1", "dut2", "ext_host"]:
            cli_input = cli_input + in_c + cfg[host] + "\n"
            cli_input = cli_input + out_c + cfg[host] + "\n"
            cli_input = cli_input + in_stamped_c + cfg[host] + "\n"
            cli_input = cli_input + out_stamped_c + cfg[host] + "\n"

        for host in (cfg["loadgen_servers"] + cfg["loadgen_clients"]):
            cli_input = cli_input + in_c + host["p4_port"] + "\n"
            cli_input = cli_input + out_c + host["p4_port"] + "\n"
            cli_input = cli_input + in_stamped_c + host["p4_port"] + "\n"
            cli_input = cli_input + out_stamped_c + host["p4_port"] + "\n"

        try:
            cmd = [cfg["bmv2_dir"] + "/targets/simple_switch/sswitch_CLI.py", "--thrift-port", "22223"]
            output = subprocess.run(cmd, stdout=subprocess.PIPE, input=cli_input.encode()).stdout.decode('UTF-8')
            lines = output.split("\n")
            for line in lines:
                print(line)

            if len(lines) > 10: # make sure there is no error, if it's not greater than 10 lines; else bmv2 not running
                # parsing output of bmv2 CLI
                start = 0
                for line in lines:
                    start = start + 1
                    if line.find("Control utility for runtime P4 table manipulation") > -1:
                        break

                cfg["total_deltas"] = int(lines[start][lines[start].find("[0]=")+5:])*1000 # because bmv2 is in microseconds but nanoseconds are expected
                cfg["delta_counter"] = int(lines[start+1][lines[start+1].find("[1]=") + 5:])
                cfg["min_delta"] = int(lines[start+2][lines[start+2].find("[0]=") + 5:])*1000
                cfg["max_delta"] = int(lines[start+3][lines[start+3].find("[1]=") + 5:])*1000
                counter = start+4
                for key in ["dut1", "dut2", "ext_host"]:
                    for direction in ["ingress", "egress", "ingress_stamped", "egress_stamped"]:
                        cfg[key+"_num_"+direction+"_packets"] = int(lines[counter][lines[counter].find("packets=")+8:lines[counter].find(",")])
                        cfg[key+"_num_"+direction+"_bytes"] = int(lines[counter][lines[counter].find("bytes=")+6:-1])
                        counter = counter + 1
                for host in (cfg["loadgen_servers"] + cfg["loadgen_clients"]):
                    for direction in ["ingress", "egress", "ingress_stamped", "egress_stamped"]:
                        host["num_"+direction+"_packets"] = int(lines[counter][lines[counter].find("packets=")+8:lines[counter].find(",")])
                        host["num_"+direction+"_bytes"] = int(lines[counter][lines[counter].find("bytes=")+6:-1])
                        counter = counter + 1

            else: # if an error occurs set everything to -1
                print("Error in BMV2 read_p4_device. Sure the mininet/bmv2 instance is running?")
                error_cfg()

        except subprocess.CalledProcessError as e:
            print("Error in BMV2 read_p4_device")
            print(e)
            error_cfg()

        return cfg

    def get_pid(self):
        lines = subprocess.run([self.realPath + "/scripts/mn_status.sh"], stdout=subprocess.PIPE).stdout.decode("utf-8").split("\n")
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
        pid = self.get_pid()
        print(pid)
        if pid > 0:
            dev_status = "Yes! PID: " + str(pid)
            running = True
            try:
                with open(self.realPath + "/data/mn.log", "r") as log:
                    lines_pm = ["Mininet link and port configuration: "]
                    for line in log.readlines():
                        lines_pm.append(line)
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
        subprocess.run([self.realPath + "/scripts/start_mininet.sh", self.realPath + "/scripts/netgen.py", cfg["bmv2_dir"]])

    def stop_p4_dev_software(self, cfg):
        subprocess.run([self.realPath + "/scripts/stop_mininet.sh"])

    # reset registers of p4 device
    def reset_p4_registers(self, cfg):
        cli_input = "register_reset ingress.time_average\nregister_reset ingress.time_delta_min_max\n"
        cli_input += "counter_reset egress.egress_counter\ncounter_reset ingress.ingress_counter\n"
        cli_input += "counter_reset egress.egress_stamped_counter\ncounter_reset ingress.ingress_stamped_counter\n"
        cmd = [cfg["bmv2_dir"] + "/targets/simple_switch/sswitch_CLI.py", "--thrift-port", "22223"]

        output = subprocess.run(cmd, stdout=subprocess.PIPE, input=cli_input.encode()).stdout.decode('UTF-8')
