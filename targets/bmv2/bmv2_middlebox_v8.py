import os
import json
import sys
import time
import subprocess
dir_path = os.path.dirname(os.path.realpath(__file__))
project_path = dir_path[0:dir_path.find("/targets")]
sys.path.append(project_path + "/core/abstract_target")
from abstract_target import AbstractTarget


class TargetImpl(AbstractTarget):

    def __init__(self, target_cfg):
        super().__init__(target_cfg)
        self.speed_list = ["n/a"]

    # creates config file for p4 device
    def stamper_specific_config(self, cfg):
        f = open(self.realPath + "/data/commands1_middlebox1.txt", "w+")
        # delete old entries
        f.write("table_clear ingress.t_add_timestamp_header" + "\n")
        f.write("table_clear ingress.multicast" + "\n")
        f.write("table_clear ingress.t_l1_forwarding" + "\n")
        f.write("table_clear ingress.t_l2_forwarding" + "\n")
        f.write("table_clear ingress.t_l3_forwarding" + "\n")
        f.write("table_clear ingress.timestamp2" + "\n")
        f.write("table_clear egress.broadcast_mac" + "\n")
        f.write("table_clear ingress.t_add_timestamp_header_udp" + "\n")
        f.write("table_clear ingress.timestamp2_udp" + "\n")
        # delete old multicast groups (up to 10 groups)
        for group in range(1, 11):
            for node in range(0, 10):
                f.write("mc_node_dissociate " + str(group) + " " + str(node) + "\n")
        for node in range(0, 10):
            f.write("mc_node_destroy " + str(node) + "\n")
        for group in range(1, 11):
            f.write("mc_mgrp_destroy " + str(group) + "\n")

        node = 0
        # multicast grp for loadgen servers:
        f.write("mc_mgrp_create 1" + "\n")
        for server in cfg["loadgen_servers"]:
            f.write("mc_node_create " + str(node) + " " + server["p4_port"] + "\n")
            f.write("mc_node_associate 1 " + str(node) + "\n")
            node = node + 1

        # multicast grp for loadgen clients:
        f.write("mc_mgrp_create 2" + "\n")
        for client in cfg["loadgen_clients"]:
            f.write("mc_node_create " + str(node) + " " + client["p4_port"] + "\n")
            f.write("mc_node_associate 2 " + str(node) + "\n")
            node = node + 1

        # multicast groups for external host, because of bmv2 the original receiver needs to be included
        group = 3
        for host in cfg["loadgen_servers"] + cfg["loadgen_clients"]:
            host["mcast_grp"] = str(group)
            f.write("mc_mgrp_create " + str(group) + "\n")
            f.write("mc_node_create " + str(node) + " " + cfg["ext_host"] + "\n")
            f.write("mc_node_associate " + str(group) + " " + str(node) + "\n")
            node = node + 1
            f.write("mc_node_create " + str(node) + " " + host["p4_port"] + "\n")
            f.write("mc_node_associate " + str(group) + " " + str(node) + "\n")
            node = node + 1
            group = group + 1

        if cfg['forwarding_mode'] == "1":
            server = cfg["loadgen_servers"][0]
            client = cfg["loadgen_clients"][0]
            f.write(
                "table_add ingress.t_l1_forwarding ingress.send " + cfg["dut1"] + " => " + server[
                    "p4_port"] + "\n")
            f.write(
                "table_add ingress.t_l1_forwarding ingress.send " + cfg["dut2"] + " => " + client[
                    "p4_port"] + "\n")
        else:
            f.write("table_add ingress.t_l1_forwarding ingress.no_op " + cfg["dut1"] + " =>\n")
            f.write("table_add ingress.t_l1_forwarding ingress.no_op " + cfg["dut2"] + " =>\n")

        f.write("table_add ingress.t_l1_forwarding ingress.no_op " + cfg["ext_host"] + " =>\n")

        for server in cfg["loadgen_servers"]:
            f.write("table_add ingress.t_l1_forwarding ingress.send " + server["p4_port"] + " => " + cfg["dut1"] + "\n")
        for client in cfg["loadgen_clients"]:
            f.write("table_add ingress.t_l1_forwarding ingress.send " + client["p4_port"] + " => " + cfg["dut2"] + "\n")

        if int(cfg['forwarding_mode']) >= 2:
            # MC l2 group
            print("create table entries for l2 forwarding")
            f.write("table_add ingress.t_l2_forwarding ingress.send_to_mc_grp " + cfg["dut1"] + " 0xffffffffffff => 1\n")
            f.write("table_add ingress.t_l2_forwarding ingress.send_to_mc_grp " + cfg["dut2"] + " 0xffffffffffff => 2\n")

            for server in cfg["loadgen_servers"]:
                f.write("table_add ingress.t_l2_forwarding ingress.send " + cfg["dut1"] + " 0x" +
                        server['loadgen_mac'].replace(":", "") + " => " + server["p4_port"] + "\n")

            for client in cfg["loadgen_clients"]:
                f.write("table_add ingress.t_l2_forwarding ingress.send " + cfg["dut2"] + " 0x" +
                        client['loadgen_mac'].replace(":", "") + " => " + client["p4_port"] + "\n")

        if cfg['forwarding_mode'] == "3":
            print("create table entries for l3 forwarding")
            # IPv4 forwarding
            for server in cfg["loadgen_servers"]:
                f.write("table_add ingress.t_l3_forwarding ingress.send " + cfg["dut1"] + " " + server["loadgen_ip"] + " => " + server["p4_port"] + "\n")

            for client in cfg["loadgen_clients"]:
                f.write("table_add ingress.t_l3_forwarding ingress.send " + cfg["dut2"] + " " + client["loadgen_ip"] + " => " + client["p4_port"] + "\n")

        f.write("table_add egress.broadcast_mac egress.change_mac " + cfg["ext_host"] + " => 0xffffffffffff" + "\n")

        if cfg["stamp_tcp"] == "checked":
            offsets_start = ["0x5", "0x8"]
            offsets_end = ["0x9", "0xc"]
            for i in range(0, 2):
                if cfg["dut_1_duplicate"] == "checked":
                    f.write("table_add ingress.t_add_timestamp_header ingress.add_timestamp_header " + offsets_start[i] + " " + cfg["dut2"] + " => " + offsets_end[i] + " 0\n")
                    f.write("table_add ingress.timestamp2 ingress.add_timestamp2 " + offsets_end[i] + " 0x0f10 " + cfg["dut1"] + " => " + hex(int(cfg["multicast"]) - 1) + " 0\n") # multicast -1 because it begins at 0

                if cfg["dut_2_duplicate"] == "checked":
                    f.write("table_add ingress.t_add_timestamp_header ingress.add_timestamp_header " + offsets_start[i] + " " + cfg["dut1"] + " => " + offsets_end[i] + " 1\n")
                    f.write("table_add ingress.timestamp2 ingress.add_timestamp2 " + offsets_end[i] + " 0x0f10 " + cfg["dut2"] + " => " + hex(int(cfg["multicast"]) - 1) + " 1\n")

        if cfg["dut_1_duplicate"] == "checked" and cfg["ext_host"] != "":
            for server in cfg["loadgen_servers"]:
                f.write("table_add ingress.multicast ingress.send_to_mc_grp " + cfg["dut1"] + " " + server["p4_port"] + " => " + server["mcast_grp"] + "\n")

        if cfg["dut_2_duplicate"] == "checked" and cfg["ext_host"] != "":
            for client in cfg["loadgen_clients"]:
                f.write("table_add ingress.multicast ingress.send_to_mc_grp "  + cfg["dut2"] + " " + client["p4_port"] + " => " + client["mcast_grp"] + "\n")

        ### UDP
        if cfg["stamp_udp"] == "checked":
            if cfg["dut_1_duplicate"] == "checked":
                f.write("table_add ingress.t_add_timestamp_header_udp ingress.add_timestamp_header_udp " + cfg["dut2"] + " => " + " 0\n")
                f.write("table_add ingress.timestamp2_udp ingress.add_timestamp2 0x0f10 " + cfg["dut1"] + " => " + hex(int(cfg["multicast"]) - 1) + " 0\n")  # multicast -1 because it begins at 0

            if cfg["dut_2_duplicate"] == "checked":
                f.write("table_add ingress.t_add_timestamp_header_udp ingress.add_timestamp_header_udp " + cfg["dut1"] + " => " + " 1\n")
                f.write("table_add ingress.timestamp2_udp ingress.add_timestamp2 0x0f10 " + cfg["dut2"] + " => " + hex(int(cfg["multicast"]) - 1) + " 1\n")  # multicast -1 because it begins at 0

        f.close()


    # returns a dict["real_ports"] and ["logical_ports"]
    def port_lists(self):
        temp = {"real_ports": [], "logical_ports": []}
        for i in range(0, 100):
            temp["real_ports"].append(str(i))
            temp["logical_ports"].append(str(i)) # = p4 ports
        return temp

    # deploy config file (table entries) again to p4 device (in case of changes)
    def deploy(self, cfg):
        self.stamper_specific_config()
        lag = "SimplePreLAG"
        cli = cfg["bmv2_dir"] + "/tools/runtime_CLI.py"
        json_path = self.realPath + "/data/" + cfg["program"] + ".json"
        cmd = [cli, "--pre", lag, "--json", json_path, "--thrift-port", str(22223)]
        with open(self.realPath + "/data/commands1_middlebox1.txt", "r") as f:
            try:
                output = subprocess.check_output(cmd, stdin=f)
            except subprocess.CalledProcessError as e:
                print (e)

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
            print (e)
            error_cfg()

        return cfg

    def get_pid(self):
        lines = subprocess.run([self.realPath + "/scripts/mn_status.sh"], stdout=subprocess.PIPE).stdout.decode("utf-8").split("\n")
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
                    lines_pm = ["There is no need to deploy the current config explicitly.",
                                "The settings were applied at the start of mininet.",
                                "Mininet link and port configuration: "]
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
        pid = self.get_pid()
        if pid > 0:
            subprocess.run([self.realPath + "/scripts/stop_mininet.sh"])

    # reset registers of p4 device
    def reset_p4_registers(self, cfg):
        cli_input = "register_reset ingress.time_average\nregister_reset ingress.time_delta_min_max\n"
        cli_input += "counter_reset egress.egress_counter\ncounter_reset ingress.ingress_counter"
        cli_input += "counter_reset egress.egress_stamped_counter\ncounter_reset ingress.ingress_stamped_counter\n"
        cmd = [cfg["bmv2_dir"] + "/targets/simple_switch/sswitch_CLI.py", "--thrift-port", "22223"]

        output = subprocess.run(cmd, stdout=subprocess.PIPE, input=cli_input.encode()).stdout.decode('UTF-8')

    def check_if_p4_compiled(self, cfg):
        return True if self.get_pid() > 0 else False, "If BMV2 is running, the selected program " + str(cfg["program"]) + " is compiled."