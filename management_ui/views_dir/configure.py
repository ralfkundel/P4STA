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
import rpyc
import time
import traceback

from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import render

# custom python modules
from core import P4STA_utils

# globals
from management_ui import globals


def get_all_targets():
    targets = P4STA_utils.flt(globals.core_conn.root.get_all_targets())
    return targets


def fetch_iface(request):
    if not request.method == "POST":
        return
    try:
        results = globals.core_conn.root.fetch_interface(
            request.POST["user"], request.POST["ssh_ip"],
            request.POST["iface"], request.POST["namespace"])
        ipv4, mac, prefix, up_state, iface_found = results
    except Exception as e:
        ipv4 = mac = prefix = up_state = "timeout"
        globals.logger.error("Exception fetch iface: " + str(e))
    return JsonResponse({"mac": mac, "ip": ipv4, "prefix": prefix,
                         "up_state": up_state, "iface_found": iface_found})


def fetch_target(request):
    if not request.method == "POST":
        return
    try:
        target = str(request.POST["target"])
        globals.logger.debug("fetching target " + target)
        
        # filter ext hosts for p4sta version if available
        if "p4sta_version" in request.POST:
            p4sta_version = request.POST["p4sta_version"]
            target_cfg = globals.core_conn.root.fetch_target(target, p4sta_version)
        else:
            target_cfg = globals.core_conn.root.fetch_target(target)

        results = P4STA_utils.flt(target_cfg)

        return JsonResponse({"target": results})
    except:
        globals.logger.error(traceback.format_exc())
        return JsonResponse({"target": str(traceback.format_exc())})
    


def set_iface(request):
    if request.method == "POST":
        set_iface = globals.core_conn.root.set_interface(
            request.POST["user"], request.POST["ssh_ip"],
            request.POST["iface"], request.POST["iface_ip"],
            request.POST["namespace"])

        return JsonResponse({"error": set_iface})


def status_overview(request):
    try:
        status_overview = rpyc.timed(
            globals.core_conn.root.status_overview, 60)()
        status_overview.wait()
        cfg = status_overview.value
        cfg = P4STA_utils.flt(cfg)
        if cfg["selected_loadgen"] == "Tofino Packet Generator":
            # do not display loadgen groups in "Current Status" GUI, nothing to check
            cfg["loadgen_groups"] = []

        return render(request, "middlebox/output_status_overview.html", cfg)
    except Exception as e:
        globals.logger.error(traceback.format_exc())
        return render(request, "middlebox/timeout.html", {
            "inside_ajax": True, "error": ("stamper status error: " + str(e))})


