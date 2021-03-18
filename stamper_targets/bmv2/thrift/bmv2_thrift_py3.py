# Copyright 2020-present Ralf Kundel, Fridolin Siegmund

# Copyright 2013-present Barefoot Networks, Inc.
# Antonin Bas (antonin@barefootnetworks.com)
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

import argparse
import json
import struct
import sys
import traceback
from collections import Counter

import SimplePreLAG
import Standard

from thrift.Thrift import TType, TMessageType, TException, \
    TApplicationException
from thrift.Thrift import TProcessor
from thrift.transport import TTransport, TSocket
from thrift.protocol import TBinaryProtocol, TProtocol, TMultiplexedProtocol
from ttypes import *


def thrift_connect(thrift_ip, thrift_port, services):
    transport = TSocket.TSocket(thrift_ip, thrift_port)
    transport = TTransport.TBufferedTransport(transport)
    bprotocol = TBinaryProtocol.TBinaryProtocol(transport)

    clients = []

    for service_name, service_cls in services:
        if service_name is None:
            clients.append(None)
            continue
        protocol = TMultiplexedProtocol.TMultiplexedProtocol(
            bprotocol, service_name)
        client = service_cls(protocol)
        clients.append(client)

    try:
        transport.open()
    except TTransport.TTransportException:
        print("Could not connect to thrift port " +
              str(thrift_port) + " at IP " + str(thrift_ip))
        sys.exit(1)

    return clients


###############################################################################
# MODIFIED FOR PYTHON3 FROM                                                   #
# https://github.com/p4lang/behavioral-model/blob/master/tools/runtime_CLI.py #
###############################################################################
TABLES = {}
ACTION_PROFS = {}
ACTIONS = {}
METER_ARRAYS = {}
COUNTER_ARRAYS = {}
REGISTER_ARRAYS = {}
CUSTOM_CRC_CALCS = {}
SUFFIX_LOOKUP_MAP = {}


class Table:
    def __init__(self, name, id_):
        self.name = name
        self.id_ = id_
        self.match_type_ = None
        self.actions = {}
        self.key = []
        self.default_action = None
        self.type_ = None
        self.support_timeout = False
        self.action_prof = None

        TABLES[name] = self

    def num_key_fields(self):
        return len(self.key)

    def key_str(self):
        return ",\t".join(
            [name + "(" + MatchType.to_str(
                t) + ", " + str(bw) + ")" for name, t, bw in self.key])

    def table_str(self):
        ap_str = "implementation={}".format(
            "None" if not self.action_prof else self.action_prof.name)
        return "{0:30} [{1}, mk={2}]".format(self.name, ap_str, self.key_str())

    def get_action(self, action_name):
        key = ResType.action, action_name
        action = SUFFIX_LOOKUP_MAP.get(key, None)
        if action is None or action.name not in self.actions:
            return None
        return action


class BmMatchParamType:
    EXACT = 0
    LPM = 1
    TERNARY = 2
    VALID = 3
    RANGE = 4

    _VALUES_TO_NAMES = {
        0: "EXACT",
        1: "LPM",
        2: "TERNARY",
        3: "VALID",
        4: "RANGE",
    }

    _NAMES_TO_VALUES = {
      "EXACT": 0,
      "LPM": 1,
      "TERNARY": 2,
      "VALID": 3,
      "RANGE": 4,
    }


class Action:
    def __init__(self, name, id_):
        self.name = name
        self.id_ = id_
        self.runtime_data = []

        ACTIONS[name] = self

    def num_params(self):
        return len(self.runtime_data)

    def runtime_data_str(self):
        return ",\t".join([name + "(" + str(
            bw) + ")" for name, bw in self.runtime_data])

    def action_str(self):
        return "{0:30} [{1}]".format(self.name, self.runtime_data_str())


class MatchType:
    EXACT = 0
    LPM = 1
    TERNARY = 2
    VALID = 3
    RANGE = 4

    @staticmethod
    def to_str(x):
        return {0: "exact", 1: "lpm", 2: "ternary", 3: "valid", 4: "range"}[x]

    @staticmethod
    def from_str(x):
        return {"exact": 0, "lpm": 1, "ternary": 2, "valid": 3, "range": 4}[x]


