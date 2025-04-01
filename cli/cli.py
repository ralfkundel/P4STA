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

from cmd import Cmd
import json
from multiprocessing.connection import Listener, Client
from tabulate import tabulate
import os
import rpyc
import sys
import time
import traceback

sys.path.append(os.path.dirname(os.path.realpath(__file__)).split("cli")[0])
from core import P4STA_utils
from analytics import analytics


def main():
    global selected_run_id
    global core_conn
    global project_path
    core_conn = rpyc.connect('localhost', 6789)
    project_path = core_conn.root.get_project_path()
    P4STA_utils.set_project_path(project_path)
    selected_run_id = core_conn.root.getLatestMeasurementId()


try:
    main()
except ConnectionRefusedError:
    print("ERROR: CORE NOT REACHABLE")
    print("Please ensure that the core is running! Use ./run.sh to start it.")
    sys.exit(0)


class PastaMenu(Cmd):
    prompt = "#P4STA: "

    def __init__(self):
        super().__init__()
        time.sleep(0.5)

        print("\n\n  *********************************")
        print("  *** Welcome to the P4STA CLI! ***")
        print("  *********************************\n")
        print("'configure' => Opens the settings to configure your testbed. "
              "This includes settings for all involved devices.")
        print("'deploy' => Opens the environment to deploy the current "
              "configuration to the selected P4-target.")
        print("'run' => Opens the run section where you can execute the heavy "
              "load performance test.")
        print("'results' => Opens the results section where the newest and "
              "older results can be evaluated.\n")

    def do_exit(self, inp):
        """Exits the P4STA CLI"""
        sys.exit(0)

    def do_configure(self, args):
        """Opens the settings to configure your testbed.
        This includes settings for all involved devices."""
        PastaConfigure().cmdloop()

    def do_deploy(self, args):
        """Opens the environment to deploy the current
        configuration to the selected P4-target."""
        DeployPasta().cmdloop()

    def do_run(self, args):
        """Opens the run section where you can execute the
        heavy load performance test."""
        RunPasta().cmdloop()

    def do_results(self, args):
        """Opens the results section where the newest and
        older results can be evaluated."""
        DisplayResultsPasta().cmdloop()


