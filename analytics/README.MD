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

To execute the script just call "python analytics.py" but if you want a different id than the one in data/name_external.config use the --id flag to pass the id of the csv files (e.g. 15495 ...)
