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

import sys, time, threading
import os
import csv
import argparse
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
csv.field_size_limit(sys.maxsize)

dir_path = os.path.dirname(os.path.realpath(__file__))
project_path = dir_path[0:dir_path.find("/calculate")]

lock = threading.RLock()

# read the csv files and plots the graphs
def main(file_id, multicast, results_path):
    # importing the csv files into integers / lists of integers
    raw_packet_counter = read_csv(results_path, "raw_packet_counter", file_id)[0]
    total_throughput = read_csv(results_path, "total_throughput", file_id)[0]
    throughput_at_time = read_csv(results_path, "throughput_at_time", file_id)
    timestamp1_list = read_csv(results_path, "timestamp1_list", file_id)
    timestamp2_list = read_csv(results_path, "timestamp2_list", file_id)

    latency_list = []
    min_latency = max_latency = ave_latency = latency_variance = latency_std_deviation = 0
    total_ipdv = abs_total_ipdv = total_pdv = total_latencies = total_packets = 0
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
            for i in range(0, len(timestamp1_list)):
                delta = timestamp2_list[i] - timestamp1_list[i]
                latency_list.append(delta)
                total_latencies = total_latencies + delta
                time_throughput.append(int(round((timestamp2_list[i] - timestamp2_list[0]) / 1000000)))  # sets the start time to 0 ms
                count_list_sec.append((timestamp2_list[i] - timestamp2_list[0]) / 1000000000)  # - [0] to set first time to 0 sec
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
                for z in range(0, len(latency_list)):
                    total_sqr_dev += (latency_list[z] - ave_latency)**2
                latency_variance = total_sqr_dev / len(ipdv_list)
                latency_std_deviation = latency_variance **(0.5)
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
                if (time_throughput[y] - last_time_hit) >= 100:  # more than 99ms difference -> 0.1s intervals
                    if (time_throughput[y] - last_time_hit) >= 100:
                        amount = (time_throughput[y] - last_time_hit) / 100
                        if amount >= 2:  # more than 200ms difference between two hits -> pause
                            for i in range(0, int(round(amount))):
                                mbit_list.append(0)
                                packet_list.append(0)
                    last_time_hit = time_throughput[y]
                    mbit_list.append((throughput_at_time[y] - last_throughput_hit) * 8 / 100000)  # byte to megabit / 10 because it measures for every 0.1s but the unit is mbit/seconds
                    packet_list.append((y - last_packet_hit)*10)  # *10 because it measures for every 0.1s but unit is packets/seconds
                    last_packet_hit = y
                    last_throughput_hit = throughput_at_time[y]
            mbit_list.append(0)  # set next entry to 0
            packet_list.append(0)
            min_packets = min(packet_list[1:-1], default=0)  # ignores the first and last second to prevent min = 0
            max_packets = max(packet_list, default=0)
            if len(packet_list) != 2:
                ave_packet_sec = round((len(throughput_at_time)/(len(packet_list)-2)) * 10, 2)  # -2 because we added 0 at beginning and end. *10 because of 0.1s steps
            else:
                ave_packet_sec = 0

            plot_graph(latency_list, count_list, "Latency of DUT for every " + multicast + ". packet", "Packets", "Latency", "latency", True, False)
            plot_graph(latency_list, count_list_sec, "Latency of DUT for every " + multicast + ". packet", "t[s]", "Latency", "latency_sec", True, False)
            plot_graph(latency_list, count_list, "Latency of DUT for every " + multicast + ". packet", "Packets", "Latency", "latency_y0", True, True)
            plot_graph(latency_list, count_list_sec, "Latency of DUT for every " + multicast + ". packet", "t[s]", "Latency", "latency_sec_y0", True, True)
            plot_graph(ipdv_list, count_list, "IPDVs of DUT for every " + multicast + ". packet", "IPDV", "Packets", "ipdv", True, False)
            plot_graph(ipdv_list, count_list_sec, "IPDVs of DUT for every " + multicast + ". packet", "t[s]", "IPDV", "ipdv_sec", True, False)
            plot_graph(pdv_list, count_list, "PDVs of DUT for every " + multicast + ". packet", "Packets", "PDV", "pdv", True, False)
            plot_graph(pdv_list, count_list_sec, "PDVs of DUT for every " + multicast + ". packet", "t[s]", "PDV", "pdv_sec", True, False)
            plot_graph(mbit_list, np.arange(0, len(mbit_list)/10, 0.1), "Throughput of DUT for every " + multicast + ". packet", "t[s]", "Megabit/s", "speed", False, False)
            plot_graph(packet_list, np.arange(0, len(packet_list)/10, 0.1), "Rate jitter of DUT for every " + multicast + ". packet", "t[s]", "Packet/s", "packet_rate", False, False)
            plot_bar(latency_list, min_latency, max_latency, "latency_bar", "Latency", "Packets", 10, True)

    return {"num_raw_packets": raw_packet_counter, "num_processed_packets": len(latency_list), "total_throughput": round(total_throughput/1000000, 2), "min_latency": min_latency, "max_latency": max_latency, "avg_latency": ave_latency, "min_ipdv": min_ipdv, "max_ipdv": max_ipdv, "avg_ipdv": ave_ipdv, "avg_abs_ipdv": ave_abs_ipdv, "min_pdv": min_pdv, "max_pdv": max_pdv, "avg_pdv": ave_pdv, "min_packets_per_second": min_packets, "max_packets_per_second": max_packets, "avg_packets_per_second": ave_packet_sec, "latency_std_deviation": latency_std_deviation, "latency_variance": latency_variance, "latency_list": latency_list}


