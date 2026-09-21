import argparse
import logging
import os
import sys
import traceback


DIR_PATH = os.path.dirname(os.path.realpath(__file__))
sys.path.append(DIR_PATH)

import grpc_interface


TOFINO_STAMPER_V1_4_RESOURCES = {
    "ingress_counter",
    "ingress_stamped_counter",
    "dbg_ipv4_valid_counter",
    "dbg_tcp_valid_counter",
    "dbg_tcp_custom_valid_counter",
    "dbg_tcp_custom_0f10_counter",
    "dbg_tcp_add_empty_counter",
    "dbg_tcp_timestamp2_apply_counter",
    "dbg_tcp_timestamp2_action_counter",
    "dbg_timestamp2_mc_counter",
    "delta_register",
    "delta_register_high",
    "delta_register_pkts",
    "delta_register_pkts_high",
    "min_register",
    "max_register",
    "multi_counter_register",
    "t_l1_forwarding",
    "t_l1_forwarding_generation",
    "t_l1_forwarding_session_all_except_load",
    "t_l2_forwarding",
    "t_l3_forwarding",
    "t_add_empty_timestamp_tcp",
    "t_timestamp2_tcp",
    "t_add_empty_timestamp_udp",
    "t_timestamp2_udp",
    "t_add_empty_timestamp_icmp",
    "t_duplicate_to_dut",
    "egress_counter",
    "egress_stamped_counter",
    "iterator_end",
    "iterator",
    "broadcast_mac",
    "broadcast_mac_gtp",
    "t_mark_duplicate",
    "t_check_local_index_increment",
    "t_session_mapping",
}

ITERATOR_REGISTER = "pipe.SwitchEgress.iterator"
ITERATOR_END_REGISTER_PARAM = "pipe.SwitchEgress.iterator_end"

P4_RESOURCE_TABLE_TYPES = {
    "Counter",
    "MatchAction_Direct",
    "Register",
    "RegisterParam",
}

SUMMARY_TABLE_TYPES = {
    "Counter",
    "Register",
    "RegisterParam",
}


class BfrtNames:
    def __init__(self, interface):
        self.tables_by_id = {}
        self.key_names = {}
        self.action_names = {}
        self.action_data_names = {}
        self.table_data_names = {}
        self._add_tables(interface.bfruntime_info.get("tables", []), "p4")
        self._add_tables(interface.non_p4_config.get("tables", []), "fixed")

    def _add_tables(self, tables, source):
        for table in tables:
            table_id = table.get("id")
            if table_id is None:
                continue
            table_name = table.get("name", str(table_id))
            self.tables_by_id[table_id] = table
            self.key_names[table_id] = {
                key.get("id"): key.get("name", str(key.get("id")))
                for key in table.get("key", [])
            }
            self.action_names[table_id] = {}
            self.action_data_names[table_id] = {}
            for action in table.get("action_specs", []):
                action_id = action.get("id")
                self.action_names[table_id][action_id] = action.get(
                    "name", str(action_id))
                self.action_data_names[table_id][action_id] = {
                    data.get("id"): data.get("name", str(data.get("id")))
                    for data in action.get("data", [])
                }
            self.table_data_names[table_id] = {}
            for data in table.get("data", []):
                singleton = data.get("singleton", data)
                data_id = singleton.get("id")
                if data_id is not None:
                    self.table_data_names[table_id][data_id] = singleton.get(
                        "name", str(data_id))
            table["_debug_source"] = source
            table["_debug_name"] = table_name

    def table_name(self, table_id):
        table = self.tables_by_id.get(table_id)
        return table.get("name", str(table_id)) if table else str(table_id)

    def key_name(self, table_id, field_id):
        return self.key_names.get(table_id, {}).get(field_id, str(field_id))

    def action_name(self, table_id, action_id):
        if action_id == 0:
            return ""
        return self.action_names.get(table_id, {}).get(action_id,
                                                       str(action_id))

    def data_name(self, table_id, action_id, field_id):
        action_data = self.action_data_names.get(table_id, {}).get(
            action_id, {})
        return action_data.get(
            field_id,
            self.table_data_names.get(table_id, {}).get(field_id,
                                                        str(field_id)))


def bytes_to_int(value):
    return int.from_bytes(value, byteorder="big") if value else 0


def bytes_to_text(value):
    if value == b"":
        return "0"
    intval = bytes_to_int(value)
    width = max(2, len(value) * 2)
    return "{} (0x{:0{}x})".format(intval, intval, width)


