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
import datetime
import importlib
import json
import multiprocessing
import os
import rpyc
from rpyc.utils.classic import obtain
import shutil
import subprocess
import sys
import time
import threading
import traceback
from pathlib import Path
from tabulate import tabulate

import P4STA_utils
import P4STA_logger

import pdb

dir_path = os.path.dirname(os.path.realpath(__file__))
project_path = dir_path[0:dir_path.find("/core")]
sys.path.append(project_path)
try:
    from analytics import analytics
except Exception as e:
    # prevent PEP3 warning because sys append must be before
    raise e

first_run = False


class P4staCore(rpyc.Service):
    all_targets = {}
    all_extHosts = {}
    all_loadGenerators = {}
    measurement_id = -1  # will be set when external host is started
    method_return = None
    logger = P4STA_logger.create_logger("#core")

    # special var for tofino stamper and loadgen to share grpc connection
    tofino_grpc_obj = None

    # current state of stop_external_background thread
    stop_ext_bckgrd_thread = None

    def get_project_path(self):
        return project_path

    def __init__(self):
        global first_run
        first_run = False
        self.logger.info("Initialize P4STA core ...")
        P4STA_utils.set_project_path(project_path)

        # Find installed Targets
        fullpath = os.path.join(project_path, "stamper_targets")
        dirs = [d for d in os.listdir(fullpath) if
                os.path.isdir(os.path.join(fullpath, d))]
        for dir in dirs:
            config_path = os.path.join(fullpath, dir, "target_config.json")
            if os.path.isfile(config_path):
                # we found a target
                with open(config_path, "r") as f:
                    cfg = json.load(f)
                    cfg["real_path"] = os.path.join(fullpath, dir)
                    self.all_targets.update({cfg["target"]: cfg})

        # Find installed extHosts
        fullpath = os.path.join(project_path, "extHost")
        dirs = [d for d in os.listdir(fullpath) if
                os.path.isdir(os.path.join(fullpath, d))]
        for dir in dirs:
            config_path = os.path.join(fullpath, dir, "extHost_config.json")
            if os.path.isfile(config_path):
                # we found a extHost
                with open(config_path, "r") as f:
                    cfg = json.load(f)
                    cfg["real_path"] = os.path.join(fullpath, dir)
                    self.all_extHosts.update({cfg["name"]: cfg})

        fullpath = os.path.join(project_path, "loadGenerators")
        dirs = [d for d in os.listdir(fullpath) if
                os.path.isdir(os.path.join(fullpath, d))]
        for dir in dirs:
            config_path = os.path.join(fullpath, dir,
                                       "loadGenerator_config.json")
            if os.path.isfile(config_path):
                # we found a load generator
                with open(config_path, "r") as f:
                    cfg = json.load(f)
                    cfg["real_path"] = os.path.join(fullpath, dir)
                    self.all_loadGenerators.update({cfg["name"]: cfg})
        self.logger.debug("Available load generators: " + str(self.all_loadGenerators))

        self.check_first_run()


        # def tofino_grpc_obj_debug_thr(core):
        #     print("init tofino_grpc_obj_debug_thr")
        #     old = core.tofino_grpc_obj
        #     new = None
        #     while True:
        #         time.sleep(0.1)
        #         new = core.tofino_grpc_obj
        #         if new != old:
        #             print("P4staCore.tofino_grpc_obj changed to " + str(new))
        #             old = new

        # import threading
        # x = threading.Thread(target=tofino_grpc_obj_debug_thr, args=(self, ))
        # x.start()

    def check_first_run(self):
        global first_run

        if P4STA_utils.read_current_cfg() is None:
            self.logger.debug("config.json not found. Creating new one from empty Wedge100B65 template.")
            path = self.get_template_cfg_path("Wedge100B65")
            if not os.path.exists(os.path.join(project_path, "data")):
                # create data directory if not exist
                os.makedirs(os.path.join(project_path, "data"))
            with open(path, "r") as f:
                cfg = json.load(f)
                P4STA_utils.write_config(cfg)
            first_run = True

        return first_run

    def first_run_finished(self):
        global first_run
        first_run = False

    def write_install_script(self, first_time_cfg, p4sta_version=""):
        install_script = []
        if "stamper_user" in first_time_cfg:
            stamper_name = first_time_cfg["selected_stamper"]
            stamper_target = self.get_stamper_target_obj(stamper_name, p4sta_version)
            if "target_specific_dict" in first_time_cfg:
                target_specific_dict = first_time_cfg["target_specific_dict"]
            else:
                target_specific_dict = {}
            install_script.extend(stamper_target.get_server_install_script(
                user_name=first_time_cfg["stamper_user"],
                ip=first_time_cfg["stamper_ssh_ip"],
                target_specific_dict=target_specific_dict))
            install_script.append("")
        if "ext_host_user" in first_time_cfg:
            ext_host_name = first_time_cfg["selected_extHost"]
            ext_host = self.get_extHost_obj(ext_host_name)
            install_script.extend(ext_host.get_server_install_script(
                user_name=first_time_cfg["ext_host_user"],
                ip=first_time_cfg["ext_host_ssh_ip"]))
            install_script.append("")

        loadgen = self.get_loadgen_obj(first_time_cfg["selected_loadgen"])
        install_script.extend(
            loadgen.get_server_install_script(first_time_cfg["loadgens"]))

        with open("autogen_scripts/install_server.sh", "w") as f:
            for line in install_script:
                f.write(line + "\n")
            f.close()
            os.chmod("autogen_scripts/install_server.sh", 0o777)

    # returns an instance of current selected target config object
    # if version is not defined, version from current config is used
    def get_stamper_target_obj(self, target_name="", version=""):
        target_description = self.all_targets[target_name]

        fail = False
        try:
            if version == "":
                cfg = P4STA_utils.read_current_cfg()
                if cfg != None and "p4sta_version" in cfg:
                    version = cfg["p4sta_version"]
                else:
                    fail = True
            
            if target_name == "":
                cfg = P4STA_utils.read_current_cfg()
                if "selected_target" in cfg:
                    target_name = cfg["selected_target"]
                else:
                    fail = True


            if "available_target_drivers" in target_description:
                for driver in target_description["available_target_drivers"]:
                    if driver["version"] == version:
                        driver = driver["target_driver"]
                        break
                else:
                    fail = True
        except:
            self.logger.error(traceback.format_exc())
            fail = True

        # use default driver if available drivers is not found in target config file
        if fail:
            driver = target_description["default_target_driver"]
            
        path_to_driver = (os.path.join(target_description["real_path"], driver))

        spec = importlib.util.spec_from_file_location("TargetImpl",
                                                      path_to_driver)
        foo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(foo)
        get_stamper_obj = foo.TargetImpl(target_description, self.logger)
        get_stamper_obj.setRealPath(target_description["real_path"])

        return get_stamper_obj

    def get_extHost_obj(self, name):
        host_description = self.all_extHosts[name]
        path_to_driver = (os.path.join(host_description["real_path"],
                                       host_description["driver"]))

        spec = importlib.util.spec_from_file_location("ExtHostImpl",
                                                      path_to_driver)
        foo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(foo)
        get_ext_host_obj = foo.ExtHostImpl(host_description, self.logger)
        get_ext_host_obj.setRealPath(host_description["real_path"])

        return get_ext_host_obj

    def get_current_extHost_obj(self):
        return self.get_extHost_obj(
            P4STA_utils.read_current_cfg()["selected_extHost"])

    # returns an instance of current selected load generator object
    def get_loadgen_obj(self, name):
        # loadgen_description: content of loadGenerator_config.json
        loadgen_description = self.all_loadGenerators[name]

        self.logger.debug("loadgen_description = " + str(loadgen_description))

        # include stamper config for loadgen 
        loadgen_description["current_stamper_cfg"] = self.get_target_cfg()

        # include stamper object for loadgen
        # loadgen_description["current_stamper_obj"] = self.get_stamper_target_obj()

        path_to_driver = (os.path.join(loadgen_description["real_path"],
                                       loadgen_description["driver"]))

        spec = importlib.util.spec_from_file_location("LoadGeneratorImpl", path_to_driver)
        foo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(foo)
        loadgen_obj = foo.LoadGeneratorImpl(loadgen_description, self.logger)
        loadgen_obj.setRealPath(loadgen_description["real_path"])

        return loadgen_obj

    def get_all_extHost(self):
        lst = []
        for extH in self.all_extHosts.keys():
            lst.append(extH)
        return lst
    
    def get_all_extHostDicts(self):
        lst = []
        for extH in self.all_extHosts.values():
            lst.append(extH)
        return lst

    def get_all_targets(self):
        lst = []
        for target in self.all_targets.keys():
            lst.append(target)
        return lst

    def get_all_loadGenerators(self):
        lst = []
        for loadgen in self.all_loadGenerators.keys():
            lst.append(loadgen)
        return lst

    def get_target_cfg(self, target_name="", version=""):
        # version not required in get_target_cfg as it just loads the json file
        try:
            if target_name == "":
                t_name = P4STA_utils.read_current_cfg()["selected_target"]
            else:
                t_name = target_name
            target = self.get_stamper_target_obj(t_name, version)
            with open(os.path.join(target.realPath, "target_config.json"),
                      "r") as f:
                return json.load(f)
        except Exception:
            self.logger.error("CORE Exception in get_target_cfg: " + traceback.format_exc())
            return {}

    def get_available_cfg_files(self):
        lst = []
        folder_path = os.path.join(project_path, "data")
        all_files = [f for f in os.listdir(folder_path) if
                     os.path.isfile(os.path.join(folder_path, f))]
        for f in all_files:
            if f == "config.json":
                continue
            if f.endswith(".json"):
                lst.append(f)
        try:
            date_time_objects = []
            all_targets = self.get_all_targets()
            for filename in lst:
                # only match json files with valid names like bmv2_
                match = False
                for target in all_targets:
                    if filename.startswith(target):
                        match = True
                        break
                if match:
                    # e.g. tofino_model_01.08.2020-16:19:06.json
                    datestr = filename.split("_")[-1].split(".json")[0]
                    date_time_objects.append([filename,
                                              datetime.datetime.strptime(
                                                  datestr,
                                                  '%d.%m.%Y-%H:%M:%S')])
            # now sort list of date_list by date (index 1)
            date_time_objects.sort(key=lambda x: x[1], reverse=True)

            final = []
            for time_list in date_time_objects:
                final.append(time_list[0])

            return final
        except Exception:
            self.logger.error(traceback.format_exc())
            return lst

    def read_result_cfg(self, run_id, silent=False):
        path = os.path.join(project_path, "results", str(run_id),
                            "config_" + str(run_id) + ".json")
        return self.open_cfg_file(path, silent)
    
    def get_custom_name_by_id(self, measurement_id, silent=False):
        measurement_id = str(measurement_id)
        try:
            if measurement_id != None and measurement_id.isdigit() and int(measurement_id) > 0:
                cfg = self.read_result_cfg(measurement_id, silent)
                if "custom_name" in cfg:
                    return cfg["custom_name"]
        except:
            pass
        return ""


    def get_template_cfg_path(self, stamper_target_name):
        target = self.get_stamper_target_obj(stamper_target_name)
        path = target.getFullTemplatePath()
        return path

    def open_cfg_file(self, path, silent=False):
        my_file = Path(path)
        if not my_file.is_file():
            if not silent:
                self.logger.warning("open_cfg_file: " + path + "; not found.")
            return None
        with open(path, "r") as f:
            cfg = json.load(f)
            return cfg

    def delete_by_id(self, file_id):
        try:
            shutil.rmtree(P4STA_utils.get_results_path(file_id))
        except Exception as e:
            self.logger.error(traceback.format_exc())

    def getAllMeasurements(self):
        found = []
        try:
            folder = os.path.join(project_path, "results")
            for f in os.listdir(folder):
                path_to_res_folder = os.path.join(folder, f)
                if os.path.isdir(path_to_res_folder):
                    for file in os.listdir(path_to_res_folder):
                        if "stamper_" in file:
                            found.append(f)
        except FileNotFoundError:
            self.logger.warning("Directory 'results' not found. No older datasets available.")
        found.sort(reverse=True)
        return found

    def getLatestMeasurementId(self):
        all = self.getAllMeasurements()
        if len(all) > 0:
            last = all[0]
            return last
        return None

    def start_loadgens(self, duration, l4_selected="tcp",
                       packet_size_mtu="1500", loadgen_rate_limit=0,
                       loadgen_flows=3, loadgen_server_groups=[1], loadgen_cfg={}, custom_name=""):
        cfg = P4STA_utils.read_current_cfg()
        loadgen = self.get_loadgen_obj(cfg["selected_loadgen"])

        if type(custom_name) == str:
            cfg["custom_name"] = custom_name
        else:
            cfg["custom_name"] = ""
        P4STA_utils.write_config(cfg)
        self.copy_cfg_to_results()

        # self.tofino_grpc_obj can always be None
        if self.tofino_grpc_obj != None:
            # check if connection is established or broken
            if "tables" in self.tofino_grpc_obj.bfruntime_info:
                loadgen_cfg["tofino_grpc_obj"] = self.tofino_grpc_obj
            else:
                try:
                    # Remove broken grpc object
                    loadgen_cfg["tofino_grpc_obj"] = None
                    self.tofino_grpc_obj.teardown()
                    self.tofino_grpc_obj = None
                except:
                    self.logger.error(traceback.format_exc())

        ret = loadgen.run_loadgens(str(P4staCore.measurement_id), duration,
                             l4_selected, packet_size_mtu,
                             self.get_current_results_path(),
                             loadgen_rate_limit, loadgen_flows,
                             loadgen_server_groups,
                             loadgen_cfg)
        
        if ret != None and "tofino_grpc_obj" in ret:
            self.tofino_grpc_obj = ret["tofino_grpc_obj"]
        
        return P4staCore.measurement_id

    # after loadgen test
    def process_loadgens(self, file_id):
        cfg = self.read_result_cfg(file_id)
        loadgen = self.get_loadgen_obj(cfg["selected_loadgen"])
        results = loadgen.process_loadgen_data(
            str(file_id), P4STA_utils.get_results_path(file_id))

        output, total_bits, error, total_retransmits, \
            total_byte, custom_attr, to_plot = results

        if not error:
            self.logger.debug(to_plot)
            for key, value in to_plot.items():
                self.logger.debug("key: " + key + "  value: " + str(value))
                analytics.plot_graph(value["value_list_input"],
                                     value["index_list"], value["titel"],
                                     value["x_label"],
                                     value["y_label"], value["filename"],
                                     value["adjust_unit"],
                                     value["adjust_y_ax"], file_id)

            with open(os.path.join(P4STA_utils.get_results_path(file_id),
                                   "output_loadgen_" + str(file_id) + ".txt"),
                      "w+") as f:
                f.write("Used Loadgenerator: " + loadgen.get_name())
                f.write("Total meaured speed: " + str(
                    analytics.find_unit_bit_byte(total_bits, "bit")[0]) + " " +
                        analytics.find_unit_bit_byte(total_bits, "bit")[
                            1] + "/s" + "\n")
                f.write("Total measured throughput: " + str(
                    analytics.find_unit_bit_byte(total_byte, "byte")[
                        0]) + " " +
                        analytics.find_unit_bit_byte(total_byte, "byte")[
                            1] + "\n")
                f.write("Total retransmitted packets: " + str(
                    total_retransmits) + " Packets" + "\n")

                for key, value in custom_attr["elems"].items():
                    try:
                        f.write(value + "\n")
                    except Exception:
                        pass

        return output, total_bits, error, total_retransmits, \
            total_byte, custom_attr, to_plot
    
    def update_port_mapping(self, target=None, tofino_grpc_obj=None):
        try:
            cfg = P4STA_utils.read_current_cfg()
            if target == None:
                target = self.get_stamper_target_obj(cfg["selected_target"])
            if hasattr(target, 'update_portmapping') and callable(target.update_portmapping):
                self.logger.warning("tofino_grpc_obj => " + str(tofino_grpc_obj))
                if tofino_grpc_obj != None and "p4sta_version" in cfg and cfg["p4sta_version"] not in ["", "1.0.0", "1.2.0", "1.2.1"]:
                    cfg = target.update_portmapping(cfg, tofino_grpc_obj)
                else:
                    cfg = target.update_portmapping(cfg)
                P4STA_utils.write_config(cfg)
                return cfg
            else:
                self.logger.debug("Target does not support update_portmapping(). Do nothing.")
                return cfg
        except:
            self.logger.error(traceback.format_exc())

    def deploy(self):
        cfg = P4STA_utils.read_current_cfg()
        target = self.get_stamper_target_obj(cfg["selected_target"])

        mapped_cfg = self.update_port_mapping(target, self.tofino_grpc_obj)

        # ensure p4sta v1.3.0 or newer
        if  "p4sta_version" in cfg and cfg["p4sta_version"] not in ["", "1.0.0", "1.2.0", "1.2.1"]:
            self.logger.debug("reuse tofino_grpc_obj")
            error = target.deploy(mapped_cfg, self.tofino_grpc_obj)
        else:
            error = target.deploy(mapped_cfg)
        if error is not None and error != "":
            self.logger.error(error)
        return error

    def ping(self):
        cfg = P4STA_utils.read_current_cfg()
        output = []

        use_port_counter = 0
        for dut in cfg["dut_ports"]:
            if dut["use_port"] == "checked":
                use_port_counter = use_port_counter + 1
        if use_port_counter > 1:
            for loadgen_grp in cfg["loadgen_groups"]:
                for host in loadgen_grp["loadgens"]:
                    for loadgen_grp2 in cfg["loadgen_groups"]:
                        if loadgen_grp is not loadgen_grp2:
                            output += ['-----------------------',
                                       'Host: ' + host['loadgen_ip'],
                                       '-----------------------']
                            for dst_host in loadgen_grp2["loadgens"]:
                                output += P4STA_utils.execute_ssh(
                                    host["ssh_user"], host["ssh_ip"],
                                    self.check_ns(
                                        host) + " timeout 1 ping " + str(
                                        dst_host[
                                            "loadgen_ip"]) + " -i 0.2 -c 3")
        elif use_port_counter == 1:
            for loadgen_grp in cfg["loadgen_groups"]:
                if loadgen_grp["use_group"] == "checked":
                    for host in loadgen_grp["loadgens"]:
                        for dst_host in loadgen_grp["loadgens"]:
                            if host["id"] != dst_host["id"]:
                                output += P4STA_utils.execute_ssh(
                                    host["ssh_user"], host["ssh_ip"],
                                    self.check_ns(
                                        host) + " timeout 1 ping " + str(
                                        dst_host[
                                            "loadgen_ip"]) + " -i 0.2 -c 3")

        return output

    def read_stamperice(self):
        # after loadgen run is finished always set tofino specific grpc to None
        target = self.get_stamper_target_obj(P4STA_utils.read_current_cfg()["selected_target"])
        if self.tofino_grpc_obj != None:
            cfg = target.read_stamperice(P4STA_utils.read_current_cfg(), self.tofino_grpc_obj)
        else:
            # non-tofino case
            cfg = target.read_stamperice(P4STA_utils.read_current_cfg())

        self.logger.info("Writing stamper results json to " + str(self.get_current_results_path()))
        try:
            os.makedirs(self.get_current_results_path())
        except FileExistsError:
            # directory already exists
            pass
        with open(os.path.join(self.get_current_results_path(),
                               "stamper_" + str(
                                       P4staCore.measurement_id) + ".json"),
                  "w+") as write_json:
            json.dump(cfg, write_json, indent=2, sort_keys=True)
        self.logger.debug("Finished writing json.")

        if cfg["delta_counter"] == 0:
            average = 0
        else:
            average = cfg["total_deltas"] / cfg["delta_counter"]

        with open(os.path.join(self.get_current_results_path(),
                               "output_stamperice_" + str(
                                       P4staCore.measurement_id) + ".txt"),
                  "w+") as f:
            try:
                f.write(
                    "###################################"
                    "#############################################\n")
                f.write("######## Results from Stamper for ID " + str(
                    P4staCore.measurement_id) + " from " + str(
                    time.strftime('%H:%M:%S %d.%m.%Y', time.localtime(
                        int(P4staCore.measurement_id)))) + " ########\n")
                f.write(
                    "#### The chosen ID results from the time"
                    " where the external hosts started. #####\n")
                f.write(
                    "#######################################"
                    "#########################################\n\n")
                f.write("Measured for all timestamped packets:" + "\n")
                f.write("Average Latency: " + str(
                    round(analytics.find_unit([average])[0][0],
                          2)) + " " + str(
                    analytics.find_unit([average])[1]) + "\n")
                f.write("Min Latency: " + str(
                    analytics.find_unit([cfg["min_delta"]])[0][0]) + " " + str(
                    analytics.find_unit([cfg["min_delta"]])[1]) + "\n")
                f.write("Max Latency: " + str(
                    analytics.find_unit([cfg["max_delta"]])[0][0]) + " " + str(
                    analytics.find_unit([cfg["max_delta"]])[1]) + "\n\n")
                f.write("Measured for all timestamped packets:" + "\n")
                # Store packetloss between dut port and destination ports
                # (where flows arrives after egressing dut)
                num_ingress_packets = 0
                num_egress_packets = 0
                num_ingress_stamped_packets = 0
                num_egress_stamped_packets = 0
                packetloss_percent = 0
                packetloss_percent_stamped = 0
                for dut in cfg["dut_ports"]:
                    if dut["use_port"] == "checked":
                        num_ingress_packets += dut["num_ingress_packets"]
                        num_egress_packets += dut["num_egress_packets"]
                        num_ingress_stamped_packets += dut[
                            "num_ingress_stamped_packets"]
                        num_egress_stamped_packets += dut[
                            "num_egress_stamped_packets"]

                packetloss = num_egress_packets - num_ingress_packets
                packetloss_stamped = \
                    num_egress_stamped_packets - num_ingress_stamped_packets
                if num_egress_packets > 0:
                    packetloss_percent = round(
                        (packetloss / num_egress_packets) * 100, 2)
                if num_egress_stamped_packets > 0:
                    packetloss_percent_stamped = round(
                        (packetloss_stamped / num_egress_stamped_packets
                         ) * 100, 2)

                f.write("Packetloss for DUT: " + str(
                    packetloss_stamped) + " of " + str(
                    num_egress_stamped_packets) + " Packets (" + str(
                    packetloss_percent_stamped) + "%)" + "\n")
                f.write("Measured for all packets (on port base):" + "\n")
                f.write(
                    "Packetloss for DUT: " + str(packetloss) + " of " + str(
                        num_egress_packets) + " Packets (" + str(
                        packetloss_percent) + "%)" + "\n")
            except Exception:
                self.logger.error(traceback.format_exc())
                f.write("\n Exception:")
                f.write("\n" + str(traceback.format_exc()))

            for word in ["", "_stamped"]:
                if word == "_stamped":
                    f.write("\n\nMeasured for timestamped packets only:")
                else:
                    f.write("\nMeasure for all packets:")
                f.write(
                    "\n----------------- INGRESS -----------------||"
                    "|---------------- EGRESS ------------------\n")

                table = [
                    ["IN", "GBytes", "Packets", "Ave Size (Byte)", "GBytes",
                     "Packets", "Ave Size (Byte)", "OUT"]]
                try:
                    for loadgen_grp in cfg["loadgen_groups"]:
                        if loadgen_grp["use_group"] == "checked":
                            for host in loadgen_grp["loadgens"]:
                                selected_dut = {}
                                for dut in cfg["dut_ports"]:
                                    if loadgen_grp["group"] == dut["id"]:
                                        selected_dut = dut
                                        break
                                try:
                                    table.append(
                                        [host["real_port"],
                                         round(host["num_ingress" + word +
                                                    "_bytes"] / 1000000000, 2),
                                         host["num_ingress" +
                                              word + "_packets"],
                                         round(host["num_ingress" + word +
                                                    "_bytes"] / host[
                                            "num_ingress" + word + "_packets"],
                                                        2),
                                         round(selected_dut["num_egress" +
                                                            word + "_bytes"
                                                            ] / 1000000000, 2),
                                         selected_dut["num_egress" + word +
                                                      "_packets"],
                                         round(selected_dut["num_egress" +
                                                            word + "_bytes"] /
                                               selected_dut["num_egress" +
                                                            word + "_packets"],
                                               2),
                                         selected_dut["real_port"]])
                                except ZeroDivisionError:
                                    table.append(
                                        [host["real_port"], "err: could be 0",
                                         host[
                                            "num_ingress" + word + "_packets"],
                                         "err: could be 0",
                                         "err: could be 0", selected_dut[
                                             "num_egress" + word + "_packets"],
                                         "err: could be 0",
                                         selected_dut["real_port"]])

                    for loadgen_grp in cfg["loadgen_groups"]:
                        if loadgen_grp["use_group"] == "checked":
                            for host in loadgen_grp["loadgens"]:
                                selected_dut = {}
                                for dut in cfg["dut_ports"]:
                                    if loadgen_grp["group"] == dut["id"]:
                                        selected_dut = dut
                                        break
                                try:
                                    table.append(
                                        [selected_dut["real_port"],
                                         round(selected_dut["num_ingress" +
                                                            word + "_bytes"] /
                                               1000000000, 2),
                                         selected_dut["num_ingress" + word +
                                                      "_packets"],
                                         round(selected_dut["num_ingress" +
                                                            word + "_bytes"] /
                                               selected_dut["num_ingress" +
                                                            word + "_packets"],
                                               2),
                                         round(host["num_egress" + word +
                                                    "_bytes"] / 1000000000,
                                               2), host["num_egress" + word +
                                                        "_packets"],
                                         round(host["num_egress" + word +
                                                    "_bytes"] / host[
                                             "num_egress" + word + "_packets"],
                                         2),
                                         host["real_port"]])

                                except ZeroDivisionError:
                                    table.append(
                                        [host["real_port"], "err: could be 0",
                                         host[
                                            "num_ingress" + word + "_packets"],
                                         "err: could be 0",
                                         "err: could be 0", selected_dut[
                                             "num_egress" + word + "_packets"],
                                         "err: could be 0",
                                         selected_dut["real_port"]])

                except Exception as e:
                    self.logger.error(traceback.format_exc())
                    table.append(["Error: " + str(e)])
                # creates table with the help of tabulate module
                f.write(tabulate(table, tablefmt="fancy_grid"))

    def stamper_results(self, file_id):
        def adjust_byte_unit(val):
            if round(val / 1000000000, 2) > 1:
                return str(round(val / 1000000000, 2)) + " GB"
            elif round(val / 1000000, 2) > 1:
                return str(round(val / 1000000, 2)) + " MB"
            else:
                return str(round(val / 1000, 2)) + " kB"

        time_created = "not available"
        try:
            time_created = time.strftime('%H:%M:%S %d.%m.%Y',
                                         time.localtime(int(file_id)))
        except Exception:
            pass
        try:
            results_path = P4STA_utils.get_results_path(file_id)
            my_file = Path(results_path + "/stamper_" + str(file_id) + ".json")
            if not my_file.is_file():
                # to maintain backward compatibility try for p4_dev_ instead
                my_file2 = Path(
                    results_path + "/p4_dev_" + str(file_id) + ".json")
                if not my_file2.is_file():
                    raise Exception(
                        "stamper_" + str(file_id) + ".json or p4_dev_" + str(
                            file_id) + ".json not found in " + results_path)
                else:
                    file_str = "/p4_dev_"
            else:
                file_str = "/stamper_"
            with open(P4STA_utils.get_results_path(file_id) + file_str + str(
                    file_id) + ".json", "r") as file:
                sw = json.load(file)
        except Exception as e:
            self.logger.error("CORE Exception: " + traceback.format_exc())
            return {"error": traceback.format_exc()}
        if sw["delta_counter"] != 0:
            average = sw["total_deltas"] / sw["delta_counter"]
        else:
            average = 0
        range_delta = sw["max_delta"] - sw["min_delta"]
        sw["average"] = analytics.find_unit([average])
        sw["min_delta"] = analytics.find_unit(sw["min_delta"])
        sw["max_delta"] = analytics.find_unit(sw["max_delta"])
        sw["range"] = analytics.find_unit(range_delta)
        sw["pkt"] = sw["delta_counter"]
        sw["time"] = time_created
        sw["filename"] = file_id

        ###################################################
        #          compute avg packet sizes ###############
        #          compute total throughput ###############
        ###################################################

        for dut in sw["dut_ports"]:
            if dut["use_port"] == "checked":
                if dut["num_ingress_packets"] > 0:
                    dut["avg_packet_size_ingress"] = round(
                        dut["num_ingress_bytes"] / dut["num_ingress_packets"],
                        1)
                else:
                    dut["avg_packet_size_ingress"] = 0
                if dut["num_ingress_stamped_packets"] > 0:
                    dut["avg_packet_size_ingress_stamped"] = round(
                        dut["num_ingress_stamped_bytes"] / dut[
                            "num_ingress_stamped_packets"], 1)
                else:
                    dut["avg_packet_size_ingress_stamped"] = 0
                if dut["num_egress_packets"] > 0:
                    dut["avg_packet_size_egress"] = round(
                        dut["num_egress_bytes"] / dut["num_egress_packets"], 1)
                else:
                    dut["avg_packet_size_egress"] = 0
                if dut["num_egress_stamped_packets"] > 0:
                    dut["avg_packet_size_egress_stamped"] = round(
                        dut["num_egress_stamped_bytes"] / dut[
                            "num_egress_stamped_packets"], 1)
                else:
                    dut["avg_packet_size_egress_stamped"] = 0

                dut["throughput_gbyte_ingress"] = adjust_byte_unit(
                    dut["num_ingress_bytes"])
                dut["throughput_gbyte_ingress_stamped"] = adjust_byte_unit(
                    dut["num_ingress_stamped_bytes"])
                dut["throughput_gbyte_egress"] = adjust_byte_unit(
                    dut["num_egress_bytes"])
                dut["throughput_gbyte_egress_stamped"] = adjust_byte_unit(
                    dut["num_egress_stamped_bytes"])

        for loadgen_grp in sw["loadgen_groups"]:
            if loadgen_grp["use_group"] == "checked":
                for port in loadgen_grp["loadgens"]:
                    port["avg_packet_size_ingress"] = port[
                        "avg_packet_size_egress"] = 0
                    port["avg_packet_size_ingress_stamped"] = port[
                        "avg_packet_size_egress_stamped"] = 0
                    if port["num_ingress_packets"] > 0:
                        port["avg_packet_size_ingress"] = round(
                            port["num_ingress_bytes"] / port[
                                "num_ingress_packets"], 1)
                    if port["num_egress_packets"] > 0:
                        port["avg_packet_size_egress"] = round(
                            port["num_egress_bytes"] / port[
                                "num_egress_packets"], 1)
                    try:
                        if port["num_ingress_stamped_packets"] > 0:
                            port["avg_packet_size_ingress_stamped"] = round(
                                port["num_ingress_stamped_bytes"] / port[
                                    "num_ingress_stamped_packets"], 1)
                        if port["num_egress_stamped_packets"] > 0:
                            port["avg_packet_size_egress_stamped"] = round(
                                port["num_egress_stamped_bytes"] / port[
                                    "num_egress_stamped_packets"], 1)
                        port["throughput_gbyte_ingress_stamped"] = \
                            adjust_byte_unit(
                                port["num_ingress_stamped_bytes"])
                        port[
                            "throughput_gbyte_egress_stamped"] = \
                            adjust_byte_unit(
                                port["num_egress_stamped_bytes"])
                    # if target has stamped counter not implemented yet
                    except KeyError:
                        self.logger.warning("Stamped counter not implemented in target?" + traceback.format_exc())
                    port["throughput_gbyte_ingress"] = adjust_byte_unit(
                        port["num_ingress_bytes"])
                    port["throughput_gbyte_egress"] = adjust_byte_unit(
                        port["num_egress_bytes"])

        # ext_host ingress throughput is ignored
        sw["ext_host_throughput_egress"] = adjust_byte_unit(
            sw["ext_host_num_egress_bytes"])
        sw["ext_host_throughput_egress_stamped"] = adjust_byte_unit(
            sw["ext_host_num_egress_stamped_bytes"])
        if sw["ext_host_num_egress_packets"] > 0:
            sw["ext_host_avg_packet_size_egress"] = round(
                sw["ext_host_num_egress_bytes"] / sw[
                    "ext_host_num_egress_packets"], 1)
        else:
            sw["ext_host_avg_packet_size_egress"] = 0

        if sw["ext_host_num_egress_stamped_packets"] > 0:
            sw["ext_host_avg_packet_size_egress_stamped"] = round(
                sw["ext_host_num_egress_stamped_bytes"] / sw[
                    "ext_host_num_egress_stamped_packets"], 1)
        else:
            sw["ext_host_avg_packet_size_egress_stamped"] = 0

        ###################################################
        #          compute packet losses ##################
        ###################################################

        # if only one dut port is used dst_dut should be same, Store packetloss
        # between dut port and dst ports (where flows arrives after dut)
        num_ingress_packets = 0
        num_egress_packets = 0
        num_ingress_stamped_packets = 0
        num_egress_stamped_packets = 0
        for dut in sw["dut_ports"]:
            if dut["use_port"] == "checked":
                num_ingress_packets += dut["num_ingress_packets"]
                num_egress_packets += dut["num_egress_packets"]
                num_ingress_stamped_packets += dut[
                    "num_ingress_stamped_packets"]
                num_egress_stamped_packets += dut["num_egress_stamped_packets"]

        sw["dut_stats"] = {}
        sw["dut_stats"]["total_num_egress_packets"] = num_egress_packets
        sw["dut_stats"][
            "total_num_egress_stamped_packets"] = num_egress_stamped_packets

        count = 0
        checked_dut_indexes = []
        for dut in sw["dut_ports"]:
            if dut["use_port"] == "checked":
                checked_dut_indexes.append(count)
                count = count + 1

        # dual_port_mode activated if 2 dut ports are used
        # => calc packetloss for 2 separate flows
        sw["dut_stats"]["dut_dual_port_mode"] = (count == 2)

        if sw["dut_stats"]["dut_dual_port_mode"]:
            for i, z in [(0, 1), (1, 0)]:
                c_i = checked_dut_indexes[i]
                c_z = checked_dut_indexes[z]
                sw["dut_ports"][c_i]["packetloss"] = \
                    sw["dut_ports"][c_i]["num_egress_packets"] - \
                    sw["dut_ports"][c_z]["num_ingress_packets"]
                if sw["dut_ports"][c_i]["num_egress_packets"] > 0:
                    sw["dut_ports"][c_i]["packetloss_percent"] = round(
                        (sw["dut_ports"][c_i]["packetloss"] / sw[
                            "dut_ports"][c_i]["num_egress_packets"]) * 100, 2)
                else:
                    sw["dut_ports"][c_i]["packetloss_percent"] = 0
                sw["dut_ports"][c_i]["packetloss_stamped"] = \
                    sw["dut_ports"][c_i]["num_egress_stamped_packets"] - \
                    sw["dut_ports"][c_z]["num_ingress_stamped_packets"]
                if sw["dut_ports"][c_i]["num_egress_stamped_packets"] > 0:
                    sw["dut_ports"][c_i]["packetloss_stamped_percent"] = round(
                        (sw["dut_ports"][c_i]["packetloss_stamped"] / sw[
                            "dut_ports"][c_i][
                            "num_egress_stamped_packets"]) * 100, 2)
                else:
                    sw["dut_ports"][c_i]["packetloss_stamped_percent"] = 0

        sw["dut_stats"][
            "total_packetloss"] = num_egress_packets - num_ingress_packets
        if sw["dut_stats"]["total_packetloss"] > 0:
            sw["dut_stats"]["total_packetloss_percent"] = round(
                (sw["dut_stats"][
                     "total_packetloss"] / num_egress_packets) * 100, 2)
        else:
            sw["dut_stats"]["total_packetloss_percent"] = 0
        sw["dut_stats"]["total_packetloss_stamped"] = \
            num_egress_stamped_packets - num_ingress_stamped_packets
        if sw["dut_stats"]["total_packetloss_stamped"] > 0:
            sw["dut_stats"]["total_packetloss_stamped_percent"] = round(
                (sw["dut_stats"]["total_packetloss_stamped"] /
                 num_egress_stamped_packets) * 100, 2)
        else:
            sw["dut_stats"]["total_packetloss_stamped_percent"] = 0

        return sw

    # resets registers in p4 device
    def reset(self):
        target = self.get_stamper_target_obj(
            P4STA_utils.read_current_cfg()["selected_target"])
        ret_val = target.reset_p4_registers(P4STA_utils.read_current_cfg())
        if ret_val is None:
            ret_val = ""
        return ret_val

    def check_ns(self, host):
        if "namespace_id" in host:
            return "sudo ip netns exec " + str(host["namespace_id"])
        else:
            return ""

    def stamper_status(self):
        def check_host(host):
            pingresp = (os.system("timeout 1 ping " + host[
                "ssh_ip"] + " -c 1") == 0)  # if ping works it should be true
            host["reachable"] = pingresp
            if pingresp:
                output_host = "\n".join(
                    P4STA_utils.execute_ssh(host["ssh_user"], host["ssh_ip"],
                                            self.check_ns(
                                                host) + " sudo ethtool " +
                                            host["loadgen_iface"]))
                pos = output_host.find("Link detected")
                try:
                    if str(output_host[pos + 15:pos + 18]) == "yes":
                        host["link"] = "up"
                    else:
                        host["link"] = "down"
                except Exception:
                    host["link"] = "error"
            else:
                host["link"] = "down"

        cfg = P4STA_utils.read_current_cfg()
        target = self.get_stamper_target_obj(cfg["selected_target"])
        lines_pm, running, dev_status = target.stamper_status(cfg)

        threads = list()
        for loadgen_group in cfg["loadgen_groups"]:
            for host in loadgen_group["loadgens"]:
                x = threading.Thread(target=check_host, args=(host,))
                threads.append(x)
                x.start()

        for thread in threads:
            thread.join()

        return cfg, lines_pm, running, dev_status

    def start_stamper_software(self):
        cfg = P4STA_utils.read_current_cfg()
        target = self.get_stamper_target_obj(cfg["selected_target"])
        cfg = target.update_portmapping(cfg)
        P4STA_utils.write_config(cfg)
        return target.start_stamper_software(cfg)

    def get_stamper_startup_log(self):
        target = self.get_stamper_target_obj(
            P4STA_utils.read_current_cfg()["selected_target"])
        return target.get_stamper_startup_log(P4STA_utils.read_current_cfg())

    def stop_stamper_software(self):
        target = self.get_stamper_target_obj(
            P4STA_utils.read_current_cfg()["selected_target"])
        target.stop_stamper_software(P4STA_utils.read_current_cfg())

    def reboot(self):
        cfg = P4STA_utils.read_current_cfg()
        for loadgen_grp in cfg["loadgen_groups"]:
            for host in loadgen_grp["loadgens"]:
                P4STA_utils.execute_ssh(host["ssh_user"], host["ssh_ip"],
                                        "sudo reboot")

    def refresh_links(self):
        cfg = P4STA_utils.read_current_cfg()
        for loadgen_grp in cfg["loadgen_groups"]:
            for host in loadgen_grp["loadgens"]:
                P4STA_utils.execute_ssh(
                    host["ssh_user"], host["ssh_ip"],
                    self.check_ns(host) + " sudo ethtool -r " +
                    host["loadgen_iface"])

    def set_new_measurement_id(self):
        file_id = str(int(round(
            time.time())))  # generates name (time in sec since 1.1.1970)4
        P4staCore.measurement_id = file_id
        return file_id

    def get_current_results_path(self):
        return P4STA_utils.get_results_path(P4staCore.measurement_id)
    
    def copy_cfg_to_results(self):
        # backup current config (e.g. ports, speed) to results directory of *CURRENT* run
        if not os.path.exists(self.get_current_results_path()):
            os.makedirs(self.get_current_results_path())
        shutil.copy(project_path + "/data/config.json",
                    os.path.join(self.get_current_results_path(),
                                 "config_" + str(
                                     P4staCore.measurement_id) + ".json"))

    def start_external(self):
        file_id = str(P4staCore.measurement_id)
        cfg = P4STA_utils.read_current_cfg()
        target = self.get_stamper_target_obj(cfg["selected_target"])
        lines_pm, running, dev_status = target.stamper_status(cfg)
        
        # later overwritten when run loadgens is executed (for custom run name)
        self.copy_cfg_to_results()
        # # backup current config (e.g. ports, speed) to results directory
        # if not os.path.exists(self.get_current_results_path()):
        #     os.makedirs(self.get_current_results_path())
        # shutil.copy(project_path + "/data/config.json",
        #             os.path.join(self.get_current_results_path(),
        #                          "config_" + str(
        #                              P4staCore.measurement_id) + ".json"))

        multi = self.get_target_cfg()['stamping_capabilities']['timestamp-multi']
        tsmax = self.get_target_cfg()['stamping_capabilities']['timestamp-max']
        errors = ()
        if running:
            errors = self.get_current_extHost_obj().start_external(file_id,
                                                                   multi=multi,
                                                                   tsmax=tsmax)
        if errors != ():
            self.logger.error(errors)
        return running, errors

    # classic approach with blocking UI
    def stop_external(self):
        self.read_stamperice()
        try:
            if int(P4staCore.measurement_id) == -1:
                raise Exception

            stoppable = self.get_current_extHost_obj().stop_external(P4staCore.measurement_id)
        except Exception:
            stoppable = False

        return stoppable
    
    def write_live_stats_json(self, live_stats_list):
        try:
            path = P4STA_utils.get_results_path(P4staCore.measurement_id)
            with open(path + "/live_metrics_list.json", "w") as f:
                json.dump(P4STA_utils.flt(live_stats_list), f)
            self.logger.info("Stored live_metrics_list.json with num elements: " + str(len(live_stats_list)))
        except:
            self.logger.error(traceback.format_exc())
    
    # dynamic approach by retrieving results in background for non-blocking UI, current state can be retrieved with get_state_stop_external_background
    def stop_external_background(self, live_stats_list):
        def stp_xtnrl(slf, live_stats_list):
            try:
                slf.read_stamperice()
                if int(P4staCore.measurement_id) == -1:
                    raise Exception("Measurement ID is -1.")
                slf.write_live_stats_json(live_stats_list)
                stoppable = slf.get_current_extHost_obj().stop_external(P4staCore.measurement_id)
            except Exception:
                stoppable = False

            slf.stop_ext_bckgrd_thread = stoppable
            
        if self.stop_ext_bckgrd_thread == None or self.stop_ext_bckgrd_thread == True or self.stop_ext_bckgrd_thread == False:
            # x = multiprocessing.Process(target=stp_xtnrl, args=(self,))
            x = threading.Thread(target=stp_xtnrl, args=(self, live_stats_list))
            x.start()
            self.stop_ext_bckgrd_thread = x

    def get_state_stop_external_background(self):
        return self.stop_ext_bckgrd_thread
    
    def kill_external_background_process(self):
        if self.stop_ext_bckgrd_thread != None or self.stop_ext_bckgrd_thread != True or self.stop_ext_bckgrd_thread != False:
            self.logger.warning("Killing not implemented for threads")
            self.stop_ext_bckgrd_thread = None

    def stop_without_external(self):
        self.read_stamperice()
        return True

    # displays results from external host from return of analytics module
    def external_results(self, measurement_id):
        cfg = self.read_result_cfg(str(measurement_id))

        extH_results = analytics.main(str(measurement_id), cfg["multicast"],
                                      P4STA_utils.get_results_path(measurement_id),
                                      self.logger)
        f = open(P4STA_utils.get_results_path(
            measurement_id) + "/output_external_host_" + str(
            measurement_id) + ".txt", "w+")
        f.write("Results from externel Host for every " + str(
            cfg["multicast"] + ". packet") + "\n")
        f.write("Raw packets: " + str(
            extH_results["num_raw_packets"]) + " Processed packets: " + str(
            extH_results[
                "num_processed_packets"]) + " Total throughput: " + str(
            extH_results["total_throughput"]) + " Megabytes \n")
        f.write("Min latency: " + str(
            analytics.find_unit(extH_results["min_latency"])[0][
                0]) + " " + str(
            analytics.find_unit(extH_results["min_latency"])[1]))
        f.write(" Max latency: " + str(
            analytics.find_unit(extH_results["max_latency"])[0][
                0]) + " " + str(
            analytics.find_unit(extH_results["max_latency"])[1]))
        f.write(" Average latency: " + str(
            analytics.find_unit(extH_results["avg_latency"])[0][
                0]) + " " + str(
            analytics.find_unit(extH_results["avg_latency"])[1]) + "\n")
        f.write("Min IPDV: " + str(
            analytics.find_unit(extH_results["min_ipdv"])[0][0]) + " " + str(
            analytics.find_unit(extH_results["min_ipdv"])[1]) + "\n")
        f.write("Max IPDV: " + str(
            analytics.find_unit(extH_results["max_ipdv"])[0][0]) + " " + str(
            analytics.find_unit(extH_results["max_ipdv"])[1]) + "\n")
        f.write("Average IPDV: " + str(
            analytics.find_unit(extH_results["avg_ipdv"])[0][0]) + " " + str(
            analytics.find_unit(extH_results["avg_ipdv"])[1])
                + " and abs(): " + str(
            analytics.find_unit(extH_results["avg_abs_ipdv"])[0][
                0]) + " " + str(
            analytics.find_unit(extH_results["avg_abs_ipdv"])[1]) + "\n")
        f.write("Min PDV: " + str(
            analytics.find_unit(extH_results["min_pdv"])[0][0]) + " " + str(
            analytics.find_unit(extH_results["min_pdv"])[1]) + "\n")
        f.write("Max PDV: " + str(
            analytics.find_unit(extH_results["max_pdv"])[0][0]) + " " + str(
            analytics.find_unit(extH_results["max_pdv"])[1]) + "\n")
        f.write("Average PDV: " + str(
            analytics.find_unit(extH_results["avg_pdv"])[0][0]) + " " + str(
            analytics.find_unit(extH_results["avg_pdv"])[1]) + "\n")
        f.write("Min packet/s: " + str(
            extH_results["min_packets_per_second"]) + " Max packet/s: " + str(
            extH_results[
                "max_packets_per_second"]) + " Average packet/s: " + str(
            extH_results["avg_packets_per_second"]) + "\n")
        f.close()

    def fetch_interface(self, ssh_user, ssh_ip, iface, namespace=""):
        return P4STA_utils.fetch_interface(ssh_user, ssh_ip, iface, namespace)
    
    def fetch_target(self, target_name, p4sta_version=""):
        target_cfg = self.get_target_cfg(target_name=target_name, version=p4sta_version)
        
        # create list of supported ext hosts of this target
        supported_ext_hosts = []
        for ext_host in self.get_all_extHostDicts():
            for individual in target_cfg["inputs"]["input_individual"]:
                if individual["target_key"] == "p4sta_version":
                    for version in individual["values"]:
                        if version in ext_host["compatible_p4sta_versions"]:
                            if p4sta_version != "":
                                if ext_host["name"] not in supported_ext_hosts:
                                    if p4sta_version in ext_host["compatible_p4sta_versions"]:
                                        supported_ext_hosts.append(ext_host["name"])
                            else:
                                if ext_host["name"] not in supported_ext_hosts:
                                    supported_ext_hosts.append(ext_host["name"])
                    break
        
        target_cfg["supported_ext_hosts"] = supported_ext_hosts

        return target_cfg
        

    def set_interface(self, ssh_user, ssh_ip, iface, iface_ip, namespace=""):
        if namespace == "":
            line = subprocess.run(
                [project_path + "/core/scripts/setIP.sh", ssh_user, ssh_ip,
                 iface, iface_ip], stdout=subprocess.PIPE).stdout.decode(
                "utf-8")
        else:
            line = subprocess.run(
                [project_path + "/core/scripts/setIP_namespace.sh", ssh_user,
                 ssh_ip, iface, iface_ip, namespace],
                stdout=subprocess.PIPE).stdout.decode("utf-8")

        # error = return True; worked = return False
        return not (line.find("worked") > -1 and line.find(
            "ifconfig_success") > -1)

    def execute_ssh(self, user, ip_address, arg):
        return P4STA_utils.execute_ssh(user, ip_address, arg)

    def check_sudo(self, user, ip_address):
        return P4STA_utils.check_sudo(user, ip_address)

    def fetch_mtu(self, user, ip_address, iface, namespace=""):
        mtu = "0"
        if namespace != "":
            namespace = "sudo ip netns exec " + namespace + " "

        lines = self.execute_ssh(
            user, ip_address, namespace + "ip addr show " +
            iface + " | grep mtu")
        if len(lines) > 0:
            mtu_ind = lines[0].find("mtu")
            mtu = lines[0][mtu_ind + 4:].split(" ")[0]
            if not mtu.isdigit():
                mtu = "0"

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

        num_loadgens = 0
        for loadgen_group in cfg["loadgen_groups"]:
            num_loadgens = num_loadgens + len(loadgen_group["loadgens"])
        results = [None] * (
                    num_loadgens + 3)  # stores the return values from threads

        # start threads
        threads = list()
        x = threading.Thread(target=self.get_stamper_target_obj(
            cfg["selected_target"]).stamper_status_overview,
                             args=(results, 0, cfg))
        threads.append(x)
        x.start()
        x = threading.Thread(
            target=self.get_current_extHost_obj().ext_host_status_overview,
            args=(results, 1, cfg))
        threads.append(x)
        x.start()

        ind = 2
        for loadgen_group in cfg["loadgen_groups"]:
            if loadgen_group["use_group"] == "checked":
                for host in loadgen_group["loadgens"]:
                    x = threading.Thread(target=self.get_loadgen_obj(
                        cfg["selected_loadgen"]).loadgen_status_overview,
                                         args=(host, results, ind))
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
                self.logger.warning("### results[" + str(i) + "] = NONE ###")

        ind = 2
        for loadgen_group in cfg["loadgen_groups"]:
            if loadgen_group["use_group"] == "checked":
                for host in loadgen_group["loadgens"]:
                    host["ssh_ping"] = results[ind]["ssh_ping"]
                    host["sudo_rights"] = results[ind]["sudo_rights"]
                    host["needed_sudos_to_add"] = results[ind][
                        "needed_sudos_to_add"]
                    host["fetched_ipv4"] = results[ind]["fetched_ipv4"]
                    host["fetched_mac"] = results[ind]["fetched_mac"]
                    host["fetched_prefix"] = results[ind]["fetched_prefix"]
                    host["up_state"] = results[ind]["up_state"]
                    host["ip_routes"] = results[ind]["ip_routes"]
                    host["namespaces"] = results[ind]["namespaces"]
                    if "custom_checks" in results[ind]:
                        host["custom_checks"] = results[ind]["custom_checks"]
                    ind = ind + 1

        return cfg

    def get_live_metrics(self):
        cfg = P4STA_utils.read_current_cfg()
        target = self.get_stamper_target_obj(cfg["selected_target"])

        try:
            self.logger.debug("Get live metrics ..")
            metrics = target.get_live_metrics(cfg, tofino_grpc_obj=self.tofino_grpc_obj)
            self.logger.debug(metrics)
            # can be empty list here also, e.g. if target implements function but to old SDE gRPC API in tofino case
        except:
            # not all stamper targets support live metrics
            self.logger.error(traceback.format_exc())
            metrics = []

        # fallback set alle ports to 0 instead of empty list
        try:
            if metrics == []:
                dut_ports = [dut_p["p4_port"] for dut_p in cfg["dut_ports"]]
                for port in dut_ports:
                    p_res = {}
                    p_res["port"] = port
                    p_res["tx_rate"] = 0
                    p_res["rx_rate"] = 0
                    p_res["tx_pps"] = 0
                    p_res["rx_pps"] = 0
                    p_res["tx_avg_packet_size"] = 0
                    p_res["rx_avg_packet_size"] = 0
                    metrics.append(p_res)
        except:
            self.logger.error(traceback.format_exc())
            metrics = []

        return metrics

    def get_ext_host_live_status(self):
        ret_dict = {}
        ext_host_obj = self.get_current_extHost_obj()

        # retrieve current logs is threaded
        log_list, error_list = ext_host_obj.retrieve_current_logs()
        ret_dict = {"log_list": log_list, "error_list": error_list}

        if hasattr(ext_host_obj, "EXT_HOST_T1_DUPLICATION"):
            if ext_host_obj.EXT_HOST_T1_DUPLICATION:
                log_list_tstamp1_only, error_list_tstamp1_only = ext_host_obj.retrieve_current_logs("_tstamp1_only")
                ret_dict.update({"log_list_timestamp1_only": log_list_tstamp1_only, "error_list_timestamp1_only": error_list_tstamp1_only})
        
        if "provides_status_api" in ext_host_obj.host_cfg:
            if ext_host_obj.host_cfg["provides_status_api"]:
                if callable(getattr(ext_host_obj, "ext_host_live_status", None)):
                    try:
                        ret_dict.update(ext_host_obj.ext_host_live_status())
                    except Exception as e:
                        self.logger.error(traceback.format_exc())
       
        self.logger.debug("get_ext_host_live_status: " + str(ret_dict))
        return ret_dict


if __name__ == '__main__':
    core = P4staCore()
    s = rpyc.utils.server.ThreadedServer(
        core,
        hostname="127.0.0.1",
        port=6789,
        protocol_config={'allow_all_attrs': True, 'allow_public_attrs': True, 'sync_request_timeout': 10},
    )
    s.start()