class PastaConfigure(Cmd):
    prompt = "#P4STA_configure: "

    def __init__(self):
        super().__init__()
        self.cfg = P4STA_utils.read_current_cfg()
        self.target_cfg = core_conn.root.get_target_cfg()
        self.table_general = []
        self.table_loadgen_groups = []
        self.table_dut = []
        self.table_external_host = []
        self.table_stamper = []
        self.do_show("")

    def do_exit(self, inp):
        """Exits the P4STA CLI"""
        sys.exit(0)

    # returns back to original cmd loop (PastaPrompt class)
    def do_back(self, args):
        """Return back to main P4STA CLI"""
        return True

    def strike(self, text, use_port="checked"):
        striked = ''
        if type(text) == str:
            for c in text:
                striked = striked + c + '\u0336'

        elif type(text) == list:
            li = []
            for elem in text:
                striked = ''
                for c in elem:
                    striked = striked + c + '\u0336'
                li.append(striked)
            striked = li

        if use_port == "unchecked":
            return striked
        else:
            return text

    def do_show(self, inp):
        """Displays an overwiew of the current total configuration"""
        self.cfg = P4STA_utils.read_current_cfg()
        self.target_cfg = core_conn.root.get_target_cfg()

        self.table_loadgen_groups = []
        for loadgen_grp in self.cfg["loadgen_groups"]:
            self.table_loadgen_groups.append([["Loadgen Group " + str(
                loadgen_grp["group"]), "SSH IP", "SSH User", "Load Iface",
                                               "Loadgen MAC", "Loadgen IP",
                                               "Port", "P4 Port"]])

        self.table_dut = [
            ["ID", "Use Port", "Port", "P4 Port", "Duplicate Flow (out)"]]
        self.table_external_host = [
            ["SSH IP", "SSH User", "Load Iface", "Port", "P4 Port"]]
        self.table_stamper = [["SSH IP", "SSH User"]]

        # read Stamper target specific config
        for t_inp in self.target_cfg["inputs"]["input_table"]:
            for table in self.table_loadgen_groups:
                table[0].append(t_inp["title"])
            self.table_dut[0].append(t_inp["title"])
            self.table_external_host[0].append(t_inp["title"])

        print("Current configuration (to change enter 'change_general_cfg':")
        self.table_general = [
            ["Target", "Mode", "Dupl. Scale", "Packet Gen", "Ext Host Type"]]
        self.table_general.append([self.cfg["selected_target"],
                                   "Layer " + self.cfg["forwarding_mode"],
                                   self.cfg["multicast"],
                                   self.cfg["selected_loadgen"],
                                   self.cfg["selected_extHost"]])
        print(tabulate(self.table_general, tablefmt="fancy_grid"))

        print("LOADGENERATORS:")
        for loadgen_grp in self.cfg["loadgen_groups"]:
            for host in loadgen_grp["loadgens"]:
                add = []
                for t_inp in self.target_cfg["inputs"]["input_table"]:
                    try:
                        add.append(host[t_inp["target_key"]])
                    except Exception:
                        add.append("")
                self.table_loadgen_groups[loadgen_grp["group"] - 1].append(
                    ["1." + str(host["id"]), host["ssh_ip"], host["ssh_user"],
                     host["loadgen_iface"], host["loadgen_mac"],
                     host["loadgen_ip"], host["real_port"],
                     host["p4_port"]] + add)

        for table in self.table_loadgen_groups:
            print(tabulate(table, tablefmt="fancy_grid"))

        print("DUT:")
        for dut in self.cfg["dut_ports"]:
            add = []
            for t_inp in self.target_cfg["inputs"]["input_table"]:
                try:
                    add.append(dut[t_inp["target_key"]])
                except Exception:
                    add.append("")
            self.table_dut.append([dut["id"], dut["use_port"],
                                   self.strike(dut["real_port"],
                                               dut["use_port"]),
                                   self.strike(dut["p4_port"],
                                               dut["use_port"]),
                                   self.strike(dut["stamp_outgoing"],
                                               dut["use_port"])] + self.strike(
                add, dut["use_port"]))
        print(tabulate(self.table_dut, tablefmt="fancy_grid"))

        print("EXTERNAL HOST:")
        add_ext_host = []
        for t_inp in self.target_cfg["inputs"]["input_table"]:
            try:
                add_ext_host.append(
                    self.cfg["ext_host_" + t_inp["target_key"]])
            except Exception:
                add_ext_host.append("")
        self.table_external_host.append(
            [self.cfg["ext_host_ssh"], self.cfg["ext_host_user"],
             self.cfg["ext_host_if"], self.cfg["ext_host_real"],
             self.cfg["ext_host"]] + add_ext_host)
        print(tabulate(self.table_external_host, tablefmt="fancy_grid"))

        print("STAMPER:")
        self.table_stamper.append(
            [self.cfg["stamper_ssh"], self.cfg["stamper_user"]])
        print(tabulate(self.table_stamper, tablefmt="fancy_grid"))

    def do_change_general_cfg(self, args):
        """Opens the environment to change the config (e.g. Stamper-target,
         duplication downscale factor, packet generator and forwarding mode."""
        ChangeGeneralConfig().cmdloop()
        self.target_cfg = core_conn.root.get_target_cfg()

    def get_target_specific_description(self):
        self.target_cfg = core_conn.root.get_target_cfg()
        answer = ""
        for t_inp in self.target_cfg["inputs"]["input_table"]:
            try:
                answer = answer + " " + t_inp["title"] + "(" + t_inp[
                    "description"] + ")"
            except Exception:
                pass
        return answer

    def do_add_loadgen_group(self, args):
        """Add a loadgenerator group: 'add_loadgen_group'"""
        group_id = len(self.cfg["loadgen_groups"]) + 1
        self.cfg["loadgen_groups"].append(
            {"group": group_id, "loadgens": [], "use_group": "checked"})
        self.cfg["dut_ports"].append(
            {"id": group_id, "p4_port": "", "real_port": "",
             "stamp_outgoing": "checked", "use_port": "checked"})
        P4STA_utils.write_config(self.cfg)

    def do_delete_loadgen_group(self, args):
        """Delete a loadgenerator group: 'delete_loadgen_group group_id'"""
        arg_list = args.split()
        if arg_list[0].isdigit() and 0 < int(arg_list[0]) <= len(
                self.cfg["loadgen_groups"]):
            group_id = int(arg_list[0])
            self.cfg["loadgen_groups"].pop(group_id - 1)
            self.cfg["dut_ports"].pop(group_id - 1)
            P4STA_utils.write_config(self.cfg)
        else:
            print("Please enter a valid group ID")

    # args = group, ssh_ip, ssh_user, load_iface, load_mac, load_ip, port, link
    def do_add_loadgen(self, args):
        """Add a loadgenerator: 'add_loadgen group ssh_ip ssh_username
        load_interface mac_adress load_ip custom_target_opt'"""

        def error():
            print("\nPlease use the following format:")
            print("add_loadgen group ssh_ip ssh_user load_iface load_mac "
                  "load_ip port link" + self.get_target_specific_description())
            print("e.g.: add_loadgen 1 172.1.1.10 mmustermann eth1 "
                  "11:22:33:44:55:66 10.10.10.1 1/1" +
                  self.get_target_specific_description())

        arg_list = args.split()
        if len(arg_list) >= 7:
            try:
                try:  # test if group is found in cfg
                    # group id's starting at 1 but index starting at 0
                    test = self.cfg["loadgen_groups"][int(
                        arg_list[0]) - 1]
                except IndexError:
                    print("\nLoadgen Group " + str(
                        arg_list[0]) + " not found in cfg.")
                    raise Exception
                all_ids = []  # store all ids to select the next as new id
                for host in self.cfg["loadgen_groups"][int(
                        arg_list[0]) - 1]["loadgens"]:
                    all_ids.append(int(host["id"]))
                new_p4_port = -1

                dict_add = {
                    "ssh_ip": arg_list[1],
                    "ssh_user": arg_list[2],
                    "loadgen_iface": arg_list[3],
                    "loadgen_mac": arg_list[4],
                    "loadgen_ip": arg_list[5],
                    "real_port": arg_list[6],
                    "p4_port": new_p4_port,
                    "id": max(all_ids) + 1
                }
                ind = 7
                for t_inp in self.target_cfg["inputs"]["input_table"]:
                    try:
                        dict_add[t_inp["target_key"]] = arg_list[ind]
                    except IndexError:
                        dict_add[t_inp["target_key"]] = ""
                    except Exception:
                        pass
                    ind = ind + 1

                self.cfg["loadgen_groups"][int(arg_list[0]) - 1][
                    "loadgens"].append(dict_add)

                P4STA_utils.write_config(self.cfg)
                self.do_show("")
            except Exception as e:
                print(e)
                error()
        else:
            error()

    def do_delete_loadgen(self, args):
        """Delete a loadgenerator:
        'delete_loadgen loadgen_group receiver/sender_id'"""

        def error():
            print("\nPlease use the following format:")
            print("delete_loadgen group_id host_id")
            print("e.g. to delete host 1 of group 2: delete_loadgen 2 1\n")

        arg_list = args.split()
        print(arg_list)
        if len(arg_list) == 2:
            try:
                deleted = False
                for loadgen_grp in self.cfg["loadgen_groups"]:
                    if str(loadgen_grp["group"]) == arg_list[0]:
                        for host in loadgen_grp["loadgens"]:
                            if str(host["id"]) == arg_list[1]:
                                loadgen_grp["loadgens"].remove(host)
                                deleted = True
                                print("deleted host " + str(
                                    host["id"]) + " from group " + str(
                                    loadgen_grp["group"]))
                if deleted:
                    P4STA_utils.write_config(self.cfg)
                else:
                    print("Group " + arg_list[0] + " | Loadgen " + arg_list[
                        1] + " not found - nothing changed.")
            except Exception as e:
                print(e)
                error()
        else:
            error()

    def do_change_dut(self, args):
        """Changes Device under Test config: 'change_dut dut_id
        use_port(checked/unchecked) phy_port stamp_outgoing(checked/unchecked)
        target_specific'"""
        arg_list = args.split()
        if len(arg_list) >= 4:
            if 0 < int(arg_list[0]) <= len(self.cfg["dut_ports"]):
                sel_dut = self.cfg["dut_ports"][int(arg_list[0]) - 1]
                if arg_list[1] == "checked" or arg_list[1] == "unchecked":
                    sel_dut["use_port"] = arg_list[1]
                    sel_dut["real_port"] = arg_list[2]
                    sel_dut["p4_port"] = -1
                    if arg_list[3] == "checked" or arg_list[3] == "unchecked":
                        sel_dut["stamp_outgoing"] = arg_list[3]
                        P4STA_utils.write_config(self.cfg)
                        self.do_show("")
                    else:
                        print("Please enter 'checked' or 'unchecked' "
                              "for stamp_outgoing")
                        print("eg: change_dut 1 checked 1/2 1/1,1/3 unchecked")
                else:
                    print("Please enter 'checked' or 'unchecked' for use_port")
                    print("eg: change_dut 1 checked 1/2 1/1,1/3 unchecked")
            else:
                print("Please enter a valid DUT ID")
                print("eg: change_dut 1 checked 1/2 1/1,1/3 unchecked")
        else:
            print("Changes Device under Test config: 'change_dut dut_id "
                  "use_port(checked/unchecked) phy_port flow_to_phy_port"
                  "(separate by ,) stamp_outgoing(checked/unchecked) "
                  "target_specific'")
            print(
                "Please enter a valid DUT configuartion like: "
                "change_dut 1 checked 1/2 1/1,1/3 unchecked")

    def do_change_external_host(self, args):
        """Changes external host config: 'change_external_host ext_host_type
        ssh_ip ssh_user load_iface port target_specific'"""
        arg_list = args.split()
        try:
            if len(arg_list) >= 5:
                all_available = core_conn.root.get_all_extHost()
                if arg_list[0] in all_available:
                    self.cfg["selected_extHost"] = arg_list[0]
                else:
                    print("ERROR")
                    print("External host type not found in available "
                          "external hosts: " + ", ".join(all_available))
                    raise Exception

                self.cfg["ext_host_ssh"] = arg_list[1]
                self.cfg["ext_host_user"] = arg_list[2]
                self.cfg["ext_host_if"] = arg_list[3]
                self.cfg["ext_host_real"] = arg_list[4]
                self.cfg["ext_host"] = -1

                i = 5
                for t_inp in self.target_cfg["inputs"]["input_table"]:
                    try:
                        self.cfg["ext_host_" + t_inp["target_key"]] = arg_list[
                            i]
                    except Exception as e:
                        print("Error:" + str(e))
                    i = i + 1

                P4STA_utils.write_config(self.cfg)
                self.do_show("")
            else:
                raise Exception
        except Exception:
            print("Please enter a valid external host configuration: "
                  "ext_host_type ssh_ip username interface " +
                  self.get_target_specific_description())
            print(
                "\"e.g.: change_external_host PythonExtHost 172.1.1.99 mmuster"
                "mann eth0 5/0 " + self.get_target_specific_description())

    def do_change_stamper(self, args):
        """Changes p4-stamper config: 'change_stamper ssh_ip ssh_user'"""
        arg_list = args.split()
        try:
            if len(arg_list) == 2:
                self.cfg["stamper_ssh"] = arg_list[0]
                self.cfg["stamper_user"] = arg_list[1]

                P4STA_utils.write_config(self.cfg)
                self.do_show("")
            else:
                raise Exception
        except Exception:
            print("Please enter a valid stamper configuration "
                  "[ssh_ip, username]: ")
            print("\"e.g.: change_stamper 172.1.1.100 mmustermann")


