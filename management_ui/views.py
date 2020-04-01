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

from django.http import HttpResponse
from django.http import JsonResponse
from django.http import HttpResponseRedirect

from django.shortcuts import render

import os, subprocess, threading, time, traceback, json, zipfile, shutil, sys
import rpyc
from pathlib import Path
# custom python modules
from calculate import calculate
from core import P4STA_utils


def main():
    global selected_run_id
    global core_conn
    global project_path
    core_conn = rpyc.connect('localhost', 6789)
    project_path = core_conn.root.get_project_path()
    P4STA_utils.set_project_path(project_path)
    selected_run_id = core_conn.root.getLatestMeasurementId()


main()


####################################################################
################# Configure ########################################
####################################################################


def get_all_targets():
    targets = P4STA_utils.flt(core_conn.root.get_all_targets())
    return targets

# builds list of available speeds without the selected one
def speedlist(port_speed):
    speed_list = core_conn.root.speed_list()
    #speed_list = P4STA_utils.flt(speed_list)
    speed_list_result = []
    try:
        for i in range(0, len(speed_list)):
            if port_speed != speed_list[i]:
                speed_list_result.append(speed_list[i])
        return speed_list_result
    except:
        return speed_list

# returns list of loadgens found in "load_generators" directory without the current selected
def get_loadgens(cfg):
    loadgens = []
    for elem in next(os.walk('./load_generators'))[1]:
        if elem != "__pycache__" and elem != cfg["selected_loadgen"]:
            loadgens.append(elem)
    return loadgens

def fetch_iface(request):
    if not request.method == "POST":
        return
    try:
        results = core_conn.root.fetch_interface(request.POST["user"], request.POST["ssh_ip"], request.POST["iface"], request.POST["namespace"])
        ipv4, mac, prefix, up_state, iface_found = results
    except Exception as e:
        ipv4 = mac = prefix = up_state = "timeout"
        print("Exception fetch iface: "+ str(e))
    return JsonResponse({"mac": mac, "ip": ipv4, "prefix": prefix, "up_state": up_state, "iface_found": iface_found})

def set_iface(request):
    if request.method == "POST":
        set_iface = core_conn.root.set_interface(request.POST["user"], request.POST["ssh_ip"], request.POST["iface"], request.POST["iface_ip"], request.POST["namespace"])

        return JsonResponse({"error": set_iface})


def status_overview(request):
    try:
        status_overview = rpyc.timed(core_conn.root.status_overview, 60)()
        status_overview.wait()
        cfg = status_overview.value
        cfg = P4STA_utils.flt(cfg)

        return render(request, "middlebox/output_status_overview.html", cfg)
    except Exception as e:
        print(e)
        return render(request, "middlebox/timeout.html", {"inside_ajax": True, "error": ("stamper status error: " + str(e))})


