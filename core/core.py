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
import importlib
import json
import multiprocessing
import os
import re
import rpyc
import shutil
import signal
import subprocess
import sys
import time
import traceback
import threading
from pathlib import Path
from tabulate import tabulate

import P4STA_utils

dir_path = os.path.dirname(os.path.realpath(__file__))
project_path = dir_path[0:dir_path.find("/core")]
sys.path.append(project_path)

# import loadgens
sys.path.append(project_path + "/load_generators")
from iperf3 import iperf3
from loadgenerator import Loadgenerator

# import abstract target
from abstract_target import AbstractTarget
from abstract_extHost import AbstractExtHost

# import calculate module
from calculate import calculate

first_run = False

class P4staCore(rpyc.Service):
    all_targets = {}
    all_extHosts = {}
    measurement_id = -1 ## will be set when external host is started
    method_return = None

    def get_project_path(self):
        return project_path

    def __init__(self):
        global first_run
        first_run = False
        print("init p4sta core")
        P4STA_utils.set_project_path(project_path)

        #Find installed Targets
        fullpath = os.path.join(project_path, "targets")
        dirs = [d for d in os.listdir(fullpath) if os.path.isdir(os.path.join(fullpath, d))]
        for dir in dirs:
            config_path = os.path.join(fullpath, dir, "target_config.json")
            if os.path.isfile(config_path):
                ### we found a target
                with open(config_path, "r") as f:
                    cfg = json.load(f)
                    cfg["real_path"] = os.path.join(fullpath, dir)
                    self.all_targets.update({cfg["target"]:cfg})

        #Find installed extHosts
        fullpath = os.path.join(project_path, "extHost")
        dirs = [d for d in os.listdir(fullpath) if os.path.isdir(os.path.join(fullpath, d))]
        for dir in dirs:
            config_path = os.path.join(fullpath, dir, "extHost_config.json")
            if os.path.isfile(config_path):
                ### we found a target
                with open(config_path, "r") as f:
                    cfg = json.load(f)
                    cfg["real_path"] = os.path.join(fullpath, dir)
                    self.all_extHosts.update({cfg["name"]:cfg})
        print(self.all_extHosts)


        #TODO find installed load generators dynamically
        
        #Check if config exists. Otherwise: create one
        if P4STA_utils.read_current_cfg() is None:
            print("config.json not found. Creating new one from empty bmv2 template.")
            path = self.get_template_cfg_path("bmv2")
            if not os.path.exists(os.path.join(project_path, "data")):
                os.makedirs(os.path.join(project_path, "data")) #create data directory if not exist
            with open(path, "r") as f:
                cfg = json.load(f)
                P4STA_utils.write_config(cfg)
            first_run = True

    def on_connect(self, con):#, listen_port=6000, answer_port=7000):
        print("connected to P4STA core")

    def check_first_run(self):
        global first_run
        return first_run

    def first_run_finished(self):
        global  first_run
        first_run = False

    def write_install_script(self, first_time_cfg):
        new = []
        with open("install.sh", "r+") as f:
            old = f.readlines()
            for line in old:
                if line.find('switch_ip="') > -1:
                    new_line = 'switch_ip="' + first_time_cfg["stamper_ssh"] + '"' + '\n'
                elif line.find('ssh_username_switch="') > -1:
                    new_line = 'ssh_username_switch="' + first_time_cfg["stamper_user"] + '"' + '\n'
                elif line.find('external_host="') > -1:
                    new_line = 'external_host="' + first_time_cfg["ext_host_ssh"] + '"' + '\n'
                elif line.find('ssh_username_external="') > -1:
                    new_line = 'ssh_username_external="' + first_time_cfg["ext_host_user"] + '"' + '\n'
                elif line.find('loadgen_ips=("') > -1:
                    new_line = 'loadgen_ips=(' + str(first_time_cfg["loadgen_ips"]).replace(",", "").replace("'", "\"").replace("[", "").replace("]", "") + ')' + ' #("ip1" "ip2" "ip3"..)\n'
                elif line.find('ssh_username_server="') > -1:
                    new_line = 'ssh_username_server="' + first_time_cfg["loadgen_user"] + '"' + ' #same user for all loadgens\n'
                else:
                    new_line = line
                new.append(new_line)

                f.seek(0)
                for line in new:
                    f.write(line)
                os.chmod("install.sh", 0o775)

    # returns an instance of current selected target config object
    def target_obj(self, target_name):
        target_description = self.all_targets[target_name]
        path_to_driver = (os.path.join(target_description["real_path"], target_description["target_driver"]))

        spec = importlib.util.spec_from_file_location("TargetImpl", path_to_driver)
        foo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(foo)
        target_obj = foo.TargetImpl(target_description) #, P4STA_utils.read_current_cfg())
        target_obj.setRealPath(target_description["real_path"])

        return target_obj

    def extHost_obj(self, name):
        host_description = self.all_extHosts[name]
        path_to_driver = (os.path.join(host_description["real_path"], host_description["driver"]))

        spec = importlib.util.spec_from_file_location("ExtHostImpl", path_to_driver)
        foo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(foo)
        target_obj = foo.ExtHostImpl(host_description) #, P4STA_utils.read_current_cfg())
        target_obj.setRealPath(host_description["real_path"])

        return target_obj

    def current_extHost_obj(self):
        return self.extHost_obj(P4STA_utils.read_current_cfg()["selected_extHost"])

    # returns an instance of current selected load generator object
    def loadgen_obj(self, cfg):
        if cfg["selected_loadgen"] == "iperf3":
            return iperf3.Iperf3(cfg)
        ###... more loadgens
        else:
            return loadgenerator.Loadgenerator(cfg)

    def get_all_targets(self):
        lst = []
        for target in self.all_targets.keys():
            lst.append(target)
        return lst

    def get_target_cfg(self):
        try:
            target = self.target_obj(P4STA_utils.read_current_cfg()["selected_target"])
            with open(os.path.join(target.realPath, "target_config.json"), "r") as f:
                return json.load(f)
        except Exception as e:
            P4STA_utils.log_error(("CORE Exception in get_target_cfg: " + traceback.format_exc()))
            return {}

    def write_config(self, cfg, file_name="config.json"):
        with open(project_path + "/data/"+file_name, "w") as write_json:
            json.dump(cfg, write_json, indent=2, sort_keys=True)

    def delete_cfg(self, name):
        if name == "config.json":
            print("CORE: Delete of config.json denied!")
            return
        os.remove(os.path.join(project_path, "data", name))

    def get_available_cfg_files(self):
        lst = []
        folder_path = os.path.join(project_path, "data")
        all_files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
        for f in all_files:
            if f == "config.json":
                continue
            if f.endswith(".json"):
                lst.append(f)
        return lst

    def read_result_cfg(self, run_id):
        path = os.path.join(project_path, "results", str(run_id), "config_"+str(run_id)+".json")
        my_file = Path(path)
        return self.open_cfg_file(path)

    def get_template_cfg_path(self, stamper_target_name):
        target = self.target_obj(stamper_target_name)
        path = target.getFullTemplatePath()
        return path

    def open_cfg_file(self, path):
        my_file = Path(path)
        if not my_file.is_file():
            print("open_cfg_file: "+ path +"; not found.")
            return None
        with open(path, "r") as f:
            cfg = json.load(f)
            return cfg

    def delete_by_id(self, file_id):
        try:
            shutil.rmtree(P4STA_utils.get_results_path(file_id))
        except Exception as e: # 
            print(e)

    def get_ports(self):
        cfg = P4STA_utils.read_current_cfg()
        target = self.target_obj(cfg["selected_target"])
        return target.port_lists()

    def speed_list(self):
        selected_target = P4STA_utils.read_current_cfg()["selected_target"]
        target = self.target_obj(selected_target)
        return target.speed_list

    def getAllMeasurements(self):
        found = []
        try:
            folder = os.path.join(project_path, "results")
            for f in os.listdir(folder):
                path_to_res_folder = os.path.join(folder, f)
                if os.path.isdir(path_to_res_folder):
                    for file in os.listdir(path_to_res_folder):
                        if "timestamp1" in file: #TODO make it less dirty. only if etHost was stopped
                            found.append(f)
        except FileNotFoundError:
            print("Directory 'results' not found. No older datasets available.")
        found.sort(reverse=True)
        return found

    def getLatestMeasurementId(self):
        all = self.getAllMeasurements()
        if len(all) > 0:
            last = all[0]
            return last
        return None

    def start_loadgens(self, duration, l4_selected="tcp", packet_size_mtu="1500"):
        cfg = P4STA_utils.read_current_cfg()
        loadgen = self.loadgen_obj(cfg)

        loadgen.run_loadgens(str(P4staCore.measurement_id), duration, l4_selected, packet_size_mtu, self.get_current_results_path())

        return P4staCore.measurement_id

    def process_loadgens(self, file_id): # after loadgen test
        cfg = self.read_result_cfg(file_id)
        loadgen = self.loadgen_obj(cfg)
        results = loadgen.process_loadgen_data(str(file_id), P4STA_utils.get_results_path(file_id))

        output, total_bits, error, total_retransmits, total_byte, custom_attr, to_plot = results

        if not error:
            print(to_plot)
            for key, value in to_plot.items():
                print("key: " + key + "  value: " + str(value))
                calculate.plot_graph(value["value_list_input"], value["index_list"], value["titel"], value["x_label"],
                                     value["y_label"], value["filename"], value["adjust_unit"], value["adjust_y_ax"])

            with open(os.path.join(P4STA_utils.get_results_path(file_id), "output_loadgen_" + str(file_id) + ".txt"), "w+") as f:
                f.write("Used Loadgenerator: " + loadgen.get_name())
                f.write("Total meaured speed: " + str(calculate.find_unit_bit_byte(total_bits, "bit")[0]) + " " +
                        calculate.find_unit_bit_byte(total_bits, "bit")[1] + "/s" + "\n")
                f.write("Total measured throughput: " + str(calculate.find_unit_bit_byte(total_byte, "byte")[0]) + " " +
                        calculate.find_unit_bit_byte(total_byte, "byte")[1] + "\n")
                f.write("Total retransmitted packets: " + str(total_retransmits) + " Packets" + "\n")

                for key, value in custom_attr["elems"].items():
                    try:
                        f.write(value + "\n")
                    except:
                        pass

        return output, total_bits, error, total_retransmits, total_byte, custom_attr, to_plot

    def deploy(self):
        target = self.target_obj(P4STA_utils.read_current_cfg()["selected_target"])
        error = target.deploy(P4STA_utils.read_current_cfg())
        if error is not None and error != "":
            P4STA_utils.log_error(error)
        return error

    def ping(self):
        cfg = P4STA_utils.read_current_cfg()
        output = []
        for server in cfg["loadgen_servers"]:
            output += ['-----------------------', 'Server: '+server['ssh_ip'], '-----------------------']
            if len(cfg["loadgen_clients"]) > 0:
                for client in cfg["loadgen_clients"]:
                    output_sub = subprocess.run([project_path + "/scripts/ping.sh", server["ssh_ip"], client["loadgen_ip"], server["ssh_user"], self.check_ns(server)], stdout=subprocess.PIPE)
                    output += (output_sub.stdout.decode("utf-8").split("\n"))
            else:
                for server2 in cfg["loadgen_servers"]:
                    if server is not server2:
                        output_sub = subprocess.run([project_path + "/scripts/ping.sh", server2["ssh_ip"], server["loadgen_ip"], server2["ssh_user"], self.check_ns(server2)], stdout=subprocess.PIPE)
                        output += (output_sub.stdout.decode("utf-8").split("\n"))
        return output

    def read_p4_device(self):
        target = self.target_obj(P4STA_utils.read_current_cfg()["selected_target"])
        cfg = target.read_p4_device(P4STA_utils.read_current_cfg())

        with open(os.path.join(self.get_current_results_path(), "p4_dev_" + str(P4staCore.measurement_id) + ".json"), "w") as write_json:
            json.dump(cfg, write_json, indent=2, sort_keys=True)

        if cfg["delta_counter"] == 0:
            average = 0
        else:
            average = cfg["total_deltas"] / cfg["delta_counter"]

        with open(os.path.join(self.get_current_results_path(), "output_p4_device_" + P4staCore.measurement_id + ".txt"), "w+") as f:
            f.write("################################################################################\n")
            f.write("######## Results from P4 device for ID " + str(P4staCore.measurement_id) + " from " + str(
                time.strftime('%H:%M:%S %d.%m.%Y', time.localtime(int(P4staCore.measurement_id)))) + " ########\n")
            f.write("#### The chosen ID results from the time where the external hosts started. #####\n")
            f.write("################################################################################\n\n")
            f.write("Measured for all timestamped packets:" + "\n")
            f.write("Average Latency: " + str(round(calculate.find_unit([average])[0][0], 2)) + " " + str(
                calculate.find_unit([average])[1]) + "\n")
            f.write("Min Latency: " + str(calculate.find_unit([cfg["min_delta"]])[0][0]) + " " + str(
                calculate.find_unit([cfg["min_delta"]])[1]) + "\n")
            f.write("Max Latency: " + str(calculate.find_unit([cfg["max_delta"]])[0][0]) + " " + str(
                calculate.find_unit([cfg["max_delta"]])[1]) + "\n\n")
            f.write("Measured for all timestamped packets:" + "\n")
            f.write("Packetloss between Port " + cfg["dut1_real"] + " and " + cfg["dut2_real"] + " : " + str(
                cfg["dut1_num_egress_stamped_packets"] - cfg["dut2_num_ingress_stamped_packets"]) + " (total: " + str(
                cfg["dut1_num_egress_stamped_packets"]) + " packets) " + "\n")
            f.write("Packetloss between Port " + cfg["dut2_real"] + " and " + cfg["dut1_real"] + " : " + str(
                cfg["dut2_num_egress_stamped_packets"] - cfg["dut1_num_ingress_stamped_packets"]) + " (total: " + str(
                cfg["dut2_num_egress_stamped_packets"]) + " packets) " + "\n\n")
            f.write("Measured for all packets (on port base):" + "\n")
            f.write("Packetloss between Port " + cfg["dut1_real"] + " and " + cfg["dut2_real"] + " : " + str(
                cfg["dut1_num_egress_packets"] - cfg["dut2_num_ingress_packets"]) + " (total: " + str(
                cfg["dut1_num_egress_packets"]) + " packets) " + "\n")
            f.write("Packetloss between Port " + cfg["dut2_real"] + " and " + cfg["dut1_real"] + " : " + str(
                cfg["dut2_num_egress_packets"] - cfg["dut1_num_ingress_packets"]) + " (total: " + str(
                cfg["dut2_num_egress_packets"]) + " packets) " + "\n\n")

            for word in ["", "_stamped"]:
                if word =="_stamped":
                    f.write("\n\nMeasured for timestamped packets only:")
                else:
                    f.write("\nMeasure for all packets:")
                f.write("\n----------------- INGRESS -----------------|||---------------- EGRESS ------------------\n")

                table = [["IN", "GBytes", "Packets", "Ave Size (Byte)", "GBytes", "Packets", "Ave Size (Byte)", "OUT"]]
                try:
                    for server in cfg["loadgen_servers"]:
                        try:
                            table.append([server["real_port"], round(server["num_ingress" + word + "_bytes"] / 1000000000, 2),
                                          server["num_ingress" + word + "_packets"],
                                          round(server["num_ingress" + word + "_bytes"] / server["num_ingress" + word + "_packets"], 2),
                                          round(cfg["dut1_num_egress" + word + "_bytes"] / 1000000000, 2), cfg["dut1_num_egress" + word + "_packets"],
                                          round(cfg["dut1_num_egress" + word + "_bytes"] / cfg["dut1_num_egress" + word + "_packets"], 2),
                                          cfg["dut1_real"]])
                        except ZeroDivisionError:
                            table.append([server["real_port"], "err: could be 0", server["num_ingress" + word + "_packets"], "err: could be 0",
                                          "err: could be 0", cfg["dut1_num_egress" + word + "_packets"], "err: could be 0", cfg["dut1_real"]])

                    for client in cfg["loadgen_clients"]:
                        try:
                            table.append([cfg["dut2_real"], round(cfg["dut2_num_ingress" + word + "_bytes"] / 1000000000, 2),
                                          cfg["dut2_num_ingress" + word + "_packets"],
                                          round(cfg["dut2_num_ingress" + word + "_bytes"] / cfg["dut2_num_ingress" + word + "_packets"], 2),
                                          round(client["num_egress" + word + "_bytes"] / 1000000000, 2), client["num_egress" + word + "_packets"],
                                          round(client["num_egress" + word + "_bytes"] / client["num_egress" + word + "_packets"], 2),
                                          client["real_port"]])
                        except ZeroDivisionError:
                            table.append([cfg["dut2_real"], "err: could be 0", cfg["dut2_num_ingress" + word + "_packets"], "err: could be 0",
                                          "err: could be 0", client["num_egress" + word + "_packets"], "err: could be 0", client["real_port"]])

                    for client in cfg["loadgen_clients"]:
                        try:
                            table.append([client["real_port"], round(client["num_ingress" + word + "_bytes"] / 1000000000, 2),
                                          client["num_ingress" + word + "_packets"],
                                          round(client["num_ingress" + word + "_bytes"] / client["num_ingress" + word + "_packets"], 2),
                                          round(cfg["dut2_num_egress" + word + "_bytes"] / 1000000000, 2), cfg["dut2_num_egress" + word + "_packets"],
                                          round(cfg["dut2_num_egress" + word + "_bytes"] / cfg["dut2_num_egress" + word + "_packets"], 2),
                                          cfg["dut2_real"]])
                        except ZeroDivisionError:
                            table.append([client["real_port"], "err: could be 0", client["num_ingress" + word + "_packets"], "err: could be 0",
                                          "err: could be 0", cfg["dut2_num_egress" + word + "_packets"], "err: could be 0", cfg["dut2_real"]])

                    for server in cfg["loadgen_servers"]:
                        try:
                            table.append([cfg["dut1_real"], round(cfg["dut1_num_ingress" + word + "_bytes"] / 1000000000, 2),
                                          cfg["dut1_num_ingress" + word + "_packets"],
                                          round(cfg["dut1_num_ingress" + word + "_bytes"] / cfg["dut1_num_ingress" + word + "_packets"], 2),
                                          round(server["num_egress" + word + "_bytes"] / 1000000000, 2), server["num_egress" + word + "_packets"],
                                          round(server["num_egress" + word + "_bytes"] / server["num_egress" + word + "_packets"], 2),
                                          server["real_port"]])
                        except ZeroDivisionError:
                            table.append([cfg["dut1_real"], "err: could be 0", cfg["dut1_num_ingress" + word + "_packets"], "err: could be 0",
                                          "err: could be 0", server["num_egress" + word + "_packets"], "err: could be 0", server["real_port"]])
                except Exception as e:
                    print(traceback.format_exc())
                    table.append(["Error: " + str(e)])

                f.write(tabulate(table, tablefmt="fancy_grid"))  # creates table with the help of tabulate module

    def p4_dev_results(self, file_id):
        #TODO: better exception handling
        time_created = "not available"
        try:
            time_created = time.strftime('%H:%M:%S %d.%m.%Y', time.localtime(int(file_id)))
        except:
            pass
        try:
            with open(P4STA_utils.get_results_path(file_id)  + "/p4_dev_" + str(file_id) + ".json", "r") as file:
                sw = json.load(file)
        except Exception as e:
            P4STA_utils.log_error("CORE Exception: " + traceback.format_exc())
        if sw["delta_counter"] != 0:
            average = sw["total_deltas"]/sw["delta_counter"]
        else:
            average = 0
        range_delta = sw["max_delta"] - sw["min_delta"]
        sw["average"] = calculate.find_unit([average])
        sw["min_delta"] = calculate.find_unit(sw["min_delta"])
        sw["max_delta"] = calculate.find_unit(sw["max_delta"])
        sw["range"] = calculate.find_unit(range_delta)
        sw["pkt"] = sw["delta_counter"]
        sw["time"] = time_created
        sw["filename"] = file_id


        ###################################################
        ########## compute avg packet sizes ###############
        ########## compute total throughput ###############
        ###################################################

        # all packets
        sw["dut1_avg_packet_size_ingress"] = sw["dut1_avg_packet_size_egress"] = sw["dut2_avg_packet_size_ingress"] = sw["dut2_avg_packet_size_egress"] = 0
        if sw["dut1_num_ingress_packets"] > 0: sw["dut1_avg_packet_size_ingress"] = round(sw["dut1_num_ingress_bytes"]/sw["dut1_num_ingress_packets"], 1)
        if sw["dut1_num_egress_packets"] > 0: sw["dut1_avg_packet_size_egress"] = round(sw["dut1_num_egress_bytes"]/sw["dut1_num_egress_packets"], 1)
        if sw["dut2_num_ingress_packets"] > 0: sw["dut2_avg_packet_size_ingress"] = round(sw["dut2_num_ingress_bytes"]/sw["dut2_num_ingress_packets"], 1)
        if sw["dut2_num_egress_packets"] > 0: sw["dut2_avg_packet_size_egress"] = round(sw["dut2_num_egress_bytes"]/sw["dut2_num_egress_packets"], 1)

        sw["dut1_throughput_gbyte_ingress"] = round(sw["dut1_num_ingress_bytes"]/1000000000, 2)
        sw["dut1_throughput_gbyte_egress"] = round(sw["dut1_num_egress_bytes"]/1000000000, 2)
        sw["dut2_throughput_gbyte_ingress"] = round(sw["dut2_num_ingress_bytes"]/1000000000, 2)
        sw["dut2_throughput_gbyte_egress"] = round(sw["dut2_num_egress_bytes"]/1000000000, 2)

        for port in sw["loadgen_servers"] + sw["loadgen_clients"]:
            port["avg_packet_size_ingress"] = port["avg_packet_size_egress"] = 0
            if port["num_ingress_packets"] > 0:
                port["avg_packet_size_ingress"] = round(port["num_ingress_bytes"]/port["num_ingress_packets"], 1)
            if port["num_egress_packets"] > 0:
                port["avg_packet_size_egress"] = round(port["num_egress_bytes"]/port["num_egress_packets"], 1)
            port["throughput_gbyte_ingress"] = round(port["num_ingress_bytes"]/1000000000, 2)
            port["throughput_gbyte_egress"] = round(port["num_egress_bytes"]/1000000000, 2)

        # stamped packets
        try:
            sw["dut1_throughput_gbyte_ingress_stamped"] = round(sw["dut1_num_ingress_stamped_bytes"]/1000000000, 2)
            sw["dut1_throughput_gbyte_egress_stamped"] = round(sw["dut1_num_egress_stamped_bytes"]/1000000000, 2)
            sw["dut2_throughput_gbyte_ingress_stamped"] = round(sw["dut2_num_ingress_stamped_bytes"]/1000000000, 2)
            sw["dut2_throughput_gbyte_egress_stamped"] = round(sw["dut2_num_egress_stamped_bytes"]/1000000000, 2)

            sw["dut1_avg_packet_size_ingress_stamped"] = sw["dut1_avg_packet_size_egress_stamped"] = sw["dut2_avg_packet_size_ingress_stamped"] = sw["dut2_avg_packet_size_egress_stamped"] = 0
            if sw["dut1_num_ingress_stamped_packets"] > 0: sw["dut1_avg_packet_size_ingress_stamped"] = round(sw["dut1_num_ingress_stamped_bytes"] / sw["dut1_num_ingress_stamped_packets"], 1)
            if sw["dut1_num_egress_stamped_packets"] > 0: sw["dut1_avg_packet_size_egress_stamped"] = round(sw["dut1_num_egress_stamped_bytes"] / sw["dut1_num_egress_stamped_packets"], 1)
            if sw["dut2_num_ingress_stamped_packets"] > 0: sw["dut2_avg_packet_size_ingress_stamped"] = round(sw["dut2_num_ingress_stamped_bytes"] / sw["dut2_num_ingress_stamped_packets"], 1)
            if sw["dut2_num_egress_stamped_packets"] > 0: sw["dut2_avg_packet_size_egress_stamped"] = round(sw["dut2_num_egress_stamped_bytes"] / sw["dut2_num_egress_stamped_packets"], 1)

            for port in sw["loadgen_servers"] + sw["loadgen_clients"]:
                port["avg_packet_size_ingress_stamped"] = port["avg_packet_size_egress_stamped"] = 0
                if port["num_ingress_stamped_packets"] > 0:
                    port["avg_packet_size_ingress_stamped"] = round(port["num_ingress_stamped_bytes"] / port["num_ingress_stamped_packets"], 1)
                if port["num_egress_stamped_packets"] > 0:
                    port["avg_packet_size_egress_stamped"] = round(port["num_egress_stamped_bytes"] / port["num_egress_stamped_packets"], 1)

                port["throughput_gbyte_ingress_stamped"] = round(port["num_ingress_stamped_bytes"] / 1000000000, 2)
                port["throughput_gbyte_egress_stamped"] = round(port["num_egress_stamped_bytes"] / 1000000000, 2)

        except:
            pass # if target has stamped counter not implemented yet (html will be automatically empty)

        ###################################################
        ########## compute packet losses ##################
        ###################################################

        # for all packets
        if sw["dut1"] != sw["dut2"]: # if same only dut1 is used
            sw["packet_loss_1"] = sw["dut1_num_egress_packets"] - sw["dut2_num_ingress_packets"]

            if sw["packet_loss_1"] > 0:
                sw["packet_loss_1_percent"] = round((sw["packet_loss_1"] / sw["dut1_num_egress_packets"]) * 100, 2)
            else:
                sw["packet_loss_1_percent"] = 0
            sw["packet_loss_2"] = sw["dut2_num_egress_packets"] - sw["dut1_num_ingress_packets"]
            if sw["packet_loss_2"] > 0:
                sw["packet_loss_2_percent"] = round((sw["packet_loss_2"] / sw["dut2_num_egress_packets"]) * 100, 2)
            else:
                sw["packet_loss_2_percent"] = 0

        else:
            sw["packet_loss_1"] = abs(sw["dut1_num_egress_packets"] - sw["dut1_num_ingress_packets"])
            divider = max(sw["dut1_num_egress_packets"], sw["dut1_num_ingress_packets"])

            if sw["packet_loss_1"] > 0:
                sw["packet_loss_1_percent"] = round((sw["packet_loss_1"] / divider) * 100, 2)
            else:
                sw["packet_loss_1_percent"] = 0

            sw["packet_loss_2"] = "n/a"

         # for stamped packets only
        if sw["dut1"] != sw["dut2"]:
            sw["packet_loss_stamped_1"] = sw["dut1_num_egress_stamped_packets"] - sw["dut2_num_ingress_stamped_packets"]
            if sw["packet_loss_stamped_1"] > 0:
                sw["packet_loss_stamped_1_percent"] = round((sw["packet_loss_stamped_1"]/sw["dut1_num_egress_stamped_packets"])*100, 2)
            else:
                sw["packet_loss_stamped_1_percent"] = 0
            sw["packet_loss_stamped_2"] = sw["dut2_num_egress_stamped_packets"] - sw["dut1_num_ingress_stamped_packets"]
            if sw["packet_loss_stamped_2"] > 0:
                sw["packet_loss_stamped_2_percent"] = round((sw["packet_loss_stamped_2"]/sw["dut2_num_egress_stamped_packets"])*100, 2)
            else:
                sw["packet_loss_stamped_2_percent"] = 0
        else:
            sw["packet_loss_stamped_1"] = abs(sw["dut1_num_egress_stamped_packets"] - sw["dut1_num_ingress_stamped_packets"])
            divider = max(sw["dut1_num_egress_stamped_packets"], sw["dut1_num_ingress_stamped_packets"])

            if sw["packet_loss_stamped_1"] > 0:
                sw["packet_loss_1_stamped_percent"] = round((sw["packet_loss_stamped_1"] / divider) * 100, 2)
            else:
                sw["packet_loss_1_stamped_percent"] = 0

            sw["packet_loss_stamped_2"] = "n/a"

        return sw

    # resets registers in p4 device
    def reset(self):
        target = self.target_obj(P4STA_utils.read_current_cfg()["selected_target"])
        ret_val = target.reset_p4_registers(P4STA_utils.read_current_cfg())
        if ret_val is None:
            ret_val = ""
        return ret_val

    def check_ns(self, host):
        if "namespace_id" in host:
            return "sudo ip netns exec " + str(host["namespace_id"])
        else:
            return ""

    def p4_dev_status(self):
        cfg = P4STA_utils.read_current_cfg()
        target = self.target_obj(cfg["selected_target"])
        lines_pm, running, dev_status = target.p4_dev_status(cfg)

        for host in (cfg["loadgen_servers"] + cfg["loadgen_clients"]):
            pingresp = (os.system("timeout 1 ping " + host["ssh_ip"] + " -c 1") == 0)  # if ping works it should be true
            host["reachable"] = pingresp
            if pingresp:
                output_host = subprocess.run(
                    [project_path + "/scripts/ethtool.sh", host["ssh_ip"], host["ssh_user"], host["loadgen_iface"], self.check_ns(host)],
                    stdout=subprocess.PIPE)
                pos = output_host.stdout.decode("utf-8").find("Link detected")
                try:
                    if str(output_host.stdout.decode("utf-8")[pos + 15:pos + 18]) == "yes":
                        host["link"] = "up"
                    else:
                        host["link"] = "down"
                except:
                    host["link"] = "error"
            else:
                host["link"] = "down"

        return cfg, lines_pm, running, dev_status

    def start_p4_dev_software(self):
        target = self.target_obj(P4STA_utils.read_current_cfg()["selected_target"])
        target.start_p4_dev_software(P4STA_utils.read_current_cfg())

    def get_p4_dev_startup_log(self):
        target = self.target_obj(P4STA_utils.read_current_cfg()["selected_target"])
        return target.get_p4_dev_startup_log(P4STA_utils.read_current_cfg())

    def stop_p4_dev_software(self):
        target = self.target_obj(P4STA_utils.read_current_cfg()["selected_target"])
        target.stop_p4_dev_software(P4STA_utils.read_current_cfg())

    def reboot(self):
        cfg = P4STA_utils.read_current_cfg()
        for host in (cfg["loadgen_servers"]+cfg["loadgen_clients"]):
            subprocess.run([project_path + "/scripts/reboot.sh", host["ssh_user"], host["ssh_ip"]], stdout=subprocess.PIPE)

    def refresh_links(self):
        cfg = P4STA_utils.read_current_cfg()
        for host in (cfg["loadgen_servers"]+cfg["loadgen_clients"]):
            subprocess.run([project_path + "/scripts/refresh_links.sh", host["ssh_user"], host["ssh_ip"], host["loadgen_iface"]])

    def visualization(self):
        target = self.target_obj(P4STA_utils.read_current_cfg()["selected_target"])

        return target.visualization(P4STA_utils.read_current_cfg())

    def set_new_measurement_id(self):
        file_id = str(int(round(time.time())))  # generates name (time in sec since 1.1.1970)4
        P4staCore.measurement_id = file_id
        return file_id

    def get_current_results_path(self):
        return P4STA_utils.get_results_path(P4staCore.measurement_id)

    def start_external(self):
        file_id = str(P4staCore.measurement_id)
        cfg = P4STA_utils.read_current_cfg()
        target = self.target_obj(cfg["selected_target"])
        lines_pm, running, dev_status = target.p4_dev_status(P4STA_utils.read_current_cfg())
        # backup current config (e.g. ports, speed) to results directory
        if not os.path.exists(self.get_current_results_path()):
            os.makedirs(self.get_current_results_path())
        shutil.copy(project_path + "/data/config.json", os.path.join(self.get_current_results_path(), "config_"+str(P4staCore.measurement_id)+".json") )

        multi = self.get_target_cfg()['stamping_capabilities']['timestamp-multi']
        tsmax = self.get_target_cfg()['stamping_capabilities']['timestamp-max']
        errors = ()
        if running:
            errors = self.current_extHost_obj().start_external(file_id, multi = multi, tsmax=tsmax)
        if errors != ():
            P4STA_utils.log_error(errors)
        return running, errors

    def stop_external(self):
        cfg = P4STA_utils.read_current_cfg()
        try:
            if int(P4staCore.measurement_id) == -1:
                raise Exception

            stoppable = self.current_extHost_obj().stop_external(P4staCore.measurement_id)
        except:
            stoppable = False

        self.read_p4_device()

	#Don't do this when stopping ext host, takes lot of time
        #self.external_results(str(P4staCore.measurement_id))

        return stoppable

    # displays results from external host python receiver from return of calculate module
    def external_results(self, measurement_id):
        cfg = self.read_result_cfg(str(measurement_id))

        extH_results = calculate.main(str(measurement_id), cfg["multicast"], P4STA_utils.get_results_path(measurement_id)) 
        ipdv_range = extH_results["max_ipdv"] - extH_results["min_ipdv"]
        pdv_range = extH_results["max_pdv"] - extH_results["min_pdv"]
        rate_jitter_range = extH_results["max_packets_per_second"] - extH_results["min_packets_per_second"]
        latency_range = extH_results["max_latency"] - extH_results["min_latency"]

        f = open(P4STA_utils.get_results_path(measurement_id) + "/output_external_host_" + str(measurement_id) + ".txt", "w+")
        f.write("Results from externel Host for every " + str(cfg["multicast"] + ". packet") + "\n")
        f.write("Raw packets: " + str(extH_results["num_raw_packets"]) + " Processed packets: " + str(
            extH_results["num_processed_packets"]) + " Total throughput: " + str(
            extH_results["total_throughput"]) + " Megabytes \n")
        f.write("Min latency: " + str(calculate.find_unit(extH_results["min_latency"])[0][0]) + " " + str(
            calculate.find_unit(extH_results["min_latency"])[1]))
        f.write(" Max latency: " + str(calculate.find_unit(extH_results["max_latency"])[0][0]) + " " + str(
            calculate.find_unit(extH_results["max_latency"])[1]))
        f.write(" Average latency: " + str(calculate.find_unit(extH_results["avg_latency"])[0][0]) + " " + str(
            calculate.find_unit(extH_results["avg_latency"])[1]) + "\n")
        f.write("Min IPDV: " + str(calculate.find_unit(extH_results["min_ipdv"])[0][0]) + " " + str(
            calculate.find_unit(extH_results["min_ipdv"])[1]) + "\n")
        f.write("Max IPDV: " + str(calculate.find_unit(extH_results["max_ipdv"])[0][0]) + " " + str(
            calculate.find_unit(extH_results["max_ipdv"])[1]) + "\n")
        f.write("Average IPDV: " + str(calculate.find_unit(extH_results["avg_ipdv"])[0][0]) + " " + str(
            calculate.find_unit(extH_results["avg_ipdv"])[1])
                + " and abs(): " + str(calculate.find_unit(extH_results["avg_abs_ipdv"])[0][0]) + " " + str(
            calculate.find_unit(extH_results["avg_abs_ipdv"])[1]) + "\n")
        f.write("Min PDV: " + str(calculate.find_unit(extH_results["min_pdv"])[0][0]) + " " + str(
            calculate.find_unit(extH_results["min_pdv"])[1]) + "\n")
        f.write("Max PDV: " + str(calculate.find_unit(extH_results["max_pdv"])[0][0]) + " " + str(
            calculate.find_unit(extH_results["max_pdv"])[1]) + "\n")
        f.write("Average PDV: " + str(calculate.find_unit(extH_results["avg_pdv"])[0][0]) + " " + str(
            calculate.find_unit(extH_results["avg_pdv"])[1]) + "\n")
        f.write("Min packet/s: " + str(extH_results["min_packets_per_second"]) + " Max packet/s: " + str(
            extH_results["max_packets_per_second"]) + " Average packet/s: " + str(
            extH_results["avg_packets_per_second"]) + "\n")
        f.close()

    def fetch_interface(self, ssh_user, ssh_ip, iface, namespace=""):
        try:
            lines = subprocess.run([project_path + "/core/scripts/fetch.sh", ssh_user, ssh_ip, iface, namespace], stdout=subprocess.PIPE).stdout.decode("utf-8").split("\n")
            mac_line = ""
            ipv4_line = ""
            for l in range(0, len(lines)):
                if lines[l].find(iface) > -1:
                    try:
                        for i in range(0, 10):
                            if lines[l + i].find("ether") > -1 or lines[l + i].find("HWaddr") > -1:
                                mac_line = lines[l + i]
                                break
                    except:
                        mac_line = ""
                    try:
                        for i in range(0, 10):
                            found = lines[l + i].find("inet ")
                            if found > -1: # ifconfig different versions, sometimes Bcast sometimes broadcast
                                if lines[l + i].find("Bcast") < lines[l + i].find("broadcast"):
                                    bcast = lines[l + i].find("broadcast")
                                else:
                                    bcast = lines[l + i].find("Bcast")
                                if lines[l + i].find("netmask") < lines[l + i].find("Mask"):
                                    nm = lines[l + i].find("Mask")
                                else:
                                    nm = lines[l + i].find("netmask")

                                if nm < bcast: # broadcast and netmask in diff versions of ifconfig swapped
                                    stop = nm
                                    nm_line = lines[l + i][nm:bcast]
                                else:
                                    stop = bcast
                                    nm_line = lines[l + i][nm:]

                                ipv4_line = lines[l + i][found:stop]
                                break
                    except:
                        ipv4_line = nm_line = ""
                    break

            re_mac = re.compile('([0-9a-f]{2}(?::[0-9a-f]{2}){5})', re.IGNORECASE)
            re_ipv4 = re.compile('[0-9]+(?:\.[0-9]+){3}')

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
            try:
                netmask = re.findall(re_ipv4, nm_line)[0]
                prefix = "/" + str(sum(bin(int(x)).count('1') for x in netmask.split('.')))
            except:
                prefix = ""

        except Exception as e:
            P4STA_utils.log_error("CORE EXCEPTION: " + str( traceback.format_exc() ))
            ipv4 = mac = "fetch error"

        # check if iface is up
        try:
            if namespace == "":
                up_state = self.execute_ssh(ssh_user, ssh_ip, 'ifconfig | grep "' + iface+'"')[0]
            else:
                up_state = self.execute_ssh(ssh_user, ssh_ip, 'sudo ip netns exec ' + str(namespace) + ' ifconfig | grep "' + iface + '"')[0]
            if len(up_state) > 0:
                up_state = "up"
                iface_found = True
            else:
                up_state = "down"
                found = self.execute_ssh(ssh_user, ssh_ip, 'ifconfig -a | grep "' + iface + '"')[0]
                if len(found) > 0:
                    iface_found = True
                else:
                    iface_found = False
        except:
            up_state = "error"

        return ipv4, mac, prefix, up_state, iface_found

    def set_interface(self, ssh_user, ssh_ip, iface, iface_ip, namespace=""):
        if namespace == "":
            line = subprocess.run([project_path + "/core/scripts/setIP.sh", ssh_user, ssh_ip, iface, iface_ip], stdout=subprocess.PIPE).stdout.decode("utf-8")
        else:
            line = subprocess.run([project_path + "/core/scripts/setIP_namespace.sh", ssh_user, ssh_ip, iface, iface_ip, namespace], stdout=subprocess.PIPE).stdout.decode("utf-8")

        # error = return True; worked = return False
        return not (line.find("worked") > -1 and line.find("ifconfig_success") > -1)

    def check_ssh_ping(self, ip):
        pingresp = (os.system("timeout 1 ping " + ip + " -c 1") == 0)  # if ping works it should be true
        return pingresp

    def execute_ssh(self, user, ip_address, arg):
        input = ["ssh", "-o ConnectTimeout=5", user + "@" + ip_address, arg] #-o StrictHostKeyChecking=no
        res = subprocess.Popen(input, stdout=subprocess.PIPE).stdout
        return res.read().decode().split("\n")

    # filters list and returns list of strings containing li
    def filter_list(self, li, to_check):
        return_results = []
        for r in li:
            if r.find(to_check) > -1:
                return_results.append(r)
        return return_results

    def check_sudo(self, user, ip_address):
        sudo_results = self.execute_ssh(user, ip_address, "sudo -l")
        if len(sudo_results) > 1:
            return self.filter_list(sudo_results, "NOPASSWD")
        else:
            return ["Error checking sudo status."]

    def check_iface(self, user, ip, iface, namespace=""):
        ipv4, mac, prefix, up_state, iface_found = self.fetch_interface(user, ip, iface, namespace)
        if ipv4 == "" or ipv4 == []:
            ipv4 = "n/a"
        if mac == "" or mac == []:
            mac = "device not found"

        return ipv4, mac, prefix, up_state

    def check_if_p4_compiled(self):
        target = self.target_obj(P4STA_utils.read_current_cfg()["selected_target"])
        return target.check_if_p4_compiled(P4STA_utils.read_current_cfg())

    def check_routes(self, user, ip):
        return self.execute_ssh(user, ip, "ip route")

    def check_namespaces(self, user, ip):
        namespaces = self.execute_ssh(user, ip, "ip netns list")
        answer = []
        for ns in namespaces:
            if ns != "":
                answer.append([str(ns)] + self.execute_ssh(user, ip, "sudo ip netns exec " + str(ns) + " ifconfig"))
        return answer

    def fetch_mtu(self, user, ip_address, iface, namespace=""):
        mtu = "0"
        if namespace != "":
            namespace = "sudo ip netns exec " + namespace + " "
        for line in self.execute_ssh(user, ip_address, namespace + "ifconfig " + iface):
            found = line.lower().find("mtu")
            if found > -1:
                mtu = line[found + 4:found + 4 + line[found + 4:].find(" ")]
                if not mtu.isdigit():
                    mtu = "0"
                break

        return mtu

    def get_results_path(self, file_id):
        return P4STA_utils.get_results_path(file_id)

    def delete_namespace(self, ns, user, ssh_ip):
        all = self.execute_ssh(user, ssh_ip, "sudo ip netns list")
        if ns in all:
            self.execute_ssh(user, ssh_ip, "sudo ip netns del " + ns)
            return True
        else:
            return False

    def status_overview(self):
        cfg = P4STA_utils.read_current_cfg()
        target_cfg = self.get_target_cfg()
        target = self.target_obj(cfg["selected_target"])
        results = [None] * (len(cfg["loadgen_servers"] + cfg["loadgen_clients"]) + 3)  # stores the return values from threads

        def check_needed_sudos(host, needed_sudos):
            to_add = []
            for needed in needed_sudos:
                found = False
                for right in host["sudo_rights"]:
                    if right.endswith("NOPASSWD: ALL"):
                        return []
                    if right.find(needed) > -1:
                        found = True
                if not found:
                    to_add.append(needed)
            return to_add

        # Stamper thread
        def stamper(results, index):
            res = {}
            res["p4_dev_ssh_ping"] = self.check_ssh_ping(ip=cfg["p4_dev_ssh"])
            res["p4_dev_sudo_rights"] = self.check_sudo(cfg["p4_dev_user"], cfg["p4_dev_ssh"])

            if res["p4_dev_ssh_ping"]:
                res["p4_dev_compile_status_color"], res["p4_compile_status"] = self.check_if_p4_compiled()
            else:
                res["p4_dev_compile_status_color"], res["p4_compile_status"] = (False, "P4-Stamper is not reachable at SSH IP!")
            # needed sudos = defined in target_config.json + dynamic sudos (e.g. software version)
            needed_sudos = target_cfg["status_check"]["needed_sudos_to_add"] + target.needed_dynamic_sudos(cfg)
            res["p4_dev_needed_sudos_to_add"] = check_needed_sudos({"sudo_rights": res["p4_dev_sudo_rights"]}, needed_sudos)

            # store in results list (no return possible for a thread)
            results[index] = res

        # external host thread
        def ext_host(results, index):
            res = {}
            res["ext_host_ssh_ping"] = self.check_ssh_ping(cfg["ext_host_ssh"])
            if res["ext_host_ssh_ping"]:
                res["ext_host_sudo_rights"] = self.check_sudo(cfg["ext_host_user"], cfg["ext_host_ssh"])
                res["ext_host_fetched_ipv4"], res["ext_host_fetched_mac"], res["ext_host_fetched_prefix"], res["ext_host_up_state"] = self.check_iface(cfg["ext_host_user"], cfg["ext_host_ssh"], cfg["ext_host_if"])
                res["ext_host_needed_sudos_to_add"] = check_needed_sudos({"sudo_rights": res["ext_host_sudo_rights"]}, ["/usr/bin/pkill", "/usr/bin/killall", "/home/" + cfg["ext_host_user"] + "/p4sta/receiver/pythonRawSocketExtHost.py"])
                # check pip modules
                try:
                    answer = self.execute_ssh(cfg["ext_host_user"], cfg["ext_host_ssh"], "python3 -c 'import pkgutil; print(1 if pkgutil.find_loader(\"setproctitle\") else 0)'")
                    res["ext_host_pip_check"] = answer[0] == "1"
                except:
                    res["ext_host_pip_check"] = False
                # store in results list (no return possible for a thread)
                results[index] = res

        # load generators threads
        def loadgen(host, results, index):
            res = {}
            res["ssh_ping"] = self.check_ssh_ping(host["ssh_ip"])
            if res["ssh_ping"]:
                if "namespace_id" in host:
                    res["fetched_ipv4"], res["fetched_mac"], res["fetched_prefix"], res["up_state"] = self.check_iface(host['ssh_user'], host['ssh_ip'], host['loadgen_iface'], host["namespace_id"])
                else:
                    res["fetched_ipv4"], res["fetched_mac"], res["fetched_prefix"], res["up_state"] = self.check_iface(host['ssh_user'], host['ssh_ip'], host['loadgen_iface'], "")

                res["sudo_rights"] = self.check_sudo(host['ssh_user'], host['ssh_ip'])
                res["needed_sudos_to_add"] = check_needed_sudos({"sudo_rights": res["sudo_rights"]}, ["/sbin/ethtool", "/sbin/reboot", "/sbin/ifconfig", "/bin/ip"])
                res["ip_routes"] = self.check_routes(host['ssh_user'], host['ssh_ip'])
                res["namespaces"] = self.check_namespaces(host['ssh_user'], host['ssh_ip'])

            else:
                res["sudo_rights"] = ["not reachable"]
                res["needed_sudos_to_add"] = []
                res["fetched_ipv4"], res["fetched_mac"], res["fetched_prefix"], res["up_state"] = ("", "", "", "down")
                res["ip_routes"] = []
                res["namespaces"] = []
            results[index] = res

        # start threads
        threads = list()
        x = threading.Thread(target=stamper, args=(results, 0))
        threads.append(x)
        x.start()
        x = threading.Thread(target=ext_host, args=(results, 1))
        threads.append(x)
        x.start()

        ind = 2
        for host in cfg["loadgen_servers"] + cfg["loadgen_clients"]:
            x = threading.Thread(target=loadgen, args=(host, results, ind))
            threads.append(x)
            x.start()
            ind = ind + 1

        for thread in threads:
            thread.join()

        # collecting all results
        for i in range(0, 2):
            if results[i] is not None:
                cfg = {**cfg, **results[i]}
            else:
                print("### results[" + str(i) + "] = NONE ###")

        ind = 2
        for host in cfg["loadgen_servers"] + cfg["loadgen_clients"]:
            host["ssh_ping"] = results[ind]["ssh_ping"]
            host["sudo_rights"] = results[ind]["sudo_rights"]
            host["needed_sudos_to_add"] = results[ind]["needed_sudos_to_add"]
            host["fetched_ipv4"] = results[ind]["fetched_ipv4"]
            host["fetched_mac"] = results[ind]["fetched_mac"]
            host["fetched_prefix"] = results[ind]["fetched_prefix"]
            host["up_state"] = results[ind]["up_state"]
            host["ip_routes"] = results[ind]["ip_routes"]
            host["namespaces"] = results[ind]["namespaces"]
            ind = ind + 1

        return cfg


if __name__ == '__main__':
    s = rpyc.utils.server.ThreadedServer(P4staCore(), port=6789, protocol_config={'allow_all_attrs': True, 'allow_public_attrs': True, 'sync_request_timeout': 10})
    s.start()