def updateCfg(request):
    cfg = P4STA_utils.read_current_cfg()
    target_cfg = globals.core_conn.root.get_target_cfg()

    try:
        # if target has changed first request all port config again
        if cfg["selected_target"] is not request.POST["target"]:
            cfg["selected_target"] = request.POST["target"]
            cfg = P4STA_utils.flt(cfg)
            P4STA_utils.write_config(cfg)
            target_cfg = globals.core_conn.root.get_target_cfg()

        cfg["selected_loadgen"] = request.POST["selected_loadgen"]
        loadgen_cfg = P4STA_utils.flt(globals.core_conn.root.get_loadgen_obj(cfg["selected_loadgen"]).loadgen_cfg)

        cfg["selected_extHost"] = request.POST["selected_extHost"]

        # rebuild loadgen_groups list based on user choice
        if len(cfg["loadgen_groups"]) != int(request.POST["num_loadgen_groups"]):
            cfg["loadgen_groups"] = []
            for i in range(1, int(request.POST["num_loadgen_groups"]) + 1):
                cfg["loadgen_groups"].append({"group": i, "loadgens": []})

        # only parse POST when selected loadgen requires ssh ip, user, loadgen ip, ...
        needs_cfg = "configure_page_inputs" in loadgen_cfg and loadgen_cfg["configure_page_inputs"]

        for loadgen_grp in cfg["loadgen_groups"]:
            num_servers = int(request.POST["num_grp_" + str(loadgen_grp["group"])])
            
            servers = []
            i = 1
            _grp = str(loadgen_grp["group"])
            for j in range(1, num_servers + 1):
                s = {"id": j}
                _key = "s" + _grp + "_" + str(i) + "_real_port"
                while _key not in request.POST:
                    i += 1
                    if i == 99:
                        break
                if needs_cfg:    
                    s["real_port"] = str(request.POST["s" + _grp + "_" + str(i) + "_real_port"])
                    s["p4_port"] = -1
                    s["ssh_ip"] = str(request.POST["s" + _grp + "_" + str(i) + "_ssh_ip"])
                    s["ssh_user"] = str(request.POST["s" + _grp + "_" + str(i) + "_ssh_user"])
                    s["loadgen_iface"] = str(request.POST["s" + _grp + "_" + str(i) + "_loadgen_iface"])
                    s["loadgen_mac"] = str(request.POST["s" + str(loadgen_grp["group"]) + "_" + str(i) + "_loadgen_mac"])
                    s["loadgen_ip"] = str(request.POST["s" + _grp + "_" + str(i) + "_loadgen_ip"]).split(" ")[0].split("/")[0]
                else:
                    if "s" + _grp + "_" + str(i) + "_real_port" in request.POST:
                        port = str(request.POST["s" + _grp + "_" + str(i) + "_real_port"])
                    else:
                        port = ""
                    s["real_port"] = port
                    s["p4_port"] = port
                    s["ssh_ip"] = ""
                    s["ssh_user"] = ""
                    s["loadgen_iface"] = ""
                    s["loadgen_mac"] = ""
                    s["loadgen_ip"] = ""

                if "s" + _grp + "_" + str(i) + "_namespace" in request.POST and needs_cfg:
                    s["namespace_id"] = str(request.POST["s" + str(loadgen_grp["group"]) + "_" + str(i) + "_namespace"])
                
                if True: #needs_cfg:
                    # read target specific config from webinterface
                    for t_inp in target_cfg["inputs"]["input_table"]:
                        try:
                            if "s" + _grp + "_" + str(i) + "_" + \
                                    t_inp["target_key"] in request.POST:
                                s[t_inp["target_key"]] = str(
                                    request.POST["s" + str(
                                        loadgen_grp["group"])
                                                + "_"
                                                + str(i)
                                                + "_"
                                                + t_inp["target_key"]])
                            elif "restrict" not in t_inp \
                                    or t_inp["restrict"] == "loadgen":
                                s[t_inp["target_key"]] = ""
                        except Exception as e:
                            globals.logger.error("\n#\nError parsing special target "
                                "config parameters:" + str(e))
                servers.append(s)
                i += 1
            
            if str(request.POST["add_to_grp_" + _grp]) == "1":
                s = {}
                s["id"] = num_servers + 1
                s["real_port"] = ""
                s["p4_port"] = ""
                s["loadgen_ip"] = ""
                s["ssh_ip"] = ""
                s["ssh_user"] = ""
                s["loadgen_iface"] = ""
                # add default values to target specific inputs
                for t_inp in target_cfg["inputs"]["input_table"]:
                    if "default_value" in t_inp:
                        s[t_inp["target_key"]] = t_inp["default_value"]
                    else:
                        s[t_inp["target_key"]] = ""
                servers.append(s)
                globals.logger.debug("created loadgen: " + str(s))

            # set target specific default values
            for s in servers:
                for t_inp in target_cfg["inputs"]["input_table"]:
                    if "default_value" in t_inp and t_inp["target_key"] in s \
                            and s[t_inp["target_key"]] == "":
                        s[t_inp["target_key"]] = t_inp["default_value"]

            loadgen_grp["loadgens"] = servers

        cfg["dut_ports"] = []
        for loadgen_grp in cfg["loadgen_groups"]:
            cfg["dut_ports"].append({"id": loadgen_grp["group"]})

        try:  # read target specific config from webinterface
            for t_inp in target_cfg["inputs"]["input_individual"]:
                if t_inp["target_key"] in request.POST:
                    cfg[t_inp["target_key"]] = str(
                        request.POST[t_inp["target_key"]])
                else:
                    cfg[t_inp["target_key"]] = ""

            for t_inp in target_cfg["inputs"]["input_table"]:
                for dut in cfg["dut_ports"]:
                    if "dut" + str(dut["id"]) + "_" + t_inp["target_key"] \
                            in request.POST:
                        dut[t_inp["target_key"]] = str(
                            request.POST["dut" + str(dut["id"]) + "_" + t_inp[
                                "target_key"]])
                    elif "restrict" not in t_inp or t_inp["restrict"] == "dut":
                        dut[t_inp["target_key"]] = ""

                    if "default_value" in t_inp \
                            and dut[t_inp["target_key"]] == "":
                        dut[t_inp["target_key"]] = t_inp["default_value"]

                if "ext_host_" + t_inp["target_key"] in request.POST:
                    cfg["ext_host_" + t_inp["target_key"]] = str(
                        request.POST["ext_host_" + t_inp["target_key"]])
                elif "restrict" not in t_inp \
                        or t_inp["restrict"] == "ext_host":
                    cfg["ext_host_" + t_inp["target_key"]] = ""

                if "default_value" in t_inp \
                        and ("ext_host_" + t_inp["target_key"]) in cfg \
                        and cfg["ext_host_" + t_inp["target_key"]] == "":
                    cfg["ext_host_" + t_inp["target_key"]] = \
                        t_inp["default_value"]
                
                # second ext host case
                try:
                    if "second_ext_host_" + t_inp["target_key"] in request.POST:
                        cfg["second_ext_host_" + t_inp["target_key"]] = str(
                            request.POST["second_ext_host_" + t_inp["target_key"]])
                    elif "restrict" not in t_inp \
                            or t_inp["restrict"] == "second_ext_host":
                        cfg["second_ext_host_" + t_inp["target_key"]] = ""

                    if "default_value" in t_inp \
                            and ("second_ext_host_" + t_inp["target_key"]) in cfg \
                            and cfg["second_ext_host_" + t_inp["target_key"]] == "":
                        cfg["second_ext_host_" + t_inp["target_key"]] = \
                            t_inp["default_value"]
                except:
                    globals.logger.warning(traceback.format_exc())

        except Exception as e:
            globals.logger.error(traceback.format_exc())

        cfg["ext_host_real"] = str(request.POST["ext_host_real"])
        cfg["ext_host"] = -1

        # check if second,third, ... dut port should be used or not
        for dut in cfg["dut_ports"]:
            if int(dut["id"]) == 1:
                dut["use_port"] = "checked"
            else:
                try:
                    if "dut_" + str(dut["id"]) + "_use_port" in request.POST:
                        dut["use_port"] = request.POST[
                            "dut_" + str(dut["id"]) + "_use_port"]
                    else:
                        dut["use_port"] = "unchecked"
                except Exception:
                    dut["use_port"] = "checked"

            for loadgen_grp in cfg["loadgen_groups"]:
                if loadgen_grp["group"] == dut["id"]:
                    loadgen_grp["use_group"] = dut["use_port"]

            try:
                if "dut_" + str(dut["id"]) + "_outgoing_stamp" in request.POST:
                    dut["stamp_outgoing"] = str(request.POST["dut_" + str(
                        dut["id"]) + "_outgoing_stamp"])
                else:
                    dut["stamp_outgoing"] = "unchecked"
            except Exception:
                globals.logger.error(traceback.format_exc())
                dut["stamp_outgoing"] = "checked"

            if "dut" + str(dut["id"]) + "_real" in request.POST:
                dut["real_port"] = str(
                    request.POST["dut" + str(dut["id"]) + "_real"])
                dut["p4_port"] = -1
            else:
                dut["real_port"] = ""
                dut["p4_port"] = ""

        # additional ports config
        try:
            additional_ports_counter = int(request.POST["additional_ports_counter"])
            
            # generate config from POST, overwrite additional_ports in cfg
            additional_ports = []
            for i in range(additional_ports_counter):
                indx = i + 1 # port id starts at 1
                port = {"id": indx}

                key = "additional_" + str(indx) + "_real_port"
                if key in request.POST:
                    port["real_port"] = request.POST[key]
                    port["p4_port"] = -1
                else:
                    globals.logger.debug(key + " not found in request.POST")
                
                for t_inp in target_cfg["inputs"]["input_table"]:        
                    # for dut in cfg["dut_ports"]:
                    key = "additional_" + str(indx) + "_" + t_inp["target_key"]
                    if key in request.POST:
                        port[t_inp["target_key"]] = str(request.POST[key])
                    elif "restrict" not in t_inp or t_inp["restrict"] == "dut":
                        port[t_inp["target_key"]] = ""

                    if "default_value" in t_inp and port[t_inp["target_key"]] == "":
                        port[t_inp["target_key"]] = t_inp["default_value"]

                additional_ports.append(port)

            cfg["additional_ports"] = additional_ports

        except:
            globals.logger.error(traceback.format_exc())

        cfg["multicast"] = str(request.POST["multicast"])
        cfg["stamper_ssh"] = str(request.POST["stamper_ssh"])
        cfg["ext_host_ssh"] = str(request.POST["ext_host_ssh"])
        cfg["ext_host_user"] = str(request.POST["ext_host_user"])
        cfg["stamper_user"] = str(request.POST["stamper_user"])
        cfg["ext_host_if"] = str(request.POST["ext_host_if"])
        cfg["ext_host_ip"] = str(request.POST["ext_host_ip"]).split(" ")[0].split("/")[0]
        cfg["ext_host_mac"] = str(request.POST["ext_host_mac"])

        try:
            print(request.POST)
            if "second_ext_host_ssh" in request.POST:
                cfg["second_ext_host"] = -1
                cfg["second_ext_host_ssh"] = str(request.POST["second_ext_host_ssh"])
                cfg["second_ext_host_user"] = str(request.POST["second_ext_host_user"])
                cfg["second_ext_host_if"] = str(request.POST["second_ext_host_if"])
                # only true if fields are not greyed out (same host/iface for second host)
                if "ip" in request.POST:
                    cfg["second_ext_host_ip"] = str(request.POST["second_ext_host_ip"]).split(" ")[0].split("/")[0]
                    cfg["second_ext_host_mac"] = str(request.POST["second_ext_host_mac"])
                    cfg["second_ext_host_real"] = str(request.POST["second_ext_host_real"])
            else:
                # explicitly remove second_ext_host config 
                to_pop = []
                for key, _value in cfg.items():
                    if key.find("second_ext_host_") > -1:
                        to_pop.append(key)
                for key in to_pop:
                    cfg.pop(key)
        except:
            globals.logger.warning(traceback.format_exc())

        cfg["program"] = str(request.POST["program"])
        cfg["forwarding_mode"] = str(request.POST["forwarding_mode"])

        if "stamp_tcp" in request.POST:
            cfg["stamp_tcp"] = "checked"
        else:
            cfg["stamp_tcp"] = "unchecked"
        if "stamp_udp" in request.POST:
            cfg["stamp_udp"] = "checked"
        else:
            cfg["stamp_udp"] = "unchecked"

        # save config to file "database"
        globals.logger.info("write config.json to /data")
        globals.logger.debug(cfg)
        cfg = P4STA_utils.flt(cfg)
        P4STA_utils.write_config(cfg)

        return True, cfg

    except Exception as e:
        globals.logger.error(traceback.format_exc())

        return False, cfg


