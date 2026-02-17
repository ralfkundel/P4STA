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
import rpyc
import time
import traceback

from django.shortcuts import render
from django.http import JsonResponse

# for packet_templates_config()
# from scapy.all import *
# from scapy.contrib import gtp
# from management_ui.views_dir.scapy_patches.ppp import PPPoE, PPP  # Needed due to https://github.com/secdev/scapy/commit/3e6900776698cd5472c5405294414d5b672a3f18


# custom python modules
from analytics import analytics
from core import P4STA_utils

# globals
from management_ui import globals


def page_run(request):
    cfg = P4STA_utils.read_current_cfg()
    ext_host_obj = globals.core_conn.root.get_current_extHost_obj()
    cfg["ext_host_cfg"] = P4STA_utils.flt(ext_host_obj.host_cfg)
    return render(request, "middlebox/page_run.html", cfg)


# executes ping test
def ping(request):
    if P4STA_utils.is_ajax(request):
        try:
            output = globals.core_conn.root.ping()
            output = P4STA_utils.flt(output)
            return render(
                request, "middlebox/output_ping.html", {"output": output})
        except Exception as e:
            return render(
                request, "middlebox/timeout.html",
                {"inside_ajax": True, "error": ("ping error: " + str(e))})


def skip_external(request):
    if P4STA_utils.is_ajax(request):
        new_id = globals.core_conn.root.set_new_measurement_id()
        globals.logger.info("Set new measurement ID: " + str(new_id))
        cfg = P4STA_utils.read_current_cfg()

        # explicitly call copy cfg to results, for normal ext host its called in core
        globals.core_conn.root.copy_cfg_to_results()

        mtu_list = []
        for loadgen_grp in cfg["loadgen_groups"]:
            if loadgen_grp["use_group"] == "checked":
                for host in loadgen_grp["loadgens"]:
                    if "namespace_id" in host \
                            and host["namespace_id"] != "":
                        host["mtu"] = globals.core_conn.root.fetch_mtu(
                            host['ssh_user'], host['ssh_ip'],
                            host['loadgen_iface'], host["namespace_id"])
                    else:
                        host["mtu"] = globals.core_conn.root.fetch_mtu(
                            host['ssh_user'], host['ssh_ip'],
                            host['loadgen_iface'])
                    mtu_list.append(int(host["mtu"]))

        if cfg["selected_loadgen"] != "Tofino Packet Generator":
            return render(
                request,
                "middlebox/output_external_started.html",
                {"running": True, "errors": [], "cfg": cfg, "min_mtu": min(mtu_list), "skipped": 1},
            )
        else:
            lgen_obj = globals.core_conn.root.get_loadgen_obj(cfg["selected_loadgen"])
            ext_host_obj = globals.core_conn.root.get_current_extHost_obj()
            py_code = lgen_obj.read_python_packet_code()
            packets = lgen_obj.exec_py_str(py_code)
            packet_names = [name for name in packets.keys()]
            return render(
                request,
                "middlebox/output_external_started_integrated_generation.html",
                {"running": True, "errors": [], "cfg": cfg, "py_code": py_code, "packet_names":packet_names, "min_mtu": min(mtu_list), "skipped": 1, "ext_host_cfg": P4STA_utils.flt(ext_host_obj.host_cfg)},
            )
        