# plots the line charts
def plot_graph(value_list_input, index_list, titel, x_label, y_label, filename, adjust_unit, adjust_y_ax):
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
                # -0.075 sets the 0 point 7.5% under 0 to have equal 0 at x and y axis
                ax.set_ylim([-0.075 * temp, temp + 0.1 * temp])
            except:
                pass  # no adjustment of y axis if error occurs (e.g. empty iperf3 results)
        plt.xlabel(x_label, fontsize=12)
        plt.ylabel(y_label, fontsize=12)
        plt.tight_layout()
        if __name__ == "__main__":
            fig.savefig(filename + ".svg", format="svg")
        else:
            fig.savefig(project_path + "/management_ui/generated/" + filename + ".svg", format="svg")
        plt.close('all')


# input: list
# returns list and string with unit
def find_unit(value_list_input):
    if (type(value_list_input) != list):
        value_list_input = [value_list_input] #cast input to list if only a single value is given
    try:
        microsec_counter = 0
        millisec_counter = 0
        value_list = []
        for i in value_list_input:
            if abs(i)/1000 >= 1:
                microsec_counter = microsec_counter + 1
            if abs(i)/1000000 >= 1:
                millisec_counter = millisec_counter + 1
        # if more than 95% of the values are bigger than 1 millisec, unit = millisec
        if millisec_counter > (0.95 * len(value_list_input)):
            unit = "milliseconds"
            for i in value_list_input:
                value_list.append(round(i/1000000, 2))
            return value_list, unit
        # if more than 95% of the values are bigger than 1 microsec, unit = microsec
        elif microsec_counter > (0.95 * len(value_list_input)):
            unit = "microseconds"
            for i in value_list_input:
                value_list.append(round(i/1000, 2))
            return value_list, unit
        else:
            unit = "nanoseconds"
            return value_list_input, unit
    except:
        unit = "nanoseconds"
        return value_list_input, unit


def find_unit_bit_byte(value, b_type): # b_type = "bit" or "byte"
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
    print(value_ns2)
    try:
        if abs(value_ns2) >= 1500000*1000000:
            unit = "ms²"
            value = round(value_ns2 /(1000000*1000000), 2)
            return value, unit
        if abs(value_ns2) >= 1500000:
            unit = "us²"
            value = round(value_ns2 /1000000, 2)
            return value, unit
        unit = "ns²"
        return round(value_ns2, 2), unit
    except:
        unit = "ns²"
        return value_ns2, unit


# plots bar chart
def plot_bar(value_list_input, min, max, filename, x, y, slices, adjust_unit):
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
        #TODO: bessere berechnung der slices / evtl. graedere werte, so dass nur 1 decimalstelle
        min = min - 0.1
        max = max + 0.1
        print("max: "+str(max)) 
        total_range = max - min
        parts = []
        stepwidth = round((total_range / slices)+0.1, 1)
        print("stepwidth: "+str(stepwidth))
        base = round(min, 1)
        for i in range(0, slices+1):
            parts.append(round(base + (i*stepwidth), 1))
        result = []
        print(parts)
        for i in range(0, slices):
            result.append(0)
        label = []
        for i in range(0, len(parts) - 1):
            label.append(str(round(parts[i]+0.01, 2)) + "-\n" + str(parts[i+1]))
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
            fig2.savefig(project_path + "/management_ui/generated/" + filename + ".svg", format="svg")
        plt.close('all')


# reads csv file and returns list with elements from csv file
def read_csv(results_path, file_name, file_id):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    temp = []
    try:
        with open(os.path.join(results_path, file_name + "_" + str(file_id) + ".csv"), "r") as csv_input:
            reader = csv.reader(csv_input, lineterminator="\n")
            for elem in reader:
                temp.append(int(elem[0]))
    except Exception as e:
        print("exception in csv reader:" + str(e))
        temp.append(-1)
    return temp


# entry point if calculate gets execute directly as a script and NOT as an included module
if __name__ == "__main__":  # for direct execution of the skript outside of the webserver
    parser = argparse.ArgumentParser(description='CSV reader for external host results.')
    parser.add_argument('--id', help='ID of the csv files. If not set the config file in /data will be used.',
                        type=str, action="store", required=True)
    args = parser.parse_args()
    if args.id is None:
          print("No ID given")
    else:
        id = args.id
        multicast = "n/a"
        dir_path = os.path.dirname(os.path.realpath(__file__))
        try:
            with open(dir_path[0:dir_path.find("calculate")]+"/data/config_" + id + ".json", "r") as cfg:
                config = json.load(cfg)
                multicast = config["multicast"]
        except:
            multicast = ""
            print("config.json not found. path: "+dir_path[0:dir_path.find("calculate")]+"/data/config_" + id + ".json")

        if len(id) > 0 and len(multicast) > 0:
            path = dir_path[0:dir_path.find("calculate")]+"results"
            results = main(id, multicast, path)
        else:
            print("Aborted execution.")