# input from configure page and reloads configure page
def configure_page(request):
    if globals.core_conn.root.check_first_run():
        globals.logger.info("FIRST RUN! Redirect to /setup_devices")
        return HttpResponseRedirect("/setup_devices")
    
    saved = ""
    target_cfg = P4STA_utils.flt(globals.core_conn.root.get_target_cfg())

    if type(target_cfg) == dict and "error" in target_cfg:
        return render(request, "middlebox/timeout.html",
                      {**target_cfg, **{"inside_ajax": False}})

    if request.method == "POST":
        saved, cfg = updateCfg(request)
        target_cfg = P4STA_utils.flt(globals.core_conn.root.get_target_cfg())
    else:
        cfg = P4STA_utils.read_current_cfg()
    cfg["target_cfg"] = target_cfg

    
    loadgen_obj = globals.core_conn.root.get_loadgen_obj(cfg["selected_loadgen"])
    cfg["loadgen_cfg"] = P4STA_utils.flt(loadgen_obj.loadgen_cfg)

    # The following config updates are only for UI representation

    if "packet_generator_ports" in target_cfg:
        num_pipes = len(cfg["target_cfg"]["packet_generator_ports"])
        if cfg["selected_loadgen"] != "Tofino Packet Generator":
            num_pipes = 50 + num_pipes  # do not limit number of pipes (= max loagen ports) for non-tofino loadgens
    else:
        num_pipes = 99
    cfg["max_loadgen_ports"] = num_pipes

    targets_without_selected = []
    all_targets = get_all_targets()
    for target in all_targets:
        if cfg["selected_target"] != target:
            targets_without_selected.append(target)
    cfg["targets_without_selected"] = targets_without_selected
    cfg["all_available_targets"] = all_targets

    # make all target configs available for javascript
    # all_target_cfgs = []
    # for t in all_targets:
    #     all_target_cfgs.append(P4STA_utils.flt(globals.core_conn.root.get_target_cfg(t)))
    # cfg["all_target_cfgs"] = all_target_cfgs

    available_cfg_files = P4STA_utils.flt(
        globals.core_conn.root.get_available_cfg_files())

    final_sorted_by_target = []

    for target in sorted(all_targets):
        found = False
        final_sorted_by_target.append("###" + target)
        for elem in available_cfg_files:
            if elem.find(target) > -1:
                final_sorted_by_target.append(elem)
                found = True
        if not found:
            del final_sorted_by_target[-1]

    cfg["available_configs"] = final_sorted_by_target

    cfg["saved"] = saved

    loadgens_without_selected = globals.core_conn.root.get_all_loadGenerators()
    if cfg["selected_loadgen"] in loadgens_without_selected:
        loadgens_without_selected.remove(cfg["selected_loadgen"])
    cfg["loadgens_without_selected"] = P4STA_utils.flt(
        loadgens_without_selected)

    # exthosts_without_selected = globals.core_conn.root.get_all_extHost()
    p4sta_ver = ""
    if cfg != None and "p4sta_version" in cfg:
        p4sta_ver = cfg["p4sta_version"]
    exthosts_without_selected = globals.core_conn.root.fetch_target(cfg["selected_target"], p4sta_ver)["supported_ext_hosts"]
    if cfg["selected_extHost"] in exthosts_without_selected:
        exthosts_without_selected.remove(cfg["selected_extHost"])
    cfg["exthosts_without_selected"] = P4STA_utils.flt(
        exthosts_without_selected)

    # if field "p4_ports" in target config,
    # target uses separate hardware ports & p4 ports (e.g. tofino)
    # now only hw (front) ports are left but relabeled as
    # "ports" and p4-ports are ignored
    # ports_list in abstract_target creates mapping 1->1    
    cfg["port_mapping"] = "p4_ports" in target_cfg
    cfg["cfg_json"] = json.dumps(cfg)
    cfg["cfg"] = cfg  # needed for dynamic target input_individual

    return render(request, "middlebox/page_config.html", cfg)


