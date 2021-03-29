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
import os
import time
import traceback
import zipfile

from django.http import HttpResponse
from django.shortcuts import render

# custom python modules
from analytics import analytics
from core import P4STA_utils

# globals
from management_ui import globals


# writes id of selected dataset in config file and reload /analyze/
def page_analyze(request):
    if request.method == "POST":
        globals.selected_run_id = request.POST["set_id"]
        saved = True
    else:
        globals.selected_run_id = \
            globals.core_conn.root.getLatestMeasurementId()
        saved = False

    return page_analyze_return(request, saved)


# return html object for /analyze/ and build list
# for selector of all available datasets
def page_analyze_return(request, saved):
    if globals.selected_run_id is None:
        globals.selected_run_id = globals.core_conn.root. \
            getLatestMeasurementId()

    if globals.selected_run_id is not None:
        id_int = int(globals.selected_run_id)
        cfg = P4STA_utils.read_result_cfg(globals.selected_run_id)
        id_ex = time.strftime('%H:%M:%S %d.%m.%Y', time.localtime(id_int))
        id_list = []
        found = globals.core_conn.root.getAllMeasurements()

        for f in found:
            time_created = time.strftime('%H:%M:%S %d.%m.%Y', time.localtime(
                int(f)))
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

    return render(request, "middlebox/page_analyze.html",
                  {**cfg, **{
                      "id": [id_int, id_ex],
                      "id_list": id_list_final,
                      "saved": saved,
                      "ext_host_real": cfg["ext_host_real"],
                      "error": error}})


# delete selected data sets and reload /analyze/
def delete_data(request):
    if request.method == "POST":
        for e in list(request.POST):
            if not e == "csrfmiddlewaretoken":
                delete_by_id(e)

    return page_analyze_return(request, False)


# delete all files in filenames in directory results for selected id
def delete_by_id(file_id):
    globals.core_conn.root.delete_by_id(file_id)


# reads stamper results json and returns html object for /ouput_info/
def stamper_results(request):
    if request.is_ajax():
        try:
            sw = globals.core_conn.root.stamper_results(
                globals.selected_run_id)
            sw = P4STA_utils.flt(sw)
            if "error" in sw:
                raise Exception(sw["error"])
            return render(request, "middlebox/output_stamper_results.html", sw)
        except Exception as e:
            print(e)
            return render(request, "middlebox/timeout.html",
                          {"inside_ajax": True, "error":
                              ("render stamper results error: " + str(e))})


# displays results from external host python receiver
# from return of analytics module
def external_results(request):
    if request.is_ajax():
        cfg = P4STA_utils.read_result_cfg(globals.selected_run_id)

        try:
            extH_results = analytics.main(str(globals.selected_run_id),
                                          cfg["multicast"],
                                          P4STA_utils.get_results_path(
                                              globals.selected_run_id))
            ipdv_range = extH_results["max_ipdv"] - extH_results["min_ipdv"]
            pdv_range = extH_results["max_pdv"] - extH_results["min_pdv"]
            rate_jitter_range = extH_results["max_packets_per_second"] - \
                extH_results["min_packets_per_second"]
            latency_range = extH_results["max_latency"] - extH_results[
                "min_latency"]

            display = True

            time_created = time.strftime('%H:%M:%S %d.%m.%Y', time.localtime(
                int(globals.selected_run_id)))

            return render(request, "middlebox/output_external_results.html",
                          {"display": display,
                           "filename": globals.selected_run_id,
                           "raw_packets": extH_results["num_raw_packets"],
                           "time": time_created,
                           "cfg": cfg,
                           "cachebuster": str(time.time()).replace(".", ""),
                           "processed_packets":
                               extH_results["num_processed_packets"],
                           "average_latency": analytics.find_unit(
                               extH_results["avg_latency"]),
                           "min_latency": analytics.find_unit(
                               extH_results["min_latency"]),
                           "max_latency": analytics.find_unit(
                               extH_results["max_latency"]),
                           "total_throughput": extH_results[
                               "total_throughput"],
                           "min_ipdv": analytics.find_unit(
                               extH_results["min_ipdv"]),
                           "max_ipdv": analytics.find_unit(
                               extH_results["max_ipdv"]),
                           "ipdv_range": analytics.find_unit(ipdv_range),
                           "min_pdv": analytics.find_unit(
                               extH_results["min_pdv"]),
                           "max_pdv": analytics.find_unit(
                               [extH_results["max_pdv"]]),
                           "ave_pdv": analytics.find_unit(
                               extH_results["avg_pdv"]),
                           "pdv_range": analytics.find_unit(pdv_range),
                           "min_rate_jitter": extH_results[
                               "min_packets_per_second"],
                           "max_rate_jitter": extH_results[
                               "max_packets_per_second"],
                           "ave_packet_sec": extH_results[
                               "avg_packets_per_second"],
                           "rate_jitter_range": rate_jitter_range,
                           "threshold": cfg["multicast"],
                           "ave_ipdv": analytics.find_unit(
                               extH_results["avg_ipdv"]),
                           "latency_range": analytics.find_unit(latency_range),
                           "ave_abs_ipdv": analytics.find_unit(
                               extH_results["avg_abs_ipdv"]),
                           "latency_std_deviation": analytics.find_unit(
                               extH_results["latency_std_deviation"]),
                           "latency_variance": analytics.find_unit_sqr(
                               extH_results["latency_variance"])})

        except Exception:
            print(traceback.format_exc())
            return render(request, "middlebox/timeout.html",
                          {"inside_ajax": True, "error": (
                                      "render external error: " + str(
                                                  traceback.format_exc()))})


