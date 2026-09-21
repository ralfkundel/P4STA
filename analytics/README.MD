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

The analytics modul reads the csv files from the external host and creates the charts of the following metrics:
- Latency for packets
- Latency over time period
- Latency as bar chart
- IPDV for packets
- IPDV over time period
- PDV for packets
- PDV over time period
- Speed at external host
- Packet rate at external host
  
You need the following directory structure:  
	your_directory  
	|  
	|--analytics(directory of this module)  
	|       |-- analytics.py  
	|  
	|--results(directory with csv files)  
  
The graphs will be saved to analytics.  

You need to install matplotlib. "python -m pip install -U matplotlib"

For large session measurements, developers can enable parallel figure generation
in `analytics.py` with `SESSION_PARALLEL_PLOTS = True`. It defaults to `True` but
can be set to `False` to reduce memory usage. `SESSION_MAX_PLOT_WORKERS` defaults to 4;
small selections below `SESSION_PARALLEL_THRESHOLD` (100000 captured packets) still render in the current process.
These options apply to the session related calculations.
The classic figures already use their existing multiprocessing implementation.

Workers read temporary NumPy files through read-only memory mappings rather than
receiving full packet arrays for every figure. Matplotlib still needs memory in
each worker, so the worker limit should suit the host. Temporary files are removed
after rendering, including after a worker error. Cached figures are reused in
either mode, and switching the flag does not invalidate a cache. All packets and
statistics are retained; plots are not downsampled. Unit selection uses NumPy and
legends have fixed positions to avoid repeatedly scanning large traces.

To execute the script just call "python analytics.py" but if you want a different id than the one in data/name_external.config use the --id flag to pass the id of the csv files (e.g. 15495 ...)
