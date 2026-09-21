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
import subprocess
import time
import traceback
import zipfile

from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.datastructures import MultiValueDictKeyError
from pathlib import Path
from packaging.version import Version

# custom python modules
from core import P4STA_utils

# globals
from management_ui import globals


def get_all_session_module_cfgs():
    session_modules_path = Path(__file__).resolve().parents[2] / "session_modules"
    session_module_cfgs = {}
    for config_path in session_modules_path.glob("*/module_cfg.json"):
        with open(config_path, "r") as f:
            cfg = json.load(f)
            cfg["real_path"] = str(config_path.parent)
            session_module_cfgs[cfg["name"]] = cfg
    return session_module_cfgs


def parse_checkbox_group_values(request, cfg):
    allowed_values = {
        tuple(value) for value in cfg.get("values_to_select", [])
    }
    selected_values = []
    for value in request.POST.getlist(cfg["target_key"]):
        selected_value = json.loads(value)
        if len(allowed_values) > 0 and tuple(selected_value) not in allowed_values:
            globals.logger.warning(
                "Ignoring invalid checkbox-group value for " +
                cfg["target_key"] + ": " + value)
            continue
        selected_values.append(selected_value)
    return selected_values


def write_session_module_cfg(module_cfg):
    module_cfg_path = Path(module_cfg["real_path"]) / "module_cfg.json"
    cfg_to_write = {
        key: value for key, value in module_cfg.items()
        if key != "real_path"
    }
    with open(module_cfg_path, "w") as f:
        json.dump(cfg_to_write, f, indent="\t")
        f.write("\n")


