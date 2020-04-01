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

import os, json
import subprocess
from pathlib import Path

def set_project_path(path):
    global project_path
    project_path = path

def read_current_cfg(name="config.json"):
    path = os.path.join(project_path, "data", name)
    if not Path(path).is_file():
       return None
    with open(path, "r") as f:
        cfg = json.load(f)
        return cfg

def get_results_path(id):
    return os.path.join(project_path, "results", str(id))

def read_result_cfg(id):
    path = os.path.join(get_results_path(id), "config_"+str(id)+".json")
    if Path(path).is_file():
        with open(path, "r") as f:
            cfg = json.load(f)
            return cfg  
    else:
        return

def write_config(cfg, file_name="config.json"):
    with open(project_path + "/data/"+file_name, "w") as write_json:
        json.dump(cfg, write_json, indent=2, sort_keys=True)

def execute_ssh(user, ip_address, arg):
    input = ["ssh", "-o ConnectTimeout=5", user + "@" + ip_address, arg] #-o StrictHostKeyChecking=no
    res = subprocess.Popen(input, stdout=subprocess.PIPE).stdout
    return res.read().decode().split("\n")

#### Logging

def log_error(error):
    print_msg = "\033[1;31m" 
    print_msg += "-------------------- P4STA ERROR -------------------- \n"

    if isinstance (error, str):
        print_msg += error
    elif isinstance (error, tuple):
        print_msg += ''.join(error)
    else:
        print_msg += ("unknown error type: " + str(type(error)) )
        print_msg += str(error)
    print_msg += "\n-----------------------------------------------------"
    print_msg += "\x1b[0m"

    print(print_msg)


### RPC tools:

def flt(x):
    if isinstance(x, dict):
        return flt_dict(x)
    elif isinstance(x, list):
        return flt_lst(x)
    elif isinstance(x, tuple):
        return flt_tuple(x)
    else:
        return x

def flt_dict(cfg):
    new = {}
    for k,v in cfg.items():
        new[k] = flt(v)
    return new

def flt_lst(lst):
    ls = []
    for e in lst:
        ls.append(flt(e))
    return ls

def flt_tuple(tpl):
    new = ()
    for e in tpl:
        new = new + (flt(e) ,)
    return new