class CounterArray:
    def __init__(self, name, id_):
        self.name = name
        self.id_ = id_
        self.is_direct = None
        self.size = None
        self.binding = None

        COUNTER_ARRAYS[name] = self

    def counter_str(self):
        return "{0:30} [{1}]".format(self.name, self.size)


class RegisterArray:
    def __init__(self, name, id_):
        self.name = name
        self.id_ = id_
        self.width = None
        self.size = None

        REGISTER_ARRAYS[name] = self

    def register_str(self):
        return "{0:30} [{1}]".format(self.name, self.size)


class UIn_Error(Exception):
    def __init__(self, info=""):
        self.info = info

    def __str__(self):
        return self.info


class UIn_ResourceError(UIn_Error):
    def __init__(self, res_type, name):
        self.res_type = res_type
        self.name = name

    def __str__(self):
        return "Invalid %s name (%s)" % (self.res_type, self.name)


class UIn_MatchKeyError(UIn_Error):
    def __init__(self, info=""):
        self.info = info

    def __str__(self):
        return self.info


class UIn_RuntimeDataError(UIn_Error):
    def __init__(self, info=""):
        self.info = info

    def __str__(self):
        return self.info


class CLI_FormatExploreError(Exception):
    def __init__(self):
        pass


class UIn_BadParamError(UIn_Error):
    def __init__(self, info=""):
        self.info = info

    def __str__(self):
        return self.info


class UIn_BadIPv4Error(UIn_Error):
    def __init__(self):
        pass


class UIn_BadIPv6Error(UIn_Error):
    def __init__(self):
        pass


class UIn_BadMacError(UIn_Error):
    def __init__(self):
        pass


_match_types_mapping = {
    MatchType.EXACT: BmMatchParamType.EXACT,
    MatchType.LPM: BmMatchParamType.LPM,
    MatchType.TERNARY: BmMatchParamType.TERNARY,
    MatchType.VALID: BmMatchParamType.VALID,
    MatchType.RANGE: BmMatchParamType.RANGE,
}


def bytes_to_string(inp_list):
    return bytes(bytearray(inp_list))


def int_to_bytes(i, num):
    byte_array = []
    while i > 0:
        byte_array.append(i % 256)
        i = int(i / 256)
        num -= 1
    if num < 0:
        raise UIn_BadParamError("Parameter is too large")
    while num > 0:
        byte_array.append(0)
        num -= 1
    byte_array.reverse()
    return byte_array


def ipv4Addr_to_bytes(addr):
    if '.' not in addr:
        raise CLI_FormatExploreError()
    s = addr.split('.')
    if len(s) != 4:
        raise UIn_BadIPv4Error()
    try:
        return [int(b) for b in s]
    except Exception:
        raise UIn_BadIPv4Error()


def macAddr_to_bytes(addr):
    if ':' not in addr:
        raise CLI_FormatExploreError()
    s = addr.split(':')
    if len(s) != 6:
        raise UIn_BadMacError()
    try:
        ret = [int(b, 16) for b in s]
        return ret
    except Exception:
        raise UIn_BadMacError()


def ipv6Addr_to_bytes(addr):
    from ipaddr import IPv6Address
    if ':' not in addr:
        raise CLI_FormatExploreError()
    try:
        ip = IPv6Address(addr)
    except Exception:
        raise UIn_BadIPv6Error()
    try:
        return [ord(b) for b in ip.packed]
    except Exception:
        raise UIn_BadIPv6Error()


def parse_param(input_str, bitwidth):
    if bitwidth == 32:
        try:
            return ipv4Addr_to_bytes(input_str)
        except CLI_FormatExploreError:
            pass
        except UIn_BadIPv4Error:
            raise UIn_BadParamError("Invalid IPv4 address")
    elif bitwidth == 48:
        try:
            return macAddr_to_bytes(input_str)
        except CLI_FormatExploreError:
            pass
        except UIn_BadMacError:
            raise UIn_BadParamError("Invalid MAC address")
    elif bitwidth == 128:
        try:
            return ipv6Addr_to_bytes(input_str)
        except CLI_FormatExploreError:
            pass
        except UIn_BadIPv6Error:
            raise UIn_BadParamError("Invalid IPv6 address")
    try:
        input_ = int(input_str, 0)
    except Exception:
        raise UIn_BadParamError(
            "Invalid input, could not cast to integer, "
            "try in hex with 0x prefix"
        )
    try:
        return int_to_bytes(input_, int((bitwidth + 7) / 8))
    except UIn_BadParamError:
        raise


