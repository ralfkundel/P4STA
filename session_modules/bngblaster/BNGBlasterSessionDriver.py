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
import json
import os
import threading
import time
import subprocess
import sys
import traceback
import traceback
import uuid
import tempfile
from pathlib import Path

from collections import Counter, OrderedDict
from typing import Any

import P4STA_utils

# globals
from management_ui import globals

from abstract_sessionModule import AbstractSessionModule

dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir_path)

from api import BlasterApiClient, BlasterApiError, BlasterInstanceNotFound, BlasterInstanceStopped
import session_mod
import traffic_calc
from session_modules.bngblaster import field_config

# p4sta_root_dir_path = os.path.abspath(os.path.join(dir_path, "..",".."))
# wedge100b65_dir = os.path.abspath(os.path.join(p4sta_root_dir_path, 'stamper_targets', 'Wedge100B65'))
# sys.path.append(wedge100b65_dir)

# import bfrt_grpc.grpc_interface as grpc_interface

class SessionModuleImpl(AbstractSessionModule):
    def __init__(self, module_cfg, logger, ip, p4_name):
        super().__init__(module_cfg, logger, ip, p4_name)
    #    self.open_connection = None

    def get_session_value(self, session, key):
        value = session.get(key)
        if value is None:
            return None
        if isinstance(value, str) and value.strip() == "0":
            return None
        if not isinstance(value, bool) and value == 0:
            return None
        return value

    # def set_grpc_connection(self, cfg):
    #     interface = grpc_interface.TofinoInterface(cfg["ssh_ip"], 0, self.logger)
    #     interface.bind_p4_name(self.libcfg["p4_program"])
    #     self.open_connection = interface

    #     return interface

    def check_live_version(self, user_name, ip):
        result = P4STA_utils.execute_ssh(user_name, ip, "bngblaster --version")

        for line in result:
            if "Version: " in line:
                version = line.split("Version: ")[1].strip()
                return version

        return "unknown"

    def save_config_json(self, config_json_str):
        try:
            config_json = json.loads(config_json_str)
            # TODO validate config_json structure

            # save to json file
            config_path = os.path.join(dir_path, f"bngblaster_config_gui.json")
            if not os.path.isfile(config_path):
                raise FileNotFoundError("Config file not found")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_json, f, indent=4)

            self.logger.debug(f"Saved BNGBlaster config JSON to {config_path}")

            return config_path
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}")
        except Exception as exc:
            raise ValueError(f"Error saving config JSON: {exc}")
        
    def read_config_json(self):
        config_path = os.path.join(dir_path, f"bngblaster_config_gui.json")
        if not os.path.isfile(config_path):
            raise FileNotFoundError("Config file not found")
        with open(config_path, "r", encoding="utf-8") as f:
            config_json_str = f.read()
        return config_json_str

    def session_config_file_reset(self):
        default_config_path = os.path.join(dir_path, "bngblaster_config_template.json")
        if not os.path.isfile(default_config_path):
            raise FileNotFoundError("Default config file not found")

        with open(default_config_path, "r", encoding="utf-8") as f:
            config_json_str = f.read()

        self.save_config_json(config_json_str)

        return config_json_str

    def establish_sessions(self, tofino_grpc_obj, sess_cfg):
        self.logger.debug("BNGBlaster session config: " + str(sess_cfg))

        p4sta_cfg = P4STA_utils.read_current_cfg()
        tofino_grpc_obj = self._grpc_obj_check(tofino_grpc_obj)

        tofino_grpc_obj.delete_table("pipe.SwitchIngress.t_l1_forwarding_session_all_except_load")

        #first clear all is_backbone_port and is_access_port
        for dut in p4sta_cfg["dut_ports"]:
            dut["session_port_type"] = None

        # find access and backbone/network p4 ports
        bng_port_map = [] # contains (session_cp, dut) p4 port tuples

        for dut in p4sta_cfg["dut_ports"]:
            # sess_cfg["access_port"] is physical front port, e.g. "22/0"
            if dut["real_port"] == sess_cfg["access_port"]:
                dut["session_port_type"] = "access"
                bng_port_map.append( (int(p4sta_cfg["session_cp"]), int(dut["p4_port"])) )
                break # for now only one access port

        for dut in p4sta_cfg["dut_ports"]:
            if dut["real_port"] == sess_cfg["backbone_port"]:
                dut["session_port_type"] = "backbone"
                bng_port_map.append( (int(p4sta_cfg["session_cp2"]), int(dut["p4_port"])) )
                break # for now only one backbone network port
        
        # store is_backbone/access .. flag in data/config.json
        P4STA_utils.write_config(p4sta_cfg)

        self.logger.debug("bng_port_map: "  + str(bng_port_map))

        try:
            for session_cp_port, dut_port in bng_port_map:
                tofino_grpc_obj.add_to_table(
                    "pipe.SwitchIngress.t_l1_forwarding_session_all_except_load", [
                        ["ig_intr_md.ingress_port", session_cp_port],
                    ],
                    [
                        ["egress_port", dut_port]
                    ],
                    "SwitchIngress.send")
                
                tofino_grpc_obj.add_to_table(
                        "pipe.SwitchIngress.t_l1_forwarding_session_all_except_load", [
                            ["ig_intr_md.ingress_port", dut_port],
                        ],
                        [
                            ["egress_port", session_cp_port]
                        ],
                        "SwitchIngress.send")
        except Exception as e:
            self.logger.error("Error while adding to t_l1_forwarding_session_all_except_load in session module: " + str(traceback.format_exc()))

        try:
            run_id = str(uuid.uuid4())
            config_path = os.path.join(dir_path, f"bngblaster_config_gui.json")
            try:
                blaster_cfg_dict = json.loads(self.read_config_json())
            except json.JSONDecodeError:
                self.logger.error("Invalid JSON in config file")
                blaster_cfg_dict = None

            # API approach
            
            client = BlasterApiClient(p4sta_cfg["session_cp_ssh"], instance="P4STA", timeout=10, logger=self.logger)
            ret = client.create_instance(blaster_cfg_dict)
            self.logger.debug(f"BNGBlaster create_instance response: {ret}")

            sess_cnt = sess_cfg.get("session_count", 1)
            if sess_cnt is None:
                sess_cnt = 1
            ret = client.establish_sessions(session_count=int(sess_cnt), logging=True, logging_flags=["debug", "pppoe", "ip"], report=True)
            self.logger.debug(f"BNGBlaster establish_sessions response: {ret}")

            return tofino_grpc_obj, {
                    "run_id": run_id,
                    "state": "Running",
                    # "pid": 123, #process.pid,
                    # "command": cmd,
                }

        except BlasterApiError as exc:
            return tofino_grpc_obj, {"state": "Failed", "error": str(exc)}
        except ValueError as exc:
            return tofino_grpc_obj, {"error": str(traceback.format_exc())}
        except FileNotFoundError:
            return tofino_grpc_obj, {"error": "FileNotFoundError: Possibly bngblaster binary not found"}
        except Exception as exc:
            return tofino_grpc_obj, {"error": str(traceback.format_exc())}


    def teardown_sessions(self, tofino_grpc_obj, sess_cfg):
        p4sta_cfg = P4STA_utils.read_current_cfg()

        tofino_grpc_obj = self._grpc_obj_check(tofino_grpc_obj)

        client = BlasterApiClient(p4sta_cfg["session_cp_ssh"], instance="P4STA", timeout=10, logger=self.logger)
        ret = client.teardown_sessions()

        self.logger.debug(f"BNGBlaster teardown_sessions response: {ret}")

        time.sleep(2) #TODO: wait until API shows no sessions anymore instead of fixed sleep

        ret = client.delete_instance()
        self.logger.debug(f"BNGBlaster delete_instance response: {ret}")

        tofino_grpc_obj.delete_table("pipe.SwitchIngress.t_l1_forwarding_session_all_except_load")

        return ret, tofino_grpc_obj
    
    # data: dict[str, Any]) -> dict[str, Any]
    def _summarize_api_result(self, data):
        print("Summarizing API result:", data)
        sessions = data.get("sessions", [])

        summary = {
            "run_id": data.get("run_id"),
            "total_requested": len(sessions),
            "ok": 0,
            "warnings": 0,
            "errors": 0,
            "established": 0,
            "not_found": 0,
            "states": Counter(),
            "interfaces": Counter(),
            "total_tx_packets": 0,
            "total_rx_packets": 0,
            "total_tx_bytes": 0,
            "total_rx_bytes": 0,
            # "sessions": [],
        }

        for entry in sessions:
            status = entry.get("status")
            code = entry.get("code")

            if status == "ok":
                summary["ok"] += 1
            elif status == "warning":
                summary["warnings"] += 1
            else:
                summary["errors"] += 1

            if code == 404:
                summary["not_found"] += 1

            session_info = entry.get("session-info")

            if not session_info:
            #     summary["sessions"].append({
            #         "requested_id": entry.get("requested_id"),
            #         "status": status,
            #         "code": code,
            #         "message": entry.get("message"),
            #     })
                continue

            state = session_info.get("session-state")
            interface = session_info.get("interface")

            summary["states"][state] += 1
            summary["interfaces"][interface] += 1

            if state == "Established":
                summary["established"] += 1

            summary["total_tx_packets"] += session_info.get("tx-packets", 0)
            summary["total_rx_packets"] += session_info.get("rx-packets", 0)
            summary["total_tx_bytes"] += session_info.get("tx-bytes", 0)
            summary["total_rx_bytes"] += session_info.get("rx-bytes", 0)

        summary["states"] = dict(summary["states"])
        summary["interfaces"] = dict(summary["interfaces"])

        return summary
    
    def get_num_established_sessions(self):
        p4sta_cfg = P4STA_utils.read_current_cfg()

        client = BlasterApiClient(p4sta_cfg["session_cp_ssh"], instance="P4STA", timeout=10, logger=self.logger)
        code, ret = client.get_sessions_summary()
        ret_dict = json.loads(ret)
        count = 0
        for session in ret_dict.get("session-summary", []):
            if session.get("session-state") == "Established":
                count = count + 1

        return count

    
    def get_session_info(self, session_ids=None):
        p4sta_cfg = P4STA_utils.read_current_cfg()
        client = BlasterApiClient(p4sta_cfg["session_cp_ssh"], instance="P4STA", timeout=10, logger=self.logger)

        try:
            return self._get_session_info(client, session_ids)
        except BlasterInstanceNotFound:
            return {"state": "Idle", "sessions": [], "summary": {}}
        except BlasterInstanceStopped as exc:
            # Normal when refreshing after sessions have been closed. Keep the
            # diagnostics for the GUI if it was expecting establishment instead.
            return {"state": "Stopped", "sessions": [], "summary": {},
                    "diagnostics": str(exc)}
        except BlasterApiError as exc:
            return {"error": str(exc), "sessions": [], "summary": {}}

    def _get_session_info(self, client, session_ids):
        info = []
        if session_ids is not None and type(session_ids) == list and len(session_ids) > 0:
            for id in session_ids:
                code, ret = client.get_session_info(session_id=id)
                print(type(ret))
                self.logger.debug(f"BNGBlaster get_session_info for session {id} response: {ret}")
                try:
                    ret_dict = json.loads(ret)
                    ret_dict["requested_id"] = id
                    info.append(ret_dict)
                except json.JSONDecodeError:
                    self.logger.error(f"Invalid JSON in get_session_info response for session {id}")
        else:
            # get summary from API with new bngblaster version 0.9.35 including pppoe session ID
            code, ret = client.get_sessions_summary()
            self.logger.debug(f"BNGBlaster get_sessions_summary response: {ret}")
            # found_sess_ids = []
            try:
                ret_dict = json.loads(ret)
                info.append(ret_dict.get("session-summary", []))
                # for session in ret_dict.get("session-summary", []):
                #     found_sess_ids.append(session.get("session-id"))
            except json.JSONDecodeError:
                self.logger.error("Invalid JSON in get_sessions_summary response")

            # # Next step: Query each session ID to get detailed info
            # for id in found_sess_ids:
            #     code, ret = client.get_session_info(session_id=id)
            #     print(type(ret))
            #     self.logger.debug(f"BNGBlaster get_session_info for session {id} response: {ret}")
            #     try:
            #         ret_dict = json.loads(ret)
            #         ret_dict["requested_id"] = id
            #         info.append(ret_dict)
            #     except json.JSONDecodeError:
            #         self.logger.error(f"Invalid JSON in get_session_info response for session {id}")
        # save to json file
        json_path = os.path.join(dir_path, f"bngblaster_last_session_info.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=4)

        self.logger.debug(f"Saved BNGBlaster last session state JSON to {json_path}")

        summary = {} # TODO remove? #self._summarize_api_result({"sessions": info})

        # info["summary"] = summary
        ret_dict = {
            "sessions": info,
            "summary": summary}
        return ret_dict
    
    def get_session_data_unified(self):
        p4sta_cfg = P4STA_utils.read_current_cfg()
        client = BlasterApiClient(p4sta_cfg["session_cp_ssh"], instance="P4STA", timeout=10, logger=self.logger)

        code, ret = client.get_sessions_summary()

        try:
            ret_dict = json.loads(ret)
            unified_established_session_data = []
            for session in ret_dict.get("session-summary", []):
                # unify state representation
                state = session.get("session-state")

                data_obj = {}
                if state == "Established":
                    data_obj["state"] = "established"
                else:
                    data_obj["state"] = state

                data_obj["ipv4_address"] = self.get_session_value(session, "ipv4-address")
                data_obj["flow_id"] = self.get_session_value(session, "session-id")
                data_obj["session_id"] = self.get_session_value(session, "pppoe-session-id")
                data_obj["sub_mac"] = self.get_session_value(session, "mac")
                data_obj["server_mac"] = self.get_session_value(session, "server-mac")
                data_obj["outer_vlan"] = self.get_session_value(session, "outer-vlan")
                data_obj["inner_vlan"] = self.get_session_value(session, "inner-vlan")
                data_obj["tx_packets"] = session.get("tx-packets", 0)
                data_obj["rx_packets"] = session.get("rx-packets", 0)
                data_obj["tx_bytes"] = session.get("tx-bytes", 0)
                data_obj["rx_bytes"] = session.get("rx-bytes", 0)

                unified_established_session_data.append(data_obj)

            return unified_established_session_data
                
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON in get_sessions_summary response")
            return {}

    def get_compile_dyn_cfg(self):
        return field_config.get_config(self.module_cfg).get("selected_values", [])

    def get_session_field_options(self):
        return field_config.get_options(self.module_cfg)

    def get_compile_direction(self, dyn_cfg=None):
        if dyn_cfg is None:
            dyn_cfg = self.get_compile_dyn_cfg()
        for field in dyn_cfg:
            if len(field) >= 2 and field[0] == "pppoe" and field[1] == "sessionID":
                return "upstream"
        return "downstream"

    def get_session_data_key_for_field(self, field, direction):
        field_name = field[0] + "." + field[1]
        upstream_mapping = {
            "ethernet.srcAddr": "sub_mac",
            "ethernet.dstAddr": "server_mac",
            "vlan.vid": "outer_vlan",
            "vlan_qinq.vid": "inner_vlan",
            "pppoe.sessionID": "session_id",
            "ipv4.srcAddr": "ipv4_address",
        }
        downstream_mapping = {
            "ipv4.dstAddr": "ipv4_address",
        }
        if direction == "upstream":
            return upstream_mapping.get(field_name)
        return downstream_mapping.get(field_name)

    def get_compile_field_rows(self, session_data_unified):
        dyn_cfg = self.get_compile_dyn_cfg()
        direction = self.get_compile_direction(dyn_cfg)
        if not isinstance(session_data_unified, list):
            session_data_unified = []

        rows = []
        for index, field in enumerate(dyn_cfg, 1):
            session_key = None
            first_value = None
            last_value = None
            if len(field) >= 2:
                session_key = self.get_session_data_key_for_field(
                    field, direction)
            if session_key is not None:
                values = [
                    session.get(session_key)
                    for session in session_data_unified
                    if isinstance(session, dict) and
                    session.get(session_key) is not None
                ]
                if len(values) > 0:
                    first_value = values[0]
                    last_value = values[-1]

            rows.append({
                "flag": "P4_HEADER" + str(index) + " / P4_FIELD" + str(index) +
                        " / P4_F_TYPE" + str(index),
                "field": field[0] + "." + field[1] + " " + field[2],
                "first_value": first_value,
                "last_value": last_value,
                "has_sample": first_value is not None,
                "session_key": session_key,
                "direction": direction,
            })
        return rows





    def set_traffic_profile(self, tofino_grpc_obj, traffic_config):
        dyn_cfg = self.get_compile_dyn_cfg()
        if "session_fields" in traffic_config:
            dyn_cfg = field_config.select_fields(
                self.module_cfg, traffic_config["session_fields"])
        p4sta_cfg = P4STA_utils.read_current_cfg()
        tofino_grpc_obj = self._grpc_obj_check(tofino_grpc_obj)
        session_info_dict = self.get_session_info()
        try:
            # tofino_grpc_obj.delete_table("pipe.SwitchEgress.iterator_end") => not required as modify changes var
            tofino_grpc_obj.delete_table("pipe.SwitchEgress.t_check_local_index_increment")
            
            #for i in range(1, 9):
            #    tofino_grpc_obj.delete_table("pipe.SwitchEgress.t_field_mod" + str(i))
            tofino_grpc_obj.delete_table("pipe.SwitchEgress.t_session_mapping")

            if "backbone_dst_ip" in traffic_config and "backbone_mac" in traffic_config:
                if "session_config" not in p4sta_cfg:
                    p4sta_cfg["session_config"] = {}
                p4sta_cfg["session_config"]["session_backbone_dst_ip"] = traffic_config["backbone_dst_ip"]
                p4sta_cfg["session_config"]["session_server_backbone_mac"] = traffic_config["backbone_mac"]
                p4sta_cfg["session_config"]["traffic_distribution"] = traffic_config.get(
                    "traffic_distribution", {})
                # update current data/config.json
                P4STA_utils.write_config(p4sta_cfg)
            else:
                raise Exception("set_traffic_profile failed: missing fields. traffic_config: " + str(traffic_config))

            
            server_mac_backbone = p4sta_cfg["session_config"]["session_server_backbone_mac"]
            # in upstream direction its the dst IP and in downstream the src IP => routing to this IP must be configured in BNG/UPF!
            backbone_ip = p4sta_cfg["session_config"]["session_backbone_dst_ip"]

            direction = self.get_compile_direction(dyn_cfg)
            flow_direction_key = "us" if direction == "upstream" else "ds"
            compiled_field_names = {
                field[0] + "." + field[1] for field in dyn_cfg if len(field) >= 2
            }

            if flow_direction_key == "ds":
                for dut in p4sta_cfg["dut_ports"]:
                    if dut.get("session_port_type") == "backbone":
                        egress_port = dut["p4_port"]
                        self.logger.debug("\n##################\nFlow Type = DOWNSTREAM\n  egress_port = " + str(egress_port) + "\n################## ")
                        break
            elif flow_direction_key == "us":
                for dut in p4sta_cfg["dut_ports"]:
                    if dut.get("session_port_type") == "access":
                        egress_port = dut["p4_port"]
                        self.logger.debug("\n##################\nFlow Type = UPSTREAM\n  egress_port = " + str(egress_port) + "\################## ")
                        break
            if egress_port is None:
                raise Exception("set_traffic_profile failed: no backbone DUT port configured.")

            tofino_grpc_obj.add_to_table(
                        "pipe.SwitchEgress.t_check_local_index_increment", [
                            ["eg_intr_md.egress_port", egress_port],
                        ],
                        [
                            # no parameter for action call required
                        ],
                        # for each table hit t_check_local_index_increment() action increment_local_index increments local counter
                        # this index (meta.logical_index) is mapped to session fields in the packet such sa session IDs, MAC, IP addresses, ..
                        # each field table t_changeField1 has entries mapping to specific indexes, e.g. with two sessions each second id mapped to flow A
                        "increment_local_index")
            
            # dyn_cfg = self.get_compile_dyn_cfg()
            # direction = self.get_compile_direction(dyn_cfg)
            # flow_direction_key = "us" if direction == "upstream" else "ds"
            # compiled_field_names = {
            #     field[0] + "." + field[1] for field in dyn_cfg if len(field) >= 2
            # }

            
            if "sessions" in session_info_dict:
                sess_flows = []
                logical_flows = []
                num_established_flows = 0
                for sess_data in session_info_dict["sessions"][0]:
                    session_id = self.get_session_value(sess_data, "session-id")
                    if sess_data.get("session-state") == "Established" and \
                            session_id is not None:
                        upstream_values = {
                            "ethernet.srcAddr": self.get_session_value(
                                sess_data, "mac"),
                            "ethernet.dstAddr": self.get_session_value(
                                sess_data, "server-mac"),
                            "vlan.vid": self.get_session_value(
                                sess_data, "outer-vlan"),
                            "vlan_qinq.vid": self.get_session_value(
                                sess_data, "inner-vlan"),
                            "pppoe.sessionID": self.get_session_value(
                                sess_data, "pppoe-session-id"),
                            "ipv4.srcAddr": self.get_session_value(
                                sess_data, "ipv4-address"),
                            "ipv4.dstAddr": backbone_ip
                        }

                        downstream_values = {
                            "ethernet.srcAddr": p4sta_cfg["session_cp2_mac"], # use MAC also used by blaster ARP response
                            "ethernet.dstAddr": server_mac_backbone,
                            "vlan.vid": None, # TODO: make configurable
                            "vlan_qinq.vid": None,
                            "pppoe.sessionID": None,
                            "ipv4.srcAddr": backbone_ip,
                            "ipv4.dstAddr": self.get_session_value(
                                sess_data, "ipv4-address")
                        }

                        us = OrderedDict()
                        ds = OrderedDict()
                        for key in upstream_values:
                            if key in compiled_field_names:
                                us[key] = upstream_values[key]
                                ds[key] = downstream_values[key]
                            else:
                                us[key] = None
                                ds[key] = None

                        sess_flows.append({"us": us, "ds": ds})
                        logical_flows.append(str(session_id))
                        num_established_flows += 1

                    else:
                        self.logger.debug(
                            "Session " + str(session_id) +
                            " is not established or misses a valid session-id "
                            "and cannot be configured for load!")


                traffic_distribution = traffic_config.get(
                    "traffic_distribution", {})
                set_percentage = {}
                gui_percentages = traffic_distribution.get(
                    "flow_percentages", {})
                for indx, logical_flow in enumerate(logical_flows):
                    for key in (
                            logical_flow,
                            str(logical_flow),
                            "index:" + str(indx),
                            str(indx)):
                        if key in gui_percentages:
                            percentage = str(gui_percentages[key]).strip()
                            if percentage != "":
                                set_percentage[logical_flow] = percentage
                            break

                session_flow_dist = traffic_calc.calculate_packet_distribution(logical_flows, set_percentage)
                self.logger.info("Session flow distribution: " + str(session_flow_dist))
                # important: session_flow_dist contains packet counts per flow, not session ids directly
                with open(os.path.join(dir_path, "debug_session_flow_dist.json"), "w") as f:
                    json.dump(session_flow_dist, f, indent=4)
                iterator_end = sum(session_flow_dist)

                tofino_grpc_obj.add_to_table(table_name="pipe.SwitchEgress.iterator_end", datas=[["value", iterator_end - 1]], default_entry=True, mod=True)
                

                sess_flows_dist_mapped = []
                if num_established_flows == len(session_flow_dist):
                    burst_flow_keys = {
                        str(flow)
                        for flow in traffic_distribution.get("burst_flows", [])
                    }
                    burst_flow_indexes = set()
                    for indx, logical_flow in enumerate(logical_flows):
                        if logical_flow in burst_flow_keys or \
                                str(logical_flow) in burst_flow_keys or \
                                ("index:" + str(indx)) in burst_flow_keys or \
                                str(indx) in burst_flow_keys:
                            burst_flow_indexes.add(indx)

                    distribution_algorithm = traffic_distribution.get(
                        "algorithm", "interleaved")
                    if distribution_algorithm == "burst":
                        burst_flow_indexes = set(range(len(sess_flows)))

                    if burst_flow_indexes:
                        for indx in sorted(burst_flow_indexes):
                            if session_flow_dist[indx] is not None:
                                sess_flows_dist_mapped.extend(
                                    [sess_flows[indx]] * session_flow_dist[indx])

                    remaining_flow_indexes = [
                        indx
                        for indx in range(len(sess_flows))
                        if indx not in burst_flow_indexes
                    ]
                    if remaining_flow_indexes:
                        remaining_weights = [
                            session_flow_dist[indx]
                            for indx in remaining_flow_indexes
                        ]
                        for remaining_indx in traffic_calc.smooth_weighted_distribution(
                                remaining_weights):
                            sess_flows_dist_mapped.append(
                                sess_flows[remaining_flow_indexes[remaining_indx]])
                else:
                    print(sess_flows)
                    print(session_flow_dist)
                    raise Exception("Number of established flows does not match configured traffic profile. num_established_flows=" + str(num_established_flows) + " len(session_flow_dist)="+str(len(session_flow_dist)))

                # Check against configured iterator_end
                if len(sess_flows_dist_mapped) != iterator_end:
                    self.logger.error("Mapped sess_flows_mapped " + str(len(sess_flows_dist_mapped)) + " vs iterator_end " + str(iterator_end))
                    return False

                # debugging
                with open(os.path.join(dir_path, "debug_session_flow_dist_mapped.json"), "w") as f:
                    json.dump(sess_flows_dist_mapped, f, indent=4)
                
                logical_index = -1
                for flow in sess_flows_dist_mapped:
                    cnt = 0
                    logical_index += 1
                    print("FLOW = ")
                    print(str(flow))
                    # {'us': OrderedDict([('ethernet.srcAddr', '02:00:00:00:00:08'), ('ethernet.dstAddr', '5c:07:58:e0:7a:55'), ('vlan.vid', None), ('vlan_qinq.vid', None), ('pppoe.sessionID', None), ('ipv4.srcAddr', '10.1.0.8'), ('ipv4.dstAddr', '10.10.10.42')]), 'ds': OrderedDict([('ethernet.srcAddr', None), ('ethernet.dstAddr', '5c:07:58:e0:7a:5d'), ('vlan.vid', None), ('vlan_qinq.vid', None), ('pppoe.sessionID', None), ('ipv4.srcAddr', '10.10.10.42'), ('ipv4.dstAddr', '10.1.0.8')])}
                    print("cnt = " + str(cnt) + " iterationIndeX = " + str(logical_index))
                    
                    # NEW approach for tofino 1 and 2

                    try:
                        generated_set_values = session_mod.get_action_params(flow[flow_direction_key])
                        # matching an action name defined in session_mod_actions.p4 to map every possible case
                        # => reduce used stages for Tofino 1 compatibility
                        generated_action_name = session_mod.get_action_name(flow[flow_direction_key])

                        self.logger.debug("generated_set_values: " + str(generated_set_values) + "\ngenerated_action_name: " + generated_action_name)

                        tofino_grpc_obj.add_to_table(
                            "pipe.SwitchEgress.t_session_mapping", [
                                ["meta.logical_index", logical_index],
                                ["eg_intr_md.egress_port", egress_port]
                            ],
                            generated_set_values,
                            "SwitchEgress." + generated_action_name
                        )
                    except Exception as e:
                        self.logger.error("Error while adding to t_session_mapping in session module: " + str(traceback.format_exc()))
                        return False
                        
            if "session_fields" in traffic_config:
                field_config.save_selected_fields(self.module_cfg, dyn_cfg, dir_path)
            return True

        except Exception as e:
            self.logger.error(traceback.format_exc())
            return False


    def get_server_install_script(self, user_name, ip):
        answer = P4STA_utils.execute_ssh(user_name, ip, "mkdir -p /home/" + user_name + "/p4sta/sessionModules/BNGBlaster;")
        lst = []
        lst.append('echo "==================================================="')
        lst.append('echo "Installing BNGBlaster on server' + ip + '"')
        lst.append('echo "==================================================="')

        lst.append('ssh ' + user_name + '@' + ip + ' "mkdir -p /home/' + user_name + '/p4sta/sessionModules/BNGBlaster/"')
        lst.append('scp ' + dir_path + '/scripts/install.sh ' + user_name + '@' + ip + ':/home/' + user_name + '/p4sta/sessionModules/BNGBlaster/')

        lst.append('echo "Running BNGBlaster install script on server ' + ip + '"')
        lst.append('ssh -tt ' + user_name + '@' + ip + ' "cd /home/' + user_name + '/p4sta/sessionModules/BNGBlaster; chmod +x install.sh; ./install.sh"')

        return lst