def setup_devices(request):
    if request.method == "POST":
        p4sta_version = ""
        setup_devices_cfg = {}
        if request.POST.get("enable_stamper") == "on":
            setup_devices_cfg["stamper_user"] = request.POST["stamper_user"]
            setup_devices_cfg["stamper_ssh_ip"] = request.POST["stamper_ip"]
            setup_devices_cfg["selected_stamper"] = request.POST["selected_stamper"]
            target_cfg = globals.core_conn.root.get_target_cfg(setup_devices_cfg["selected_stamper"])
            setup_devices_cfg["target_specific_dict"] = {}
            if "config" in target_cfg and "stamper_specific" in target_cfg["config"]:
                for cfg in target_cfg["config"]["stamper_specific"]:
                    try:
                        if cfg["type"] == "input" and cfg["target_key"] in request.POST:
                            setup_devices_cfg["target_specific_dict"][cfg["target_key"]] = request.POST[cfg["target_key"]]
                        if cfg["type"] == "info":
                            setup_devices_cfg["target_specific_dict"][cfg["target_key"]] = cfg["target_value"]
                        if cfg["type"] == "drop-down":
                            # special case for p4sta_version
                            if cfg["target_key"] == "p4sta_version":
                                if "p4sta_version" in request.POST:
                                    for version in cfg["values"]:
                                        if version == request.POST["p4sta_version"]:
                                            p4sta_version = request.POST["p4sta_version"]
                            setup_devices_cfg["target_specific_dict"][cfg["target_key"]] = request.POST[cfg["target_key"]]
                        if cfg["type"] == "checkbox-group":
                            selected_values = parse_checkbox_group_values(
                                request, cfg)
                            setup_devices_cfg["target_specific_dict"][cfg["target_key"]] = selected_values
                    except MultiValueDictKeyError:
                        pass # if key is not in POST data, just skip it
                    except Exception as e:
                        globals.logger.error("Error processing target specific config for key " + cfg["target_key"] + ": " + str(e))
                        globals.logger.error(traceback.format_exc())

            session_module_name = setup_devices_cfg[
                "target_specific_dict"].get("session_module")
            if session_module_name is not None and session_module_name != "NONE" \
                    and p4sta_version and Version(p4sta_version) >= Version("1.4.0"):
                try:
                    session_module_cfg = get_all_session_module_cfgs()[
                        session_module_name]
                    if "config" in session_module_cfg and \
                            "setup_specific" in session_module_cfg["config"]:
                        session_module_cfg_changed = False
                        for cfg in session_module_cfg["config"]["setup_specific"]:
                            if cfg["type"] == "input":
                                value = request.POST.get(cfg["target_key"], "").strip()
                                if cfg.get("required", False) and not value \
                                        and "create_setup_script_button" in request.POST:
                                    return HttpResponse(
                                        cfg["title"] + " is required.", status=400)
                                setup_devices_cfg[cfg["target_key"]] = value
                            elif cfg["type"] == "checkbox-group":
                                selected_values = parse_checkbox_group_values(
                                    request, cfg)
                                setup_devices_cfg["target_specific_dict"][
                                    cfg["target_key"]] = selected_values
                                cfg["selected_values"] = selected_values
                                session_module_cfg_changed = True
                        if session_module_cfg_changed:
                            write_session_module_cfg(session_module_cfg)
                except Exception as e:
                    globals.logger.error(
                        "Error processing session module setup config for " +
                        session_module_name + ": " + str(e))
                    globals.logger.error(traceback.format_exc())

        if request.POST.get("enable_ext_host") == "on" and "ext_host_user" in request.POST:
            setup_devices_cfg["ext_host_user"] = request.POST["ext_host_user"]
            setup_devices_cfg["ext_host_ssh_ip"] = request.POST["ext_host_ip"]
            setup_devices_cfg["selected_extHost"] = request.POST["selected_extHost"]

        setup_devices_cfg["selected_loadgen"] = request.POST["selected_loadgen"]
        setup_devices_cfg["loadgens"] = []
        for i in range(1, 99):
            if ("loadgen_user_" + str(i)) in request.POST:
                loadgen = {"loadgen_user": request.POST[
                                "loadgen_user_" + str(i)],
                           "loadgen_ssh_ip": request.POST[
                                "loadgen_ip_" + str(i)]}
                setup_devices_cfg["loadgens"].append(loadgen)

        globals.logger.debug("=== Setup Device Config from management UI:  ======")
        globals.logger.debug(setup_devices_cfg)
        # only create install script if button is clicked
        if "create_setup_script_button" in request.POST:
            globals.core_conn.root.write_install_script(setup_devices_cfg, p4sta_version)

            # now write config.json with new data
            if request.POST.get("enable_stamper") == "on":
                path = globals.core_conn.root.get_template_cfg_path(
                    request.POST["selected_stamper"])
                cfg = globals.core_conn.root.open_cfg_file(path)
                cfg["stamper_ssh"] = request.POST["stamper_ip"]
                cfg["stamper_user"] = request.POST["stamper_user"]
                # Access and network interfaces share the session module host.
                for suffix in ("ssh", "user"):
                    key = "session_cp_" + suffix
                    if key in setup_devices_cfg:
                        cfg[key] = setup_devices_cfg[key]
                        cfg["session_cp2_" + suffix] = setup_devices_cfg[key]
                if request.POST.get(
                        "enable_ext_host") == "on" \
                        and "ext_host_user" in request.POST:
                    cfg["ext_host_user"] = request.POST["ext_host_user"]
                    cfg["ext_host_ssh"] = request.POST["ext_host_ip"]
                    cfg["selected_extHost"] = request.POST["selected_extHost"]
                cfg["selected_loadgen"] = request.POST["selected_loadgen"]

                if globals.core_conn.root.check_first_run():
                    # only overwrite when first run
                    P4STA_utils.write_config(cfg)

            globals.core_conn.root.first_run_finished()
            return HttpResponseRedirect("/run_setup_script/")

        # cancel case
        globals.core_conn.root.first_run_finished()
        return HttpResponseRedirect("/")

    else:  # request the page
        params = {}
        params["stampers"] = P4STA_utils.flt(globals.core_conn.root.get_all_targets())
        params["stampers"].sort(key=lambda y: y.lower())
        params["extHosts"] = P4STA_utils.flt(
            globals.core_conn.root.get_all_extHost())
        params["extHosts"].sort(key=lambda y: y.lower())
        # bring python on position 1
        if "PythonExtHost" in params["extHosts"]:
            params["extHosts"].insert(0, params["extHosts"].pop(
                params["extHosts"].index("PythonExtHost")))
        params["loadgens"] = P4STA_utils.flt(
            globals.core_conn.root.get_all_loadGenerators())
        params["loadgens"].sort(key=lambda y: y.lower())

        params["isFirstRun"] = globals.core_conn.root.check_first_run()

        all_target_cfg = {}
        for stamper in params["stampers"]:
            print("+++++++++++++++++++++++++++++++++++++++++++++++++++" + str(stamper))
            # directly converting to json style because True
            # would be uppercase otherwise => JS needs "true"
            stamper_obj = globals.core_conn.root.get_stamper_target_obj(target_name=stamper)
            print(stamper_obj)
            all_target_cfg[stamper] = P4STA_utils.flt(stamper_obj.target_cfg)

        all_session_module_cfg = P4STA_utils.flt(get_all_session_module_cfgs())

        if not globals.core_conn.root.check_first_run():
            params["current_cfg"] = P4STA_utils.read_current_cfg()

        for module_cfg in all_session_module_cfg.values():
            for opt in module_cfg.get("config", {}).get("setup_specific", []):
                if opt["type"] == "input":
                    opt["value"] = params.get("current_cfg", {}).get(
                        opt["target_key"], "")

        params["all_target_cfg"] = json.dumps(all_target_cfg)
        params["all_session_module_cfg"] = json.dumps(all_session_module_cfg)
        return render(request, "middlebox/setup_page.html", {**params})


def skip_setup_redirect_to_config(request):
    globals.core_conn.root.first_run_finished()
    return HttpResponseRedirect("/")


def run_setup_script(request):
    def bash_command(cmd):
        subprocess.Popen(['/bin/bash', '-c', cmd])

    bash_command(
        "sudo pkill shellinaboxd; shellinaboxd -p 4201 --disable-ssl "
        "-u $(id -u) --service /:${USER}:${USER}:${PWD}:./core/scripts"
        "/spawn_install_server_bash.sh")
    return render(request, "middlebox/run_setup_script_page.html", {})


def stop_shellinabox_redirect_to_config(request):
    def bash_command(cmd):
        subprocess.Popen(['/bin/bash', '-c', cmd])

    bash_command("sudo pkill shellinaboxd;")
    globals.logger.debug("stop_shellinabox_redirect_to_config")
    return HttpResponseRedirect("/")


def setup_ssh_checker(request):
    ssh_works = False
    ping_works = (os.system("timeout 1 ping " + request.POST[
        "ip"] + " -c 1") == 0)  # if ping works it should be true
    if ping_works:
        answer = P4STA_utils.execute_ssh(request.POST["user"],
                                         request.POST["ip"], "echo ssh_works")
        answer = list(answer)
        if len(answer) > 0 and answer[0] == "ssh_works":
            ssh_works = True

    return JsonResponse({"ping_works": ping_works, "ssh_works": ssh_works})
