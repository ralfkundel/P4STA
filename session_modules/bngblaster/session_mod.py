# Copyright 2026-present Fridolin Siegmund, Ralf Kundel
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
from collections import OrderedDict

# maps fields in P4 v1.4.0, if P4 changes this needs to be adapted here
GROUP_ORDER = ["ethernet", "vlan", "vlan_qinq", "pppoe", "ipv4"]
FIELD_TO_GROUP = {
    "ethernet.srcAddr": "ethernet",
    "ethernet.dstAddr": "ethernet",
    "vlan.vid": "vlan",
    "vlan_qinq.vid": "vlan_qinq",
    "pppoe.sessionID": "pppoe",
    "ipv4.srcAddr": "ipv4",
    "ipv4.dstAddr": "ipv4",
}
GROUP_FIELDS = {
    "ethernet": ["ethernet.dstAddr", "ethernet.srcAddr"],
    "vlan": ["vlan.vid"],
    "vlan_qinq": ["vlan_qinq.vid"],
    "pppoe": ["pppoe.sessionID"],
    "ipv4": ["ipv4.srcAddr", "ipv4.dstAddr"],
}
FIELD_TO_PARAM = {
    "ethernet.dstAddr": "eth_dstAddr",
    "ethernet.srcAddr": "eth_srcAddr",
    "vlan.vid": "vlan_vid",
    "vlan_qinq.vid": "vlan_qinq_vid",
    "pppoe.sessionID": "pppoe_sessionID",
    "ipv4.srcAddr": "ipv4_srcAddr",
    "ipv4.dstAddr": "ipv4_dstAddr",
}


def get_action_name(fields):
    groups = []

    for group in GROUP_ORDER:
        if any(value is not None and FIELD_TO_GROUP[field] == group
            for field, value in fields.items()):
            groups.append(group)

    if not groups:
        return ""

    if len(groups) == 1:
        group = groups[0]
        if group in ("ethernet", "ipv4"):
            return "mod_fields_" + group
        return "mod_fields_" + group

    return "mod_fields_" + "_".join(groups)


def prepare_value(key, value):
    if isinstance(value, str):
        if "ethernet" in key:      # MAC addr
            value = int("".join(value.split(":")), 16)
        elif "ipv4" in key:       # IPv4 addr
            value = int(ipaddress.IPv4Address(value))
        elif value.isdigit():     # VLAN IDs, session IDs, ..
            value = int(value)

    return value


def get_used_groups(fields):
    groups = []
    for group in GROUP_ORDER:
        group_fields = GROUP_FIELDS[group]
        values = [fields.get(field) for field in group_fields]
        any_filled = any(value is not None for value in values)
        all_filled = all(value is not None for value in values)
        if any_filled and not all_filled:
            raise ValueError("Incomplete field group " + str(group) + ": need all of " + str(group_fields))
        if all_filled:
            groups.append(group)
    return groups


def get_action_params(fields):
    params = []
    for group in get_used_groups(fields):
        for field in GROUP_FIELDS[group]:
            value = prepare_value(field, fields[field])
            params.append([FIELD_TO_PARAM[field], value])
    return params