def data_value_to_text(field):
    value_type = field.WhichOneof("value")
    if value_type == "stream":
        return bytes_to_text(field.stream)
    if value_type == "float_val":
        return str(field.float_val)
    if value_type == "str_val":
        return repr(field.str_val)
    if value_type == "int_arr_val":
        return "[" + ", ".join(str(v) for v in field.int_arr_val.val) + "]"
    if value_type == "bool_arr_val":
        return "[" + ", ".join(str(v) for v in field.bool_arr_val.val) + "]"
    if value_type == "str_arr_val":
        return "[" + ", ".join(repr(v) for v in field.str_arr_val.val) + "]"
    if value_type == "bool_val":
        return str(field.bool_val)
    if value_type == "container_arr_val":
        containers = []
        for container in field.container_arr_val.container:
            containers.append("{" + ", ".join(
                "{}={}".format(child.field_id, data_value_to_text(child))
                for child in container.val) + "}")
        return "[" + ", ".join(containers) + "]"
    return "<unset>"


def data_value_to_int(field):
    value_type = field.WhichOneof("value")
    if value_type == "stream":
        return bytes_to_int(field.stream)
    if value_type == "float_val":
        return int(field.float_val)
    if value_type == "bool_val":
        return int(field.bool_val)
    return None


def key_value_to_text(field):
    match_type = field.WhichOneof("match_type")
    if match_type == "exact":
        return bytes_to_text(field.exact.value)
    if match_type == "ternary":
        return "{} &&& {}".format(bytes_to_text(field.ternary.value),
                                  bytes_to_text(field.ternary.mask))
    if match_type == "lpm":
        return "{}/{}".format(bytes_to_text(field.lpm.value),
                              field.lpm.prefix_len)
    if match_type == "range":
        return "{}..{}".format(bytes_to_text(field.range.low),
                               bytes_to_text(field.range.high))
    if match_type == "optional":
        return "{} valid={}".format(bytes_to_text(field.optional.value),
                                    field.optional.is_valid)
    return "<unset>"


def format_entry(entry, names):
    table_id = entry.table_id
    parts = []
    if entry.is_default_entry:
        parts.append("default")
    if entry.key.fields:
        keys = []
        for field in entry.key.fields:
            keys.append("{}={}".format(
                names.key_name(table_id, field.field_id),
                key_value_to_text(field)))
        parts.append("keys: " + ", ".join(keys))

    action = names.action_name(table_id, entry.data.action_id)
    data = []
    for field in entry.data.fields:
        data.append("{}={}".format(
            names.data_name(table_id, entry.data.action_id, field.field_id),
            data_value_to_text(field)))
    if action:
        parts.append("action: " + action)
    if data:
        parts.append("data: " + ", ".join(data))
    return "  - " + "; ".join(parts) if parts else "  - <empty entry>"


def read_table(interface, table_id, default_entry=False, from_hw=True):
    request = interface._get_request(req_type="read")
    request.p4_name = interface.p4_program
    table_entry = request.entities.add().table_entry
    table_entry.table_id = table_id
    table_entry.is_default_entry = default_entry
    table_entry.table_read_flag.from_hw = from_hw
    for answer in interface.grpc_stub.Read(request):
        for entity in answer.entities:
            if entity.HasField("table_entry"):
                yield entity.table_entry


def should_try_default(table):
    table_type = table.get("table_type", "")
    if table_type in ("ActionProfile", "Counter", "Meter", "Register",
                      "RegisterParam", "Selector"):
        return False
    return bool(table.get("action_specs"))


def short_field_name(field_name):
    return field_name.split(".")[-1]


def first_key_text(entry, names):
    if not entry.key.fields:
        return "default"
    field = entry.key.fields[0]
    return "{}={}".format(
        names.key_name(entry.table_id, field.field_id).split(".")[-1],
        key_value_to_text(field))


def summarize_numeric_entries(entries, names):
    totals = {}
    total_entries = 0
    nonzero_entries = 0
    samples = []

    for entry in entries:
        total_entries += 1
        entry_has_value = False
        entry_values = {}
        for field in entry.data.fields:
            value = data_value_to_int(field)
            if value is None:
                continue
            field_name = names.data_name(
                entry.table_id, entry.data.action_id, field.field_id)
            field_name = short_field_name(field_name)
            totals[field_name] = totals.get(field_name, 0) + value
            if value != 0:
                entry_has_value = True
                entry_values[field_name] = entry_values.get(field_name, 0) + value
        if entry_has_value:
            nonzero_entries += 1
            if len(samples) < 8:
                samples.append("{}: {}".format(
                    first_key_text(entry, names),
                    ", ".join("{}={}".format(name, entry_values[name])
                              for name in sorted(entry_values))))

    summary = [
        "entries={}".format(total_entries),
        "nonzero_entries={}".format(nonzero_entries),
    ]
    for field_name in sorted(totals):
        if totals[field_name] != 0:
            summary.append("{}_sum={}".format(field_name, totals[field_name]))
    if samples:
        summary.append("samples=[" + "; ".join(samples) + "]")
    return "  summary: " + ", ".join(summary)