def get_ext_host_zip_list():
    globals.core_conn.root.external_results(globals.selected_run_id)
    fid = str(globals.selected_run_id)
    files = [
        "results/" + fid + "/generated/latency.svg",
        "results/" + fid + "/generated/latency_sec.svg",
        "results/" + fid + "/generated/latency_bar.svg",
        "results/" + fid + "/generated/latency_sec_y0.svg",
        "results/" + fid + "/generated/latency_y0.svg",
        "results/" + fid + "/generated/ipdv.svg",
        "results/" + fid + "/generated/ipdv_sec.svg",
        "results/" + fid + "/generated/pdv.svg",
        "results/" + fid + "/generated/pdv_sec.svg",
        "results/" + fid + "/generated/speed.svg",
        "results/" + fid + "/generated/packet_rate.svg",
        "results/" + fid + "/generated/speed_upscaled.svg",
        "results/" + fid + "/generated/packet_rate_upscaled.svg",
    ]

    folder = P4STA_utils.get_results_path(fid)
    for i in range(0, len(files)):
        name = files[i][files[i][16:].find("/") + 17:]
        files[i] = [files[i], "results/" + fid + "/" +
                    name[:-4] + fid + ".svg"]

    files.append([folder + "/timestamp1_list_" + fid + ".csv",
                  "results/" + fid + "/timestamp1_list_" + fid + ".csv"])
    files.append([folder + "/timestamp2_list_" + fid + ".csv",
                  "results/" + fid + "/timestamp2_list_" + fid + ".csv"])
    files.append([folder + "/packet_sizes_" + fid + ".csv",
                  "results/" + fid + "/packet_sizes_" + fid + ".csv"])
    files.append([folder + "/raw_packet_counter_" + fid + ".csv",
                  "results/" + fid + "/raw_packet_counter_" + fid + ".csv"])
    files.append([folder + "/output_external_host_" + fid + ".txt",
                  "results/" + fid + "/output_external_host_" + fid + ".txt"])
    files.append(["analytics/analytics.py", "analytics/analytics.py"])
    files.append(["analytics/README.MD", "analytics/README.MD"])

    f = open("create_graphs.sh", "w+")
    f.write("#!/bin/bash\n")
    f.write("python3 analytics/analytics.py --id " + fid)
    f.close()
    os.chmod("create_graphs.sh", 0o777)  # make run script executable
    files.append(["create_graphs.sh", "create_graphs.sh"])

    files.append([folder + "/config_" + fid + ".json",
                  "data/config_" + fid + ".json"])

    return files


# packs zip object for results from external host
def download_external_results(request):
    files = get_ext_host_zip_list()
    file_id = str(globals.selected_run_id)

    zip_file = pack_zip(files, file_id, "external_host_")

    try:
        os.remove("create_graphs.sh")
    except Exception:
        pass

    return zip_file