# sub cmd for changing general config (p4 prog, target, loadgen software etc)
class ChangeGeneralConfig(Cmd):
    prompt = "#P4STA_general_config: "

    def __init__(self):
        super().__init__()
        self.cfg = P4STA_utils.read_current_cfg()
        self.target_cfg = core_conn.root.get_target_cfg()
        self.all_cfgs = core_conn.root.get_available_cfg_files()

        print("Available targets: " + ", ".join(
            core_conn.root.get_all_targets()))
        print("Available forwarding modes (Layer): "
              "1 (1 to 1 loadgen only), 2, 3")
        print("Available packet generators: " + ",".join(
            P4STA_utils.flt(core_conn.root.get_all_loadGenerators())))

        self.show()

    def show(self):
        """Shows the current general config
        (like target, forwarding mode, packet generator)"""
        print("Current configuration:")
        table_general = [["Target", "Mode", "Dupl. Scale", "Packet Gen"],
                         [self.cfg["selected_target"],
                          "Layer " + self.cfg["forwarding_mode"],
                          self.cfg["multicast"], self.cfg["selected_loadgen"]]]
        table_specific = [[], []]
        for tbl_inp in self.target_cfg["inputs"]["input_individual"]:
            table_specific[0].append(tbl_inp["title"])
            table_specific[1].append(self.cfg[tbl_inp["target_key"]])

        print(tabulate(table_general, tablefmt="fancy_grid"))
        print("Stamp TCP packets: " + (
            "True" if (self.cfg["stamp_tcp"] == "checked") else "False"))
        print("Stamp UDP packets: " + (
            "True" if (self.cfg["stamp_udp"] == "checked") else "False"))
        print("")
        print("Stamper target specific configuration:")
        print(tabulate(table_specific, tablefmt="fancy_grid"))
        print("\nEnter \"back\" to return to main menu.\n")

    def update_and_show(self):
        P4STA_utils.write_config(self.cfg)
        print("Configuration changed:")
        self.show()

    # returns back to original cmd loop (PastaPrompt class)
    def do_back(self, args):
        """Return back to main P4STA CLI"""
        return True

    def do_exit(self, args):
        """Exits CLI completely"""
        sys.exit(0)

    def get_stamper_target_specific_description(self):
        self.target_cfg = core_conn.root.get_target_cfg()
        answer = ""
        for t_inp in self.target_cfg["inputs"]["input_individual"]:
            try:
                answer = answer + " " + t_inp["title"] + " (" + t_inp[
                    "description"] + ")\n"
            except Exception as e:
                pass
        return answer

    def do_change_specific(self, args):
        """Changes Stamper target specific settings:
        'change_specific arg1 arg2 ..'"""
        arg_list = args.split()
        if len(arg_list) == len(self.target_cfg["inputs"]["input_individual"]):
            c = 0
            for tbl_inp in self.target_cfg["inputs"]["input_individual"]:
                self.cfg[tbl_inp["target_key"]] = arg_list[c]
                c = c + 1
            self.update_and_show()
        else:
            print(
                "Please enter a valid setting like: change_specific SETTING "
                "VALUE\n Available target specific settings are:\n" +
                self.get_stamper_target_specific_description())

    def do_save_config(self, args):
        """Save the current configuration"""
        arg_list = args.split()
        if len(arg_list) == 0:
            cfg = P4STA_utils.read_current_cfg()
            time_created = time.strftime('%d.%m.%Y-%H:%M:%S', time.localtime())
            file_name = cfg["selected_target"] + "_" + str(
                time_created) + ".json"
            P4STA_utils.write_config(cfg, file_name)
            print(file_name)
        else:
            print("No arguements needed")

    def do_create_new_cfg_from_template(self, args):
        """"Create a new config based on a target template"""
        arg_list = args.split()
        if len(arg_list) == 1:
            path = core_conn.root.get_template_cfg_path(arg_list[0])
            with open(path, "r") as f:
                cfg = json.load(f)
                P4STA_utils.write_config(cfg)
        else:
            print("Use: create_new_cfg_from_template <bmv2, ...>")

    def complete_open_config(self, text, line, begidx, endidx):
        mline = line.partition(' ')[2]
        offs = len(mline) - len(text)
        return [s[offs:] for s in self.all_cfgs if s.startswith(mline)]

    def do_open_config(self, args):
        """"Open Configuration"""
        arg_list = args.split()
        if len(arg_list) == 1:
            self.all_cfgs = core_conn.root.get_available_cfg_files()
            if arg_list[0] in self.all_cfgs:
                cfg = P4STA_utils.read_current_cfg(arg_list[0])
                P4STA_utils.write_config(cfg)
            else:
                print(arg_list[0] + " not found! Please enter a correct "
                                    "name of the following:")
                for line in self.all_cfgs:
                    print("-> " + line)
        else:
            self.do_show_available_stamper_targets("")
            print("Use: open_config <file_name>")

    def do_delete_config(self, args):
        """"Delete Configuration, e.g.: delete_config
        bmv2_12.07.2019-11:21:05.json"""
        arg_list = args.split()
        if len(arg_list) == 1:
            name = arg_list[0]
            if name == "config.json":
                print("CORE: Delete of config.json denied!")
                return
            os.remove(os.path.join(project_path, "data", name))
        else:
            print("Use: delete_config <file_name>")

    def do_show_available_stamper_targets(self, args):
        """"Shows all config-files which can be opened/deleted"""
        arg_list = args.split()
        if len(arg_list) == 0:
            self.all_cfgs = core_conn.root.get_available_cfg_files()
            for line in self.all_cfgs:
                print("-> " + line)
        else:
            print("[Error: No arguements needed]")

    def do_change_forwarding_mode(self, args):
        """"Change forwarding mode: 'change_forwarding_mode layer_number'"""
        arg_list = args.split()
        try:
            int_layer = int(arg_list[0])
            if len(arg_list) == 1 and 0 < int_layer < 4:
                self.cfg["forwarding_mode"] = arg_list[0]
                self.update_and_show()
            else:
                raise Exception
        except Exception:
            print("Please enter a correct forwarding mode. E.g. \"change_"
                  "forwarding_mode 2\" to apply layer 2 forwarding.")

    def do_change_duplication_downscale(self, args):
        """Change duplication downscale factor (20 = every 20th packet gets
        duplicated): 'change_duplication_downscale dwn_factor'"""
        arg_list = args.split()
        try:
            int_scale = int(arg_list[0])
            if len(arg_list) == 1 and int_scale > 0:
                self.cfg["multicast"] = arg_list[0]
                self.update_and_show()
            else:
                raise Exception
        except Exception:
            print(
                "Please enter a correct multicast duplication downscale factor"
                ". E.g. \"change_duplication_downscale 20\" to apply that "
                "every 20th packet gets duplicated.")

    def do_change_packet_generator(self, args):
        """Change the packet generator: 'change_packet_generator pg_name'"""
        arg_list = args.split()
        if len(arg_list) == 1 and arg_list[0] in P4STA_utils.flt(
                core_conn.root.get_all_loadGenerators()):
            self.cfg["selected_loadgen"] = arg_list[0]
            self.update_and_show()
        else:
            print("Please enter a correct packet generator which is available."
                  " E.g. change_packet_generator iperf3")


