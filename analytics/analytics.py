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

###############################################
# Creates graphs out of csv files from python #
# receiver; can be used included in views.py  #
# OR                                          #
# standalone by passing the --id flag         #
# OR                                          #
# standalone using the config in readme.txt   #
###############################################
import argparse
import csv
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import logging
import multiprocessing
import numpy as np
import os
import re
import sys
import tempfile
import threading
import time

import matplotlib
matplotlib.use("Agg")
try:
    import matplotlib.pyplot as plt
except Exception as e:
    # prevent PEP3 warning because Agg import must be before pyplot
    raise e


csv.field_size_limit(sys.maxsize)
dir_path = os.path.dirname(os.path.realpath(__file__))
project_path = dir_path[0:dir_path.find("/analytics")]
lock = threading.RLock()


def get_fallback_logger():
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.DEBUG)
    logger.info("Using default Python logger as fallback.")
    return logger


# read the csv files and plots the graphs
def main(file_id, multicast, results_path, logger=None):
    def thread_join(thrs):
        for thread in thrs:
            thread.start()
        for thread in thrs:
            thread.join()

    if logger == None:
        logger = get_fallback_logger()

    fpath = project_path + "/results/" + str(
        file_id) + "/generated/extHost_results.json"
    if os.path.isfile(fpath):
        with open(fpath, "r") as f:
            dict_from_json = json.load(f)
            if "pos_latency_std_deviation" in dict_from_json:
                logger.info("Using cached version of " + fpath)
                return dict_from_json
            else:
                logger.info("Calculating results with newest P4STA features ...")

    start = time.time()
    raw_packet_counter = read_csv(logger, results_path, "raw_packet_counter", file_id)[0]
    packet_sizes = read_csv(logger, results_path, "packet_sizes", file_id)
    timestamp1_list = read_csv(logger, results_path, "timestamp1_list", file_id)
    timestamp2_list = read_csv(logger, results_path, "timestamp2_list", file_id)
    end = time.time()
    logger.debug("It took " + str(end-start) + "s to load csv files for P4STA analytics.")

    # get list of cumulative packet sizes
    throughput_at_time = []
    total_throughput = 0
    
    # debugging
    logger.debug("LEN PACKET SIZES: " + str(len(packet_sizes)) )
    logger.debug("len(timestamp1_list) = " + str(len(timestamp1_list)))
    logger.debug("len(timestamp2_list) = " + str(len(timestamp2_list)))

    for i in range(len(packet_sizes)):
        total_throughput = total_throughput + packet_sizes[i]
        throughput_at_time.append(total_throughput)

    latency_list = []
    min_latency = max_latency = ave_latency = latency_variance = 0
    latency_std_deviation = pos_latency_std_deviation = neg_latency_std_deviation = 0
    total_ipdv = abs_total_ipdv = total_pdv = total_latencies = 0
    min_ipdv = max_ipdv = ave_ipdv = ave_abs_ipdv = 0
    min_pdv = max_pdv = ave_pdv = 0
    min_packets = max_packets = ave_packet_sec = 0
    ipdv_list = []
    count_list = []
    count_list_sec = []
    pdv_list = []
    mbit_list = []
    packet_list = []
    time_throughput = []
    if len(timestamp1_list) > 0 and len(timestamp2_list) > 0:
        if timestamp1_list[0] > 0 and len(timestamp1_list) == len(timestamp2_list):
            # creates list of all latencies

            # 50% faster than for loop calculating t2-t1 for each packet
            latency_list = list(map(int.__sub__, timestamp2_list, timestamp1_list))
            total_latencies = sum(latency_list) # maybe numpy sum here
            for i in range(0, len(timestamp1_list)):
                # sets the start time to 0 ms
                diff = timestamp2_list[i] - timestamp2_list[0]
                time_throughput.append(int(round(diff / 1000000)))
                # - [0] to set first time to 0 sec
                count_list_sec.append(diff / 1000000000)
            # minimum and maximum latency
            min_latency = min(latency_list, default=0)
            max_latency = max(latency_list, default=0)
            # fills pdv and ipdv lists
            for z in range(0, len(latency_list)):
                count_list.append(z)
                pdv = latency_list[z] - min_latency
                pdv_list.append(pdv)
                total_pdv = total_pdv + pdv
                if 0 < z < len(latency_list):
                    ipdv = latency_list[z] - latency_list[z - 1]
                    ipdv_list.append(ipdv)
                    total_ipdv = total_ipdv + ipdv
                    abs_total_ipdv = abs_total_ipdv + abs(ipdv)
                else:
                    ipdv_list.append(0)
            # calculate average latency, ipdv and pdv
            if len(latency_list) > 0:
                ave_latency = round(total_latencies / len(latency_list), 2)
                ave_ipdv = round(total_ipdv / len(ipdv_list))
                ave_abs_ipdv = round(abs_total_ipdv / len(ipdv_list))
                ave_pdv = round(total_pdv / len(pdv_list))
                # calculate standard deviation of latency
                total_sqr_dev = 0
                pos_sqr_dev = 0
                pos_counter = 0
                neg_sqr_dev = 0
                neg_counter = 0
                for z in range(0, len(latency_list)):
                    total_sqr_dev += (latency_list[z] - ave_latency)**2
                    # we count equal values to positive
                    if latency_list[z] >= ave_latency:
                        pos_sqr_dev += (latency_list[z] - ave_latency)**2
                        pos_counter += 1
                    else:
                        neg_sqr_dev += (latency_list[z] - ave_latency)**2
                        neg_counter += 1


                latency_variance = total_sqr_dev / len(ipdv_list)
                latency_std_deviation = latency_variance ** 0.5

                if pos_counter > 0:
                    pos_latency_std_deviation = (pos_sqr_dev / pos_counter) ** 0.5
                else:
                    pos_latency_std_deviation = 0

                if neg_counter > 0:
                    neg_latency_std_deviation = (neg_sqr_dev / neg_counter) ** 0.5
                else:
                    neg_latency_std_deviation = 0


            # minimum and maximum ipdv
            min_ipdv = min(ipdv_list, default=0)
            max_ipdv = max(ipdv_list, default=0)
            # minimum and maximum pdv
            min_pdv = min(pdv_list, default=0)
            max_pdv = max(pdv_list, default=0)
            # fill speed and packet rate lists
            last_time_hit = 0
            last_throughput_hit = 0
            last_packet_hit = 0
            mbit_list.append(0)
            packet_list.append(0)
            # prepares lists for speed and packet rate graph
            for y in range(0, len(throughput_at_time)):
                # more than 99ms difference -> 0.1s intervals
                if (time_throughput[y] - last_time_hit) >= 100:
                    amount = (time_throughput[y] - last_time_hit) / 100
                    # more than 200ms difference between two hits -> pause
                    if amount >= 2:
                        for i in range(0, int(round(amount))):
                            mbit_list.append(0)
                            packet_list.append(0)
                    last_time_hit = time_throughput[y]
                    # byte->megabit/10 measure every 0.1s but unit is mbit/s
                    mbit_list.append((throughput_at_time[y] -
                                      last_throughput_hit) * 8 / 100000)
                    # *10 measure for every 0.1s but unit is packets/seconds
                    packet_list.append((y - last_packet_hit)*10)
                    last_packet_hit = y
                    last_throughput_hit = throughput_at_time[y]
            mbit_list.append(0)  # set next entry to 0
            packet_list.append(0)

            # round by 9 digits after , float could result in weird fractions
            upsc_mbit_list = [round(x*int(multicast), 9) for x in mbit_list]

            upsc_packet_list = [x*int(multicast) for x in packet_list]
            # ignores the first and last second to prevent min = 0
            min_packets = min(packet_list[1:-1], default=0)
            max_packets = max(packet_list, default=0)
            if len(packet_list) != 2:
                # -2 because added 0 at start and end. *10 because of 0.1s step
                ave_packet_sec = round(
                    (len(throughput_at_time)/(len(packet_list)-2)) * 10, 2)
            else:
                ave_packet_sec = 0

            start = time.time()
            processes = []
            x = multiprocessing.Process(
                target=plot_graph, args=(
                    latency_list, count_list,
                    "Latency of DUT for every " + multicast + ". packet",
                    "Packets", "Latency", "latency", True, False, file_id))
            processes.append(x)

            x = multiprocessing.Process(
                target=plot_graph, args=(
                    latency_list, count_list_sec,
                    "Latency of DUT for every " + multicast + ". packet",
                    "t[s]", "Latency", "latency_sec", True, False, file_id))
            processes.append(x)

            x = multiprocessing.Process(
                target=plot_graph, args=(
                    latency_list, count_list,
                    "Latency of DUT for every " + multicast + ". packet",
                    "Packets", "Latency", "latency_y0", True, True, file_id))
            processes.append(x)

            x = multiprocessing.Process(
                target=plot_graph, args=(
                    latency_list, count_list_sec,
                    "Latency of DUT for every " + multicast + ". packet",
                    "t[s]", "Latency", "latency_sec_y0", True, True, file_id))
            processes.append(x)

            x = multiprocessing.Process(
                target=plot_graph, args=(
                    ipdv_list, count_list,
                    "IPDVs of DUT for every " + multicast + ". packet",
                    "IPDV", "Packets", "ipdv", True, False, file_id))
            processes.append(x)

            x = multiprocessing.Process(
                target=plot_graph, args=(
                    ipdv_list, count_list_sec,
                    "IPDVs of DUT for every " + multicast + ". packet",
                    "t[s]", "IPDV", "ipdv_sec", True, False, file_id))
            processes.append(x)

            x = multiprocessing.Process(
                target=plot_graph, args=(
                    pdv_list, count_list,
                    "PDVs of DUT for every " + multicast + ". packet",
                    "Packets", "PDV", "pdv", True, False, file_id))
            processes.append(x)

            x = multiprocessing.Process(
                target=plot_graph, args=(
                    pdv_list, count_list_sec,
                    "PDVs of DUT for every " + multicast + ". packet",
                    "t[s]", "PDV", "pdv_sec", True, False, file_id))
            processes.append(x)

            x = multiprocessing.Process(
                target=plot_graph, args=(
                    mbit_list, np.arange(0, len(mbit_list) / 10, 0.1),
                    "Throughput of DUT for every " + multicast + ". packet",
                    "t[s]", "Megabit/s", "speed", False, False, file_id))
            processes.append(x)

            x = multiprocessing.Process(
                target=plot_graph, args=(
                    upsc_mbit_list,
                    np.arange(0, len(upsc_mbit_list) / 10, 0.1),
                    "Upscaled throughput of DUT", "t[s]", "Megabit/s",
                    "speed_upscaled", False, False, file_id))
            processes.append(x)

            x = multiprocessing.Process(
                target=plot_graph, args=(
                    upsc_packet_list,
                    np.arange(0, len(upsc_packet_list) / 10, 0.1),
                    "Upscaled rate jitter of DUT", "t[s]", "Packet/s",
                    "packet_rate_upscaled", False, False, file_id))
            processes.append(x)

            x = multiprocessing.Process(
                target=plot_graph, args=(
                    packet_list, np.arange(0, len(packet_list) / 10, 0.1),
                    "Rate jitter of DUT for every " + multicast + ". packet",
                    "t[s]", "Packet/s", "packet_rate", False, False, file_id))
            processes.append(x)

            x = multiprocessing.Process(
                target=plot_bar, args=(
                    latency_list, min_latency, max_latency, "latency_bar",
                    "Latency", "Packets", 10, True, file_id))
            processes.append(x)

            thread_join(processes)
            end = time.time()
            logger.debug("MULTIP: It took " + str(end - start) + " s to plot graphs in analytics.")

    results = {"num_raw_packets": raw_packet_counter,
               "num_processed_packets": len(latency_list),
               "total_throughput": round(total_throughput/1000000, 2),
               "min_latency": min_latency, "max_latency": max_latency,
               "avg_latency": ave_latency, "min_ipdv": min_ipdv,
               "max_ipdv": max_ipdv, "avg_ipdv": ave_ipdv,
               "avg_abs_ipdv": ave_abs_ipdv, "min_pdv": min_pdv,
               "max_pdv": max_pdv, "avg_pdv": ave_pdv,
               "min_packets_per_second": min_packets,
               "max_packets_per_second": max_packets,
               "avg_packets_per_second": ave_packet_sec,
               "latency_std_deviation": latency_std_deviation,
               "pos_latency_std_deviation": pos_latency_std_deviation,
               "neg_latency_std_deviation": neg_latency_std_deviation,
               "latency_variance": latency_variance,
               "latency_list": latency_list}
    if __name__ == "__main__":
        fpath = "extHost_results.json"
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=4)

    return results


