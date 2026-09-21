# Copyright 2026-present Fridolin Siegmund, Ralf Kundel
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
import traceback

from django.shortcuts import render
from django.http import JsonResponse

from core import P4STA_utils
from session_modules.bngblaster import traffic_calc

# globals
from management_ui import globals

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST


def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON body")


@require_GET
def session_version(request):
    try:
        module_name = request.GET.get("module_name")
        globals.current_session_module = module_name

        if not module_name:
            return JsonResponse({"error": "Missing module_name"}, status=400)

        version = P4STA_utils.flt(globals.core_conn.root.check_session_module_live_version(module_name))

        return JsonResponse({
            "module_name": module_name,
            "version": version
        })
    except Exception as exc:
        return JsonResponse({"error": str(traceback.format_exc())}, status=500)


@csrf_exempt
@require_POST
def session_start(request):
    try:
        payload = _json_body(request)
        result = P4STA_utils.flt(globals.core_conn.root.start_run_session_module(payload))

        if result.get("error"):
            return JsonResponse(result, status=502)

        globals.current_session_run_id = result.get("run_id")

        try:
            globals.current_session_module = payload.get("module_name")
        except KeyError:
            print("No module name provided in session start payload, cannot update current session module global variable.")

        return JsonResponse(
            {
                "run_id": result.get("run_id"),
                "state": result.get("state", "Running"),
                # "pid": result.get("pid"),
                # "command": result.get("command"),
                **{k: v for k, v in result.items() if k not in {"run_id", "state", "pid", "command"}},
            }
        )
    except ValueError as exc:
        return JsonResponse({"error": str(traceback.format_exc())}, status=400)
    except Exception as exc:
        return JsonResponse({"error": str(traceback.format_exc())}, status=500)


@require_GET
def session_status(request, run_id=0, id_start=0, id_end=0):
    try:
        module_name = request.GET.get("module_name")
        if run_id == 0:
            if globals.current_session_run_id is not None:
                run_id = globals.current_session_run_id
            elif module_name == "BNGBlaster":
                # BNG Blaster queries the controller's P4STA instance, so status
                # also works before a local run or after teardown/UI restart.
                run_id = None
            else:
                raise Exception("No run ID provided and no current session run ID found.")
        # id_list=[1, 2, 3] # TODO! 
        globals.current_session_module = module_name #update to be sure

        try:
            if request.GET.get("id_start") is not None and request.GET.get("id_end") is not None:
                id_start = int(request.GET.get("id_start"))
                id_end = int(request.GET.get("id_end"))
                id_list = list(range(id_start, id_end+1)) # +1 to include id_end in the list
            else:
                id_list = None
        except ValueError:
            id_list = None
        
        result = P4STA_utils.flt(globals.core_conn.root.get_run_status_session_module({"module_name": module_name}, id_list))
        # print("Session status result:", result)
        # print(type(result))
        return JsonResponse(
            {
                "run_id": run_id,
                **{"results": result},
                **({"error": result["error"]} if result.get("error") else {}),
            },
            status=502 if result.get("error") else 200,
        )
    except KeyError:
        return JsonResponse({"error": "Run not found"}, status=404)
    except Exception as exc:
        return JsonResponse({"error": str(traceback.format_exc())}, status=500)


@csrf_exempt
@require_POST
def session_stop(request, run_id):
    try:
        if run_id == 0:
            if globals.current_session_run_id is not None:
                run_id = globals.current_session_run_id
            else:
                raise Exception("No run ID provided and no current session run ID found.")
            
        print(request.body)

        data = json.loads(request.body.decode("utf-8"))
        module_name = data.get("module_name")
            
        print(f"Stopping session run {run_id} for module {module_name}...")
        result = P4STA_utils.flt(globals.core_conn.root.stop_run_session_module({"module_name": module_name}, run_id))

        globals.current_session_run_id = None

        if result is not None:
            return JsonResponse(
                {
                    "run_id": run_id,
                    **{"result": list(result)},
                }
            )
        else:
            return JsonResponse({"run_id": run_id})
    except KeyError:
        return JsonResponse({"error": "Run not found"}, status=404)
    except Exception as exc:
        
        return JsonResponse({"error": str(traceback.format_exc())}, status=500)