def updateCfg(request):
    cfg = P4STA_utils.read_current_cfg()
    target_cfg = core_conn.root.get_target_cfg()
    ports = core_conn.root.get_ports()
    real_ports = ports["real_ports"]
    logical_ports = ports["logical_ports"]
    try:
        cfg["selected_target"] = request.POST["target"]
        cfg["selected_loadgen"] = request.POST["selected_loadgen"]
        num_servers = int(request.POST["num_server"])
        servers = cfg["loadgen_servers"] = [] #loss of hidden information!?!
        i = 1
        for j in range(1, num_servers+1):
            s = {}
            s["id"] = j
            #while "s_"+str(i)+"_speed" not in request.POST:
            while "s_" + str(i) + "_real_port" not in request.POST:
                i += 1
                if i == 99:
                    break
            s["real_port"] = str(request.POST["s_"+str(i)+"_real_port"])
            try:
                s["p4_port"] = logical_ports[real_ports.index(s["real_port"])].strip("\n")
            except Exception as e:
                print("FAILED: Finding: " + str(e))
                s["p4_port"] = ""
            s["ssh_ip"] = str(request.POST["s_"+str(i)+"_ssh_ip"])
            s["ssh_user"] = str(request.POST["s_"+str(i)+"_ssh_user"])
            s["loadgen_iface"] = str(request.POST["s_"+str(i)+"_loadgen_iface"])
            s["loadgen_mac"] = str(request.POST["s_"+str(i)+"_loadgen_mac"])
            s["loadgen_ip"] = str(request.POST["s_"+str(i)+"_loadgen_ip"]).split(" ")[0].split("/")[0]
            #s["speed"] = str(request.POST["s_"+str(i)+"_speed"])
            if "s_"+str(i)+"_namespace" in request.POST:
                s["namespace_id"] = str(request.POST["s_"+str(i)+"_namespace"])
            # read target specific config from webinterface
            for t_inp in target_cfg["inputs"]["input_table"]:
                try:
                    s[t_inp["target_key"]] = str(request.POST["s_"+str(i)+"_"+t_inp["target_key"]])
                except Exception as e:
                    print("#\n#\n#\n#\n#\n#\n#\nError parsing special target config parameters:" + str(e))
            servers.append(s)
            i += 1

        if str(request.POST["add_server"]) == "1":
            s = {}
            s["id"] = num_servers + 1
            s["real_port"] = ""
            s["p4_port"] = ""
            s["loadgen_ip"] = ""
            s["ssh_ip"] = ""
            s["ssh_user"] = ""
            s["loadgen_iface"] = ""
            #s["speed"] = "1G"
            servers.append(s)

        num_clients = int(request.POST["num_clients"])
        clients = cfg["loadgen_clients"] = []
        i = 1
        for j in range(1, num_clients+1):
            c = {}
            c["id"] = j
            #while "c_"+str(i)+"_speed" not in request.POST:
            while "c_" + str(i) + "_real_port" not in request.POST:
                i += 1
                if i == 99:
                    break
            c["real_port"] = str(request.POST["c_"+str(i)+"_real_port"])
            try:
                    c["p4_port"] = logical_ports[real_ports.index(c["real_port"])].strip("\n")
            except Exception as e:
                print("FAILED: Finding: " + str(e))
                c["p4_port"] = ""
            c["ssh_ip"] = str(request.POST["c_"+str(i)+"_ssh_ip"])
            c["ssh_user"] = str(request.POST["c_"+str(i)+"_ssh_user"])
            c["loadgen_iface"] = str(request.POST["c_"+str(i)+"_loadgen_iface"])
            c["loadgen_mac"] = str(request.POST["c_"+str(i)+"_loadgen_mac"])
            c["loadgen_ip"] = str(request.POST["c_"+str(i)+"_loadgen_ip"]).split(" ")[0].split("/")[0]
            #c["speed"] = str(request.POST["c_"+str(i)+"_speed"])
            if "c_"+str(i)+"_namespace" in request.POST:
                c["namespace_id"] = str(request.POST["c_"+str(i)+"_namespace"])
                # read target specific config from webinterface
            for t_inp in target_cfg["inputs"]["input_table"]:
                try:
                    c[t_inp["target_key"]] = str(request.POST["c_"+str(i)+"_"+t_inp["target_key"]])
                except Exception as e:
                    print(e)

            clients.append(c)
            i += 1

        if str(request.POST["add_client"]) == "1":
            c = {}
            c["id"] = num_clients + 1
            c["real_port"] = ""
            c["p4_port"] = ""
            c["loadgen_ip"] = ""
            c["ssh_ip"] = ""
            c["ssh_user"] = ""
            c["loadgen_iface"] = ""
            #c["speed"] = "1G"
            clients.append(c)

        try:  # read target specific config from webinterface
            for t_inp in target_cfg["inputs"]["input_individual"]:
                cfg[t_inp["target_key"]] = str(request.POST[t_inp["target_key"]])

            for t_inp in target_cfg["inputs"]["input_table"]:
                cfg["dut1_" + t_inp["target_key"]] = str(request.POST["dut1_" + t_inp["target_key"]])
                try:
                    cfg["dut2_" + t_inp["target_key"]] = str(request.POST["dut2_" + t_inp["target_key"]])
                except: # exception when dut2 is unused
                    pass
                cfg["ext_host_" + t_inp["target_key"]] = str(request.POST["ext_host_" + t_inp["target_key"]])

        except Exception as e:
            print("EXCEPTION: " + str(e))

        cfg["ext_host_real"] = str(request.POST["ext_host_real"])
        try:
            cfg["ext_host"] = logical_ports[real_ports.index(cfg["ext_host_real"])].strip("\n")
        except Exception as e:
            print("FAILED: Finding Ext-Host Real Port: " + str(e))
        cfg["dut1_real"] = str(request.POST["dut1_real"])
        try:
            cfg["dut1"] = logical_ports[real_ports.index(cfg["dut1_real"])].strip("\n")
        except Exception as e:
            print("FAILED: Finding Dut1 Real Port: " + str(e))
        #cfg["dut1_speed"] = str(request.POST["dut1_speed"])

        # check if second dut port should be used or not
        try:
            if request.POST["dut_2_use_port"] == "checked":
                cfg["dut_2_use_port"] = "checked"
            else:
                cfg["dut_2_use_port"] = "unchecked"
        except:
            cfg["dut_2_use_port"] = "unchecked"

        if cfg["dut_2_use_port"] == "checked":
            cfg["dut2_real"] = str(request.POST["dut2_real"])
            try:
                cfg["dut2"] = logical_ports[real_ports.index(cfg["dut2_real"])].strip("\n")
            except Exception as e:
                print("FAILED: Finding Dut2 Real Port: " + str(e))
            #cfg["dut2_speed"] = str(request.POST["dut2_speed"])
        else:
            cfg["dut2_real"] = cfg["dut1_real"]
            cfg["dut2"] = cfg["dut1"]
            if "dut1_speed" in cfg:
                cfg["dut2_speed"] = cfg["dut1_speed"]

        #cfg["ext_host_speed"] = str(request.POST["ext_host_speed"])
        cfg["multicast"] = str(request.POST["multicast"])
        cfg["p4_dev_ssh"] = str(request.POST["p4_dev_ssh"])
        cfg["ext_host_ssh"] = str(request.POST["ext_host_ssh"])
        cfg["ext_host_user"] = str(request.POST["ext_host_user"])
        cfg["p4_dev_user"] = str(request.POST["p4_dev_user"])
        cfg["ext_host_if"] = str(request.POST["ext_host_if"])
        try:
            cfg["dut_1_outgoing_stamp"] = str(request.POST["dut_1_outgoing_stamp"])
        except:
            cfg["dut_1_outgoing_stamp"] = "unchecked"
        try:
            cfg["dut_2_outgoing_stamp"] = str(request.POST["dut_2_outgoing_stamp"])
        except:
            cfg["dut_2_outgoing_stamp"] = "unchecked"
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
        print("write config")
        cfg = P4STA_utils.flt(cfg) # TODO

        P4STA_utils.write_config(cfg)
        print("finished config write")
        # DELETE when all targets are ported to thrift, no need for creation of txt file anymore

        return True, cfg

    except Exception as e:
        print("EXCEPTION: " + str(e))

        return False, cfg