# Session figures have their own cache, so older classic caches remain usable.
SESSION_CACHE_VERSION = 6
SESSION_PLOT_LIMIT = 12
# Developer option: extra plotting processes trade RAM for faster cold loads.
# Keep disabled on small hosts. Existing cached SVGs are reused in either mode.
SESSION_PARALLEL_PLOTS = True
SESSION_PARALLEL_THRESHOLD = 100000
SESSION_MAX_PLOT_WORKERS = 4


def read_session_packets(file_id, results_path):
    values = {}
    for name in ("session_identifier_list", "timestamp1_list",
                 "timestamp2_list", "packet_sizes"):
        values[name] = []
        with open(os.path.join(results_path, name + "_" + str(file_id)
                               + ".csv"), "r", encoding="utf-8") as csv_input:
            for row in csv.reader(csv_input):
                if len(row) != 1 or not row[0].strip():
                    raise ValueError("Invalid row in " + name + ".csv.")
                if name == "session_identifier_list":
                    # Identifiers are opaque labels, including zero and IPs.
                    values[name].append(row[0])
                else:
                    values[name].append(int(row[0]))
    lengths = [len(value) for value in values.values()]
    if len(set(lengths)) != 1:
        raise ValueError("The session identifier, timestamp and packet-size "
                         "CSV files have different row counts. Packets cannot "
                         "be matched to session identifiers.")
    if not lengths[0]:
        raise ValueError("No timestamped packets are available for session analysis.")
    if any(value < 0 for name in ("timestamp1_list", "timestamp2_list", "packet_sizes")
           for value in values[name]):
        raise ValueError("Timestamps and packet sizes must not be negative.")
    return values