# starts monitor/ receiver instance at external host
def start_external(request):
    if P4STA_utils.is_ajax(request):
        try:
            cfg = P4STA_utils.read_current_cfg()

            ext_host_cfg = \
                globals.core_conn.root.get_current_extHost_obj().host_cfg
            if "status_check" in ext_host_cfg \
                    and "needed_sudos_to_add" in ext_host_cfg["status_check"]:
                sudos_ok = []
                indx_of_sudos_missing = []
                for found_sudo in globals.core_conn.root.check_sudo(
                        cfg["ext_host_user"], cfg["ext_host_ssh"]):
                    globals.logger.debug("found sudo: " + str(found_sudo))
                    if found_sudo.find("Error checking sudo status") > -1:
                        return render(
                            request, "middlebox/timeout.html",
                            {"inside_ajax": True, "error":
                                "Error checking sudo status of "
                                "ext host, sure it is reachable?"})
                    i = 0
                    _nsta = ext_host_cfg["status_check"]["needed_sudos_to_add"]
                    for needed_sudo in _nsta:
                        if found_sudo.find(needed_sudo) > -1:
                            sudos_ok.append(True)
                        elif i not in indx_of_sudos_missing:
                            indx_of_sudos_missing.append(i)
                        i = i + 1
                if len(sudos_ok) < len(_nsta):
                    error_msg = "Missing visudos: "
                    for i in indx_of_sudos_missing:
                        error_msg = error_msg + _nsta[i] + "  |  "
                    globals.logger.error(error_msg)
                    return render(
                        request, "middlebox/timeout.html",
                        {"inside_ajax": True, "error": error_msg})

            new_id = globals.core_conn.root.set_new_measurement_id()
            globals.logger.info("Set new measurement ID: " + str(new_id))

            stamper_running, errors = globals.core_conn.root.start_external()
            mtu_list = []
            for loadgen_grp in cfg["loadgen_groups"]:
                if loadgen_grp["use_group"] == "checked":
                    for host in loadgen_grp["loadgens"]:
                        if "namespace_id" in host \
                                and host["namespace_id"] != "":
                            host["mtu"] = globals.core_conn.root.fetch_mtu(
                                host['ssh_user'], host['ssh_ip'],
                                host['loadgen_iface'], host["namespace_id"])
                        else:
                            host["mtu"] = globals.core_conn.root.fetch_mtu(
                                host['ssh_user'], host['ssh_ip'],
                                host['loadgen_iface'])
                        mtu_list.append(int(host["mtu"]))

            ext_host_obj = globals.core_conn.root.get_current_extHost_obj()
            if cfg["selected_loadgen"] != "Tofino Packet Generator":
                return render(
                    request,
                    "middlebox/output_external_started.html",
                    {
                        "running": stamper_running,
                        "errors": list(errors),
                        "cfg": cfg,
                        "min_mtu": min(mtu_list),
                        "skipped": 0,
                        "ext_host_cfg": P4STA_utils.flt(ext_host_obj.host_cfg),
                        "new_run_id": new_id,
                    }
                )
            else:
                globals.current_live_stats = []
                lgen_obj = globals.core_conn.root.get_loadgen_obj(cfg["selected_loadgen"])
                py_code = lgen_obj.read_python_packet_code()
                packets = lgen_obj.exec_py_str(py_code)
                packet_names = [name for name in packets.keys()]

                return render(
                    request,
                    "middlebox/output_external_started_integrated_generation.html",
                    {
                        "running": True,
                        "errors": [],
                        "cfg": cfg,
                        "py_code": py_code,
                        "packet_names": packet_names,
                        "min_mtu": min(mtu_list),
                        "skipped": 0,
                        "ext_host_cfg": P4STA_utils.flt(ext_host_obj.host_cfg),
                        "new_run_id": new_id,
                    },
                )

        except Exception as e:
            globals.logger.error(traceback.format_exc())
            return render(
                request, "middlebox/timeout.html",
                {"inside_ajax": True,
                 "error": ("start external host error: " + str(e))})
    else:
        globals.logger.warning("start_external request is not ajax! Do nothing.")


def packet_templates_config(request):
    if P4STA_utils.is_ajax(request) and request.method == "POST":
        ok = True

        cfg = P4STA_utils.read_current_cfg()
        if "packets_python_code" in request.POST:

            try:
                lgen_obj = globals.core_conn.root.get_loadgen_obj(cfg["selected_loadgen"])
                packets = lgen_obj.exec_py_str(request.POST["packets_python_code"])
                packet_names = [name for name in packets.keys()]
                lgen_obj.save_python_packet_code(request.POST["packets_python_code"])
            except:
                globals.logger.error(traceback.format_exc())
                ok = False

            return JsonResponse({"ok": ok, "packet_names": packet_names})
        
        elif "reset" in request.POST:
            if request.POST["reset"] == True or request.POST["reset"] == "true":
                lgen_obj = globals.core_conn.root.get_loadgen_obj(cfg["selected_loadgen"])
                py_code_template = lgen_obj.read_python_packet_code_template()

                packets = lgen_obj.exec_py_str(py_code_template)
                packet_names = [name for name in packets.keys()]
                
                return JsonResponse({"ok": ok, "packet_names": packet_names, "py_code": py_code_template})


def live_metrics(request):
    metrics = P4STA_utils.flt(globals.core_conn.root.get_live_metrics())

    if type(globals.current_live_stats) == list:
        globals.current_live_stats.append({time.time(): metrics})

    ## DEBUGGING only
    if False:
        live_metrics=[]
        import random
        for port in [2,3]:
            p_res = {}
            p_res["port"] = port
            p_res["tx_rate"] = 10000 * random.randrange(10,100, 1)
            p_res["rx_rate"] = 10000 * random.randrange(10,100, 1)
            p_res["tx_pps"] = 4242
            p_res["rx_pps"] = 4242
            p_res["tx_avg_packet_size"] = 1300
            p_res["rx_avg_packet_size"] = 1300
            live_metrics.append(p_res)

        return JsonResponse({"metrics": live_metrics})

    return JsonResponse({"metrics": metrics})