def first_run(request):
    if request.method == "POST":
        first_time_cfg = {}
        first_time_cfg["stamper_user"] = request.POST["stamper_user"]
        first_time_cfg["stamper_ssh"] = request.POST["stamper_ip"]
        first_time_cfg["ext_host_user"] = request.POST["ext_host_user"]
        first_time_cfg["ext_host_ssh"] = request.POST["ext_host_ip"]
        first_time_cfg["loadgen_user"] = request.POST["loadgen_user"]
        first_time_cfg["loadgen_ips"] = request.POST["loadgen_ips"].replace(" ", "").split(",")
        core_conn.root.write_install_script(first_time_cfg)
        return HttpResponseRedirect("/")
    else:
        print("### FIRST RUN #####")
        core_conn.root.first_run_finished()
        return render(request, "middlebox/first_run.html")

def first_run_ssh_checker(request):
    ssh_works = False
    ping_works = (os.system("timeout 1 ping " + request.POST["ip"] + " -c 1") == 0)  # if ping works it should be true
    if ping_works:
        answer = core_conn.root.execute_ssh(request.POST["user"], request.POST["ip"], "echo ssh_works")
        answer = list(answer)
        if len(answer) > 0 and answer[0] == "ssh_works":
            ssh_works = True

    return JsonResponse({"ping_works": ping_works, "ssh_works": ssh_works})


