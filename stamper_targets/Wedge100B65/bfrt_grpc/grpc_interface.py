# Copyright 2021-present Ralf Kundel, Fridolin Siegmund
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
import grpc
import json
import math
import queue
import os
from random import randint
import sys
import threading
import traceback


def print_error(error, yellow=False):
    if yellow:
        print_msg = "\033[1;33m"
        print_msg += "-------------------- GRPC Tofino " \
                     "WARNING -------------- \n"
    else:
        print_msg = "\033[1;31m"
        print_msg += "-------------------- GRPC Tofino " \
                     "ERROR ---------------- \n"
    if isinstance(error, str):
        print_msg += error
    elif isinstance(error, tuple):
        print_msg += ''.join(error)
    else:
        print_msg += ("unknown error type: " + str(type(error)))
        print_msg += str(error)
    print_msg += "\n-----------------------------------------------------"
    print_msg += "\x1b[0m"
    print(print_msg)


dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir_path)
try:
    import bfruntime_pb2
except ImportError:
    print_error("bfruntime_pb2 MODULE NOT FOUND. Sure you followed the install"
                " instructions? Please stop and restart p4sta after the"
                " initial installation of the Tofino driver.")
try:
    import bfruntime_pb2_grpc
except ImportError:
    print_error(
        "bfruntime_pb2_grpc MODULE NOT FOUND. Sure you followed the install "
        "instructions? Please stop and restart p4sta after the initial "
        "installation of the Tofino driver.")