class DeployPasta(Cmd):
    prompt = "#P4STA_deploy: "

    def __init__(self):
        super().__init__()
        self.ready_to_deploy = False
        self.cfg = P4STA_utils.read_current_cfg()
        self.do_status("")

    def do_exit(self, args):
        """Exits CLI completely (better use back)"""
        sys.exit(0)

    @staticmethod
    def red(txt):
        return "\033[1;31m" + txt + "\x1b[0m"

    @staticmethod
    def green(txt):
        return "\033[1;32m" + txt + "\x1b[0m"

    def do_status(self, args):
        """Displays status of P4 device and loadgenerators."""
        stamper_status = rpyc.timed(core_conn.root.stamper_status, 15)
        stamper_status_job = stamper_status()
        try:
            stamper_status_job.wait()
        except Exception as e:
            print(e)
            return

        self.cfg, lines_pm, running, dev_status = stamper_status_job.value

        if running:
            print(self.green("P4 device is running."))
            print(dev_status + "\n\n")
            for line in lines_pm:
                print(line)
            print("\n\n")
            self.ready_to_deploy = True
        else:
            print(self.red("P4 device is not running."))
            print("Please enter 'start_device' to start P4 device.\n")
            self.ready_to_deploy = False

        for loadgen_grp in self.cfg["loadgen_groups"]:
            for host in loadgen_grp["loadgens"]:
                if host["reachable"]:
                    print("Server " + host[
                        "ssh_ip"] + " is currently " + self.green(
                        "reachable") + " and " + host[
                              "loadgen_iface"] + "(" + host[
                              "loadgen_ip"] + ")" + " is: " + host["link"])
                else:
                    print("Server " + host[
                        "ssh_ip"] + " is currently " + self.red(
                        " not reachable"))
                    print("Enter 'refresh_links' to automatically refresh the"
                          " network interfaces.")

    def do_start_device(self, args):
        """Starts P4 device, after this you can deploy your
        config to the device."""
        answer = core_conn.root.start_stamper_software()
        print(
            "Started P4 device. Please check the status by entering 'status'")
        self.wait(50)

    def do_show_log(self, args):
        """"Shows P4 device startup log."""
        if self.ready_to_deploy:
            try:
                log = core_conn.root.get_stamper_startup_log()
                log = P4STA_utils.flt(log)
                for lg in log:
                    print(lg)
            except Exception as e:
                print("error: " + str(e))
        else:
            print("P4 device is not running! Use start_device to start it.")

    @staticmethod
    def wait(msec):
        print("Please wait .", sep="", end="", flush=True)
        for i in range(0, msec):
            time.sleep(0.1)
            print(".", sep="", end="", flush=True)
        print("\n")

    def do_stop_device(self, args):
        """Stops P4 device."""
        try:
            answer = core_conn.root.stop_stamper_software()
            print("Stopped P4 device. Please check the status by "
                  "entering 'status'")
        except Exception as e:
            print("error: " + str(e))

        self.wait(20)

    def do_deploy_to_device(self, args):
        """Deploy config to P4 device. This activates the ports and
        configures the P4 runtime tables."""
        if self.ready_to_deploy:
            try:
                deploy = rpyc.timed(core_conn.root.deploy, 40)
                answer = deploy()
                answer.wait()
                deploy_error = answer.value

                if deploy_error is None or len(deploy_error) < 2:
                    print("deployed successfully")
            except Exception as e:
                print(traceback.format_exc())
        else:
            print("P4-device seems not to be ready to deploy. Please "
                  "check 'status' to see if it is ready and start it "
                  "with 'start_device'.")

    def do_refresh_link(self, args):
        """Refresh links at the loadgenerators. Ethtool needs to be
        installed on the loadgenerators."""
        core_conn.root.refresh_links()
        print("Refreshing all links on all packet generators started. "
              "Please check the status by entering 'status'")

    # returns back to original cmd loop (PastaPrompt class)
    def do_back(self, args):
        """Return back to main P4STA CLI"""
        return True


