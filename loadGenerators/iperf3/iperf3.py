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
import copy
import json
import numpy as np
import os
import re
import subprocess
import sys
import threading
import time
import traceback

from abstract_loadgenerator import AbstractLoadgenerator

import P4STA_utils

dir_path = os.path.dirname(os.path.realpath(__file__))


class LoadGeneratorImpl(AbstractLoadgenerator):
    def __init__(self, loadgen_cfg):
        super().__init__(loadgen_cfg)
        self.directory = os.path.dirname(os.path.realpath(__file__))

    def get_name(self):
        return "iPerf3"

    def run_loadgens(self, file_id, duration, l4_selected, packet_size_mtu,
                     results_path, loadgen_rate_limit, loadgen_flows,
                     loadgen_server_groups):
        self.cfg = P4STA_utils.read_current_cfg()
        loadgen_flows = int(loadgen_flows)

        def check_ns(host):
            if "namespace_id" in host:
                return "sudo ip netns exec " + str(host["namespace_id"])
            else:
                return ""

        def thread_join(thrs):
            for thread in thrs:
                thread.start()
            for thread in thrs:
                thread.join()

        def check_iperf_server(server_ssh_user, server_ip, start_port,
                               ns_option):
            # ssh into server and check locally if port is open
            def check_port_open(server_ssh_user, server_ip, port, ns_option):
                answer_list = P4STA_utils.execute_ssh(
                    server_ssh_user, server_ip,
                    str(ns_option) + " if lsof -Pi :" + str(port) +
                    " -sTCP:LISTEN -t >/dev/null; then echo running; fi " +
                    ns_option_end)
                return "running" in answer_list

            def check_thrd(server_ssh_user, server_ip, port, ns_option):
                print_str = "check iPerf3 Server Port " + str(
                    port) + " at " + server["ssh_ip"] + \
                            " with Namespace " + ns_option + " => "
                time.sleep(0.5)
                if not check_port_open(server_ssh_user, server_ip,
                                       port, ns_option):
                    time.sleep(1.5)
                    if not check_port_open(server_ssh_user, server_ip,
                                           port, ns_option):
                        print_str += "[fail]"
                        raise Exception("iPerf3 Server Port " + str(
                            port) + " at " + server[
                                            "ssh_ip"] + " not open.")
                    else:
                        print_str += "[ok]"
                        print(print_str)
                else:
                    print_str += "[ok]"
                    print(print_str)

            ns_option_end = ""
            if ns_option != "":
                ns_option = ns_option + " bash -c '"
                ns_option_end = "'"

            thrds = []
            for add in range(loadgen_flows):
                x = threading.Thread(target=check_thrd, args=(
                    server_ssh_user, server_ip, start_port + add, ns_option))
                thrds.append(x)
            thread_join(thrds)

        # iperf -s threads at one (!) host
        def start_servers(ssh_user, ssh_ip, start_port, flows, ns_option,
                          server_dict):
            def start_server(ssh_user, ssh_ip, start_port, ns_option):
                P4STA_utils.execute_ssh(ssh_user, ssh_ip, str(
                    ns_option) + " iperf3 -s -p " + str(start_port))

            port = int(start_port)
            for fl in range(flows):
                print("iperf3 server flow " + str(fl) + " start at " + str(
                    ssh_ip) + " port " + str(port) + " with NS option " + str(
                    ns_option))
                server_dict["open_iperf_ports"].append(port)
                thread = threading.Thread(target=start_server, args=(
                    ssh_user, ssh_ip, port, ns_option))
                thread.start()
                port = port + 1

        def stop_all_servers(servers):
            for server in servers:
                # no need to define namespace because
                # sudo pkill kills all processes running on host
                print(
                    "Trying to stop all iPerf3 instances at server " + server[
                        "ssh_ip"])
                P4STA_utils.execute_ssh(server["ssh_user"], server["ssh_ip"],
                                        "sudo pkill iperf3")

        # iperf -c threads at one (!) host
        def start_clients(ssh_user, ssh_ip, dst_ip, start_port, flows,
                          ns_option, duration, flag, start_json_id):
            def start_client(ssh_user, ssh_ip, dst_ip, port, ns_option,
                             duration, json_id, flag):
                exec = str(ns_option) + " iperf3 -c " + str(
                    dst_ip) + " -T s" + str(json_id) + " -p " + str(
                    port) + " " + flag + " -J --logfile s" + str(
                    json_id) + ".json -t " + str(duration)
                print(exec)
                P4STA_utils.execute_ssh(ssh_user, ssh_ip, exec)

            threads = []
            port = int(start_port)
            json_id = int(start_json_id)
            for fl in range(flows):
                print("iperf3 client " + str(fl) + " start at " + str(
                    ssh_ip) + " connect to " + str(dst_ip) + " port " + str(
                    port) + " with NS option " + str(ns_option))
                thread = threading.Thread(target=start_client, args=(
                    ssh_user, ssh_ip, dst_ip, port, ns_option,
                    duration, json_id, flag))
                threads.append(thread)
                port = port + 1
                json_id = json_id + 1
            thread_join(threads)

        # [1,2,3,4,5,6,7...] with y = 3 => 1,2,3,1,2,3,1,2,3
        def custom_modulo(x, y):
            if x % y == 0:
                return y
            else:
                return x % y

        # first kill all running iperf instances
        for loadgen_grp in self.cfg["loadgen_groups"]:
            if loadgen_grp["use_group"] == "checked":
                stop_all_servers(loadgen_grp["loadgens"])

        iperf_server_groups = []
        iperf_client_groups = []
        for loadgen_grp in self.cfg["loadgen_groups"]:
            if loadgen_grp["use_group"] == "checked":
                if loadgen_grp["group"] in loadgen_server_groups:
                    iperf_server_groups.append(loadgen_grp)
                else:
                    iperf_client_groups.append(loadgen_grp)

        num_clients = sum([len(x["loadgens"]) for x in iperf_client_groups])
        print("num_clients")
        print(num_clients)

        if loadgen_rate_limit > 0 and num_clients > 0:
            limit_per_host_in_bit_s = int(
                (loadgen_rate_limit * 1000000) / (loadgen_flows * num_clients))
            limit_str = "-b " + str(limit_per_host_in_bit_s)
        elif loadgen_rate_limit > 0 and num_clients == 0:
            limit_str = "-b " + str(
                int((loadgen_rate_limit * 1000000) / loadgen_flows))
        else:
            limit_str = ""

        if l4_selected == "tcp":
            # normally MSS = MTU - 40 here - 16 because 16 byte tstamps added
            mss = int(packet_size_mtu) - 56
            flag = "-M " + str(mss)
            flag = flag + " " + limit_str
        else:
            # timestamps in payload! no need for extra 16 byte space
            mss = int(packet_size_mtu) - 40
            if limit_str == "":
                flag = "-u -b 100G --length " + str(
                    mss)  # 100G option allows to use maximum speed
            else:
                flag = "-u " + limit_str + "--length " + str(mss)
        print("iperf flags: " + flag)

        # case where only one group and one DUT port is used
        if len(iperf_client_groups) == 0 and len(iperf_server_groups) == 1:
            iperf_client_groups = copy.deepcopy(iperf_server_groups)
            # move first entry to end
            first_loadgen = iperf_client_groups[0]["loadgens"][0]
            del (iperf_client_groups[0]["loadgens"][0])
            iperf_client_groups[0]["loadgens"].append(first_loadgen)
            counter = 1
            for client in iperf_client_groups[0]["loadgens"]:
                client["id"] = counter
                counter += 1
            num_clients = 1
            print("num_clients updated because only one loadgen group is used")
            print(num_clients)

        # case where all groups are servers
        elif len(iperf_client_groups) == 0 and len(iperf_server_groups) == len(
                self.cfg["loadgen_groups"]):
            iperf_client_groups = copy.deepcopy(iperf_server_groups)
            first_group = iperf_client_groups[0]
            del (iperf_client_groups[0])
            iperf_client_groups.append(first_group)
            counter = 1
            for client_grp in iperf_client_groups:
                client_grp["group"] = counter
                counter = counter + 1

        for server_group in iperf_server_groups:
            for server in server_group["loadgens"]:
                server["open_iperf_ports"] = []

        start_port = 5101
        for server_group in iperf_server_groups:
            for server in server_group["loadgens"]:
                for i in range(num_clients):
                    start_servers(server["ssh_user"], server["ssh_ip"],
                                  str(start_port), loadgen_flows,
                                  check_ns(server), server_dict=server)
                    start_port = start_port + loadgen_flows

        start_port = 5101
        check_threads = list()
        for server_group in iperf_server_groups:
            for server in server_group["loadgens"]:
                for i in range(num_clients):

                    x = threading.Thread(target=check_iperf_server,
                                         args=(server["ssh_user"],
                                               server["ssh_ip"],
                                               start_port,
                                               check_ns(server)))
                    check_threads.append(x)

                    start_port = start_port + loadgen_flows
        thread_join(check_threads)

        print("iperf server groups")
        print(iperf_server_groups)
        print("iperf client groups")
        print(iperf_client_groups)

        threads = list()
        json_id = 1
        for client_group in iperf_client_groups:
            for client in client_group["loadgens"]:
                client["num_started_flows"] = 0
                for server_group in iperf_server_groups:
                    for server in server_group["loadgens"]:
                        start_client = False
                        do_break = False
                        # if more clients in client grp than server grp connect
                        # remaining clients to first servers again
                        if len(client_group["loadgens"]) >= len(
                                server_group["loadgens"]):
                            c_mod = custom_modulo(
                                client["id"], len(server_group["loadgens"]))
                            if server["id"] == c_mod \
                                    and client["loadgen_ip"] != \
                                    server["loadgen_ip"]:
                                start_client = True
                                do_break = True
                        else:
                            c_mod = custom_modulo(server["id"], len(
                                    client_group["loadgens"]))

                            if client["id"] == c_mod \
                                    and client["loadgen_ip"] != \
                                    server["loadgen_ip"]:
                                start_client = True
                                do_break = False

                        if start_client:
                            if len(server["open_iperf_ports"]) > 0:
                                start_port = server["open_iperf_ports"][0]
                                for i in range(loadgen_flows):
                                    if start_port + i \
                                            in server["open_iperf_ports"]:
                                        server["open_iperf_ports"].remove(
                                            start_port + i)
                                print("select port range starting at " + str(
                                    start_port) + " to connect from " + client[
                                          "loadgen_ip"] + " to " + server[
                                          "loadgen_ip"])
                                x = threading.Thread(target=start_clients,
                                                     args=(client["ssh_user"],
                                                           client["ssh_ip"],
                                                           server[
                                                               "loadgen_ip"],
                                                           start_port,
                                                           loadgen_flows,
                                                           check_ns(client),
                                                           duration, flag,
                                                           json_id))
                                threads.append(x)
                                json_id = json_id + loadgen_flows
                                client["num_started_flows"] = \
                                    client["num_started_flows"] + loadgen_flows
                                if do_break:
                                    break
                            else:
                                print(
                                    "No available port found in server dict: "
                                    + str(server) + " from server group id "
                                    + str(server_group["group"]))

        thread_join(threads)

        # get jsons from clients
        json_id = 1
        for client_grp in iperf_client_groups:
            for client in client_grp["loadgens"]:
                for f in range(client["num_started_flows"]):
                    exc = "scp " + client["ssh_user"] + "@" + client[
                        "ssh_ip"] + ":s" + str(
                        json_id + f) + ".json " + results_path + "/iperf3_s" \
                          + str(json_id + f) + "_" + str(file_id) + ".json"
                    print(exc)
                    subprocess.run(exc, shell=True)
                json_id = json_id + client["num_started_flows"]

        # delete in second loop because
        # e.g. in case of docker one rm -f deletes all jsons for all clients
        for client_grp in iperf_client_groups:
            for client in client_grp["loadgens"]:
                P4STA_utils.execute_ssh(client["ssh_user"], client["ssh_ip"],
                                        "rm -f s*.json")

        for server_group in iperf_server_groups:
            stop_all_servers(server_group["loadgens"])

    # reads the iperf3 results and combine them into one result and into graphs
    def process_loadgen_data(self, file_id, results_path):
        min_rtt_list = []
        max_rtt_list = []
        total_interval_mbits = []
        total_interval_rtt = []
        total_interval_pl = []  # pl => packetloss
        total_interval_packets = []

        jsons = []
        for elem in next(os.walk(results_path))[2]:
            if elem.find(file_id) > 0 and elem.startswith("iperf3"):
                jsons.append(elem)

        jsons_dicts = []
        # to compare later if every interval has the same length
        total_intervals = 0
        l4_type = ""
        for js in jsons:
            print("joined path")
            print(os.path.join(results_path, js))
            l4_type, json_dict = self.read_iperf_json(
                os.path.join(results_path, js), file_id)
            jsons_dicts.append(json_dict)
        lowest_mbit_len = -1
        for json_dict in jsons_dicts:
            if len(json_dict["interval_mbits"]) < lowest_mbit_len \
                    or lowest_mbit_len == -1:
                lowest_mbit_len = len(json_dict["interval_mbits"])
        for json_dict in jsons_dicts:
            json_dict["interval_mbits"] = json_dict["interval_mbits"][
                                          0:lowest_mbit_len]
        for json_dict in jsons_dicts:
            if l4_type == "tcp":
                min_rtt_list.append(json_dict["s_min_rtt"])
                max_rtt_list.append(json_dict["s_max_rtt"])
            total_intervals = total_intervals + len(
                json_dict["interval_mbits"])

        to_plot = {"mbits": {}, "packetloss": {}}
        # if all intervals have same length it is compareable
        if len(jsons) > 0 and (total_intervals / len(jsons)) == len(
                jsons_dicts[0]["interval_mbits"]):
            for i in range(0, len(jsons_dicts[0]["interval_mbits"])):
                current_interval_mbits = current_interval_rtt = \
                    current_interval_pl = current_interval_packets = 0

                for js in jsons_dicts:
                    current_interval_mbits = current_interval_mbits + \
                                             js["interval_mbits"][i]
                    current_interval_pl = current_interval_pl + \
                        js["intervall_pl"][i]
                    if l4_type == "tcp":
                        current_interval_rtt = current_interval_rtt + \
                                               js["interval_rtt"][i]
                    else:
                        current_interval_packets = current_interval_packets + \
                                                   js["interval_packets"][i]

                total_interval_mbits.append(round(current_interval_mbits, 2))
                total_interval_pl.append(round(current_interval_pl, 2))
                if l4_type == "tcp":
                    total_interval_rtt.append(round(current_interval_rtt, 2))
                else:
                    total_interval_packets.append(
                        round(current_interval_packets, 2))

            if len(total_interval_mbits) > 0 and len(
                    total_interval_pl) > 0 and ((l4_type == "tcp" and len(
                    total_interval_rtt) > 0) or l4_type == "udp"):

                to_plot["mbits"] = {"value_list_input": total_interval_mbits,
                                    "index_list": np.arange(
                                        len(total_interval_mbits)),
                                    "titel": "iPerf3 " + l4_type.upper() +
                                             " throughput for all streams",
                                    "x_label": "t[s]",
                                    "y_label": "Speed [Mbit/s]",
                                    "filename": "loadgen_1",
                                    "adjust_unit": False, "adjust_y_ax": True}
                to_plot["packetloss"] = {"value_list_input": total_interval_pl,
                                         "index_list": np.arange(
                                             len(total_interval_pl)),
                                         "titel": "iPerf3 " + l4_type.upper()
                                                  + " retransmits for "
                                                    "all streams",
                                         "x_label": "t[s]",
                                         "y_label": "Retransmits [packets]",
                                         "filename": "loadgen_2",
                                         "adjust_unit": False,
                                         "adjust_y_ax": True}
                if l4_type == "tcp":
                    to_plot["rtt"] = {"value_list_input": total_interval_rtt,
                                      "index_list": np.arange(
                                          len(total_interval_rtt)),
                                      "titel": "iPerf3 " + l4_type.upper() +
                                               " average Round-Trip-Time for"
                                               " all streams",
                                      "x_label": "t[s]",
                                      "y_label": "RTT [microseconds]",
                                      "filename": "loadgen_3",
                                      "adjust_unit": False,
                                      "adjust_y_ax": True}
                else:
                    to_plot["packets"] = {
                        "value_list_input": total_interval_packets,
                        "index_list": np.arange(len(total_interval_packets)),
                        "titel":
                            "iPerf3 UDP packets per second for all streams",
                        "x_label": "t[s]", "y_label": "[packets/s]",
                        "filename": "loadgen_3", "adjust_unit": False,
                        "adjust_y_ax": True}
        else:
            to_plot = self.empty_plot()

        error = False
        # check if some iperf instance measured 0 bits -> not good
        if len(["s_bits" for elem in jsons_dicts if elem == 0]) == 0:
            total_bits = total_byte = total_retransmits = total_mean_rtt = \
                total_jitter = total_packets = total_lost = 0
            for js in jsons_dicts:
                total_bits = total_bits + js["s_bits"]
                total_byte = total_byte + js["s_byte"]
                if l4_type == "tcp":
                    total_retransmits = total_retransmits + js["s_retransmits"]
                    total_mean_rtt = total_mean_rtt + js["s_mean_rtt"]
                else:
                    total_jitter = total_jitter + js["s_jitter_ms"]
                    total_packets = total_packets + js["total_packets"]
                    total_lost = total_lost + js["total_lost"]

            if l4_type == "tcp":
                mean_rtt = round((total_mean_rtt / len(jsons)), 2)
                min_rtt = min(min_rtt_list)
                max_rtt = max(max_rtt_list)
            else:
                if len(jsons) > 0:
                    average_jitter_ms = round(total_jitter / len(jsons_dicts),
                                              2)
                else:
                    average_jitter_ms = 0

            output = [""]
        else:
            print("A iPerf3 instance measured 0 bits. Abort processing.")
            total_bits = total_byte = -1
            average_jitter_ms = total_packets = total_lost = -1
            total_retransmits = "error"
            mean_rtt = min_rtt = max_rtt = "error"
            output = ["error" for elem in jsons_dicts]
            error = True

        if l4_type == "tcp":
            custom_attr = \
                {"l4_type": l4_type, "elems": {
                    "mean_rtt": "Mean RTT: " + str(mean_rtt) + " microseconds",
                    "min_rtt": "Min RTT: " + str(min_rtt) + " microseconds",
                    "max_rtt": "Max RTT: " + str(max_rtt) + " microseconds"}}
        else:
            custom_attr = {"l4_type": l4_type, "elems": {
                "average_jitter_ms": "Jitter: " + str(
                    average_jitter_ms) + " milliseconds",
                "total_packets": "Total packets: " + str(
                    total_packets) + " packets/s",
                "total_lost": "Total Packetloss: " + str(
                    total_lost) + " packets"}}

        return output, total_bits, error, str(
            total_retransmits), total_byte, custom_attr, to_plot

    # reads iperf3 json into python variables
    def read_iperf_json(self, file_path, id):
        s_bits = s_byte = s_retransmits = s_mean_rtt = \
            s_min_rtt = s_max_rtt = -1
        interval_mbits = []
        interval_rtt = []
        intervall_pl = []  # pl=packetloss

        with open(file_path, "r") as s_json:
            s = json.load(s_json)

        l4_type = s["start"]["test_start"]["protocol"].lower()
        if l4_type == "tcp":
            try:
                s_bits = int(s["end"]["streams"][0]["sender"][
                                 "bits_per_second"])  # bits/second
                s_byte = int(s["end"]["streams"][0]["sender"][
                                 "bytes"])  # bytes total transfered
                s_retransmits = s["end"]["streams"][0]["sender"]["retransmits"]
                s_mean_rtt = int(s["end"]["streams"][0]["sender"]["mean_rtt"])
                s_min_rtt = int(s["end"]["streams"][0]["sender"]["min_rtt"])
                s_max_rtt = int(s["end"]["streams"][0]["sender"]["max_rtt"])
                for i in list(s["intervals"]):
                    if i["sum"]["seconds"] > 0.5:
                        # from bits to megabits
                        interval_mbits.append(i["streams"][0][
                                                  "bits_per_second"] / 1000000)
                        interval_rtt.append(i["streams"][0]["rtt"])
                        intervall_pl.append(i["streams"][0]["retransmits"])
                error = ""
            except Exception:
                print(traceback.format_exc())
                try:
                    error = s["error"]
                except Exception:
                    error = "Not able to find error report in " + file_path

            iperf_json = {"s_bits": s_bits, "s_byte": s_byte,
                          "s_retransmits": s_retransmits,
                          "s_mean_rtt": s_mean_rtt, "s_min_rtt": s_min_rtt,
                          "name": id,
                          "s_max_rtt": s_max_rtt, "error": error,
                          "interval_mbits": interval_mbits,
                          "interval_rtt": interval_rtt,
                          "intervall_pl": intervall_pl}

        else:
            interval_packets = []
            try:
                s_bits = int(s["end"]["sum"]["bits_per_second"])  # bits/second
                s_byte = int(
                    s["end"]["sum"]["bytes"])  # bytes total transfered
                s_jitter_ms = s["end"]["sum"]["jitter_ms"]
                total_packets = s["end"]["sum"]["packets"]
                total_lost = s["end"]["sum"]["lost_packets"]
                if total_packets != 0:
                    packetloss = total_lost / total_packets
                else:
                    packetloss = 0

                for i in list(s["intervals"]):
                    # from bits to megabits
                    interval_mbits.append(i["streams"][0][
                                              "bits_per_second"] / 1000000)
                    interval_packets.append(i["sum"]["packets"])
                    intervall_pl.append(packetloss / len(list(s["intervals"])))
                    # udp does not support intervall packet loss
                    # -> even distribution

                error = ""
            except Exception:
                print(traceback.format_exc())
                s_bits = s_byte = 0
                interval_mbits = intervall_pl = [0]
                try:
                    error = s["error"]
                except Exception:
                    error = "Not able to find error report in " + file_path

            iperf_json = {"s_bits": s_bits, "s_byte": s_byte,
                          "s_jitter_ms": s_jitter_ms,
                          "total_packets": total_packets, "name": file_path,
                          "total_lost": total_lost, "error": error,
                          "interval_mbits": interval_mbits,
                          "interval_packets": interval_packets,
                          "intervall_pl": intervall_pl}

        return l4_type, iperf_json

    def get_server_install_script(self, list_of_server):
        add_sudo_rights_str = "current_user=$USER\nadd_sudo_rights() {\n  " \
                              "current_user=$USER\n  if " \
                              "(sudo -l | grep -q '(ALL : ALL) " \
                              "NOPASSWD: '$1); then\n    echo 'visudo entry " \
                              "already exists';\n  else\n    sleep 0.1\n" \
                              "    echo $current_user' ALL=(ALL:ALL) " \
                              "NOPASSWD:'$1 | sudo EDITOR='tee -a' visudo;\n" \
                              "  fi\n}\n"

        with open(dir_path + "/scripts/install_iperf3_sudo.sh", "w") as f:
            f.write(add_sudo_rights_str)
            for sudo \
                    in self.loadgen_cfg["status_check"]["needed_sudos_to_add"]:
                f.write("add_sudo_rights $(which " + sudo + ")\n")
            f.write("\n")
        os.chmod(dir_path + "/scripts/install_iperf3_sudo.sh", 0o775)

        lst = []
        for server in list_of_server:
            user_name = server["loadgen_user"]
            ip = server["loadgen_ssh_ip"]
            lst.append('echo "====================================="')
            lst.append('echo "Installing IPERF3 loadgen on ' + ip + '"')
            lst.append('echo "====================================="')
            lst.append(
                'if ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
                user_name + '@' + ip + ' "echo \'ssh to ' + ip +
                ' ***worked***\';"; [ $? -eq 255 ]; then')

            lst.append('  echo "====================================="')
            lst.append('  echo "\033[0;31m ERROR: Failed to connect '
                       'to loadgen server ' + ip + ' \033[0m"')
            lst.append('  echo "====================================="')

            lst.append('else')
            lst.append('  echo "START: installing iperf3 server:"')

            lst.append('  cd ' + self.realPath + '/scripts')
            lst.append(
                '  ssh  -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
                user_name + '@' + ip + ' "mkdir -p /home/' + user_name +
                '/p4sta/loadGenerator/iperf3;"')
            lst.append(
                '  scp {install_iperf3_at_loadgen,install_iperf3_sudo}.sh ' +
                user_name + '@' + ip + ':/home/' + user_name +
                '/p4sta/loadGenerator/iperf3')
            lst.append(
                '  ssh  -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
                user_name + '@' + ip + ' "cd /home/' + user_name +
                '/p4sta/loadGenerator/iperf3; chmod +x '
                'install_iperf3_at_loadgen.sh install_iperf3_sudo.sh;"')
            lst.append(
                '  ssh  -t -o ConnectTimeout=2 -o StrictHostKeyChecking=no ' +
                user_name + '@' + ip + ' "cd /home/' + user_name +
                '/p4sta/loadGenerator/iperf3; ./install_iperf3_at_loadgen.sh;'
                './install_iperf3_sudo.sh;"')

            lst.append('  echo "FINISHED installing iperf3"')

            lst.append('fi')
        return lst

    def loadgen_status_overview(self, host, results, index):
        super(LoadGeneratorImpl, self).loadgen_status_overview(host, results,
                                                               index)
        answer = P4STA_utils.execute_ssh(host["ssh_user"], host["ssh_ip"],
                                         "iperf3 -v")
        version = ""
        try:
            for line in answer:
                if line.find("iperf") > -1:
                    version = line
        except Exception:
            pass
        if version != "":
            version = re.sub('[^0-9,.]', '', version)
            ver_split = version.split(".")
            if len(ver_split) == 3 and ver_split[0] == "3":
                if float(".".join(ver_split[1:3])) >= 1.3:
                    results[index]["custom_checks"] = [
                        [True, "iPerf3", version]]
                else:
                    results[index]["custom_checks"] = [
                        [False, "iPerf3", version +
                         " [version older than 3.1.3 will not work]"]]
            elif len(ver_split) == 2 and ver_split[0] == "3":
                if float(ver_split[1] > 7):
                    results[index]["custom_checks"] = [
                        [True, "iPerf3", version]]
                else:
                    results[index]["custom_checks"] = [
                        [False, "iPerf3", version +
                         " [version older than 3.1.3 will not work]"]]
        else:
            answer = P4STA_utils.execute_ssh(host["ssh_user"], host["ssh_ip"],
                                             "which iperf3")
            if answer[0] != "":
                results[index]["custom_checks"] = [
                    [False, "iPerf3",
                     "version not detected but installed at " + answer[0]]]
            else:
                results[index]["custom_checks"] = [
                    [False, "iPerf3", "installation not found"]]
