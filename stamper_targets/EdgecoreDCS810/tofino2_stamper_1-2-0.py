# Copyright 2024-present Ralf Kundel, Fridolin Siegmund
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

import ipaddress
import os
import subprocess
import sys
import time
import traceback

from tabulate import tabulate

dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir_path)
project_path = dir_path[0:dir_path.find("/stamper_targets")]
sys.path.append(project_path + "/core")
sys.path.append(project_path + "/stamper_targets/Wedge100B65")
try:
    from abstract_target import AbstractTarget
    import P4STA_utils

    import bfrt_grpc.grpc_interface as grpc_interface
    from tofino1_65p_stamper_v1_2_0 import TargetImpl as tofino1Impl
except Exception as e:
    print(e)


class TargetImpl(tofino1Impl):
    def __init__(self, target_cfg, logger):
        super().__init__(target_cfg, logger)
        self.port_mapping = None

    def start_stamper_software(self, cfg):
        script_dir = dir_path + "/scripts/run_switchd.sh"
        user_name = cfg["stamper_user"]
        output_sub = subprocess.run(
            [dir_path + "/scripts/start_switchd_tofino2.sh", cfg["stamper_ssh"],
             cfg["stamper_user"], self.get_sde(cfg),
             '/home/' + user_name + '/p4sta/stamper/tofino1/compile/' + cfg["program"] + '.conf',
             script_dir], stdout=subprocess.PIPE)
        print(output_sub)
        time.sleep(5)
        

        reachable = False
        for i in range(12):
            time.sleep(10)
            interface = grpc_interface.TofinoInterface(cfg["stamper_ssh"], 0, self.logger, print_errors=False)
            established = interface.connection_established
            print("Probing gRPC connection to Tofino 2... Established: " + str(established))
            interface.teardown()
            if established:
                reachable = True
                break
                
        if reachable:
            print("Tofino 2 gRPC server reachable.")
        else:
            print("Tofino 2 gRPC server not reachable after 2 minutes trying.")


    def get_server_install_script(self, user_name, ip, target_specific_dict={}):
        lst = super().get_server_install_script(user_name, ip, target_specific_dict)
        lst.append('cd ' + dir_path + "/scripts")
        lst.append('chmod +x start_switchd_tofino2.sh')
        return lst