# input from configure page and reloads configure page
def configure_page(request):
    if core_conn.root.check_first_run():
        return HttpResponseRedirect("/first_run")

    saved = ""
    target_cfg = core_conn.root.get_target_cfg()
    target_cfg = P4STA_utils.flt(target_cfg)

    if type(target_cfg) == dict and "error" in target_cfg:
        return render(request, "middlebox/timeout.html", {**cfg, **{"inside_ajax": False}})

    if request.method == "POST":
        saved, cfg = updateCfg(request)
    else:
        cfg = P4STA_utils.read_current_cfg()
    cfg["target_cfg"] = target_cfg

    #The following config updates are only for UI representation
    targets_without_selected = []
    all_targets = get_all_targets()
    for target in all_targets:
        if cfg["selected_target"] != target:
            targets_without_selected.append(target)
    cfg["targets_without_selected"] = targets_without_selected
    cfg["all_available_targets"] = all_targets

    cfg["available_configs"] = P4STA_utils.flt(core_conn.root.get_available_cfg_files())

    cfg["saved"] = saved
    #for server in cfg["loadgen_servers"]:
    #    server["speed_list"] = speedlist(server["speed"])

    #for client in cfg["loadgen_clients"]:
    #    client["speed_list"] = speedlist(client["speed"])

    #cfg["speed_list_result_ext_host"] = speedlist(cfg["ext_host_speed"])
    #cfg["speed_list_result_dut1"] = speedlist(cfg["dut1_speed"])
    #cfg["speed_list_result_dut2"] = speedlist(cfg["dut2_speed"])

    cfg["available_loadgens"] = get_loadgens(cfg)
    # if field "p4_ports" in target config, target uses separate hardware ports & p4 ports (e.g. tofino)
    # now only hw (front) ports are left but relabeled as "ports" and p4-ports are ignored
    # ports_list in abstract_target creates mapping 1->1
    cfg["port_mapping"] = "p4_ports" in target_cfg

    cfg["cfg"] = cfg  # needed for dynamic target input_individual

    return render(request, "middlebox/config.html", cfg)


def create_new_cfg_from_template(request):
    print("CREATE CONFIG:")
    path = core_conn.root.get_template_cfg_path(request.POST["selected_cfg_template"])
    with open(path, "r") as f:
        cfg = json.load(f)
        P4STA_utils.write_config(cfg)
    return HttpResponseRedirect("/")


def open_selected_config(request):
    print("OPEN SELECTED CONFIG:")
    cfg = P4STA_utils.read_current_cfg(request.POST["selected_cfg_file"])
    P4STA_utils.write_config(cfg)
    return HttpResponseRedirect("/")


def delete_selected_config(request):
    print("DELETE SELECTED CONFIG:")
    name = request.POST["selected_cfg_file"]
    if name == "config.json":
        print("CORE: Delete of config.json denied!")
        return
    os.remove(os.path.join(project_path, "data", name))
    return HttpResponseRedirect("/")


def save_config_as_file(request):
    print("SAVE CONFIG:")
    saved, cfg = updateCfg(request)
    time_created = time.strftime('%d.%m.%Y-%H:%M:%S', time.localtime())
    file_name = cfg["selected_target"]+ "_" + str(time_created) + ".json"
    P4STA_utils.write_config (cfg, file_name)
    return HttpResponseRedirect("/")


def delete_namespace(request):
    if request.method == "POST":
        if "namespace" in request.POST and "user" in request.POST and "ssh_ip" in request.POST:
            ns = request.POST["namespace"]
            user = request.POST["user"]
            ssh_ip = request.POST["ssh_ip"]
            worked = core_conn.root.delete_namespace(ns, user, ssh_ip)
            if worked:
                return JsonResponse({"error": False})
    return JsonResponse({"error": True})


####################################################################
################# DEPLOY ###########################################
####################################################################


# return html object for /deploy/
def page_deploy(request):
    return render(request, "middlebox/page_deploy.html")


# shows current p4 device status and status of packet generators
def p4_dev_status(request):
    return p4_dev_status_wrapper(request, "middlebox/output_p4_software_status.html")


def p4_dev_ports(request):
    return p4_dev_status_wrapper(request, "middlebox/portmanager.html")


def host_iface_status(request):
    return p4_dev_status_wrapper(request, "middlebox/host_iface_status.html")


def p4_dev_status_wrapper(request, html_file):
    p4_dev_status = rpyc.timed(core_conn.root.p4_dev_status, 20)
    p4_dev_status_job = p4_dev_status()
    try:
        p4_dev_status_job.wait()
        result = p4_dev_status_job.value
        cfg, lines_pm, running, dev_status = result
        cfg = P4STA_utils.flt(cfg)  # cfg contains host status information
        lines_pm = P4STA_utils.flt(lines_pm)

        return render(request, html_file, {"dev_status": dev_status, "dev_is_running": running, "pm": lines_pm, "cfg": cfg})
    except Exception as e:
        print(e)
        return render(request, "middlebox/timeout.html", {"inside_ajax": True, "error": ("stamper status error "+str(e))})


