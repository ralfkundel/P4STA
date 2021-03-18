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

from core import P4STA_utils


def main():
    global selected_run_id
    global core_conn
    global project_path
    core_conn = rpyc.connect('localhost', 6789)
    project_path = core_conn.root.get_project_path()
    P4STA_utils.set_project_path(project_path)
    selected_run_id = core_conn.root.getLatestMeasurementId()