class TofinoInterface:
    used_client_ids = []

    def __init__(self, grpc_addr, device_id, client_id=randint(1, 100),
                 is_master=False):
        def f_stream_receive_thr(strm):
            try:
                for inp in strm:
                    self.in_queue.put(inp)
            except grpc.RpcError:
                print(traceback.format_exc())

        def stream_iter():
            while True:
                out = self.out_queue.get()
                if out is None:  # if None is inserted stop execution!
                    break
                yield out

        while client_id in TofinoInterface.used_client_ids:
            client_id = randint(1, 100)
        print("Selected client id: " + str(client_id))
        self.device_id = device_id
        self.client_id = client_id
        self.p4_program = ""
        self.bfruntime_info = dict()
        self.non_p4_config = dict()
        self.in_queue = queue.Queue()
        self.out_queue = queue.Queue()
        opt_size = 1024 ** 3

        if grpc_addr.find(":") == -1:
            grpc_addr = grpc_addr + ":50052"
        self.grpc_channel = grpc.insecure_channel(grpc_addr, options=[
            ('grpc.max_send_message_length', opt_size),
            ('grpc.max_receive_message_length', opt_size),
            ('grpc.max_metadata_size', opt_size)])

        self.grpc_stub = bfruntime_pb2_grpc.BfRuntimeStub(self.grpc_channel)
        self.stream = self.grpc_stub.StreamChannel(stream_iter())
        # start receiver in thread until teardown of connection
        self.stream_receive_thr = threading.Thread(target=f_stream_receive_thr,
                                                   args=(self.stream,))
        self.stream_receive_thr.start()

        stream_request = bfruntime_pb2.StreamMessageRequest()
        stream_request.subscribe.device_id = device_id
        stream_request.client_id = client_id
        stream_request.subscribe.is_master = is_master
        stream_request.subscribe.notifications.\
            enable_learn_notifications = True
        stream_request.subscribe.notifications.\
            enable_idletimeout_notifications = True
        stream_request.subscribe.notifications.\
            enable_port_status_change_notifications = True

        self.out_queue.put(stream_request)
        try:
            if self.in_queue.get(timeout=3).subscribe.status.code == 0:
                print("Subscription was successful.")
                TofinoInterface.used_client_ids.append(client_id)
        except Exception:
            print_error("Subscribing failed!")
            print(traceback.format_exc())

    def bind_p4_name(self, p4_program):
        self.p4_program = p4_program
        request = bfruntime_pb2.SetForwardingPipelineConfigRequest()
        request.client_id = self.client_id
        request.action = bfruntime_pb2.SetForwardingPipelineConfigRequest.BIND
        cfg = request.config.add()
        cfg.p4_name = p4_program
        try:
            self.grpc_stub.SetForwardingPipelineConfig(request)
            print("Binding P4 name " + p4_program + " was successful")

            send_request = bfruntime_pb2.GetForwardingPipelineConfigRequest()
            send_request.device_id = self.device_id
            send_request.client_id = self.client_id
            bfrt_info = self.grpc_stub.GetForwardingPipelineConfig(
                send_request)
            self.non_p4_config = json.loads(
                bfrt_info.non_p4_config.bfruntime_info.decode())
            for config in bfrt_info.config:
                if config.p4_name == p4_program:
                    self.bfruntime_info = json.loads(
                        config.bfruntime_info.decode())

        except grpc.RpcError as e:
            print("Binding P4 name " + p4_program + " error")
            return str(traceback.format_exc())

        return ""

    def teardown(self):
        print("Teardown...")
        while self.client_id in TofinoInterface.used_client_ids:
            try:
                TofinoInterface.used_client_ids.remove(self.client_id)
            except ValueError:
                pass
        self.out_queue.put(None)
        self.stream_receive_thr.join()

    # compatibility for code using table/key/data/action names without pipe.###
    def _get_full_name(self, name):
        """ Searches in json for given name and creates full name,
        e.g. "table1" => "pipe.SwitchIngress.table1" """
        for table in self.bfruntime_info["tables"]:
            if table["name"].split(".")[-1] == name:
                print("Replaced table name " + name + " with " + table["name"])
                return table["name"]
            if "key" in table:
                for key in table["key"]:
                    if key["name"].split(".")[-1] == name:
                        print("Replaced key name " + name + " with " + key[
                            "name"])
                        return key["name"]
            if "action_specs" in table:
                for action in table["action_specs"]:
                    if action["name"].split(".")[-1] == name:
                        return action["name"]
                    if "data" in action:
                        for data in action["data"]:
                            if data["name"].split(".")[-1] == name:
                                print("Replaced data name " + name + " with " +
                                      data["name"])
                                return data["name"]
        # no replacement found, just return original string=>it may be correct
        return name

    def get_table_id(self, table_name):
        for i in range(2):
            for table in self.bfruntime_info["tables"]:
                if table["name"] == table_name:
                    return table["id"]
            # if not found search in non_p4_config
            for table in self.non_p4_config["tables"]:
                if table["name"] == table_name:
                    return table["id"]
            if i == 0:
                print_error(
                    "Table " + table_name + " not found for given p4 program: "
                    + self.p4_program +
                    " try to substitute name with suitable from json.",
                    yellow=True)
                table_name = self._get_full_name(table_name)
            else:
                print_error(
                    "Table " + table_name + " not found for given p4 program: "
                    + self.p4_program)
        return None

    def get_key_id(self, key_name, table_name):
        if table_name.find("$") == 0:
            for table in self.non_p4_config["tables"]:
                if table["name"] == table_name:
                    for key in table["key"]:
                        if key_name == "$MGID":
                            bit_width = 16
                        else:
                            bit_width = 32
                        if key["name"] == key_name:
                            # 32 bit fixed size for port stuff?
                            return key["id"], bit_width
        else:
            for i in range(2):
                for table in self.bfruntime_info["tables"]:
                    if table["name"] == table_name:
                        for key in table["key"]:
                            if key["name"] == key_name:
                                if table["table_type"] == "Counter" \
                                        or table["table_type"] == "Register":
                                    if key["type"]["type"] == "uint32":
                                        bit_width = 32
                                    elif key["type"]["type"] == "uint64":
                                        bit_width = 64
                                    else:
                                        bit_width = 32
                                        print_error(
                                            "Bit width for key " + key["name"]
                                            + " from table " + table_name +
                                            " not determinable - using 32 bit")
                                else:
                                    bit_width = key["type"]["width"]
                                return key["id"], bit_width
                if i == 0:
                    table_name = self._get_full_name(table_name)
                    key_name = self._get_full_name(key_name)
        return None

    def get_action_id(self, action_name, table_name):
        for i in range(2):
            for table in self.bfruntime_info["tables"]:
                if table["name"] == table_name and "action_specs" in table:
                    for action in table["action_specs"]:
                        if action["name"] == action_name:
                            return action["id"]
            if i == 0:
                table_name = self._get_full_name(table_name)
                action_name = self._get_full_name(action_name)
        return None

    def get_data_id(self, data_name, action_name, table_name):
        if table_name.find("$") == 0:
            for table in self.non_p4_config["tables"]:
                if table["name"] == table_name:
                    for data in table["data"]:
                        if data["singleton"]["name"] == data_name:
                            if data_name == "$MULTICAST_RID":
                                bit_width = 16
                            elif data_name == "$MULTICAST_LAG_ID":
                                bit_width = 8
                            elif data_name == "MULTICAST_NODE_L1_XID":
                                bit_width = 16
                            elif data_name == "MULTICAST_NODE_L1_XID":
                                bit_width = 16
                            else:
                                bit_width = 32
                            # 32 bit fixed size for port stuff?
                            return data["singleton"]["id"], bit_width
        else:
            for i in range(2):
                for table in self.bfruntime_info["tables"]:
                    if table["name"] == table_name:
                        if table["table_type"] == "Counter":
                            for data in table["data"]:
                                if data["singleton"]["name"] == data_name:
                                    if data["singleton"]["type"]["type"] \
                                            == "uint32":
                                        bit_width = 32
                                    elif data["singleton"]["type"]["type"] \
                                            == "uint64":
                                        bit_width = 64
                                    else:
                                        bit_width = 32
                                        print_error(
                                            "Bit width for data " +
                                            data["name"] + " from table " +
                                            table_name + " not determinable - "
                                                         "using 32 bit")
                                    return data["singleton"]["id"], bit_width
                        elif table["table_type"] == "Register":
                            for data in table["data"]:
                                if data["singleton"]["name"] == data_name:
                                    return data["singleton"]["id"], \
                                           data["singleton"]["type"]["width"]
                        else:
                            for action in table["action_specs"]:
                                if action["name"] == action_name:
                                    for data in action["data"]:
                                        if data["name"] == data_name:
                                            return data["id"], data["type"][
                                                "width"]
                if i == 0:
                    table_name = self._get_full_name(table_name)
                    action_name = self._get_full_name(action_name)
        return None

    # internal function to start a WriteRequest
    def _get_request(self, req_type="write"):
        if req_type == "write":
            request = bfruntime_pb2.WriteRequest()
            request.atomicity = bfruntime_pb2.WriteRequest.CONTINUE_ON_ERROR
        else:
            request = bfruntime_pb2.ReadRequest()
        request.target.device_id = self.device_id
        request.client_id = self.client_id
        request.target.pipe_id = 0xffff
        request.target.direction = 0xff
        request.target.prsr_id = 0xff

        return request

    # add_to_table("t_l1_forwarding",
    # [["ig_intr_md.ingress_port", int(dut["p4_port"])]],
    # [["egress_port", int(loadgen_grp["loadgens"][0]["p4_port"])]],
    # "SwitchIngress.send")
    def add_to_table(self, table_name, keys=[], datas=[], action="",
                     mod_inc=False, silent=False):
        def get_table_type(table_name):
            for table in self.bfruntime_info["tables"]:
                if table["name"] == table_name:
                    return table["table_type"]

        if not silent:
            print("Adding to table: " + table_name + "\nkeys:" + str(
                keys) + " => " + action + "(" + str(datas) + ")\n")
        request = self._get_request(req_type="write")

        table_id = self.get_table_id(table_name)
        # bfruntime_pb2.Update.INSERT or bfruntime_pb2.Update.MODIFY_INC
        update = request.updates.add()
        if mod_inc:
            update.type = bfruntime_pb2.Update.MODIFY_INC
        else:
            update.type = bfruntime_pb2.Update.INSERT
        tbl_entry = update.entity.table_entry
        tbl_entry.table_id = table_id
        for key_pair in keys:
            key_field = tbl_entry.key.fields.add()
            key_field.field_id, key_bit_width = self.get_key_id(key_pair[0],
                                                                table_name)
            if type(key_pair[1]) == str:
                key_field.exact.value = key_pair[1].encode()
            elif type(key_pair[1]) == int:
                key_field.exact.value = key_pair[1].to_bytes(
                    math.ceil(key_bit_width / 8), "big")
            else:
                print_error("Key value must be String or Int! Table: " +
                            table_name + " Key: " + str(key_pair[0]))

        action_id = self.get_action_id(action, table_name)
        if action_id is not None:
            tbl_entry.data.action_id = action_id
            for data_pair in datas:
                data_field = tbl_entry.data.fields.add()
                data_field.field_id, data_bit_width = self.get_data_id(
                    data_pair[0], action, table_name)
                if type(data_pair[1]) == int:
                    data_field.stream = data_pair[1].to_bytes(
                        math.ceil(data_bit_width / 8), "big")
                elif type(data_pair[1]) == float:
                    data_field.float_val = data_pair[1]
                elif type(data_pair[1]) == str:
                    data_field.str_val = data_pair[1]
                elif type(data_pair[1]) == bool:
                    data_field.bool_val = data_pair[1]
                elif type(data_pair[1]) == list:
                    if (len(data_pair[1])) > 0 and type(
                            data_pair[1][0]) == int:
                        data_field.int_arr_val.val.extend(data_pair[1])
                    elif (len(data_pair[1])) > 0 and type(
                            data_pair[1][0]) == bool:
                        data_field.bool_arr_val.val.extend(data_pair[1])
                else:
                    print_error(
                        "Data value must be Int, Float, String, Bool! Table: "
                        + table_name + " Action: " + action + " Data: " + str(
                            data_pair[0]))

        elif table_name.find("$") == 0 or get_table_type(
                table_name) == "Counter" or get_table_type(
                table_name) == "Register":
            for data_pair in datas:
                data_field = tbl_entry.data.fields.add()
                data_field.field_id, data_bit_width = self.get_data_id(
                    data_pair[0], action, table_name)
                if type(data_pair[1]) == int:
                    data_field.stream = data_pair[1].to_bytes(
                        math.ceil(data_bit_width / 8), "big")
                elif type(data_pair[1]) == float:
                    data_field.float_val = data_pair[1]
                elif type(data_pair[1]) == str:
                    data_field.str_val = data_pair[1]
                elif type(data_pair[1]) == bool:
                    data_field.bool_val = data_pair[1]
                elif type(data_pair[1]) == list:
                    if (len(data_pair[1])) > 0 and type(
                            data_pair[1][0]) == int:
                        data_field.int_arr_val.val.extend(data_pair[1])
                    elif (len(data_pair[1])) > 0 and type(
                            data_pair[1][0]) == bool:
                        data_field.bool_arr_val.val.extend(data_pair[1])
                else:
                    print_error("Data value must be Int, Float, String, Bool, "
                                "List! Table: " + table_name + " Data: " + str(
                                    data_pair[0]))

        self.grpc_stub.Write(request)

    def delete_table(self, table_name):
        try:
            table_id = self.get_table_id(table_name)
            # first get table entries for given table
            read_request = self._get_request(req_type="read")
            tbl_entry = read_request.entities.add().table_entry
            tbl_entry.table_id = table_id
            # we don't need to delete default entries because they are default
            tbl_entry.is_default_entry = False
            tbl_entry.table_read_flag.from_hw = True  # not sure
            answers = self.grpc_stub.Read(read_request)

            entries = []
            for answer in answers:
                for e in answer.entities:
                    key_ids_to_delete = []
                    for key_field in e.table_entry.key.fields:
                        key_tuple = (key_field.field_id, key_field.exact.value)
                        key_ids_to_delete.append(key_tuple)
                    if len(key_ids_to_delete) > 0:
                        entries.append(key_ids_to_delete)

            request = self._get_request(req_type="write")
            for entry in entries:
                update = request.updates.add()
                update.type = bfruntime_pb2.Update.DELETE
                tbl_entry = update.entity.table_entry
                tbl_entry.table_id = table_id
                for del_id, del_value in entry:
                    key_field = tbl_entry.key.fields.add()
                    key_field.field_id = del_id
                    key_field.exact.value = del_value

            self.grpc_stub.Write(request)
            print("Deleted Table " + table_name)
        except Exception:
            print_error(traceback.format_exc())

    def clear_all_tables(self, ignore_tables_list=[]):
        ignore_tables_list.append("$")
        for table in self.bfruntime_info["tables"]:
            total_found_indexes = 0
            for elem in ignore_tables_list:
                total_found_indexes = total_found_indexes + table["name"].find(
                    elem)
            if total_found_indexes == -(len(ignore_tables_list)):
                try:
                    self.delete_table(table["name"])
                except Exception:
                    print_error(traceback.format_exc())

    # hosts = [{"p4_port": xxx, "speed": 10G, "fec": "NONE",
    # "an": "default"}, {..}, ..]
    def set_ports(self, hosts):
        def get_an(host):
            try:
                if "an" in host:
                    if host["an"] == "default":
                        return "PM_AN_DEFAULT"
                    elif host["an"] == "on":
                        return "PM_AN_FORCE_ENABLE"
                    elif host["an"] == "off":
                        return "PM_AN_FORCE_DISABLE"
                    else:
                        raise Exception
                else:
                    raise Exception
            except Exception as e:
                print_error(
                    "Error at parsing an-set status for port " +
                    host["p4_port"] + " setting to 0 (default). This message c"
                                      "an occure several times during the port"
                                      " activation process and can be ignored "
                                      "if no AN setting is set. Msg: " +
                    str(e), yellow=True)
                return "PM_AN_DEFAULT"

        def get_fec(fec, speed):
            if fec == "FC":
                if speed == "100G":
                    print_error("FIRECODE IS NOT AVAILABLE FOR 100G")
                    return "NONE"
                else:
                    return "FIRECODE"
            elif fec == "RS":
                return "REED_SOLOMON"
            else:
                return "NONE"

        already_added_p4_ports = []
        for host in hosts:
            if "speed" not in host or host["speed"] == "":
                host["speed"] = "10G"
            try:
                if host["speed"] == "10G":
                    # get "1" from 2/1 hw port because ALL 4 ports must be
                    # enabled if breakout cable is used (instead 2/1 all
                    # ports (2/0, 2/1, 2/2, 2/3) activated)
                    port_ind = int(host["real_port"].split("/")[-1])
                    if port_ind == 0:
                        p4_ports = [int(host["p4_port"]),
                                    int(host["p4_port"]) + 1,
                                    int(host["p4_port"]) + 2,
                                    int(host["p4_port"]) + 3]
                    elif port_ind == 1:
                        p4_ports = [int(host["p4_port"]) - 1,
                                    int(host["p4_port"]),
                                    int(host["p4_port"]) + 1,
                                    int(host["p4_port"]) + 2]
                    elif port_ind == 2:
                        p4_ports = [int(host["p4_port"]) - 2,
                                    int(host["p4_port"]) - 1,
                                    int(host["p4_port"]),
                                    int(host["p4_port"]) + 1]
                    else:
                        p4_ports = [int(host["p4_port"]) - 3,
                                    int(host["p4_port"]) - 2,
                                    int(host["p4_port"]) - 1,
                                    int(host["p4_port"])]
                    if p4_ports not in already_added_p4_ports:
                        for p4_port in p4_ports:
                            self.add_to_table(
                                "$PORT", keys=[["$DEV_PORT", p4_port]],
                                datas=[["$SPEED", "BF_SPEED_" + host["speed"]],
                                       ["$AUTO_NEGOTIATION", get_an(host)],
                                       ["$FEC", "BF_FEC_TYP_" + get_fec(
                                           host["fec"], host["speed"])],
                                       ["$PORT_ENABLE", True]],
                                action="")
                        # by adding p4_ports list to already_added.. a second
                        # entry_add if host1 has 2/1 and host2 has 2/2
                        # is prevented
                        already_added_p4_ports.append(p4_ports)
                else:
                    self.add_to_table("$PORT",
                                      keys=[
                                          ["$DEV_PORT", int(host["p4_port"])]],
                                      datas=[["$SPEED",
                                              "BF_SPEED_" + host["speed"]],
                                             ["$AUTO_NEGOTIATION",
                                              get_an(host)],
                                             ["$FEC", "BF_FEC_TYP_" + get_fec(
                                                 host["fec"], host["speed"])],
                                             ["$PORT_ENABLE", True]],
                                      action="")
            except Exception:
                print_error(traceback.format_exc())

    def delete_ports(self):
        self.delete_table("$PORT")

    def set_multicast_groups(self, mcast_inp):
        created_mcast_grps = []
        for item in mcast_inp:
            try:
                # non_p4 json repeated = True, list is important!
                mbr_lags = [0]
                # non_p4 json repeated = True, list is important!
                mbr_ports = [item["port"]]
                # first create node for port
                self.add_to_table("$pre.node",
                                  keys=[
                                      ["$MULTICAST_NODE_ID", item["node_id"]]],
                                  datas=[["$MULTICAST_RID", 1],
                                         ["$MULTICAST_LAG_ID", mbr_lags],
                                         ["$DEV_PORT", mbr_ports]],
                                  action="")
                # now associate node with group (this creates mcast group too)
                # non_p4 json repeated = True, list is important!
                node_ids = [item["node_id"]]
                # non_p4 json repeated = True, list is important!
                l1_xid_valids = [False]
                # non_p4 json repeated = True, list is important!
                l1_xids = [0]
                self.add_to_table(
                    "$pre.mgid", keys=[["$MGID", item["group_id"]]],
                    datas=[["$MULTICAST_NODE_ID", node_ids],
                           ["$MULTICAST_NODE_L1_XID_VALID", l1_xid_valids],
                           ["$MULTICAST_NODE_L1_XID", l1_xids]],
                    action="", mod_inc=item["group_id"] in created_mcast_grps)
                if item["group_id"] not in created_mcast_grps:
                    created_mcast_grps.append(item["group_id"])

                print("Added port " + str(item["port"]) + " to node " + str(
                    item["node_id"]) + " and to mcast group " + str(
                    item["group_id"]))
            except Exception:
                print_error(
                    "Exception at multicast creating for item: " + str(item))
                print_error(traceback.format_exc())

    def clear_multicast_groups(self):
        self.delete_table("$pre.mgid")
        self.delete_table("$pre.node")

    # reads register and returns dictionary
    def read_register(self, table_name, register_index=0):
        table_id = self.get_table_id(table_name)
        read_request = self._get_request(req_type="read")
        tbl_entry = read_request.entities.add().table_entry
        tbl_entry.table_id = table_id
        tbl_entry.is_default_entry = False
        tbl_entry.table_read_flag.from_hw = True  # not sure
        key_field = tbl_entry.key.fields.add()
        key_field.field_id, key_bit_width = self.get_key_id("$REGISTER_INDEX",
                                                            table_name)
        key_field.exact.value = register_index.to_bytes(
            math.ceil(key_bit_width / 8), "big")
        answers = self.grpc_stub.Read(read_request)

        data_fields_values = []
        for answer in answers:
            for e in answer.entities:
                for data_field in e.table_entry.data.fields:
                    data_fields_values.append(int(data_field.stream.hex(), 16))

        if len(data_fields_values) == 0:
            print_error("No values retrieved for register " + table_name)
            data_fields_values.append(0)
        return data_fields_values

    # reads counter and returns list of tuple(pckts, bytes) where indx 0=port 0
    def read_counter(self, table_name, port_list=range(512)):
        def get_name_by_id(_id):
            for table in self.bfruntime_info["tables"]:
                if table["table_type"] == "Counter":
                    for data in table["data"]:
                        if data["singleton"]["id"] == _id:
                            return data["singleton"]["name"]

        table_id = self.get_table_id(table_name)
        read_request = self._get_request(req_type="read")

        for port in port_list:
            tbl_entry = read_request.entities.add().table_entry
            tbl_entry.table_id = table_id
            tbl_entry.is_default_entry = False
            tbl_entry.table_read_flag.from_hw = True  # not sure
            key_field = tbl_entry.key.fields.add()
            key_field.field_id, key_bit_width = self.get_key_id(
                "$COUNTER_INDEX", table_name)
            key_field.exact.value = port.to_bytes(math.ceil(key_bit_width / 8),
                                                  "big")

        answers = self.grpc_stub.Read(read_request)
        counter_read_datas = []
        for answer in answers:
            for e in answer.entities:
                as_dict = {}
                for data_field in e.table_entry.data.fields:
                    as_dict[get_name_by_id(data_field.field_id)] = int(
                        data_field.stream.hex(), 16)
                counter_read_datas.append(as_dict)

        all = [(0, 0) for i in range(512)]
        i = 0
        for elem in counter_read_datas:
            index = port_list[i]
            i = i + 1
            all[index] = (
                elem["$COUNTER_SPEC_PKTS"], elem["$COUNTER_SPEC_BYTES"])

        return all

    # clears all entries of indirect counter
    def clear_indirect_counter(self, counter_name, id_list=None):
        def get_counter_size(_counter_name):
            for table in self.bfruntime_info["tables"]:
                if table["table_type"] == "Counter" \
                        and table["name"] == _counter_name:
                    return table["size"]

        if id_list is None:
            id_list = range(get_counter_size(counter_name))

        for i in id_list:
            try:
                self.add_to_table(counter_name,
                                  keys=[["$COUNTER_INDEX", i]],
                                  datas=[["$COUNTER_SPEC_BYTES", 0],
                                         ["$COUNTER_SPEC_PKTS", 0]],
                                  action="",
                                  mod_inc=False,
                                  silent=True)
            except Exception:
                print_error(traceback.format_exc())

    def clear_register(self, register_name):
        table_id = self.get_table_id(register_name)
        request = self._get_request(req_type="write")
        update = request.updates.add()
        update.type = bfruntime_pb2.Update.DELETE
        tbl_entry = update.entity.table_entry
        tbl_entry.table_id = table_id
        self.grpc_stub.Write(request)
        print("Cleared Register " + register_name)

    def read_port_status(self):
        def get_name_by_id(_id):
            for table in self.non_p4_config["tables"]:
                if table["table_type"] == "PortConfigure":
                    for data in table["data"]:
                        if data["singleton"]["id"] == _id:
                            return data["singleton"]["name"]

        try:
            table_id = self.get_table_id("$PORT")
            read_request = self._get_request(req_type="read")
            tbl_entry = read_request.entities.add().table_entry
            tbl_entry.table_id = table_id

            answers = self.grpc_stub.Read(read_request)

            port_read_datas = []
            for answer in answers:
                for e in answer.entities:
                    as_dict = {}
                    for data_field in e.table_entry.data.fields:
                        data_name = get_name_by_id(data_field.field_id)
                        as_dict[data_name] = data_field
                    port_read_datas.append(as_dict)

            return port_read_datas
        except Exception:
            print_error(traceback.format_exc())