def enum(type_name, *sequential, **named):
    enums = dict(list(zip(sequential, list(range(len(sequential))))), **named)
    reverse = dict((value, key) for key, value in enums.items())

    @staticmethod
    def to_str(x):
        return reverse[x]
    enums['to_str'] = to_str

    @staticmethod
    def from_str(x):
        return enums[x]

    enums['from_str'] = from_str
    return type(type_name, (), enums)


PreType = enum('PreType', 'None', 'SimplePre', 'SimplePreLAG')
MeterType = enum('MeterType', 'packets', 'bytes')
TableType = enum('TableType', 'simple', 'indirect', 'indirect_ws')
ResType = enum('ResType', 'table', 'action_prof', 'action', 'meter_array',
               'counter_array', 'register_array')


def parse_runtime_data(action, params):
    def parse_param_(field, bw):
        try:
            return parse_param(field, bw)
        except UIn_BadParamError as e:
            raise UIn_RuntimeDataError(
                "Error while parsing %s - %s" % (field, e)
            )

    bitwidths = [bw for(_, bw) in action.runtime_data]
    byte_array = []
    for input_str, bitwidth in zip(params, bitwidths):
        byte_array += [bytes_to_string(parse_param_(input_str, bitwidth))]

    return byte_array


def get_res(type_name, name, res_type):
    key = res_type, name
    if key not in SUFFIX_LOOKUP_MAP:
        raise UIn_ResourceError(type_name, name)
    return SUFFIX_LOOKUP_MAP[key]


def reset_config():
    TABLES.clear()
    ACTION_PROFS.clear()
    ACTIONS.clear()
    METER_ARRAYS.clear()
    COUNTER_ARRAYS.clear()
    REGISTER_ARRAYS.clear()
    CUSTOM_CRC_CALCS.clear()

    SUFFIX_LOOKUP_MAP.clear()