def create_new_cfg_from_template(request):
    path = globals.core_conn.root.get_template_cfg_path(
        request.POST["selected_cfg_template"])
    with open(path, "r") as f:
        cfg = json.load(f)
        P4STA_utils.write_config(cfg)
        globals.logger.info("Created new config from template: " + str(path))
    return HttpResponseRedirect("/")


def open_selected_config(request):
    cfg = P4STA_utils.read_current_cfg(request.POST["selected_cfg_file"])
    # check if old style cfg is used and convert to new style
    if "dut1_real" in cfg and "loadgen_clients" in cfg:
        globals.logger.info("old config structure -> converting to new style....")
        cfg["dut_ports"] = [{"id": 1}, {"id": 2}]
        cfg["dut_ports"][0]["p4_port"] = cfg.pop("dut1")
        cfg["dut_ports"][0]["real_port"] = cfg.pop("dut1_real")
        cfg["dut_ports"][0]["stamp_outgoing"] = cfg.pop("dut_1_outgoing_stamp")
        cfg["dut_ports"][0]["use_port"] = "checked"

        cfg["dut_ports"][1]["p4_port"] = cfg.pop("dut2")
        cfg["dut_ports"][1]["real_port"] = cfg.pop("dut2_real")
        cfg["dut_ports"][1]["stamp_outgoing"] = cfg.pop("dut_2_outgoing_stamp")
        cfg["dut_ports"][1]["use_port"] = cfg.pop("dut_2_use_port")

        to_del = []
        for key, value in cfg.items():
            if key.find("dut1") > -1 or key.find("dut2") > -1:
                to_del.append(key)
        for key in to_del:
            cfg.pop(key)

        cfg["loadgen_groups"] = [
            {"group": 1, "loadgens": [], "use_group": "checked"},
            {"group": 2, "loadgens": [], "use_group": "checked"}]
        for host in cfg["loadgen_servers"]:
            cfg["loadgen_groups"][0]["loadgens"].append(host)
        cfg.pop("loadgen_servers")
        for host in cfg["loadgen_clients"]:
            cfg["loadgen_groups"][1]["loadgens"].append(host)
        cfg.pop("loadgen_clients")

    P4STA_utils.write_config(cfg)
    return HttpResponseRedirect("/")


def delete_selected_config(request):
    name = request.POST["selected_cfg_file"]
    if name == "config.json":
        globals.logger.warning("Deletion of config.json denied.")
        return
    os.remove(os.path.join(globals.project_path, "data", name))
    return HttpResponseRedirect("/")


def save_config_as_file(request):
    saved, cfg = updateCfg(request)
    time_created = time.strftime('%d.%m.%Y-%H:%M:%S', time.localtime())
    file_name = cfg["selected_target"] + "_" + str(time_created) + ".json"
    P4STA_utils.write_config(cfg, file_name)
    return HttpResponseRedirect("/")


def delete_namespace(request):
    if request.method == "POST":
        if "namespace" in request.POST and "user" in request.POST \
                and "ssh_ip" in request.POST:
            ns = request.POST["namespace"]
            user = request.POST["user"]
            ssh_ip = request.POST["ssh_ip"]
            worked = globals.core_conn.root.delete_namespace(ns, user, ssh_ip)
            if worked:
                return JsonResponse({"error": False})
    return JsonResponse({"error": True})
