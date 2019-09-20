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
dir_path = os.path.dirname(os.path.realpath(__file__))
project_path = dir_path[0:dir_path.find("/load_generators")]

import time
import subprocess
import json
import numpy as np
import math
import traceback
import sys

sys.path.append(project_path + "/core/abstract_loadgenerator")
from loadgenerator import Loadgenerator

class Iperf3(Loadgenerator):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.directory = os.path.dirname(os.path.realpath(__file__))
    def get_name(self):
        return "iPerf3"

    def run_loadgens(self, file_id, duration, l4_selected, packet_size_mtu, results_path):
        devnull = open(os.devnull, 'w')
        if l4_selected == "tcp":
            mss = int(packet_size_mtu) - 56 # normally MSS = MTU - 40 but here - 16 because of 16 byte timestamps added
            flag = "-M " + str(mss)
        else:
            mss = int(packet_size_mtu) - 40 # timestamps in payload! no need for extra 16 byte space
            flag = "-u -b 100G --length " + str(mss) # 100G option allows to use maximum speed

        ###############################
        if (len(self.cfg["loadgen_servers"]) == 1 and len(self.cfg["loadgen_clients"]) > 0) or len(self.cfg["loadgen_servers"]) > 1 and len(self.cfg["loadgen_clients"]) == 1: # n clients : 1 server or 1 client: n server (only one server used)

            server = self.cfg["loadgen_servers"][0]
            # start all server ports -> 3 ports per client
            port = 5101
            for client in self.cfg["loadgen_clients"]:
                output_sub = subprocess.run(  # start 1 iperf server host but with 3*n connections (n = # clients)
                    [self.directory + "/scripts/iperf_server.sh", server["ssh_ip"], server["ssh_user"], str(port), str(port+1), str(port+2), str(duration+10)], stdout=devnull)
                port = port + 3

            time.sleep(1)
            # start client instances
            json_id = 1
            port = 5101
            for client in self.cfg["loadgen_clients"]:
                output_sub = subprocess.run(
                    [self.directory + "/scripts/iperf_client.sh", server["loadgen_ip"], client["ssh_ip"],
                        client["ssh_user"], file_id, str(port), str(port+1), str(port+2), str(json_id), str(duration), flag])
                port = port + 3
                json_id = json_id + 3

            time.sleep(5+duration)
            # get jsons from clients
            json_id = 1
            for client in self.cfg["loadgen_clients"]:
                output_sub = subprocess.run([self.directory + "/scripts/get_json.sh", client["ssh_ip"], client["ssh_user"], file_id, str(json_id), results_path])
                json_id = json_id + 3

        ###############################
        # N:N only basic tested
        ###############################
        elif len(self.cfg["loadgen_servers"]) > 1 and len(self.cfg["loadgen_clients"]) > 1: # n server : n clients
            # start all server ports -> 3 ports per client
            server_per_client = []
            port = 5101
            counter = 0
            for server in self.cfg["loadgen_servers"]:
                for i in range(math.ceil(len(self.cfg["loadgen_clients"])/len(self.cfg["loadgen_servers"]))): # e.g. 3 clients and 2 servers: 3/2=1.5 round up to 2 => 2 servers  with 2*3 ports started
                    counter = counter + 1
                    output_sub = subprocess.run(  # start 1 iperf server host but with 3*n connections (n = # clients)
                        [self.directory + "/scripts/iperf_server.sh", server["ssh_ip"], server["ssh_user"], str(port), str(port+1), str(port+2), str(duration+10)], stdout=devnull)
                    port = port + 3
                    server_per_client.append(server)
                    if counter == len(self.cfg["loadgen_clients"]):
                        break
            time.sleep(1)

            # start client instances
            json_id = 1
            port = 5101
            server_index = 0
            for client in self.cfg["loadgen_clients"]:
                output_sub = subprocess.run(
                    [self.directory + "/scripts/iperf_client.sh", server_per_client[server_index]["loadgen_ip"], client["ssh_ip"],
                        client["ssh_user"], file_id, str(port), str(port+1), str(port+2), str(json_id), str(duration), flag])
                port = port + 3
                json_id = json_id + 3
                server_index = server_index + 1

            time.sleep(5+duration)
            # get jsons from clients
            json_id = 1
            for client in self.cfg["loadgen_clients"]:
                output_sub = subprocess.run([self.directory + "/scripts/get_json.sh", client["ssh_ip"], client["ssh_user"], file_id, str(json_id), results_path])
                json_id = json_id + 3

        ###############################

        elif len(self.cfg["loadgen_clients"]) == 0 and len(self.cfg["loadgen_servers"]) > 1: #only server group (grp 1) (0 clients : n>1 server)
            # start all server ports -> 3 ports per client
            port = 5101
            for server in self.cfg["loadgen_servers"]:
                output_sub = subprocess.run(  # start 1 iperf server host but with 3*n connections (n = # clients)
                    [self.directory + "/scripts/iperf_server.sh", server["ssh_ip"], server["ssh_user"], str(port), str(port+1), str(port+2), str(duration+10)], stdout=devnull)
                port = port + 3

            time.sleep(1)

            # start client instances
            index = 0
            json_id = 1
            port = 5101
            # last client connects to first server
            connect_to = self.cfg["loadgen_servers"][0]
            client = self.cfg["loadgen_servers"][-1] # client and server are the same now ..
            output_sub = subprocess.run(
                [self.directory + "/scripts/iperf_client.sh", connect_to["loadgen_ip"], client["ssh_ip"],
                    client["ssh_user"], file_id, str(port), str(port + 1), str(port + 2), str(json_id), str(duration), flag])

            # now from the second on every client connects to server
            for client in self.cfg["loadgen_servers"][0:-1]:
                index = index + 1
                port = port + 3
                json_id = json_id + 3
                connect_to = self.cfg["loadgen_servers"][index] # connect to next server in list (last host connects to first)
                output_sub = subprocess.run(
                    [self.directory + "/scripts/iperf_client.sh", connect_to["loadgen_ip"], client["ssh_ip"],
                        client["ssh_user"], file_id, str(port), str(port + 1), str(port + 2), str(json_id), str(duration)])

            time.sleep(5+duration)

            # get jsons from clients
            json_id = 1
            for client in self.cfg["loadgen_servers"][-1:] + self.cfg["loadgen_servers"][0:-1]:
                output_sub = subprocess.run(
                    [self.directory + "/scripts/get_json.sh", client["ssh_ip"], client["ssh_user"], file_id,  str(json_id), results_path])
                json_id = json_id + 3

        #return self.process_loadgen_data(file_id)

    # reads the iperf3 results and combine them into one result and into graphs
    def process_loadgen_data(self, file_id, results_path):
        min_rtt_list = []
        max_rtt_list = []
        total_interval_mbits = []
        total_interval_rtt = []
        total_interval_pl = []  # pl = packetloss
        total_interval_packets = []

        jsons = []
        for elem in next(os.walk(results_path))[2]:
            if elem.find(file_id) > 0 and elem.startswith("iperf3"):
                jsons.append(elem)

        jsons_dicts = []
        total_intervals = 0 # to compare later if every interval has the same length
        l4_type = ""
        for js in jsons:
            print("joined path")
            print(os.path.join(results_path, js))
            l4_type, json_dict = self.read_iperf_json(os.path.join(results_path, js), file_id)
            jsons_dicts.append(json_dict)
            if l4_type == "tcp":
                min_rtt_list.append(json_dict["s_min_rtt"])
                max_rtt_list.append(json_dict["s_max_rtt"])
            total_intervals = total_intervals + len(json_dict["interval_mbits"])

        to_plot = {"mbits": {}, "packetloss": {}}
        if (total_intervals/len(jsons)) == len(jsons_dicts[0]["interval_mbits"]) :  # if all intervals have same length it is compareable
            for i in range(0, len(jsons_dicts[0]["interval_mbits"])):
                current_interval_mbits = current_interval_rtt = current_interval_pl = current_interval_packets = 0

                for js in jsons_dicts:
                    current_interval_mbits = current_interval_mbits + js["interval_mbits"][i]
                    current_interval_pl = current_interval_pl + js["intervall_pl"][i]
                    if l4_type == "tcp":
                        current_interval_rtt = current_interval_rtt + js["interval_rtt"][i]
                    else:
                        current_interval_packets = current_interval_packets + js["interval_packets"][i]

                total_interval_mbits.append(round(current_interval_mbits,2))
                total_interval_pl.append(round(current_interval_pl, 2))
                if l4_type == "tcp":
                    total_interval_rtt.append(round(current_interval_rtt, 2))
                else:
                    total_interval_packets.append(round(current_interval_packets, 2))

            if len(total_interval_mbits) > 0 and len(total_interval_pl) > 0 and ((l4_type == "tcp" and len(total_interval_rtt) > 0) or l4_type == "udp"):

                to_plot["mbits"] = {"value_list_input": total_interval_mbits, "index_list": np.arange(len(total_interval_mbits)),
                                    "titel": "iPerf3 " + l4_type.upper() + " throughput for all streams", "x_label": "t[s]", "y_label": "Speed [Mbit/s]",
                                    "filename": "loadgen_1", "adjust_unit": False, "adjust_y_ax": True}
                to_plot["packetloss"] = {"value_list_input": total_interval_pl, "index_list": np.arange(len(total_interval_pl)),
                                  "titel": "iPerf3 " + l4_type.upper() + " retransmits for all streams", "x_label": "t[s]", "y_label": "Retransmits [packets]",
                                  "filename": "loadgen_2", "adjust_unit": False, "adjust_y_ax": True}
                if l4_type == "tcp":
                    to_plot["rtt"] = {"value_list_input": total_interval_rtt, "index_list": np.arange(len(total_interval_rtt)),
                                        "titel": "iPerf3 " + l4_type.upper() + " average Round-Trip-Time for all streams", "x_label": "t[s]", "y_label": "RTT [microseconds]",
                                        "filename": "loadgen_3", "adjust_unit": False, "adjust_y_ax": True}
                else:
                    to_plot["packets"] = {"value_list_input": total_interval_packets, "index_list": np.arange(len(total_interval_packets)),
                                          "titel": "iPerf3 UDP packets per second for all streams", "x_label": "t[s]", "y_label": "[packets/s]",
                                          "filename": "loadgen_3", "adjust_unit": False, "adjust_y_ax": True}
        else:
            to_plot = self.empty_plot()

        error = False
        if len(["s_bits" for elem in jsons_dicts if elem == 0]) == 0: # check if some iperf instance measured 0 bits -> not good
            total_bits = total_byte = total_retransmits = total_mean_rtt = total_jitter = total_packets = total_lost = 0
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
                mean_rtt = round((total_mean_rtt/len(jsons)), 2)
                min_rtt = min(min_rtt_list)
                max_rtt = max(max_rtt_list)
            else:
                average_jitter_ms = round(total_jitter / len(jsons_dicts), 2)

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
            custom_attr = {"l4_type": l4_type, "elems":
                {"mean_rtt": "Mean RTT: " + str(mean_rtt) + " microseconds", "min_rtt": "Min RTT: " + str(min_rtt) + " microseconds",
                 "max_rtt": "Max RTT: " + str(max_rtt) + " microseconds"}}
        else:
            custom_attr = {"l4_type": l4_type, "elems": {"average_jitter_ms": "Jitter: " + str(average_jitter_ms) + " milliseconds",
                "total_packets": "Total packets: " + str(total_packets) + " packets/s", "total_lost": "Total Packetloss: " + str(total_lost) + " packets"}}

        return output, total_bits, error, str(total_retransmits), total_byte, custom_attr, to_plot

    # reads iperf3 json into python variables
    def read_iperf_json(self, file_path, id):
        s_bits = s_byte = s_retransmits = s_mean_rtt = s_min_rtt = s_max_rtt = -1
        interval_mbits = []
        interval_rtt = []
        intervall_pl = []  # pl=packetloss

        with open(file_path, "r") as s_json:
            s = json.load(s_json)

        l4_type = s["start"]["test_start"]["protocol"].lower()
        if l4_type == "tcp":
            try:
                s_bits = int(s["end"]["streams"][0]["sender"]["bits_per_second"])  # bits/second
                s_byte = int(s["end"]["streams"][0]["sender"]["bytes"]) # bytes total transfered
                s_retransmits = s["end"]["streams"][0]["sender"]["retransmits"]
                s_mean_rtt = int(s["end"]["streams"][0]["sender"]["mean_rtt"])
                s_min_rtt = int(s["end"]["streams"][0]["sender"]["min_rtt"])
                s_max_rtt = int(s["end"]["streams"][0]["sender"]["max_rtt"])
                for i in list(s["intervals"]):
                    interval_mbits.append(i["streams"][0]["bits_per_second"] / 1000000)  # from bits to megabits
                    interval_rtt.append(i["streams"][0]["rtt"])
                    intervall_pl.append(i["streams"][0]["retransmits"])
                error = ""
            except:
                try:
                    error = s["error"]
                except:
                    error = "Not able to find error report in " + file_path

            iperf_json = {"s_bits": s_bits, "s_byte": s_byte, "s_retransmits": s_retransmits,
                          "s_mean_rtt": s_mean_rtt, "s_min_rtt": s_min_rtt, "name": id,
                          "s_max_rtt": s_max_rtt, "error": error, "interval_mbits": interval_mbits,
                          "interval_rtt": interval_rtt, "intervall_pl": intervall_pl}

        else:
            interval_packets = []
            try:
                s_bits = int(s["end"]["sum"]["bits_per_second"])  # bits/second
                s_byte = int(s["end"]["sum"]["bytes"]) # bytes total transfered
                s_jitter_ms = s["end"]["sum"]["jitter_ms"]
                total_packets = s["end"]["sum"]["packets"]
                total_lost = s["end"]["sum"]["lost_packets"]
                if total_packets != 0:
                    packetloss = total_lost/total_packets
                else:
                    packetloss = 0

                for i in list(s["intervals"]):
                    interval_mbits.append(i["streams"][0]["bits_per_second"] / 1000000)  # from bits to megabits
                    #interval_rtt.append(i["streams"][0]["rtt"])
                    interval_packets.append(i["sum"]["packets"])
                    #intervall_pl.append(i["streams"][0]["retransmits"])
                    intervall_pl.append(packetloss/len(list(s["intervals"]))) # udp does not support intervall packet loss -> even distribution

                error = ""
            except Exception as e:
                print(traceback.format_exc())
                s_bits = s_byte = s_retransmits = s_mean_rtt = s_min_rtt = s_max_rtt = 0
                interval_mbits = interval_rtt = intervall_pl = [0]
                try:
                    error = s["error"]
                except:
                    error = "Not able to find error report in " + file_path

            iperf_json = {"s_bits": s_bits, "s_byte": s_byte, "s_jitter_ms": s_jitter_ms,
                          "total_packets": total_packets, "name": file_path,
                          "total_lost": total_lost, "error": error, "interval_mbits": interval_mbits,
                          "interval_packets": interval_packets, "intervall_pl": intervall_pl}

        return l4_type, iperf_json