# starts instance of p4 device software for handling the live table entries
def start_p4_dev_software(request):
    if request.is_ajax():
        try:
            start_stamper = rpyc.timed(core_conn.root.start_p4_dev_software, 80) ##netronome takes very long time
            answer = start_stamper()
            answer.wait()
            time.sleep(1) #TODO target dependend
            return render(request, "middlebox/empty.html")
        except Exception as e:
            return render(request, "middlebox/timeout.html", {"inside_ajax": True, "error": ("start stamper "+str(e))})


def get_p4_dev_startup_log(request):
    try:
        log = core_conn.root.get_p4_dev_startup_log()
        log = P4STA_utils.flt(log)
        return render(request, "middlebox/p4_dev_startup_log.html", {"log": log})
    except Exception as e:
        return render(request, "middlebox/timeout.html", {"inside_ajax": True, "error": ("stamper Log: "+str(e))})


 # pushes p4 table entries and port settings onto p4 device
def deploy(request):
    if not request.is_ajax():
        return
    try:
        deploy = rpyc.timed(core_conn.root.deploy, 20)
        answer = deploy()
        answer.wait()
        try:
            deploy_error = answer.value.replace("  ", "").replace("\n", "")
        except:
            deploy_error = ""
        return render(request, "middlebox/output_deploy.html", {"deploy_error": deploy_error})
    except Exception as e:
        print(e)
        return render(request, "middlebox/timeout.html", {"inside_ajax": True, "error": ("Exception Deploy: " + str(e))})


# stops instance of p4 device software for handling the live table entries
def stop_p4_dev_software(request):
    if request.is_ajax():
        try:
            answer = core_conn.root.stop_p4_dev_software()
            time.sleep(1)
            return render(request, "middlebox/empty.html")
        except Exception as e:
            return render(request, "middlebox/timeout.html", {"inside_ajax": True, "error": ("stop stamper error: "+str(e))})


# reboots packet generator server and client
def reboot(request):
    if request.is_ajax():
        try:
            answer = core_conn.root.reboot()
            return render(request, "middlebox/output_reboot.html")
        except Exception as e:
            return render(request, "middlebox/timeout.html", {"inside_ajax": True, "error": ("reboot host error: "+str(e))})


# executes ethtool -r at packet generators to refresh link status
def refresh_links(request):
    if request.is_ajax():
        try: 
            answer = core_conn.root.refresh_links()
            return render(request, "middlebox/output_refresh.html")
        except Exception as e:
            return render(request, "middlebox/timeout.html", {"inside_ajax": True, "error": ("refresh links error: "+str(e))})

        


# loads visualization html from p4 device if there is one.
def visualization(request):
    if request.is_ajax():
        try:
            html = core_conn.root.visualization()
            return HttpResponse(html)
        except Exception as e:
            return render(request, "middlebox/timeout.html", {"inside_ajax": True, "error": ("visualization error: "+str(e))})


        
####################################################################
################# RUN ##############################################
####################################################################

def page_run(request):
    cfg = P4STA_utils.read_current_cfg()
    return render(request, "middlebox/page_run.html", cfg)

# executes ping test
def ping(request):
    if request.is_ajax():
        try:
            output = core_conn.root.ping()
            output = P4STA_utils.flt(output)
            return render(request, "middlebox/output_ping.html", {"output": output})
        except Exception as e:
            return render(request, "middlebox/timeout.html", {"inside_ajax": True, "error": ("ping error: "+str(e))})

# starts python receiver instance at external host
def start_external(request):
    if request.is_ajax():
        cfg = P4STA_utils.read_current_cfg()
        new_id = core_conn.root.set_new_measurement_id()
        try:
            p4_dev_running, errors = core_conn.root.start_external()

            mtu_list = []
            for host in cfg["loadgen_servers"] + cfg["loadgen_clients"]:
                if "namespace_id" in host and host["namespace_id"] != "":
                    host["mtu"] = core_conn.root.fetch_mtu(host['ssh_user'], host['ssh_ip'], host['loadgen_iface'], host["namespace_id"])
                else:
                    host["mtu"] = core_conn.root.fetch_mtu(host['ssh_user'], host['ssh_ip'], host['loadgen_iface'])
                mtu_list.append(int(host["mtu"]))

            return render(request, "middlebox/external_started.html", {"running": p4_dev_running, "errors": list(errors), "cfg": cfg, "min_mtu": min(mtu_list)})

        except Exception as e:
            print(e)
            return render(request, "middlebox/timeout.html", {"inside_ajax": True, "error": ("start external host error: "+str(e))})