def load_json_str(json_str):
    def get_header_type(header_name, j_headers):
        for h in j_headers:
            if h["name"] == header_name:
                return h["header_type"]
        assert (0)

    def get_field_bitwidth(header_type, field_name, j_header_types):
        for h in j_header_types:
            if h["name"] != header_type:
                continue
            for t in h["fields"]:
                # t can have a third element (field signedness)
                f, bw = t[0], t[1]
                if f == field_name:
                    return bw
        assert (0)

    reset_config()
    json_ = json.loads(json_str)

    def get_json_key(key):
        return json_.get(key, [])

    for j_action in get_json_key("actions"):
        action = Action(j_action["name"], j_action["id"])
        for j_param in j_action["runtime_data"]:
            action.runtime_data += [(j_param["name"], j_param["bitwidth"])]

    for j_pipeline in get_json_key("pipelines"):
        if "action_profiles" in j_pipeline:  # new JSON format
            for j_aprof in j_pipeline["action_profiles"]:
                action_prof = ActionProf(j_aprof["name"], j_aprof["id"])
                action_prof.with_selection = "selector" in j_aprof

        for j_table in j_pipeline["tables"]:
            table = Table(j_table["name"], j_table["id"])
            table.match_type = MatchType.from_str(j_table["match_type"])
            table.type_ = TableType.from_str(j_table["type"])
            table.support_timeout = j_table["support_timeout"]
            for action in j_table["actions"]:
                table.actions[action] = ACTIONS[action]

            if table.type_ in {TableType.indirect, TableType.indirect_ws}:
                if "action_profile" in j_table:
                    action_prof = ACTION_PROFS[j_table["action_profile"]]
                else:  # for backward compatibility
                    assert ("act_prof_name" in j_table)
                    action_prof = ActionProf(j_table["act_prof_name"],
                                             table.id_)
                    action_prof.with_selection = "selector" in j_table
                action_prof.actions.update(table.actions)
                action_prof.ref_cnt += 1
                table.action_prof = action_prof

            for j_key in j_table["key"]:
                target = j_key["target"]
                match_type = MatchType.from_str(j_key["match_type"])
                if match_type == MatchType.VALID:
                    field_name = target + "_valid"
                    bitwidth = 1
                elif target[1] == "$valid$":
                    field_name = target[0] + "_valid"
                    bitwidth = 1
                else:
                    field_name = ".".join(target)
                    header_type = get_header_type(target[0],
                                                  json_["headers"])
                    bitwidth = get_field_bitwidth(header_type, target[1],
                                                  json_["header_types"])
                table.key += [(field_name, match_type, bitwidth)]

    for j_meter in get_json_key("meter_arrays"):
        meter_array = MeterArray(j_meter["name"], j_meter["id"])
        if "is_direct" in j_meter and j_meter["is_direct"]:
            meter_array.is_direct = True
            meter_array.binding = j_meter["binding"]
        else:
            meter_array.is_direct = False
            meter_array.size = j_meter["size"]
        meter_array.type_ = MeterType.from_str(j_meter["type"])
        meter_array.rate_count = j_meter["rate_count"]

    for j_counter in get_json_key("counter_arrays"):
        counter_array = CounterArray(j_counter["name"], j_counter["id"])
        counter_array.is_direct = j_counter["is_direct"]
        if counter_array.is_direct:
            counter_array.binding = j_counter["binding"]
        else:
            counter_array.size = j_counter["size"]

    for j_register in get_json_key("register_arrays"):
        register_array = RegisterArray(j_register["name"], j_register["id"])
        register_array.size = j_register["size"]
        register_array.width = j_register["bitwidth"]

    for j_calc in get_json_key("calculations"):
        calc_name = j_calc["name"]
        if j_calc["algo"] == "crc16_custom":
            CUSTOM_CRC_CALCS[calc_name] = 16
        elif j_calc["algo"] == "crc32_custom":
            CUSTOM_CRC_CALCS[calc_name] = 32

    # Builds a dictionary mapping (object type, unique suffix) to the object
    # (Table, Action, etc...). In P4_16 the object name is the fully-qualified
    # name, which can be quite long, which is why we accept unique suffixes as
    # valid identifiers.
    suffix_count = Counter()
    for res_type, res_dict in [
            (ResType.table, TABLES), (ResType.action_prof, ACTION_PROFS),
            (ResType.action, ACTIONS), (ResType.meter_array, METER_ARRAYS),
            (ResType.counter_array, COUNTER_ARRAYS),
            (ResType.register_array, REGISTER_ARRAYS)]:
        for name, res in list(res_dict.items()):
            suffix = None
            for s in reversed(name.split('.')):
                suffix = s if suffix is None else s + '.' + suffix
                key = (res_type, suffix)
                SUFFIX_LOOKUP_MAP[key] = res
                suffix_count[key] += 1
    for key, c in list(suffix_count.items()):
        if c > 1:
            del SUFFIX_LOOKUP_MAP[key]