class RunPasta(Cmd):
    prompt = "#P4STA_run: "

    def __init__(self):
        super().__init__()
        self.cfg = P4STA_utils.read_current_cfg()
        self.ext_running = False

    # returns back to original cmd loop (PastaPrompt class)
    def do_back(self, args):
        """Return back to main P4STA CLI"""
        return True

    def do_exit(self, args):
        """Exits CLI completely (better use back)"""
        sys.exit(0)

    def do_ping(self, args):
        """Ping from every loadgenerator to every loadgenerator"""
        output = core_conn.root.ping()
        for o in output:
            print(o)

    def do_start_external(self, args):
        """Starts external host which captures duplicated packets"""
        print("Starting external python receiver ...")
        new_id = core_conn.root.set_new_measurement_id()

        try:
            answer, errors = core_conn.root.start_external()
            self.ext_running = answer
        except Exception as e:
            print("error: " + str(e))
            return

        if self.ext_running:
            if len(errors) > 0:
                for err in errors:
                    print(err)
                print("Starting of external host aborted!")
            else:
                print("External host started listening successfully.")
        else:
            print("Target (P4 device) is not running. Please go back and "
                  "then to deploy to start the target.")

    def do_stop_external(self, args):
        """Stop the external host. Not needed if run_load is executed as it
        is stopped automatically after load generation."""
        try:
            stop_external = rpyc.timed(core_conn.root.stop_external, 45)
            stoppable = stop_external()
            stoppable.wait()
            self.ext_running = False
            print("Stopped external host successfully.")
        except Exception as e:
            print("error: " + str(e))

    def do_reset_registers(self, args):
        print("Resetting registers at P4 device...")
        answer = core_conn.root.reset()
        print("Registers resetted successfully.")

    def do_run_load(self, args):
        """Start the load generator with its configured configuration for
        chosen duration: run_load 15 tcp 1500-> run for 15 seconds in TCP
        mode with 1500 Byte Packet Size (MTU)"""
        arg_list = args.split()
        try:
            if len(arg_list) == 3 and arg_list[0].isdigit():
                duration = int(arg_list[0])
                if arg_list[1].lower() == "tcp" \
                        or arg_list[1].lower() == "udp":
                    l4_type = arg_list[1].lower()
                else:
                    raise Exception

                # check if string only contains digits
                if arg_list[2].isdigit():
                    if 199 < int(arg_list[2]) < 1501:
                        mtu = arg_list[2]
                    else:
                        print("Please use a packet size between 200 and "
                              "1500 Bytes!")
                        raise Exception
                else:
                    raise Exception

                if not self.ext_running:
                    answer = input("External host is not running. "
                                   "Do you want to start it now?. Y/N: ")
                    if answer == "Y" or answer == "y":
                        self.do_start_external("")

                answer = input("Do you want to reset the registers at stamper?"
                               " If not, old values could influence current"
                               " measurement. Y/N:")
                if answer == "Y" or answer == "y":
                    self.do_reset_registers("")

                if self.ext_running:
                    print("Start execution of load generators, "
                          "please wait up to " + str(duration + 5) +
                          " seconds...")
                    t_timeout = round(duration * 1.5 + 20)
                    start_loadgens = rpyc.timed(core_conn.root.start_loadgens,
                                                t_timeout)
                    file_id = start_loadgens(duration, l4_type, mtu)
                    file_id.wait()

                    process_loadgens = rpyc.timed(
                        core_conn.root.process_loadgens, duration * 2)
                    results = process_loadgens(file_id.value)
                    results.wait()
                    output, total_bits, error, total_retransmits, total_byte, \
                        custom_attr, to_plot = results.value

                    DisplayResultsPasta.show_loadgen_results(output,
                                                             total_bits, error,
                                                             total_retransmits,
                                                             total_byte,
                                                             custom_attr,
                                                             to_plot)

                    if not error:
                        print("\n Load generators finished, trying to stop "
                              "external host (if started) and retrieving data"
                              " from P4-target registers ...")
                        self.do_stop_external("")

                else:
                    print("Run loadgenerators aborted because external "
                          "host is not running.")
                    if self.ext_running:
                        print("External host still seems to be running. "
                              "Try 'stop_external' to stop it.")
            else:
                raise Exception
        except Exception:
            print(traceback.format_exc())
            print("Please use the following format: run_loadgen time_in_sec "
                  "l4_type packet_size; e.g.: 'run_loadgen 10 tcp 1500'")