# resets registers in p4 device by overwriting them with 0
def reset(request):
    if request.is_ajax():
        try:
            answer = core_conn.root.reset()
            return render(request, "middlebox/output_reset.html", {"answer": answer})
        except Exception as e:
            return render(request, "middlebox/timeout.html", {"inside_ajax": True, "error": ("reset stamper register error: "+str(e))})


# stops last started instance of python receiver at external host and starts reading p4 registers
def stop_external(request):
    if request.is_ajax():
        try:
            stop_external = rpyc.timed(core_conn.root.stop_external, 60*50) # read time increases with amount of hosts
            stoppable = stop_external()
            stoppable.wait()
            return render(request, "middlebox/external_stopped.html", {"stoppable": stoppable.value})
        except Exception as e:
            return render(request, "middlebox/timeout.html", {"inside_ajax": True, "error": ("stop external host error: "+str(e))})


def run_loadgens_first(request): #called at Run if "Start" is clicked
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
        try:
            t_timeout = round(duration*1.5 + 20) 
            start_loadgens =  rpyc.timed(core_conn.root.start_loadgens, t_timeout) 
            file_id = start_loadgens(duration, l4_selected, packet_size_mtu)
            file_id.wait()
            return render_loadgens(request, file_id.value, duration=duration)

        except Exception as e:
            print("Exception in run_loadgens: "+ str(e))
            return render(request, "middlebox/timeout.html", {"inside_ajax": True, "error": ("run loadgen error: "+str(e))})


# loads loadgen results again without executing another test
def read_loadgen_results_again(request):
    global selected_run_id
    if request.is_ajax():
        return render_loadgens(request, selected_run_id)


def render_loadgens(request, file_id, duration=10):
    try:
        process_loadgens = rpyc.timed(core_conn.root.process_loadgens, duration*2)
        results = process_loadgens(file_id)
        results.wait()
        results = results.value
        if results is not None:
            output, total_bits, error, total_retransmits, total_byte, custom_attr, to_plot = results

            output = P4STA_utils.flt(output)
            custom_attr=P4STA_utils.flt(custom_attr)
            to_plot = P4STA_utils.flt(to_plot)
        else:
            error = True
            output = ["Sorry an error occured!", "The core returned NONE from loadgens which is a result of an internal error in the loadgen module."]
            total_bits = total_retransmits = total_byte = 0
            custom_attr = {"l4_type": "", "name_list": [], "elems":{}}

        cfg = P4STA_utils.read_result_cfg(file_id) 

        return render(request, "middlebox/output_loadgen.html",
                    {"cfg": cfg, "output": output, "total_gbits": calculate.find_unit_bit_byte(total_bits, "bit"), "cachebuster": str(time.time()).replace(".", ""),
                    "total_retransmits": total_retransmits, "total_gbyte": calculate.find_unit_bit_byte(total_byte, "byte"), "error": error, "custom_attr": custom_attr,
                    "filename": file_id, "time": time.strftime('%H:%M:%S %d.%m.%Y', time.localtime(int(file_id)))})#"mean_rtt": mean_rtt, "min_rtt": min_rtt, "max_rtt": max_rtt,
    except Exception as e:
        print(e)
        return render(request, "middlebox/timeout.html", {"inside_ajax": True, "error": ("render loadgen error: "+str(e))})

####################################################################
################# Analyze ##########################################
####################################################################


# writes id of selected dataset in config file and reload /analyze/
def page_analyze(request):
    global selected_run_id
    if request.method == "POST":
        selected_run_id = request.POST["set_id"]
        saved = True
    else:
        selected_run_id = core_conn.root.getLatestMeasurementId()
        saved = False

    return page_analyze_return(request, saved)

# return html object for /analyze/ and build list for selector of all available datasets
def page_analyze_return(request, saved):
    global selected_run_id
    if selected_run_id is None:
        selected_run_id = core_conn.root.getLatestMeasurementId()

    if selected_run_id is not None:
        id_int = int(selected_run_id)
        cfg = P4STA_utils.read_result_cfg(selected_run_id)
        id_ex = time.strftime('%H:%M:%S %d.%m.%Y', time.localtime(id_int))
        id_list = []
        found = core_conn.root.getAllMeasurements()

        for f in found:
            time_created = time.strftime('%H:%M:%S %d.%m.%Y', time.localtime(int(f)))
            id_list.append([f, time_created])
        id_list_final = []
        for f in range(0, len(id_list)):
            if id_list[f][1] != id_ex:
                id_list_final.append(id_list[f])
        error = False

    else:
        cfg = P4STA_utils.read_current_cfg()
        saved = False
        id_int = 0
        id_list_final = []
        id_ex = "no data sets available"
        error = True

    return render(request, "middlebox/page_analyze.html", {**cfg, **{'id': [id_int, id_ex], 'id_list': id_list_final, 'saved': saved, 'ext_host_real': cfg["ext_host_real"], "error": error}})

