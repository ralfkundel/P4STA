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
from pathlib import Path

# custom python modules
from core import P4STA_utils

# globals
from management_ui import globals


def setup_devices(request):
    if request.method == "POST":
        print(request.POST)
        setup_devices_cfg = {}
        if request.POST.get("enable_stamper") == "on":
            setup_devices_cfg["stamper_user"] = request.POST["stamper_user"]
            setup_devices_cfg["stamper_ssh_ip"] = request.POST["stamper_ip"]
            setup_devices_cfg["selected_stamper"] = request.POST[
                "selected_stamper"]
            target_cfg = globals.core_conn.root.get_target_cfg(
                setup_devices_cfg["selected_stamper"])
            setup_devices_cfg["target_specific_dict"] = {}
            if "config" in target_cfg \
                    and "stamper_specific" in target_cfg["config"]:
                for cfg in target_cfg["config"]["stamper_specific"]:
                    if cfg["target_key"] in request.POST:
                        setup_devices_cfg["target_specific_dict"][
                            cfg["target_key"]] = request.POST[
                            cfg["target_key"]]

        if request.POST.get(
                "enable_ext_host") == "on" and "ext_host_user" in request.POST:
            setup_devices_cfg["ext_host_user"] = request.POST["ext_host_user"]
            setup_devices_cfg["ext_host_ssh_ip"] = request.POST["ext_host_ip"]
            setup_devices_cfg["selected_extHost"] = request.POST[
                "selected_extHost"]

        setup_devices_cfg["selected_loadgen"] = request.POST[
            "selected_loadgen"]
        setup_devices_cfg["loadgens"] = []
        for i in range(1, 99):
            if ("loadgen_user_" + str(i)) in request.POST:
                loadgen = {"loadgen_user": request.POST[
                                "loadgen_user_" + str(i)],
                           "loadgen_ssh_ip": request.POST[
                                "loadgen_ip_" + str(i)]}
                setup_devices_cfg["loadgens"].append(loadgen)

        print("===================================================")
        print("=== Setup Device Config from management UI:  ======")
        print("===================================================")
        print(setup_devices_cfg)
        # only create install script if button is clicked
        if "create_setup_script_button" in request.POST:
            globals.core_conn.root.write_install_script(setup_devices_cfg)

            # now write config.json with new data
            if request.POST.get("enable_stamper") == "on":
                path = globals.core_conn.root.get_template_cfg_path(
                    request.POST["selected_stamper"])
                cfg = globals.core_conn.root.open_cfg_file(path)
                cfg["stamper_ssh"] = request.POST["stamper_ip"]
                cfg["stamper_user"] = request.POST["stamper_user"]
                if request.POST.get(
                        "enable_ext_host") == "on" \
                        and "ext_host_user" in request.POST:
                    cfg["ext_host_user"] = request.POST["ext_host_user"]
                    cfg["ext_host_ssh"] = request.POST["ext_host_ip"]
                    cfg["selected_extHost"] = request.POST["selected_extHost"]
                cfg["selected_loadgen"] = request.POST["selected_loadgen"]

                # add all loadgens to loadgen group 1 and 2
                cfg["loadgen_groups"] = [
                    {"group": 1, "loadgens": [], "use_group": "checked"},
                    {"group": 2, "loadgens": [], "use_group": "checked"}]
                grp1 = setup_devices_cfg["loadgens"][
                       len(setup_devices_cfg["loadgens"]) // 2:]
                grp2 = setup_devices_cfg["loadgens"][
                       :len(setup_devices_cfg["loadgens"]) // 2]
                id_c = 1
                for loadgen in grp1:
                    cfg["loadgen_groups"][0]["loadgens"].append(
                        {"id": id_c, "loadgen_iface": "", "loadgen_ip": "",
                         "loadgen_mac": "", "real_port": "",
                         "p4_port": "", "ssh_ip": loadgen["loadgen_ssh_ip"],
                         "ssh_user": loadgen["loadgen_user"]})
                    id_c = id_c + 1
                id_c = 1
                for loadgen in grp2:
                    cfg["loadgen_groups"][1]["loadgens"].append(
                        {"id": id_c, "loadgen_iface": "", "loadgen_ip": "",
                         "loadgen_mac": "", "real_port": "",
                         "p4_port": "", "ssh_ip": loadgen["loadgen_ssh_ip"],
                         "ssh_user": loadgen["loadgen_user"]})
                    id_c = id_c + 1

                if globals.core_conn.root.check_first_run():
                    P4STA_utils.write_config(cfg)
            globals.core_conn.root.first_run_finished()
            return HttpResponseRedirect("/run_setup_script/")

        # cancel case
        globals.core_conn.root.first_run_finished()
        return HttpResponseRedirect("/")

    else:  # request the page
        print("### Setup Devices #####")
        params = {}
        params["stampers"] = P4STA_utils.flt(
            globals.core_conn.root.get_all_targets())
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
            # directly converting to json style because True
            # would be uppercase otherwise => JS needs "true"
            all_target_cfg[stamper] = P4STA_utils.flt(
                globals.core_conn.root.get_stamper_target_obj(
                    target_name=stamper).target_cfg)
        params["all_target_cfg"] = json.dumps(all_target_cfg)
        return render(request, "middlebox/setup_page.html", {**params})


def skip_setup_redirect_to_config(request):
    print("First run finished (skip setup): skip_setup_redirect_to_config")
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
    print("stop_shellinabox_redirect_to_config")
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