class DisplayResultsPasta(Cmd):
    selected_run_id = core_conn.root.getLatestMeasurementId()
    prompt = "#P4STA_results: "

    def __init__(self):
        super().__init__()
        self.cfg = P4STA_utils.read_current_cfg()
        self.ext_running = False
        print("\nSelected dataset with ID " + self.selected_run_id + " (" +
              time.strftime('%H:%M:%S %d.%m.%Y', time.localtime(
                  int(self.selected_run_id))) + ")")
        print("To change the selected dataset call show_datasets and "
              "follow the instructions.")

    @staticmethod
    def show_loadgen_results(output, total_bits, error, total_retransmits,
                             total_byte, custom_attr, to_plot):
        if error:
            print("An error occurred during processing load generators. "
                  "Please try again.")
            for out in output:
                print(out)
        else:
            tot_bits = analytics.find_unit_bit_byte(total_bits, "bit")
            print("Load generators total average throughput speed: " + str(
                tot_bits[0]) + " " + tot_bits[1] + "/s")
            tot_byte = analytics.find_unit_bit_byte(total_byte, "byte")
            print("Load generators total transmitted data: " + str(
                tot_byte[0]) + " " + tot_byte[1])
            print("Load generators total retransmitted packets: " + str(
                total_retransmits))

            for key, value in custom_attr["elems"].items():
                try:
                    print(value)
                except Exception:
                    pass

    # returns back to original cmd loop (PastaPrompt class)
    def do_back(self, args):
        """Return back to main P4STA CLI"""
        return True

    def do_exit(self, args):
        """Exits CLI completely (better use back)"""
        sys.exit(0)

    def show_datasets(self, display=True):
        found = core_conn.root.getAllMeasurements()
        print("\nAvailable datasets:")
        count = 1
        for f in found:
            time_created = time.strftime('%H:%M:%S %d.%m.%Y',
                                         time.localtime(int(f)))
            if f == self.selected_run_id and display:
                print(DeployPasta.green(str(
                    count) + ") " + time_created + " <-- current selected"))
            elif display:
                print(str(count) + ") " + time_created)
            count = count + 1

        return found

    def do_show_datasets(self, args):
        found = self.show_datasets()
        print("Use 'select_dataset or 'delete_dataset' to select or "
              "delete a dataset.")

    def do_select_dataset(self, args):
        def set_new_id(answer):
            new_id = found[int(answer) - 1]
            self.selected_run_id = new_id
            print("Now selected: " + time.strftime('%H:%M:%S %d.%m.%Y',
                                                   time.localtime(int(
                                                       self.selected_run_id))))

        arg_list = args.split()
        found = self.show_datasets(display=(len(arg_list) < 1))
        if len(arg_list) < 1:
            run = True
            while run:
                answer = input("To select a data set enter the data set "
                               "id (id could be 1, 2 ..): ")
                if answer == "exit" or answer == "back":
                    run = False
                if run:
                    try:
                        set_new_id(answer)
                        run = False
                    except Exception:
                        print("Please enter a correct id or 'back'")
        else:
            try:
                set_new_id(arg_list[0])
                found = self.show_datasets()
            except Exception:
                print("Please enter a correct id 'select_dataset ID' or "
                      "'select_dataset' without id to get more information.")

    def do_delete_dataset(self, args):
        arg_list = args.split()
        found = self.show_datasets(display=(len(arg_list) < 1))

        def delete_by_id(sel_index):
            id_to_delete = found[int(sel_index) - 1]
            core_conn.root.delete_by_id(id_to_delete)
            print("Deleted: " + time.strftime(
                '%H:%M:%S %d.%m.%Y', time.localtime(
                    int(id_to_delete))) + " successfully.")

        if len(arg_list) < 1:
            run = True
            while run:
                answer = input("To delete a data set enter the data set "
                               "id (id could be 1, 2 ..): ")
                if answer == "exit" or answer == "back":
                    run = False
                if run:
                    try:
                        delete_by_id(answer)
                        run = False
                    except Exception:
                        print("Please enter a correct id or 'back'")
        else:
            try:
                delete_by_id(arg_list[0])
            except Exception:
                print("Please enter a correct id 'delete_dataset ID' or "
                      "'delete_dataset' without id to get more information.")

    def do_show_stamper_results(self, args):
        sw = core_conn.root.stamper_results(self.selected_run_id)

        print("\n##### RESULTS FROM P4 TARGET REGISTERS ####\n")
        print("Average latency: " + str(sw["average"][0][0]) + " " + str(
            sw["average"][1]))
        print("Minimum latency: " + str(sw["min_delta"][0][0]) + " " + str(
            sw["min_delta"][1]))
        print("Maximum latency: " + str(sw["max_delta"][0][0]) + " " + str(
            sw["max_delta"][1]))
        print("Range: " + str(sw["range"][0][0]) + " " + str(sw["range"][1]))

        print("\nMeasured for _all_ packets:")
        print(str(sw["dut_stats"]["total_packetloss"]) + " Packets (" + str(
            sw["dut_stats"]["total_packetloss_percent"]) + " % of " + str(
            sw["dut_stats"]["total_num_egress_packets"]) + ")")

        print("\nMeasured only for _timestamped_ packets:")
        print(str(
            sw["dut_stats"]["total_packetloss_stamped"]) + " Packets (" + str(
            sw["dut_stats"][
                "total_packetloss_stamped_percent"]) + " % of " + str(
            sw["dut_stats"]["total_num_egress_stamped_packets"]) + ")")

        table = {
            "": [["In\nport", "Volume\ndata", "Volume\npackets",
                  "Average\nPacket-\nsize\n(Bytes)", "->", "Volume\ndata",
                  "Volume\npackets", "Average\nPacket-\nsize\n(Bytes)",
                  "Out\nport"]],
            "_stamped": [["In\nport", "Volume\ndata", "Volume\npackets",
                          "Average\nPacket-\nsize\n(Bytes)", "->",
                          "Volume\ndata", "Volume\npackets",
                          "Average\nPacket-\nsize\n(Bytes)", "Out\nport"]]
        }

        for word in ["", "_stamped"]:
            try:
                for loadgen_grp in sw["loadgen_groups"]:
                    if loadgen_grp["use_group"] == "checked":
                        for host in loadgen_grp["loadgens"]:
                            selected_dut = {}
                            for dut in sw["dut_ports"]:
                                if loadgen_grp["group"] == dut["id"]:
                                    selected_dut = dut
                                    break
                            try:
                                table[word].append(
                                    [
                                        host["real_port"],
                                        round(host["num_ingress" + word +
                                                   "_bytes"] / 1000000000, 2),
                                        host["num_ingress" + word +
                                             "_packets"],
                                        round(host["num_ingress" + word +
                                                   "_bytes"] / host[
                                            "num_ingress" +
                                            word + "_packets"], 2),
                                        round(selected_dut["num_egress" +
                                                           word +
                                                           "_bytes"] /
                                              1000000000, 2),
                                        selected_dut["num_egress" + word +
                                                     "_packets"],
                                        round(selected_dut["num_egress" +
                                                           word + "_bytes"] /
                                              selected_dut["num_egress" +
                                                           word + "_packets"],
                                              2),
                                        selected_dut["real_port"]
                                    ])
                            except ZeroDivisionError:
                                table[word].append(
                                    [host["real_port"], "err: could be 0",
                                     host["num_ingress" + word + "_packets"],
                                     "err: could be 0",
                                     "err: could be 0", selected_dut[
                                         "num_egress" + word + "_packets"],
                                     "err: could be 0",
                                     selected_dut["real_port"]])

                for loadgen_grp in sw["loadgen_groups"]:
                    if loadgen_grp["use_group"] == "checked":
                        for host in loadgen_grp["loadgens"]:
                            selected_dut = {}
                            for dut in sw["dut_ports"]:
                                if loadgen_grp["group"] == dut["id"]:
                                    selected_dut = dut
                                    break
                            try:
                                table[word].append(
                                    [
                                        selected_dut["real_port"],
                                        round(selected_dut["num_ingress" +
                                                           word + "_bytes"] /
                                              1000000000, 2),
                                        selected_dut["num_ingress" + word +
                                                     "_packets"],
                                        round(selected_dut["num_ingress" +
                                                           word + "_bytes"] /
                                              selected_dut["num_ingress" +
                                                           word + "_packets"],
                                              2),
                                        round(host["num_egress" + word +
                                                   "_bytes"] / 1000000000, 2),
                                        host["num_egress" + word + "_packets"],
                                        round(host["num_egress" + word +
                                                   "_bytes"] /
                                              host["num_egress" + word +
                                                   "_packets"], 2),
                                        host["real_port"]
                                    ])

                            except ZeroDivisionError:
                                table[word].append(
                                    [host["real_port"], "err: could be 0",
                                     host["num_ingress" + word + "_packets"],
                                     "err: could be 0",
                                     "err: could be 0", selected_dut[
                                         "num_egress" + word + "_packets"],
                                     "err: could be 0",
                                     selected_dut["real_port"]])

            except Exception as e:
                print(traceback.format_exc())
                table[word].append(["Error: " + str(e)])

        for word in ["", "_stamped"]:
            if word == "_stamped":
                print("\n\nMeasured for timestamped packets only:")
            else:
                print("\nMeasured for all packets:")
            print(
                "\n\n              INGRESS PIPELINE"
                "                         EGRESS PIPELINE")
            print(tabulate(table[word], tablefmt="fancy_grid"))

        print("\n###########################################")

    def do_show_external_results(self, args):
        cfg = P4STA_utils.read_result_cfg(self.selected_run_id)
        extH_results = analytics.main(str(self.selected_run_id),
                                      cfg["multicast"],
                                      P4STA_utils.get_results_path(self.selected_run_id))

        print("\n\nShowing results from external host for id: " +
              self.selected_run_id + " from " + time.strftime(
                '%H:%M:%S %d.%m.%Y',
                time.localtime(int(self.selected_run_id))))
        print("Results from external Host for every " + str(
            cfg["multicast"] + ". packet") + "\n")
        print("Raw packets: " + str(
            extH_results["num_raw_packets"]) + " Processed packets: " + str(
            extH_results[
                "num_processed_packets"]) + " Total throughput: " + str(
            extH_results["total_throughput"]) + " Megabytes \n")
        print("Min latency: " + str(
            analytics.find_unit(extH_results["min_latency"])[0][
                0]) + " " + str(
            analytics.find_unit(extH_results["min_latency"])[1]))

        print("Max latency: " + str(
            analytics.find_unit(extH_results["max_latency"])[0][
                0]) + " " + str(
            analytics.find_unit(extH_results["max_latency"])[1]))
        print("Average latency: " + str(
            analytics.find_unit(extH_results["avg_latency"])[0][
                0]) + " " + str(
            analytics.find_unit(extH_results["avg_latency"])[1]) + "\n")
        print("Min IPDV: " + str(
            analytics.find_unit(extH_results["min_ipdv"])[0][0]) + " " + str(
            analytics.find_unit(extH_results["min_ipdv"])[1]))
        print("Max IPDV: " + str(
            analytics.find_unit(extH_results["max_ipdv"])[0][0]) + " " + str(
            analytics.find_unit(extH_results["max_ipdv"])[1]))
        print("Average IPDV: " + str(
            analytics.find_unit(extH_results["avg_ipdv"])[0][0]) + " " + str(
            analytics.find_unit(extH_results["avg_ipdv"])[1])
              + " and abs(): " + str(
            analytics.find_unit(extH_results["avg_abs_ipdv"])[0][
                0]) + " " + str(
            analytics.find_unit(extH_results["avg_abs_ipdv"])[1]) + "\n")
        print("Min PDV: " + str(
            analytics.find_unit(extH_results["min_pdv"])[0][0]) + " " + str(
            analytics.find_unit(extH_results["min_pdv"])[1]))
        print("Max PDV: " + str(
            analytics.find_unit(extH_results["max_pdv"])[0][0]) + " " + str(
            analytics.find_unit(extH_results["max_pdv"])[1]))
        print("Average PDV: " + str(
            analytics.find_unit(extH_results["avg_pdv"])[0][0]) + " " + str(
            analytics.find_unit(extH_results["avg_pdv"])[1]) + "\n")
        print("Min packet/s: " + str(extH_results["min_packets_per_second"]))
        print("Max packet/s: " + str(extH_results["max_packets_per_second"]))
        print("Average packet/s: " + str(
            extH_results["avg_packets_per_second"]) + "\n")

    def do_show_loadgen_results(self, args):
        print("\nShowing results of loadgen for id: " + self.selected_run_id +
              " from " + time.strftime('%H:%M:%S %d.%m.%Y',
                                       time.localtime(
                                           int(self.selected_run_id))) + "\n")
        # True = not first run, just reading results again
        process_loadgens = rpyc.timed(core_conn.root.process_loadgens, 60)
        results = process_loadgens(self.selected_run_id)
        results.wait()
        output, total_bits, error, total_retransmits, total_byte, \
            custom_attr, to_plot = results.value

        self.show_loadgen_results(output, total_bits, error, total_retransmits,
                                  total_byte, custom_attr, to_plot)


PastaMenu().cmdloop()