# table = instance of table class
# key fields = list of searched key, e.g. ["1", "2"]
# when table_add ingress.t_l3_forwarding ingress.send 1 2 => 3
def parse_match_key(table, key_fields):
    def parse_param_(field, bw):
        try:
            return parse_param(field, bw)
        except UIn_BadParamError as e:
            raise UIn_MatchKeyError("Error while parsing %s - %s" % (field, e))

    params = []
    match_types = [t for (_, t, _) in table.key]
    bitwidths = [bw for (_, _, bw) in table.key]
    for idx, field in enumerate(key_fields):
        param_type = _match_types_mapping[match_types[idx]]
        bw = bitwidths[idx]
        if param_type == BmMatchParamType.EXACT:
            key = bytes_to_string(parse_param_(field, bw))
            param = BmMatchParam(type=param_type,
                                 exact=BmMatchParamExact(key))
        elif param_type == BmMatchParamType.LPM:
            try:
                prefix, length = field.split("/")
            except ValueError:
                raise UIn_MatchKeyError(
                    "Invalid LPM value {}, use '/' to separate prefix "
                    "and length".format(field))
            key = bytes_to_string(parse_param_(prefix, bw))
            param = BmMatchParam(type=param_type,
                                 lpm=BmMatchParamLPM(key, int(length)))
        elif param_type == BmMatchParamType.TERNARY:
            try:
                key, mask = field.split("&&&")
            except ValueError:
                raise UIn_MatchKeyError(
                    "Invalid ternary value {}, use '&&&' to separate key and "
                    "mask".format(field))
            key = bytes_to_string(parse_param_(key, bw))
            mask = bytes_to_string(parse_param_(mask, bw))
            if len(mask) != len(key):
                raise UIn_MatchKeyError(
                    "Key and mask have "
                    "different lengths in expression %s" % field
                )
            param = BmMatchParam(type=param_type,
                                 ternary=BmMatchParamTernary(key, mask))
        elif param_type == BmMatchParamType.VALID:
            key = bool(int(field))
            param = BmMatchParam(type=param_type,
                                 valid=BmMatchParamValid(key))
        elif param_type == BmMatchParamType.RANGE:
            try:
                start, end = field.split("->")
            except ValueError:
                raise UIn_MatchKeyError(
                    "Invalid range value {}, use '->' to separate range start "
                    "and range end".format(field))
            start = bytes_to_string(parse_param_(start, bw))
            end = bytes_to_string(parse_param_(end, bw))
            if len(start) != len(end):
                raise UIn_MatchKeyError(
                    "start and end have "
                    "different lengths in expression %s" % field
                )
            if start > end:
                raise UIn_MatchKeyError(
                    "start is less than end in expression %s" % field
                )
            param = BmMatchParam(type=param_type,
                                 range=BmMatchParamRange(start, end))
        else:
            assert(0)
        params.append(param)
    return params


def get_json_config(standard_client=None, json_path=None, out=sys.stdout):
    if json_path:
        with open(json_path, 'r') as f:
            return f.read()
    else:
        assert(standard_client is not None)
        try:
            print("Obtaining JSON from switch...\n")
            json_cfg = standard_client.bm_get_config()
            print("Done\n")
        except Exception:
            print("Error when requesting JSON config from switch\n")
            sys.exit(1)
        return json_cfg

##############################################
#           runtime_CLI.py part end          #
##############################################


