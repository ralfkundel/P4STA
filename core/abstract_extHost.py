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
import subprocess

class AbstractExtHost:
    def __init__(self, host_cfg):
        self.host_cfg = host_cfg
        print("init abstract ext Host")
        print(host_cfg)

    def setRealPath(self, path):
        self.realPath = path

    def start_external(self, file_id):
        return
    def stop_external(self, file_id):
        return
