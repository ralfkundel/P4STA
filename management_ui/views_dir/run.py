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
import rpyc
import time
import traceback

from django.shortcuts import render

# custom python modules
from analytics import analytics
from core import P4STA_utils

# globals
from management_ui import globals


def page_run(request):
    cfg = P4STA_utils.read_current_cfg()
    return render(request, "middlebox/page_run.html", cfg)


# executes ping test
def ping(request):
    if request.is_ajax():
        try:
            output = globals.core_conn.root.ping()
            output = P4STA_utils.flt(output)
            return render(
                request, "middlebox/output_ping.html", {"output": output})
        except Exception as e:
            return render(
                request, "middlebox/timeout.html",
                {"inside_ajax": True, "error": ("ping error: " + str(e))})


# starts python receiver instance at external host
def start_external(request):
    if request.is_ajax():
        print("start_external is ajax")
        try:
            cfg = P4STA_utils.read_current_cfg()

            ext_host_cfg = \
                globals.core_conn.root.get_current_extHost_obj().host_cfg
            print(ext_host_cfg)
            if "status_check" in ext_host_cfg \
                    and "needed_sudos_to_add" in ext_host_cfg["status_check"]:
                print("if true")
                sudos_ok = []
                indx_of_sudos_missing = []
                for found_sudo in globals.core_conn.root.check_sudo(
                        cfg["ext_host_user"], cfg["ext_host_ssh"]):
                    print("found sudo: " + str(found_sudo))
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
                    print(error_msg)
                    return render(
                        request, "middlebox/timeout.html",
                        {"inside_ajax": True, "error": error_msg})

            new_id = globals.core_conn.root.set_new_measurement_id()
            print("\nSET NEW MEASUREMENT ID")
            print(new_id)
            print("###############################\n")

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

            return render(
                request, "middlebox/output_external_started.html",
                {"running": stamper_running, "errors": list(errors),
                 "cfg": cfg, "min_mtu": min(mtu_list)})

        except Exception as e:
            print(e)
            return render(
                request, "middlebox/timeout.html",
                {"inside_ajax": True,
                 "error": ("start external host error: " + str(e))})
    else:
        print("start_external request is not ajax! Do nothing.")


# resets registers in p4 device by overwriting them with 0
def reset(request):
    if request.is_ajax():
        try:
            answer = globals.core_conn.root.reset()
            return render(
                request, "middlebox/output_reset.html", {"answer": answer})
        except Exception as e:
            return render(
                request, "middlebox/timeout.html",
                {"inside_ajax": True,
                 "error": ("reset stamper register error: " + str(e))})


# stops last started instance of python receiver at external host
# and starts reading p4 registers
def stop_external(request):
    if request.is_ajax():
        try:
            # read time increases with amount of hosts
            stop_external = rpyc.timed(
                globals.core_conn.root.stop_external, 60*50)
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
                print("Loadgen duration is not a number. Taking 10 seconds.")
                duration = 10
        else:
            duration = 10
        l4_selected = request.POST["l4_selected"]
        packet_size_mtu = request.POST["packet_size_mtu"]
        if "loadgen_rate_limit" in request.POST:
            try:
                loadgen_rate_limit = int(request.POST["loadgen_rate_limit"])
            except ValueError:
                print("loadgen_rate_limit is not a number, no rate limit set.")
                loadgen_rate_limit = 0
        else:
            loadgen_rate_limit = 0
        if "loadgen_flows" in request.POST:
            try:
                loadgen_flows = int(request.POST["loadgen_flows"])
            except ValueError:
                loadgen_flows = 3
                print("loadgen_flows is not a number, set 3 flows")
        else:
            loadgen_flows = 3
        if "loadgen_server_groups[]" in request.POST:
            try:
                loadgen_server_groups = []
                for item in request.POST.getlist("loadgen_server_groups[]"):
                    loadgen_server_groups.append(int(item))
            except Exception:
                loadgen_server_groups = [1]
                print(traceback.format_exc())
        else:
            loadgen_server_groups = [1]
        try:
            t_timeout = round(duration*2*loadgen_flows + 60)
            start_loadgens = rpyc.timed(
                globals.core_conn.root.start_loadgens, t_timeout)
            file_id = start_loadgens(
                duration, l4_selected, packet_size_mtu, loadgen_rate_limit,
                loadgen_flows, loadgen_server_groups)
            file_id.wait()
            file_id_val = file_id.value
            globals.selected_run_id = file_id_val
            return render_loadgens(request, file_id_val, duration=duration)

        except Exception as e:
            print("Exception in run_loadgens: " + str(e))
            return render(
                request, "middlebox/timeout.html",
                {"inside_ajax": True, "error": ("run loadgen error: "+str(e))})


# loads loadgen results again without executing another test
def read_loadgen_results_again(request):
    if request.is_ajax():
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
        print(e)
        return render(
            request, "middlebox/timeout.html",
            {"inside_ajax": True, "error": ("render loadgen error: "+str(e))})
