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

# parent class for individual target implementation
# every method should be overwritten by specific target methods

import os
import traceback
import P4STA_utils
import threading
import sys

dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir_path)
p4sta_root_dir_path = os.path.abspath(os.path.join(dir_path, ".."))
wedge100b65_dir = os.path.abspath(os.path.join(p4sta_root_dir_path, 'stamper_targets', 'Wedge100B65'))
sys.path.append(wedge100b65_dir)

import bfrt_grpc.grpc_interface as grpc_interface


class AbstractSessionModule:
    def __init__(self, module_cfg, logger, ip, p4_name):
        self.logger = logger
        self.module_cfg = module_cfg
        self.ip = ip
        self.p4_name = p4_name

    def _grpc_obj_check(self, grpc_obj):
        def _default_ret():
            if grpc_obj is not None:
                grpc_obj.teardown()
            interface = grpc_interface.TofinoInterface.get_bound_instance(
                self.ip, 0, self.p4_name)
            if interface is not None:
                self.logger.info("Reusing tofino gRPC session: " + str(interface))
                return interface
            interface, _, error = \
                grpc_interface.TofinoInterface.get_or_create_bound_instance(
                    self.ip, 0, self.logger, self.p4_name)
            if error != "":
                self.logger.warning(error)
            self.logger.info("Returning new tofino gRPC session: " + str(interface))
            return interface
        
        self.logger.info("Checking tofino gRPC module: " + str(grpc_obj))
        
        if grpc_obj is None:
            return _default_ret()
        else:
            try:
                state = grpc_obj.p4_connected
                if state:
                    self.logger.info("Utilizing existing tofino gRPC session: " + str(grpc_obj))
                    return grpc_obj
                else:
                    return _default_ret()
            except Exception as e:
                self.logger.debug(traceback.format_exc())
                return _default_ret()

    def setRealPath(self, path):
        self.realPath = path

    def getModuleName(self):
        return self.module_cfg["name"]
    
    def check_live_version(self, user_name, ip):
        return "unknown"

    def establish_sessions(self, tofino_grpc_obj, sess_cfg, user_name, ip):
        return tofino_grpc_obj

    def teardown_sessions(self, sess_cfg):
        return

    def get_server_install_script(self, user_name, ip):
        lst = []
        lst.append('echo "======================================="')
        lst.append('echo "not implemented for this session module"')
        lst.append('echo "======================================="')
        return lst