class Bmv2Thrift():
    def __init__(self, ip, json_path):
        # Thrift client, start later
        services = [("standard", Standard.Client)] + \
                   [("simple_pre_lag", SimplePreLAG.Client)]
        self.standard_client, self.mc_client = thrift_connect(
            ip, "22223", services)
        load_json_str(get_json_config(self.standard_client, json_path))

    def call_method(self, method, arguments, p4_action_args=[]):
        if method == "table_add":
            result = self.table_add(
                arguments[0], arguments[1], arguments[2:],
                action_parameters=p4_action_args)
        else:
            result = getattr(self, method)(*arguments)
        return result

    def get_table_num_entries(self, table_name):
        return self.standard_client.bm_mt_get_num_entries(0, table_name)

    def get_table_obj(self, table_name):
        table = get_res("table", table_name, ResType.table)
        return table

    # table_name="ingress.t_l1_forwarding"; e.g.
    # action_name="ingress.send"; machtes=["1"], action_parameters=["2", "3"]
    def table_add(self, table_name, action_name, matches=[],
                  action_parameters=[]):
        last_add = "table add " + table_name + " " + action_name + \
                   " matches=" + str(matches) + " action_parameters=" + \
                   str(action_parameters)
        print(last_add)
        try:
            if type(matches) == tuple:
                matches = list(matches)
            table_obj = get_res("table", table_name, ResType.table)
            matches = parse_match_key(table_obj, matches)
            action = table_obj.get_action(action_name)
            runtime_data = parse_runtime_data(action, action_parameters)
            entry_handle = self.standard_client.bm_mt_add_entry(
                0, table_name, matches, action_name, runtime_data,
                BmAddEntryOptions(priority=0)
            )
            return ""
        except Exception:
            msg = "ERROR while: \n" + last_add + "\n" + traceback.format_exc()
            print(msg)
            return msg

    def table_clear(self, table_name):
        self.standard_client.bm_mt_clear_entries(0, table_name, False)

    def get_table_entries(self, table):
        return self.mc_client.bm_mt_get_entries(0, table)

    def clear_all_tables(self):
        try:
            for table_name in sorted(TABLES):
                self.table_clear(str(table_name))
            print("clear_all_tables_finished")
        except Exception as e:
            print(e)
            print("clear_all_tables_error")

    def create_mcast_grp(self, mcast_group):
        if type(mcast_group) == str and mcast_group.isdigit():
            mcast_group = int(mcast_group)
        if type(mcast_group) != int:
            print("arg must be int as string")
        mgrp_hdl = self.mc_client.bm_mc_mgrp_create(0, mcast_group)

        return mgrp_hdl

    def destroy_mcast_grp(self, mcast_group):
        if type(mcast_group) == str and mcast_group.isdigit():
            mcast_group = int(mcast_group)
        if type(mcast_group) != int:
            print("arg must be int as string")
        self.mc_client.bm_mc_mgrp_destroy(0, mcast_group)

    def create_mc_node(self, rid, port):
        if type(rid) == str and rid.isdigit():
            rid = int(rid)
        if type(port) == str and port.isdigit():
            port = int(port)
        if type(rid) != int or type(port) != int:
            print("args must be int as strings")
            return
        port_map_str = "1"
        # 0 = port_map_str -> 1; 1->10; 2->100; 3->1000 etc.
        for i in range(port):
            port_map_str = port_map_str + "0"
        l1_hdl = self.mc_client.bm_mc_node_create(0, rid, port_map_str, "")

        return l1_hdl

    def destroy_mc_node(self, l1_hdl):
        if type(l1_hdl) == str and l1_hdl.isdigit():
            l1_hdl = int(l1_hdl)
        if type(l1_hdl) != int:
            print("arg must be int as string")
            return
        self.mc_client.bm_mc_node_destroy(0, l1_hdl)

    def associate_mc_node(self, mcast_group, l1_hdl):
        if type(mcast_group) == str and mcast_group.isdigit():
            mcast_group = int(mcast_group)
        if type(l1_hdl) == str and l1_hdl.isdigit():
            l1_hdl = int(l1_hdl)
        if type(mcast_group) != int or type(l1_hdl) != int:
            print("args must be numbers as int or strings")
            return
        self.mc_client.bm_mc_node_associate(0, mcast_group, l1_hdl)

    def dissociate_mc_node(self, mcast_group, l1_hdl):
        if type(mcast_group) == str and mcast_group.isdigit():
            mcast_group = int(mcast_group)
        if type(l1_hdl) == str and l1_hdl.isdigit():
            l1_hdl = int(l1_hdl)
        if type(mcast_group) != int or type(l1_hdl) != int:
            print("args must be numbers as int or strings")
            return
        self.mc_client.bm_mc_node_dissociate(0, mcast_group, l1_hdl)

    def clear_all_mcast_grps(self):
        try:
            json_dump = self.mc_client.bm_mc_get_entries(0)
            mc_json = json.loads(json_dump)
            for group in mc_json["mgrps"]:
                for handle in group["l1_handles"]:
                    self.dissociate_mc_node(group["id"], handle)
                    self.destroy_mc_node(handle)
                self.destroy_mcast_grp(group["id"])
            return "clear_all_mcast_grps_finished"
        except Exception as e:
            print(e)
            return "clear_all_mcast_grps_error"


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="bmv2 thrift module")
    parser.add_argument("--json", help="Path to the compiled p4 json",
                        type=str, action="store", required=True)
    parser.add_argument("--method", help="Method to call", type=str,
                        action="store", required=True)
    parser.add_argument('--args', help="Arguments to pass as list", nargs='+',
                        default=[], required=False)
    parser.add_argument('--p4_action_args',
                        help="Arguments to pass to p4 action", nargs='+',
                        default=[], required=False)
    args = parser.parse_args()

    thr = Bmv2Thrift(args.json)
    if len(args.p4_action_args) == 0:
        thr.call_method(args.method, args.args)
    else:
        thr.call_method(args.method, args.args, args.p4_action_args)
else:
    print("bmv2_thrift loaded as module...")
