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

# parent class for individual load generator implementation
# every method should be overwritten by specific loadgen methods
import os


class Loadgenerator:
    def __init__(self, cfg):
        self.cfg = cfg

    def get_name(self):
        return "[Loadgenerator Template]"

    # return output, total_gbits, error, total_retransmits, total_gbyte, mean_rtt, min_rtt, max_rtt, to_plot dict
    def run_loadgens(self, file_id, duration, l4_selected, packt_size_mtu, results_path):
        return ["Sure you selected a load generator?"], "", True, "", "", "", 0, 0, self.empty_plot()

    def process_loadgen_data(self, file_id, results_path):
        to_plot = self.empty_plot()

    # returns "empty" to_plot dict
    # can be called by inherited class if implemented type of loadgen is not able to measure metrics like RTT
    def empty_plot(self):
        to_plot = {"mbits": {}, "rtt": {}, "packetloss": {}}
        to_plot["mbits"] = {"value_list_input": [0, 0, 0], "index_list": [0, 1, 2],
                            "titel": "no throughput data available", "x_label": "t[s]", "y_label": "Speed [Mbit/s]",
                            "filename": "loadgen_mbits", "adjust_unit": False, "adjust_y_ax": False}

        to_plot["rtt"] = {"value_list_input": [0, 0, 0], "index_list": [0, 1, 2],
                          "titel": "no RTT data available", "x_label": "t[s]", "y_label": "RTT [microseconds]",
                          "filename": "loadgen_rtt", "adjust_unit": False, "adjust_y_ax": False}

        to_plot["packetloss"] = {"value_list_input": [0, 0, 0], "index_list": [0, 1, 2],
                                 "titel": "no packetloss data available", "x_label": "t[s]",
                                 "y_label": "Packetloss [packets]",
                                 "filename": "loadgen_pl", "adjust_unit": False, "adjust_y_ax": False}
        return to_plot