# delete selected data sets and reload /analyze/
def delete_data(request):
    if request.method == "POST":
        for e in list(request.POST):
            if not e == "csrfmiddlewaretoken":
                delete_by_id(e)

    return page_analyze_return(request, False)


# delete all files in filenames in directory results for selected id
def delete_by_id(file_id):
    core_conn.root.delete_by_id(file_id)


# reads p4 device results json and returns html object for /ouput_info/
def p4_dev_results(request):
    global selected_run_id
    if request.is_ajax():
        try:
            sw = core_conn.root.p4_dev_results(selected_run_id)
            sw = P4STA_utils.flt(sw)
            return render(request, "middlebox/output_p4_dev_results.html", sw)
        except Exception as e:
            print(e)
            return render(request, "middlebox/timeout.html", {"inside_ajax": True, "error": ("render stamper results error: "+str(e))})

# displays results from external host python receiver from return of calculate module
def external_results(request):
    global selected_run_id
    if request.is_ajax():
        cfg = P4STA_utils.read_result_cfg(selected_run_id)

        try:
            extH_results = calculate.main(str(selected_run_id), cfg["multicast"], P4STA_utils.get_results_path(selected_run_id))
            ipdv_range = extH_results["max_ipdv"] - extH_results["min_ipdv"]
            pdv_range = extH_results["max_pdv"] - extH_results["min_pdv"]
            rate_jitter_range = extH_results["max_packets_per_second"] - extH_results["min_packets_per_second"]
            latency_range = extH_results["max_latency"] - extH_results["min_latency"]

            display = True
            
            # list for "Dygraph" javascript graph
            graph_list = []
            counter = 1
            adjusted_latency_list, unit = calculate.find_unit(extH_results["latency_list"])
            for latency in adjusted_latency_list:
                graph_list.append([counter, latency])
                counter = counter + 1 #TODO use duplication factor instead of 1?

            time_created = time.strftime('%H:%M:%S %d.%m.%Y', time.localtime(int(selected_run_id)))

            return render(request, "middlebox/external_results.html",
                        {"display": display, "filename": selected_run_id, "raw_packets": extH_results["num_raw_packets"], 'time': time_created, "cfg": cfg, "cachebuster": str(time.time()).replace(".", ""),
                        "processed_packets": extH_results["num_processed_packets"], "average_latency": calculate.find_unit(extH_results["avg_latency"]),
                        "min_latency": calculate.find_unit(extH_results["min_latency"]), "max_latency": calculate.find_unit(extH_results["max_latency"]), "total_throughput": extH_results["total_throughput"], "unit": unit,
                        "min_ipdv": calculate.find_unit(extH_results["min_ipdv"]), "max_ipdv": calculate.find_unit(extH_results["max_ipdv"]), "ipdv_range": calculate.find_unit(ipdv_range), "min_pdv": calculate.find_unit(extH_results["min_pdv"]),
                        "max_pdv": calculate.find_unit([extH_results["max_pdv"]]), "ave_pdv": calculate.find_unit(extH_results["avg_pdv"]), "pdv_range": calculate.find_unit(pdv_range), "min_rate_jitter": extH_results["min_packets_per_second"],
                        "max_rate_jitter": extH_results["max_packets_per_second"], "ave_packet_sec": extH_results["avg_packets_per_second"], "rate_jitter_range": rate_jitter_range, "threshold": cfg["multicast"], "latencies": graph_list,
                        "ave_ipdv": calculate.find_unit(extH_results["avg_ipdv"]), "latency_range": calculate.find_unit(latency_range), "ave_abs_ipdv": calculate.find_unit(extH_results["avg_abs_ipdv"]),
                        "latency_std_deviation": calculate.find_unit(extH_results["latency_std_deviation"]), "latency_variance": calculate.find_unit_sqr(extH_results["latency_variance"])})

        except Exception as e:
            print(traceback.format_exc())
            return render(request, "middlebox/timeout.html", {"inside_ajax": True, "error": ("render external error: "+str(traceback.format_exc()))})