def calculate_session_results(values):
    sessions = {}
    origin = min(values["timestamp2_list"])
    for index, identifier in enumerate(values["session_identifier_list"]):
        if identifier not in sessions:
            sessions[identifier] = {"identifier": identifier, "latency": [],
                                    "packets": [], "time": [], "sizes": [],
                                    "bins": []}
        session = sessions[identifier]
        session["latency"].append(values["timestamp2_list"][index]
                                  - values["timestamp1_list"][index])
        session["packets"].append(index)
        elapsed = values["timestamp2_list"][index] - origin
        session["time"].append(elapsed / 1000000000)
        session["bins"].append(elapsed // 100000000)
        session["sizes"].append(values["packet_sizes"][index])

    summaries = []
    for color_index, identifier in enumerate(sorted(sessions)):
        session = sessions[identifier]
        session["color_index"] = color_index
        latency = session["latency"]
        minimum = min(latency)
        average = sum(latency) / len(latency)
        # Match the classic convention: the first IPDV sample is zero.
        session["ipdv"] = [0] + [latency[i] - latency[i - 1]
                                   for i in range(1, len(latency))]
        session["pdv"] = [value - minimum for value in latency]
        summaries.append({
            "identifier": identifier, "num_packets": len(latency),
            "total_bytes": sum(session["sizes"]),
            "min_latency": minimum, "max_latency": max(latency),
            "avg_latency": round(average, 2),
            "latency_std_deviation": (sum((value - average)**2
                                           for value in latency) / len(latency))**0.5,
            "avg_abs_ipdv": sum(abs(value) for value in session["ipdv"]) / len(latency),
            "avg_pdv": sum(session["pdv"]) / len(latency),
        })
    return sessions, summaries


def session_main(file_id, multicast, results_path, logger=None,
                 session_identifier=None):
    if logger is None:
        logger = get_fallback_logger()
    identifier_path = os.path.join(results_path, "session_identifier_list_"
                                   + str(file_id) + ".csv")
    if not os.path.isfile(identifier_path):
        return {"available": False,
                "message": "No session identifier CSV is available for this measurement."}

    # Include source timestamps/sizes, sampling factor and format version. A
    # replaced CSV or changed sampling factor must not reuse an old figure.
    try:
        sources = []
        for name in ("session_identifier_list", "timestamp1_list",
                     "timestamp2_list", "packet_sizes"):
            stat = os.stat(os.path.join(results_path, name + "_" + str(file_id) + ".csv"))
            sources.append([name, stat.st_size, stat.st_mtime_ns])
        factor = int(multicast)
        if factor < 1:
            raise ValueError("The sampling factor must be at least one.")
    except (OSError, ValueError, TypeError) as exc:
        return {"available": False, "message": "Session analysis unavailable: " + str(exc)}
    signature = json.dumps([SESSION_CACHE_VERSION, SESSION_PLOT_LIMIT,
                            factor, sources]).encode("utf-8")
    cache_name = "sessions_" + hashlib.sha256(signature).hexdigest()[:16]
    cache_path = os.path.join(results_path, "generated", cache_name)
    summary_path = os.path.join(cache_path, "summary.json")
    sessions = None
    with lock:
        if os.path.isfile(summary_path):
            with open(summary_path, "r", encoding="utf-8") as f:
                summaries = json.load(f)
        else:
            try:
                values = read_session_packets(file_id, results_path)
                sessions, summaries = calculate_session_results(values)
            except (OSError, ValueError) as exc:
                logger.warning("Session analysis unavailable: " + str(exc))
                return {"available": False, "message": str(exc)}
            os.makedirs(cache_path, exist_ok=True)
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(summaries, f, indent=4)

        identifiers = [session["identifier"] for session in summaries]
        if session_identifier is None:
            selected = identifiers[:SESSION_PLOT_LIMIT]
            prefix = "all"
        elif session_identifier in identifiers:
            selected = [session_identifier]
            # Never use a raw identifier in a file path.
            prefix = "session_" + str(identifiers.index(session_identifier))
        else:
            return {"available": False, "message": "Unknown session identifier."}

        fpath = os.path.join(cache_path, prefix + "_results.json")
        if os.path.isfile(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                results = json.load(f)
            if all(os.path.isfile(os.path.join(results_path, "generated", plot["filename"]))
                   for figure in results["figures"] for plot in figure["plots"]):
                logger.info("Using cached version of " + fpath)
                return results

        if sessions is None:
            values = read_session_packets(file_id, results_path)
            sessions, _ = calculate_session_results(values)
        selected_sessions = [sessions[identifier] for identifier in selected]
        # All sessions share 100 ms bins; include the final partial bin and
        # quiet periods, so adding the traces gives the captured aggregate.
        bin_count = (max(values["timestamp2_list"]) - min(values["timestamp2_list"])) // 100000000 + 1
        for session in selected_sessions:
            packets = np.bincount(session["bins"], minlength=bin_count)
            sizes = np.bincount(session["bins"], weights=session["sizes"], minlength=bin_count)
            session["rate_time"] = list(np.arange(bin_count + 1) / 10)
            session["packet_rate"] = list(packets * 10) + [0]
            session["speed"] = list(sizes * 8 / 100000) + [0]
            session["packet_rate_upscaled"] = [value * factor for value in session["packet_rate"]]
            session["speed_upscaled"] = [value * factor for value in session["speed"]]

        figures = []
        plot_jobs = []
        definitions = [
            ("Latency", "latency", "Latency", True, False),
            ("Latency with Y Start 0", "latency", "Latency", True, True),
            ("IPDV", "ipdv", "IPDV", True, False),
            ("PDV", "pdv", "PDV", True, False),
        ]
        for title, metric, label, adjust_unit, adjust_y_ax in definitions:
            plots = []
            for x_key, suffix, x_label in (("packets", "", "Captured packet index"),
                                            ("time", "_sec", "t[s]")):
                name = prefix + "_" + metric + suffix + ("_y0" if adjust_y_ax else "") + ".svg"
                plot_jobs.append((metric, x_key, title, x_label, label,
                                  os.path.join(cache_path, name), adjust_unit,
                                  adjust_y_ax, False, False))
                plots.append({"filename": cache_name + "/" + name,
                              "title": title + " / " + x_label})
            figures.append({"title": title, "plots": plots})

        name = prefix + "_latency_bar.svg"
        plot_jobs.append(("latency", "packets", "Latency distribution", "Latency",
                          "Packets", os.path.join(cache_path, name), True, False, True, False))
        figures.insert(2, {"title": "Latency distribution", "plots": [
            {"filename": cache_name + "/" + name, "title": "Latency distribution"}]})

        for upscaled in (False, True):
            plots = []
            suffix = "_upscaled" if upscaled else ""
            for metric, label in (("speed", "Megabit/s"), ("packet_rate", "Packet/s")):
                name = prefix + "_" + metric + suffix + ".svg"
                plot_jobs.append((metric + suffix, "rate_time",
                                  ("Upscaled " if upscaled else "Captured ") + label,
                                  "t[s]", label, os.path.join(cache_path, name),
                                  False, False, False, True))
                plots.append({"filename": cache_name + "/" + name, "title": label})
            figures.append({"title": "Upscaled throughput and packet rate" if upscaled
                            else "Captured throughput and packet rate", "plots": plots})

        render_session_plots(selected_sessions, plot_jobs, cache_path, logger)

        name = "session_mean_std.svg" if session_identifier is None else prefix + "_mean_std.svg"
        overview = calculate_session_overview(sessions, values, factor)
        plot_session_overview(overview, file_id, os.path.join(cache_path, name),
                              session_identifier=session_identifier)
        figures.insert(0, {
            "title": "Mean latency across all sessions", "full_width": True,
            "description": "All sessions are shown; a selected session is highlighted in orange. "
                           "The line shows mean latency; the band shows ± one sample "
                           "standard deviation (zero for a single packet). "
                           "Session indices start at zero and follow sorted identifiers. "
                           "Average throughput uses captured bytes over the time between "
                           "the first and last timestamp 2; the estimate applies the sampling factor.",
            "plots": [{"filename": cache_name + "/" + name,
                       "title": "Mean latency and standard deviation across all sessions"}]})

        results = {"available": True, "identifiers": identifiers,
                   "selected_identifier": session_identifier,
                   "shown_identifiers": selected,
                   "limited": len(selected) < len(identifiers) and session_identifier is None,
                   "summaries": [session for session in summaries if session["identifier"] in selected],
                   "figures": figures, "cache_dir": cache_name, "threshold": factor}
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4)
        return results


def session_identifier_sort_key(identifier):
    # Match the evaluation script: numeric identifiers first, then labels by
    # their final number, with a lexical fallback for arbitrary identifiers.
    try:
        return (0, int(identifier), identifier)
    except ValueError:
        numbers = re.findall(r"\d+", identifier)
        return (0, int(numbers[-1]), identifier) if numbers else (1, identifier)


def calculate_session_overview(sessions, values, factor):
    identifiers = sorted(sessions, key=session_identifier_sort_key)
    means = []
    deviations = []
    for identifier in identifiers:
        latency = sessions[identifier]["latency"]
        means.append(float(np.mean(latency)))
        deviations.append(float(np.std(latency, ddof=1)) if len(latency) > 1 else 0.0)
    duration = max(values["timestamp2_list"]) - min(values["timestamp2_list"])
    # Bits/ns equals Gbit/s. A single timestamp cannot give a measured rate.
    captured = sum(values["packet_sizes"]) * 8 / duration if duration > 0 else None
    return {"identifiers": identifiers, "mean": means, "std": deviations,
            "captured_gbps": captured,
            "estimated_gbps": captured * factor if captured is not None else None,
            "factor": factor}


def plot_session_overview(overview, file_id, fpath, session_identifier=None):
    if os.path.isfile(fpath):
        return
    with lock:
        x = np.arange(len(overview["identifiers"]))
        _, unit = find_unit(overview["mean"])
        divisor = {"nanoseconds": 1, "microseconds": 1000,
                   "milliseconds": 1000000}[unit]
        mean = np.asarray(overview["mean"]) / divisor
        deviation = np.asarray(overview["std"]) / divisor
        lower = mean - deviation
        upper = mean + deviation
        logarithmic = bool(np.all(mean > 0))
        clipped = logarithmic and bool(np.any(lower <= 0))
        if clipped:
            # Keep the positive mean visible even when its band crosses zero.
            floor = min(mean) / 10
            lower = np.maximum(lower, floor)
        rate = overview["captured_gbps"]
        if rate is None:
            rate_label = "Average throughput unavailable (zero capture duration)"
        else:
            rate_label = "Average throughput: {:.4g} Gbit/s captured".format(rate)
            if overview["factor"] > 1:
                rate_label += "; {:.4g} Gbit/s estimated (sampling ×{})".format(
                    overview["estimated_gbps"], overview["factor"])

        fig, ax = plt.subplots(figsize=(10, 5))
        try:
            ax.plot(x, mean, linewidth=1.8, color="tab:blue", label="Mean latency",
                    marker="." if len(x) < 20 else None)
            ax.fill_between(x, lower, upper, color="tab:blue", alpha=0.2,
                            linewidth=0, label="± StdDev (sample)")
            if len(x) == 1:
                ax.vlines(x, lower, upper, color="tab:blue", alpha=0.4, linewidth=3)
            if session_identifier is not None:
                index = overview["identifiers"].index(session_identifier)
                ax.axvline(index, color="tab:orange", linestyle="--", linewidth=1.5,
                           zorder=4, clip_on=False)
                ax.plot([index], [mean[index]], marker="o", markersize=8,
                        linestyle="None", color="tab:orange", markeredgecolor="white",
                        label="Selected: " + session_identifier, zorder=5, clip_on=False)
            ax.set_title("Run " + str(file_id) + " — all sessions\n" + rate_label, fontsize=11)
            ax.set_xlabel("Session index (sorted by session identifier)")
            ax.set_ylabel("Packet latency [" + unit + "]")
            ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
            if len(x) > 1:
                ax.set_xlim(0, len(x) - 1)
            else:
                ax.set_xlim(-0.5, 0.5)
            if logarithmic:
                ax.set_yscale("log")
                if clipped:
                    ax.set_ylim(bottom=floor)
                for which in ("major", "minor"):
                    formatter = matplotlib.ticker.ScalarFormatter()
                    formatter.set_scientific(False)
                    formatter.set_useOffset(False)
                    if which == "major":
                        ax.yaxis.set_major_formatter(formatter)
                    else:
                        ax.yaxis.set_minor_formatter(formatter)
            notes = "Band clipped at the positive axis floor." if clipped else ""
            if not logarithmic:
                notes = "Linear scale: non-positive mean latency is present."
            ax.grid(True, which="both", linestyle="--", alpha=0.45)
            legend = ax.legend(loc="best")
            for text in legend.get_texts():
                text.set_parse_math(False)
            if notes:
                fig.text(0.5, 0.01, notes, ha="center", fontsize=8)
            fig.tight_layout(rect=(0, 0.04 if notes else 0, 1, 1))
            fig.savefig(fpath, format="svg")
        finally:
            plt.close(fig)


def init_session_plot_worker(metadata):
    global session_plot_data
    # Read-only mappings share the OS page cache without pickling the packet
    # arrays for every plot or copying the complete run into every worker.
    session_plot_data = []
    for entry in metadata:
        session = {"identifier": entry["identifier"], "color_index": entry["color_index"]}
        for key, path in entry["arrays"].items():
            session[key] = np.load(path, mmap_mode="r", allow_pickle=False)
        session_plot_data.append(session)


def run_session_plot_job(job):
    plot_session_graph(session_plot_data, *job)


def render_session_plots(sessions, jobs, cache_path, logger):
    jobs = [job for job in jobs if not os.path.isfile(job[5])]
    if not jobs:
        return
    cpu_count = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 1)
    workers = min(SESSION_MAX_PLOT_WORKERS, cpu_count, len(jobs))
    if (not SESSION_PARALLEL_PLOTS or workers < 2
            or sum(len(session["latency"]) for session in sessions) < SESSION_PARALLEL_THRESHOLD):
        for job in jobs:
            plot_session_graph(sessions, *job)
        return

    logger.info("Rendering session figures with " + str(workers) + " worker processes.")
    with tempfile.TemporaryDirectory(prefix="plot_data_", dir=cache_path) as folder:
        keys = {key for job in jobs for key in job[:2]}
        metadata = []
        for index, session in enumerate(sessions):
            entry = {"identifier": session["identifier"],
                     "color_index": session["color_index"], "arrays": {}}
            for key in keys:
                path = os.path.join(folder, str(index) + "_" + key + ".npy")
                np.save(path, np.asarray(session[key]), allow_pickle=False)
                entry["arrays"][key] = path
            metadata.append(entry)
        # Spawn avoids inheriting a locked Matplotlib/threading state from
        # Django. Each process has its own plotting lock and pyplot state.
        with ProcessPoolExecutor(max_workers=workers,
                                 mp_context=multiprocessing.get_context("spawn"),
                                 initializer=init_session_plot_worker,
                                 initargs=(metadata,)) as pool:
            # Consume results so worker failures reach the view; a failed run
            # must not be recorded as a successfully generated result cache.
            list(pool.map(run_session_plot_job, jobs))