def get_ext_host_live_status(request):
    # kill ext host collection thread (discard button in GUI when ext host API is not reachable)
    if "kill" in request.GET and request.GET["kill"] == "11":
        globals.core_conn.root.kill_external_background_process()
        return JsonResponse({})
    else:
        live_status = P4STA_utils.flt(globals.core_conn.root.get_ext_host_live_status())
        # for stop_external, can be None (ext host not started or after stopped), True (is stoppable), False (is not stoppable) or the stop thread obj
        # None is null in json
        stop_state = P4STA_utils.flt(globals.core_conn.root.get_state_stop_external_background())
        if stop_state == None:
            live_status["stop_state"] = 0 #"not started"
        elif stop_state == True:
            live_status["stop_state"] = 1 #"stopped"
        elif stop_state == False:
            live_status["stop_state"] = 2 #"stopping failed"
        else:
            live_status["stop_state"] = 3 #"currently stopping ... 
        

        if "current_run_state" in live_status and live_status["current_run_state"].find("UP") > -1:
            live_status["green_light"] = True
        else:
            live_status["green_light"] = False

        return JsonResponse({"live_status": live_status})


# resets registers in p4 device by overwriting them with 0
def reset(request):
    if P4STA_utils.is_ajax(request):
        try:
            answer = globals.core_conn.root.reset()
            return render(
                request, "middlebox/output_reset.html", {"answer": answer})
        except Exception as e:
            return render(
                request, "middlebox/timeout.html",
                {"inside_ajax": True,
                 "error": ("reset stamper register error: " + str(e))})


# stops last started instance of receiver at external host
# and starts reading p4 registers
def stop_external(request, background=False):
    if P4STA_utils.is_ajax(request):
        try:
            if background:
                stoppable = globals.core_conn.root.stop_external_background(copy.deepcopy(globals.current_live_stats)) # copy so we can set globals var back to None
                globals.current_live_stats = None
                return render(
                    request, "middlebox/output_external_stopped.html", {"stoppable": stoppable})
            # Legacy (core_conn stop_external is blocking for many seconds)
            else:
                # read time increases with amount of hosts
                stop_external = rpyc.timed(globals.core_conn.root.stop_external, 60*50)
                stoppable = stop_external()
                stoppable.wait()
                return render(
                    request, "middlebox/output_external_stopped.html",
                    {"stoppable": stoppable.value})
        except Exception as e:
            return render(request, "middlebox/timeout.html",
                          {"inside_ajax": True,
                           "error": ("stop external host error: " + str(e))})


def stop_external_background(request):
    return stop_external(request, background=True)

 
# case when external host was not started, read only stamper 
def stop_without_external(request):
    if P4STA_utils.is_ajax(request):
        try:
            # read time increases with amount of hosts
            stop_external = rpyc.timed(
                globals.core_conn.root.stop_without_external, 30)
            stoppable = stop_external()
            stoppable.wait()
            return render(
                request, "middlebox/output_external_stopped.html",
                {"stoppable": stoppable.value})
        except Exception as e:
            return render(request, "middlebox/timeout.html",
                          {"inside_ajax": True,
                           "error": ("stop external host error: " + str(e))})


# called at Run if "Start" is clicked
def run_loadgens_first(request):
    if request.method == "POST":
        if "duration" in request.POST:
            try:
                duration = int(request.POST["duration"])
            except ValueError:
                globals.logger.warning("Loadgen duration is not a number. Defaulting to 10 seconds.")
                duration = 10
        else:
            duration = 10

        if "custom_name" in request.POST:
            try:
                custom_name = str(request.POST["custom_name"])
            except:
                custom_name = ""
                globals.logger.warning(traceback.format_exc())
        else:
            custom_name = ""

        l4_selected = request.POST["l4_selected"]
        packet_size_mtu = request.POST["packet_size_mtu"]
        if "loadgen_rate_limit" in request.POST:
            try:
                loadgen_rate_limit = int(request.POST["loadgen_rate_limit"])
            except ValueError:
                globals.logger.warning("loadgen_rate_limit is not a number, no rate limit set.")
                loadgen_rate_limit = 0
        else:
            loadgen_rate_limit = 0
        if "loadgen_flows" in request.POST:
            try:
                loadgen_flows = int(request.POST["loadgen_flows"])
            except ValueError:
                loadgen_flows = 3
                globals.logger.warning("loadgen_flows is not a number, set 3 flows")
        else:
            loadgen_flows = 3
        if "loadgen_server_groups[]" in request.POST:
            try:
                loadgen_server_groups = []
                for item in request.POST.getlist("loadgen_server_groups[]"):
                    loadgen_server_groups.append(int(item))
            except Exception:
                loadgen_server_groups = [1]
                globals.logger.warning(traceback.format_exc())
        else:
            loadgen_server_groups = [1]
        try:
            t_timeout = round(duration*2*loadgen_flows + 60)
            start_loadgens = rpyc.timed(
                globals.core_conn.root.start_loadgens, t_timeout)
            file_id = start_loadgens(
                duration, l4_selected, packet_size_mtu, loadgen_rate_limit,
                loadgen_flows, loadgen_server_groups, {}, custom_name) # run_loadgens={}, not required for iperf3 (legacy)
            file_id.wait()
            file_id_val = file_id.value
            globals.selected_run_id = file_id_val
            return render_loadgens(request, file_id_val, duration=duration)

        except Exception as e:
            globals.logger.error("Exception in run_loadgens: " + str(e))
            return render(
                request, "middlebox/timeout.html",
                {"inside_ajax": True, "error": ("run loadgen error: "+str(e))})