# packs zip object for results from external host
def download_external_results(request):
    global selected_run_id
    core_conn.root.external_results(selected_run_id) ## create output_external_host_...
    file_id = str(selected_run_id)
    files = [
        "management_ui/generated/latency.svg",
        "management_ui/generated/latency_sec.svg",
        "management_ui/generated/latency_bar.svg",
        "management_ui/generated/latency_sec_y0.svg",
        "management_ui/generated/latency_y0.svg",
        "management_ui/generated/ipdv.svg",
        "management_ui/generated/ipdv_sec.svg",
        "management_ui/generated/pdv.svg",
        "management_ui/generated/pdv_sec.svg",
        "management_ui/generated/speed.svg",
        "management_ui/generated/packet_rate.svg",
             ]
    folder = P4STA_utils.get_results_path(selected_run_id)
    for i in range(0, len(files)):
        name = files[i][files[i][16:].find("/")+17:]
        files[i] = [files[i], "graphs/" + name[:-4] + file_id + ".svg"]

    files.append([folder+"/timestamp1_list_" + file_id + ".csv", "results/timestamp1_list_" + file_id + ".csv"])
    files.append([folder+"/timestamp2_list_" + file_id + ".csv", "results/timestamp2_list_" + file_id + ".csv"])
    files.append([folder+"/total_throughput_" + file_id + ".csv","results/total_throughput_" + file_id + ".csv"])
    files.append([folder+"/throughput_at_time_" + file_id + ".csv", "results/throughput_at_time_" + file_id + ".csv"])
    files.append([folder+"/raw_packet_counter_" + file_id + ".csv", "results/raw_packet_counter_" + file_id + ".csv"])
    files.append([folder+"/output_external_host_" + file_id + ".txt", "results/output_external_host_" + file_id + ".txt"])
    files.append(["calculate/calculate.py", "calculate/calculate.py"])
    files.append(["calculate/README.MD", "calculate/README.MD"])

    f = open("create_graphs.sh", "w+")
    f.write("#!/bin/bash\n")
    f.write("python3 calculate/calculate.py --id "+ file_id)
    f.close()
    os.chmod("create_graphs.sh", 0o777) # make run script executable
    files.append(["create_graphs.sh", "create_graphs.sh"])    

    files.append([folder+"/config_" + file_id + ".json", "data/config_" + file_id + ".json"])

    zip_file = pack_zip(request, files, file_id, "external_host_")

    try:
        os.remove("create_graphs.sh")
    except:
        pass

    return zip_file


# packs zip object for results from p4 registers
def download_p4_dev_results(request):
    global selected_run_id
    folder =  P4STA_utils.get_results_path(selected_run_id)
    files = [
                [folder+"/p4_dev_" + str(selected_run_id) + ".json", "results/p4_dev_" + str(selected_run_id) + ".json"], 
                [folder+"/output_p4_device_" + str(selected_run_id) + ".txt", "results/output_p4_device_" + str(selected_run_id) + ".txt"]
        ]

    return pack_zip(request, files, str(selected_run_id), "p4_device_results_")


# packs zip object for results from load generator
def download_loadgen_results(request):
    global selected_run_id
    file_id = str(selected_run_id)
    cfg = P4STA_utils.read_result_cfg(selected_run_id)
    files = [
        ["management_ui/generated/loadgen_1.svg", "loadgen_1.svg"],
        ["management_ui/generated/loadgen_2.svg", "loadgen_2.svg"],
        ["management_ui/generated/loadgen_3.svg", "loadgen_3.svg"]
             ]

    folder =  P4STA_utils.get_results_path(selected_run_id)
    file_id = str(file_id)
    files.append([folder+"/output_loadgen_" + file_id + ".txt", "output_loadgen_" + file_id + ".txt"])
    zip_file = pack_zip(request, files, file_id, cfg["selected_loadgen"] + "_")
    return zip_file


# returns downloadable zip in browser
def pack_zip(request, files, file_id, zip_name):
    response = HttpResponse(content_type="application/zip")
    zip_file = zipfile.ZipFile(response, "w")
    for f in files:
        try:
            zip_file.write(filename=f[0], arcname=f[1])
        except FileNotFoundError:
            print(str(f) + ": adding to zip object failed")
            continue  # if a file is not found continue writing the remaining files in the zip file
    zip_file.close()
    if file_id is not None:
      response["Content-Disposition"] = "attachment; filename={}".format(zip_name + str(file_id) + ".zip")

    return response