def download_all_zip(request):
    # first check if cached results are already available
    # this step is not neccessary for download_external_results because
    # it's only possible to trigger inside the ext host results view
    # which already generated the graphs
    cfg = P4STA_utils.read_result_cfg(globals.selected_run_id)
    folder = P4STA_utils.get_results_path(globals.selected_run_id)
    fid = str(globals.selected_run_id)

    # ext host
    files = get_ext_host_zip_list()
    trigger_generation = False
    for file in files:
        if not os.path.isfile(file[0]):
            trigger_generation = True
    if trigger_generation:
        # trigger generation of graphs
        _ = analytics.main(
            str(globals.selected_run_id), cfg["multicast"],
            P4STA_utils.get_results_path(globals.selected_run_id)
        )

    # stamper
    files.append([folder + "/stamper_" + fid + ".json",
                  "results/" + fid + "/stamper_" + fid + ".json"])
    files.append([folder + "/output_stamperice_" + fid + ".txt",
                  "results/" + fid + "/output_stamperice_" + fid + ".txt"])

    # loadgen
    files.extend([
        ["results/" + fid + "/generated/loadgen_1.svg",
         "results/" + fid + "/generated/loadgen_1.svg"],
        ["results/" + fid + "/generated/loadgen_2.svg",
         "results/" + fid + "/generated/loadgen_2.svg"],
        ["results/" + fid + "/generated/loadgen_3.svg",
         "results/" + fid + "/generated/loadgen_3.svg"]
    ])

    zip = pack_zip(files, fid, "stamper_and_ext_host_")

    try:
        os.remove("create_graphs.sh")
    except Exception:
        pass

    return zip


# packs zip object for results from p4 registers
def download_stamper_results(request):
    folder = P4STA_utils.get_results_path(globals.selected_run_id)
    files = [
        [folder + "/stamper_" + str(globals.selected_run_id) + ".json",
         "results/stamper_" + str(globals.selected_run_id) + ".json"],
        [folder + "/output_stamperice_" + str(
            globals.selected_run_id) + ".txt",
         "results/output_stamperice_" + str(globals.selected_run_id) + ".txt"]
    ]

    return pack_zip(files, str(globals.selected_run_id),
                    "stamperice_results_")


# packs zip object for results from load generator
def download_loadgen_results(request):
    file_id = str(globals.selected_run_id)
    cfg = P4STA_utils.read_result_cfg(globals.selected_run_id)

    files = [
        ["results/" + file_id + "/generated/loadgen_1.svg", "loadgen_1.svg"],
        ["results/" + file_id + "/generated/loadgen_2.svg", "loadgen_2.svg"],
        ["results/" + file_id + "/generated/loadgen_3.svg", "loadgen_3.svg"]
    ]

    folder = P4STA_utils.get_results_path(globals.selected_run_id)
    file_id = str(file_id)
    files.append([folder + "/output_loadgen_" + file_id + ".txt",
                  "output_loadgen_" + file_id + ".txt"])
    zip_file = pack_zip(files, file_id, cfg["selected_loadgen"] + "_")
    return zip_file


# returns downloadable zip in browser
def pack_zip(files, file_id, zip_name):
    response = HttpResponse(content_type="application/zip")
    zip_file = zipfile.ZipFile(response, "w")
    for f in files:
        try:
            zip_file.write(filename=f[0], arcname=f[1])
        except FileNotFoundError:
            print(str(f) + ": adding to zip object failed")
            # if a file is not found continue writing the
            # remaining files in the zip file
            continue
    zip_file.close()
    if file_id is not None:
        response["Content-Disposition"] = "attachment; filename={}".format(
            zip_name + str(file_id) + ".zip")

    return response


def dygraph(request):
    if request.is_ajax():
        cfg = P4STA_utils.read_result_cfg(globals.selected_run_id)
        try:
            extH_results = analytics.main(str(globals.selected_run_id),
                                          cfg["multicast"],
                                          P4STA_utils.get_results_path(
                                              globals.selected_run_id))
            # list for "Dygraph" javascript graph
            graph_list = []
            counter = 1
            adjusted_latency_list, unit = analytics.find_unit(
                extH_results["latency_list"])
            for latency in adjusted_latency_list:
                graph_list.append([counter, latency])
                counter = counter + 1

            timestamp1_list = analytics.read_csv(
                P4STA_utils.get_results_path(globals.selected_run_id),
                "timestamp1_list", str(globals.selected_run_id))
            timestamp2_list = analytics.read_csv(
                P4STA_utils.get_results_path(globals.selected_run_id),
                "timestamp2_list", str(globals.selected_run_id))

            # time in ms when packet was timestamped but starting at 0 ms
            time_throughput = []
            if len(timestamp1_list) > 0 and len(timestamp1_list) == len(
                    timestamp2_list):
                for i in range(0, len(timestamp1_list)):
                    time_throughput.append(int(round(
                        (timestamp2_list[i] - timestamp2_list[0]) / 1000000)))

            return render(request, "middlebox/dygraph.html",
                          {"latencies": graph_list,
                           "time_throughput": time_throughput, "unit": unit})

        except Exception:
            print(traceback.format_exc())
            return render(request, "middlebox/timeout.html",
                          {"inside_ajax": True, "error": (
                                      "render external error: " + str(
                                              traceback.format_exc()))})
