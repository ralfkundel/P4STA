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

from django.shortcuts import render

# custom python modules
from core import P4STA_utils

# globals
from management_ui import globals


# return html object for /deploy/
def page_deploy(request):
    return render(request, "middlebox/page_deploy.html")


# shows current p4 device status and status of packet generators
def stamper_status(request):
    return stamper_status_wrapper(
        request, "middlebox/output_stamper_software_status.html")


def stamper_ports(request):
    return stamper_status_wrapper(
        request, "middlebox/portmanager.html")


def host_iface_status(request):
    return stamper_status_wrapper(request, "middlebox/host_iface_status.html")


def stamper_status_wrapper(request, html_file):
    stamper_status = rpyc.timed(globals.core_conn.root.stamper_status, 40)
    stamper_status_job = stamper_status()
    try:
        stamper_status_job.wait()
        result = stamper_status_job.value
        cfg, lines_pm, running, dev_status = result
        cfg = P4STA_utils.flt(cfg)  # cfg contains host status information
        lines_pm = P4STA_utils.flt(lines_pm)

        return render(request, html_file,
                      {"dev_status": dev_status, "dev_is_running": running,
                       "pm": lines_pm, "cfg": cfg})
    except Exception as e:
        print(e)
        return render(
            request, "middlebox/timeout.html",
            {"inside_ajax": True, "error": ("stamper status error "+str(e))})


# starts instance of p4 device software for handling the live table entries
def start_stamper_software(request):
    if request.is_ajax():
        try:
            # some stamper targets may take long time to start
            start_stamper = rpyc.timed(
                globals.core_conn.root.start_stamper_software, 80)
            answer = start_stamper()
            answer.wait()
            if answer.value is not None:
                raise Exception(answer.value)

            time.sleep(1)
            return render(request, "middlebox/empty.html")
        except Exception as e:
            return render(
                request, "middlebox/timeout.html",
                {"inside_ajax": True, "error": ("start stamper "+str(e))})


def get_stamper_startup_log(request):
    try:
        log = globals.core_conn.root.get_stamper_startup_log()
        log = P4STA_utils.flt(log)
        return render(
            request, "middlebox/stamper_startup_log.html", {"log": log})
    except Exception as e:
        return render(
            request, "middlebox/timeout.html",
            {"inside_ajax": True, "error": ("stamper Log: "+str(e))})


# pushes p4 table entries and port settings onto p4 device
def deploy(request):
    if not request.is_ajax():
        return
    try:
        deploy = rpyc.timed(globals.core_conn.root.deploy, 40)
        answer = deploy()
        answer.wait()
        try:
            deploy_error = answer.value.replace("  ", "").replace("\n", "")
        except Exception:
            deploy_error = ""
        return render(request, "middlebox/output_deploy.html",
                      {"deploy_error": deploy_error})
    except Exception as e:
        print(e)
        return render(
            request, "middlebox/timeout.html",
            {"inside_ajax": True, "error": ("Exception Deploy: " + str(e))})


# stops instance of p4 device software for handling the live table entries
def stop_stamper_software(request):
    if request.is_ajax():
        try:
            globals.core_conn.root.stop_stamper_software()
            time.sleep(1)
            return render(request, "middlebox/empty.html")
        except Exception as e:
            return render(
                request, "middlebox/timeout.html",
                {"inside_ajax": True, "error": ("stop stamper err:" + str(e))})


# reboots packet generator server and client
def reboot(request):
    if request.is_ajax():
        try:
            globals.core_conn.root.reboot()
            return render(request, "middlebox/output_reboot.html")
        except Exception as e:
            return render(
                request, "middlebox/timeout.html",
                {"inside_ajax": True, "error": ("reboot host error: "+str(e))})


# executes ethtool -r at packet generators to refresh link status
def refresh_links(request):
    if request.is_ajax():
        try:
            globals.core_conn.root.refresh_links()
            return render(request, "middlebox/output_refresh.html")
        except Exception as e:
            return render(
                request, "middlebox/timeout.html",
                {"inside_ajax": True,
                 "error": ("refresh links error: "+str(e))})