def is_tofino_stamper_v1_4_resource(table):
    table_type = table.get("table_type", "")
    table_name = table.get("name", "")
    short_name = table_name.split(".")[-1]
    return table_type in P4_RESOURCE_TABLE_TYPES and (
        table_name in TOFINO_STAMPER_V1_4_RESOURCES
        or short_name in TOFINO_STAMPER_V1_4_RESOURCES)


def format_register_read(values):
    if len(values) == 1:
        return str(values[0])
    return "[" + ", ".join(str(value) for value in values) + "]"


def dump_iterator_incr_action_state(interface, iterator_indexes):
    if iterator_indexes is None:
        iterator_indexes = [0]

    names = BfrtNames(interface)
    print("\niterator_incr_action state")

    try:
        table_id = interface.get_table_id(ITERATOR_END_REGISTER_PARAM)
        entries = list(read_table(interface, table_id, default_entry=True,
                                  from_hw=False))
        if entries:
            for entry in entries:
                print(format_entry(entry, names))
        else:
            print("  {}: <empty>".format(ITERATOR_END_REGISTER_PARAM))
    except Exception:
        print("  ! {} read failed".format(ITERATOR_END_REGISTER_PARAM))
        print("    " + traceback.format_exc().strip().replace("\n",
                                                              "\n    "))

    for index in iterator_indexes:
        try:
            values = interface.read_register(ITERATOR_REGISTER, index)
            print("  {}[{}]={}".format(
                ITERATOR_REGISTER, index, format_register_read(values)))
        except Exception:
            print("  ! {}[{}] read failed".format(ITERATOR_REGISTER, index))
            print("    " + traceback.format_exc().strip().replace("\n",
                                                                  "\n    "))


def dump_tables(interface, include_fixed):
    names = BfrtNames(interface)
    tables = list(interface.bfruntime_info.get("tables", []))
    if include_fixed:
        tables.extend(interface.non_p4_config.get("tables", []))
    tables = [table for table in tables if is_tofino_stamper_v1_4_resource(
        table)]

    for table in sorted(tables, key=lambda item: item.get("name", "")):
        table_id = table.get("id")
        if table_id is None:
            continue
        table_name = table.get("name", str(table_id))
        table_type = table.get("table_type", "unknown")
        print("\n{} ({}, id={})".format(table_name, table_type, table_id))

        count = 0
        try:
            if table_type == "RegisterParam":
                entries = list(read_table(interface, table_id,
                                          default_entry=True,
                                          from_hw=False))
                for entry in entries:
                    print(format_entry(entry, names))
                count = len(entries)
            elif table_type in SUMMARY_TABLE_TYPES:
                entries = list(read_table(interface, table_id))
                print(summarize_numeric_entries(entries, names))
                count = len(entries)
            else:
                for entry in read_table(interface, table_id):
                    print(format_entry(entry, names))
                    count += 1
            if should_try_default(table):
                for entry in read_table(interface, table_id,
                                        default_entry=True):
                    print(format_entry(entry, names))
                    count += 1
        except Exception:
            print("  ! read failed")
            print("    " + traceback.format_exc().strip().replace("\n",
                                                                  "\n    "))
            continue

        if count == 0:
            print("  <empty>")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Dump tofino_stamper_v1_4_0 BFRT resources.")
    parser.add_argument("grpc_server",
                        help="gRPC server IP or host[:port], default port 50052")
    parser.add_argument("p4_program", help="P4 program name to bind")
    parser.add_argument("--device-id", type=int, default=0,
                        help="BFRT device id, default: 0")
    parser.add_argument("--client-id", type=int, default=99,
                        help="BFRT client id, default: 99")
    parser.add_argument("--fixed", action="store_true",
                        help="also consider matching fixed/non-P4 BFRT tables")
    parser.add_argument("--iterator-index", type=int, action="append",
                        default=None,
                        help=("read pipe.SwitchEgress.iterator at this "
                              "register index/egress port, default: 0; "
                              "can be passed multiple times"))
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.WARNING,
                        format="%(levelname)s: %(message)s")
    logger = logging.getLogger("bfrt-debug")

    interface = grpc_interface.TofinoInterface(
        args.grpc_server, args.device_id, logger, client_id=args.client_id,
        is_master=False)
    try:
        if not interface.connection_established:
            print("gRPC connection to Tofino failed.", file=sys.stderr)
            return 1
        error = interface.bind_p4_name(args.p4_program)
        if error:
            print(error, file=sys.stderr)
            return 1
        dump_tables(interface, args.fixed)
        dump_iterator_incr_action_state(interface, args.iterator_index)
    finally:
        interface.teardown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