# for session submodules, e.g. BNGBlaster
def session_config_file(request):
    if P4STA_utils.is_ajax(request) and request.method == "POST":
        ok = True

        if "module_name" not in request.POST:
            globals.logger.error("No module name provided in session config!")
            return
        try:
            sess_module_obj = globals.core_conn.root.get_sessionModule_obj(request.POST["module_name"])
            if "config_json" in request.POST:
                try:
                    sess_module_obj.save_config_json(request.POST["config_json"])
                    return JsonResponse({"ok": ok})
                except:
                    globals.logger.error(traceback.format_exc())
                    ok = False  
                    return JsonResponse({"ok": ok, "error": "Error saving session module config: " + str(traceback.format_exc())})
            
            elif "reset" in request.POST:
                if request.POST["reset"] == True or request.POST["reset"] == "true":
                    config_json_template = sess_module_obj.read_config_json_template()
                    
                    return JsonResponse({"ok": ok, "config_json": config_json_template})
        except Exception as e:
            globals.logger.error(traceback.format_exc())
            return
        
    elif request.method == "GET":
        if "module_name" not in request.GET:
            globals.logger.error("No module name provided in session config GET request!")
            return
        try:
            sess_module_obj = globals.core_conn.root.get_sessionModule_obj(request.GET["module_name"])
            config_json = sess_module_obj.read_config_json()
            return JsonResponse({"ok": True, "config_json": config_json})
        except Exception as e:
            globals.logger.error(traceback.format_exc())
            return JsonResponse({"ok": False, "error": "Error reading session module config: " + str(traceback.format_exc())})

def session_config_file_reset(request):
    if P4STA_utils.is_ajax(request) and request.method == "POST":
        ok = True

        if "module_name" not in request.POST:
            globals.logger.error("No module name provided in session config reset!")
            return
        try:
            sess_module_obj = globals.core_conn.root.get_sessionModule_obj(request.POST["module_name"])
            config_json = sess_module_obj.session_config_file_reset()
                    
            return JsonResponse({"ok": ok, "config_json": P4STA_utils.flt(config_json)})
        except Exception as e:
            globals.logger.error(traceback.format_exc())
            return JsonResponse({"ok": False, "error": "Error resetting session module config: " + str(traceback.format_exc())})
        
@require_POST
def preview_traffic_profile(request):
    try:
        payload = _json_body(request)
        percentages = payload.get("flow_percentages", [])
        if not isinstance(percentages, list) or not all(
                isinstance(value, str) for value in percentages):
            raise ValueError("Flow percentages must be a list of strings.")
        if not percentages:
            raise ValueError("No established flows.")

        preset_result = {}
        if "preset" in payload:
            percentages = traffic_calc.calculate_preset_percentages(
                len(percentages), payload["preset"])
            preset_result = {
                "flow_percentages": [str(value) for value in percentages],
                "display_percentages": [format(float(value), ".12g")
                                        for value in percentages],
            }
            percentages = preset_result["flow_percentages"]

        distribution = traffic_calc.calculate_packet_distribution(
            range(len(percentages)),
            {index: value for index, value in enumerate(percentages)
             if value.strip()})
        pattern_entries = sum(distribution)
        target = P4STA_utils.read_current_cfg().get("selected_target")
        # Match LOG_INDX_MAX_SIZE in tofino_stamper_v1_4_0.p4
        # all Tof1 are mapped by Wedge100B65 module
        architecture, entry_limit = {
            "Wedge100B65": ("Tofino 1", 135168),
            "tofino_model": ("Tofino 1", 135168),
            "EdgecoreDCS810": ("Tofino 2", 404381),
        }.get(target, (None, None))
        return JsonResponse({
            "pattern_entries": str(pattern_entries),
            "entry_limit": entry_limit,
            "architecture": architecture,
            "within_limit": entry_limit is None or pattern_entries <= entry_limit,
            **preset_result,
        })
    except (ValueError, TypeError, AttributeError, ZeroDivisionError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)


def set_traffic_profile(request):
    if P4STA_utils.is_ajax(request) and request.method == "POST":
        if "module_name" not in request.POST:
            globals.logger.error("No module name provided in session config reset!")
            return
        try:
            print(request.POST["traffic_config"])
            payload = json.loads(request.POST["traffic_config"])
            globals.logger.debug("session traffic configuration from GUI: " + str(payload))
            ret = globals.core_conn.root.set_session_traffic_profile(request.POST["module_name"], payload)

            return JsonResponse({"ok": ret})

        except ValueError as exc:
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
        except Exception as e:
            globals.logger.error(traceback.format_exc())
            return JsonResponse({"ok": False, "error": "Error setting traffic profile: " + str(traceback.format_exc())})