def session_plot_unit(arrays):
    count = sum(len(values) for values in arrays)
    if count:
        if sum(np.count_nonzero(np.abs(values) >= 1000000) for values in arrays) > 0.95 * count:
            return 1000000, "milliseconds"
        if sum(np.count_nonzero(np.abs(values) >= 1000) for values in arrays) > 0.95 * count:
            return 1000, "microseconds"
    return 1, "nanoseconds"


def plot_session_graph(sessions, metric, x_key, title, x_label, y_label,
                       fpath, adjust_unit, adjust_y_ax, histogram=False, rate=False):
    if os.path.isfile(fpath):
        return
    with lock:
        arrays = [np.asarray(session[metric]) for session in sessions]
        divisor = 1
        unit = ""
        if adjust_unit:
            divisor, unit = session_plot_unit(arrays)
        fig, ax = plt.subplots()
        try:
            if histogram:
                minimum = min(values.min() for values in arrays) / divisor
                maximum = max(values.max() for values in arrays) / divisor
                bins = np.histogram_bin_edges([minimum, maximum], bins=10)
            for session, array in zip(sessions, arrays):
                values = array / divisor
                color_index = session["color_index"] % 20
                color = plt.get_cmap("tab20")((color_index % 10) * 2 + color_index // 10)
                label = "ID " + session["identifier"]
                if histogram:
                    ax.hist(values, bins=bins, histtype="step", linewidth=1.5,
                            label=label, color=color)
                elif rate:
                    ax.step(session[x_key], values, where="post", label=label, color=color)
                else:
                    ax.plot(session[x_key], values, marker="." if len(values) == 1 else None,
                            label=label, color=color)
            ax.set_title(title + " by session identifier")
            ax.set_xlabel(x_label + (" [" + unit + "]" if histogram else ""))
            ax.set_ylabel(y_label + (" [" + unit + "]" if adjust_unit and not histogram else ""))
            if adjust_y_ax:
                maximum = max(values.max() for values in arrays) / divisor
                minimum = min(0, min(values.min() for values in arrays) / divisor)
                margin = max((maximum - minimum) * 0.075, 0.1)
                ax.set_ylim(minimum - margin, maximum + margin)
            legend = ax.legend(title="Session identifier", fontsize=8,
                               loc="upper right" if len(sessions) <= 4 else "upper left",
                               bbox_to_anchor=None if len(sessions) <= 4 else (1, 1))
            for text in legend.get_texts():
                text.set_parse_math(False)
            fig.tight_layout()
            fig.savefig(fpath, format="svg")
        finally:
            plt.close(fig)


# plots the line charts
def plot_graph(value_list_input, index_list, titel, x_label, y_label,
               filename, adjust_unit, adjust_y_ax, file_id):
    fpath = project_path + "/results/" + str(
                    file_id) + "/generated/" + filename + ".svg"
    if not os.path.isfile(fpath) or __name__ == "__main__":
        with lock:
            if adjust_unit:
                value_list, unit = find_unit(value_list_input)
            else:
                value_list = value_list_input
                unit = ""
            fig, ax = plt.subplots()
            ax.plot(index_list, value_list)
            plt.title(titel)
            if adjust_unit:
                y_label = y_label + " [" + unit + "]"
            # if adjust_y_ax is True sets y-axis to 0
            if adjust_y_ax:
                try:
                    temp = max(value_list_input)
                    if adjust_unit:
                        if unit == "microseconds":
                            temp = temp / 1000
                        elif unit == "milliseconds":
                            temp = temp / 1000000
                    # -0.075 sets 0 point 7.5% under 0
                    # for equal 0 at x and y axis
                    ax.set_ylim([-0.075 * temp, temp + 0.1 * temp])
                except Exception:
                    # no adjustment of y axis if error
                    # (e.g. empty iperf3 results)
                    pass
            plt.xlabel(x_label, fontsize=12)
            plt.ylabel(y_label, fontsize=12)
            plt.tight_layout()
            if __name__ == "__main__":
                fig.savefig(filename + ".svg", format="svg")
            else:
                try:
                    os.mkdir(project_path + "/results/" + str(
                        file_id) + "/generated")
                except OSError:
                    # case where directory already exists
                    pass
                fig.savefig(fpath, format="svg")
            plt.close('all')
    else:
        # print("Using cached version of " + fpath)
        pass


# input: list
# returns list and string with unit
def find_unit(value_list_input):
    if type(value_list_input) != list:
        value_list_input = [value_list_input]
    try:
        microsec_counter = 0
        millisec_counter = 0
        value_list = []
        for i in value_list_input:
            if abs(i)/1000 >= 1:
                microsec_counter = microsec_counter + 1
            if abs(i)/1000000 >= 1:
                millisec_counter = millisec_counter + 1
        # if more than 95% of the values are bigger than 1 millisec = millisec
        if millisec_counter > (0.95 * len(value_list_input)):
            unit = "milliseconds"
            for i in value_list_input:
                value_list.append(round(i/1000000, 2))
            return value_list, unit
        # if more than 95% of the values are bigger than 1 microsec = microsec
        elif microsec_counter > (0.95 * len(value_list_input)):
            unit = "microseconds"
            for i in value_list_input:
                value_list.append(round(i/1000, 2))
            return value_list, unit
        else:
            unit = "nanoseconds"
            return value_list_input, unit
    except Exception:
        unit = "nanoseconds"
        return value_list_input, unit


# b_type = "bit" or "byte"
def find_unit_bit_byte(value, b_type):
    unit = b_type
    new_value = value
    if (value/1000) >= 1:
        unit = "kilo" + b_type
        new_value = value/1000
    if (value/1000000) >= 1:
        unit = "mega" + b_type
        new_value = value/1000000
    if (value/1000000000) >= 1:
        unit = "giga" + b_type
        new_value = value/1000000000

    return [new_value, unit]  # 1000bit => [1, "kilobit"]


# returns the given input value(ns^2), scaled to a matching unit
def find_unit_sqr(value_ns2):
    try:
        if abs(value_ns2) >= 1500000*1000000:
            unit = "ms²"
            value = round(value_ns2 / (1000000*1000000), 2)
            return value, unit
        if abs(value_ns2) >= 1500000:
            unit = "us²"
            value = round(value_ns2 / 1000000, 2)
            return value, unit
        unit = "ns²"
        return round(value_ns2, 2), unit
    except Exception:
        unit = "ns²"
        return value_ns2, unit


# plots bar chart
def plot_bar(value_list_input, min, max, filename,
             x, y, slices, adjust_unit, file_id):
    fpath = project_path + "/results/" + str(
        file_id) + "/generated/" + filename + ".svg"
    if not os.path.isfile(fpath) or __name__ == "__main__":
        with lock:
            if adjust_unit:
                value_list, unit = find_unit(value_list_input)
                if unit == "microseconds":
                    min = float(min) / 1000
                    max = float(max) / 1000
                elif unit == "milliseconds":
                    min = float(min) / 1000000
                    max = float(max) / 1000000
            else:
                value_list = value_list_input
                unit = ""

            min = min - 0.1
            max = max + 0.1
            total_range = max - min
            parts = []
            stepwidth = round((total_range / slices)+0.1, 1)
            base = round(min, 1)
            for i in range(0, slices+1):
                parts.append(round(base + (i*stepwidth), 1))
            result = []
            for i in range(0, slices):
                result.append(0)
            label = []
            for i in range(0, len(parts) - 1):
                label.append(str(
                    round(parts[i]+0.01, 2))+"-\n" + str(parts[i+1]))
            for z in value_list:
                for i in range(0, len(parts) - 1):
                    if parts[i] < z <= parts[i+1]:
                        result[i] = result[i] + 1
            fig2 = plt.figure()
            index = np.arange(len(label))
            plt.bar(index, result)
            plt.title("Distribution of " + x)
            if adjust_unit:
                x = x + " [" + unit + "]"
            if adjust_unit:
                plt.xlabel(x, fontsize=10)
            else:
                plt.xlabel(x, fontsize=10)
            plt.ylabel(y, fontsize=10)
            plt.xticks(index, label, fontsize=8, rotation=30)
            plt.tight_layout()
            for a, b in zip(index, result):
                plt.text(a, b, str(b), fontsize=8)
            if __name__ == "__main__":
                fig2.savefig(filename + ".svg", format="svg")
            else:
                try:
                    os.mkdir(project_path + "/results/" + str(
                        file_id) + "/generated")
                except OSError:
                    # case where directory already exists
                    pass
                fig2.savefig(project_path + "/results/" + str(
                    file_id) + "/generated/" + filename + ".svg", format="svg")
            plt.close('all')
    else:
        # print("Using cached version of " + fpath)
        pass

# reads csv file and returns list with elements from csv file
def read_csv(logger, results_path, file_name, file_id, thread_return=[], thr_id=-1):
    temp = []
    try:
        with open(os.path.join(results_path, file_name + "_" + str(file_id)
                               + ".csv"), "r") as csv_input:
            reader = csv.reader(csv_input, lineterminator="\n")
            for elem in reader:
                temp.append(int(elem[0]))
    except Exception as e:
        logger.error("exception in csv reader:" + str(e))
        temp.append(-1)
    # if thread id is set use passed list to store results
    if thr_id > -1:
        thread_return[thr_id] = temp
    else:
        return temp


# entry point if analytics gets execute directly as a script
# and NOT as an included module
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='CSV reader for external host results.')
    parser.add_argument(
        '--id', help='ID of the csv files. Not set: use cfg file in /data',
        type=str, action="store", required=True)
    args = parser.parse_args()

    logger = get_fallback_logger()

    logger.info("Start standalone analytics")

    if args.id is None:
        logger.info("No ID given")
    else:
        id = args.id
        multicast = "n/a"
        dir_path = os.path.dirname(os.path.realpath(__file__))
        try:
            with open(dir_path[0:dir_path.find("analytics")]+"/data/config_"
                      + id + ".json", "r") as cfg:
                config = json.load(cfg)
                multicast = config["multicast"]
        except Exception:
            multicast = ""
            logger.warning("config.json not found. path: " + dir_path[0:dir_path.find(
                "analytics")]+"/data/config_" + id + ".json")

        if len(id) > 0 and len(multicast) > 0:
            path = dir_path[0:dir_path.find("analytics")]+"results/"+str(id)
            results = main(id, multicast, path, logger)
            session_main(id, multicast, path, logger)
        else:
            logger.error("Aborted execution.")