def run_loadgens_first_integrated_generator(request):
    if request.method == "POST":

        if "duration" in request.POST:
            try:
                duration = int(request.POST["duration"])
            except ValueError:
                globals.logger.warning("Loadgen duration is not a number. Defaulting to 10 seconds.")
                duration = 10
        else:
            duration = 10
        
        if "custom_name" in request.POST:
            try:
                custom_name = str(request.POST["custom_name"])
            except:
                custom_name = ""
                globals.logger.warning(traceback.format_exc())
        else:
            custom_name = ""

        # Legacy P4sta core API params
        l4_selected = None
        packet_size_mtu = None
        loadgen_rate_limit = None
        loadgen_flows = None
        loadgen_server_groups = None

        # new combined loadgen cfg dict
        loadgen_cfg = {}
        gen_port_cfgs_json = request.POST["gen_ports_cfgs_json_str"]
        loadgen_cfg["gen_ports"] = json.loads(gen_port_cfgs_json)

        try:
            t_timeout = round(duration*2 + 60)
            start_loadgens = rpyc.timed(
                globals.core_conn.root.start_loadgens, t_timeout)
            file_id = start_loadgens(
                duration, l4_selected, packet_size_mtu, loadgen_rate_limit,
                loadgen_flows, loadgen_server_groups, loadgen_cfg, custom_name)
            file_id.wait()
            file_id_val = file_id.value
            globals.selected_run_id = file_id_val

            # the integrated generation runs in background, we return here immediately after starting
            # show live values html 

            return render_live_metrics(request, duration)

            # return render_loadgens(request, file_id_val, duration=duration) #TODO: render loadgens maybe not useful here

        except Exception as e:
            globals.logger.error("Exception in run_loadgens: " + str(e))
            return render(
                request, "middlebox/timeout.html",
                {"inside_ajax": True, "error": ("run loadgen error: "+str(e))})


# loads loadgen results again without executing another test
def read_loadgen_results_again(request):
    if P4STA_utils.is_ajax(request):
        return render_loadgens(request, globals.selected_run_id)


def render_loadgens(request, file_id, duration=10):
    try:
        process_loadgens = rpyc.timed(
            globals.core_conn.root.process_loadgens, duration*2)
        results = process_loadgens(file_id)
        results.wait()
        results = results.value
        if results is not None:
            output, total_bits, error, total_retransmits, total_byte, \
                custom_attr, to_plot = results

            output = P4STA_utils.flt(output)
            custom_attr = P4STA_utils.flt(custom_attr)
        else:
            error = True
            output = ["Sorry an error occured!",
                      "The core returned NONE from loadgens which is a result"
                      " of an internal error in the loadgen module."]
            total_bits = total_retransmits = total_byte = 0
            custom_attr = {"l4_type": "", "name_list": [], "elems": {}}

        cfg = P4STA_utils.read_result_cfg(file_id)

        return render(
            request, "middlebox/output_loadgen.html",
            {"cfg": cfg, "output": output,
             "total_gbits": analytics.find_unit_bit_byte(total_bits, "bit"),
             "cachebuster": str(time.time()).replace(".", ""),
             "total_retransmits": total_retransmits,
             "total_gbyte": analytics.find_unit_bit_byte(total_byte, "byte"),
             "error": error, "custom_attr": custom_attr, "filename": file_id,
             "time": time.strftime(
                 "%H:%M:%S %d.%m.%Y", time.localtime(int(file_id)))})
    except Exception as e:
        globals.logger.error(traceback.format_exc())
        return render(
            request, "middlebox/timeout.html",
            {"inside_ajax": True, "error": ("render loadgen error: "+str(traceback.format_exc()))})


def live_metrics_page(request):
    return render_live_metrics(request, 10)
    

def render_live_metrics(request, duration):
    # cfg = P4STA_utils.read_result_cfg(file_id)
    cfg = P4STA_utils.read_current_cfg()
    return render(request, "middlebox/output_live_metrics.html", {"cfg": cfg, "duration": duration})
