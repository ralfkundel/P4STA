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
from tabulate import tabulate
from multiprocessing.connection import Listener, Client
import os
import sys
import time
import traceback
import rpyc

dir_path = os.path.dirname(os.path.realpath(__file__))
project_path = dir_path[0:dir_path.find("/cli")]
sys.path.append(project_path)
from calculate import calculate
from core import P4STA_utils


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
        print("'configure' => Opens the settings to configure your testbed. This includes settings for all involved devices.")
        print("'deploy' => Opens the environment to deploy the current configuration to the selected P4-target.")
        print("'run' => Opens the run section where you can execute the heavy load performance test.")
        print("'results' => Opens the results section where the newest and older results can be evaluated.\n")

    def do_exit(self, inp):
        """Exits the P4STA CLI"""
        sys.exit(0)

    def do_configure(self, args):
        """Opens the settings to configure your testbed. This includes settings for all involved devices."""
        PastaConfigure().cmdloop()

    def do_deploy(self, args):
        """Opens the environment to deploy the current configuration to the selected P4-target."""
        DeployPasta().cmdloop()

    def do_run(self, args):
        """Opens the run section where you can execute the heavy load performance test."""
        RunPasta().cmdloop()

    def do_results(self, args):
        """Opens the results section where the newest and older results can be evaluated."""
        DisplayResultsPasta().cmdloop()





class PastaConfigure(Cmd):
    prompt = "#P4STA_configure: "

    def __init__(self):
        super().__init__()
        #time.sleep(0.5)
        self.cfg = P4STA_utils.read_current_cfg()
        self.target_cfg = core_conn.root.get_target_cfg()

        self.table_general = []
        self.table_loadgen_1 = []
        self.table_loadgen_2 = []
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

    def strike(self, text):
        striked = ''
        if type(text) == str:
            for c in text:
                striked = striked + c + '\u0336'

        elif type(text) == list:
            l = []
            for elem in text:
                striked = ''
                for c in elem:
                    striked = striked + c + '\u0336'
                l.append(striked)
            striked = l

        if self.cfg["dut_2_use_port"] == "unchecked":
            return striked
        else:
            return text

    def do_show(self, inp):
        """Displays an overwiew of the current total configuration"""
        self.cfg = P4STA_utils.read_current_cfg()
        self.target_cfg = core_conn.root.get_target_cfg()

        self.table_loadgen_1 = [
            ["Loadgens 1", "SSH IP", "SSH User", "Load Iface", "Loadgen MAC", "Loadgen IP", "Port", "P4 Port"]]
        self.table_loadgen_2 = [
            ["Loadgens 2", "SSH IP", "SSH User", "Load Iface", "Loadgen MAC", "Loadgen IP", "Port", "P4 Port"]]

        self.table_dut = [["Use Port", "Port", "P4 Port", "Duplicate Flow (income)"]]
        self.table_external_host = [["SSH IP", "SSH User", "Load Iface", "Port", "P4 Port"]]
        self.table_stamper = [["SSH IP", "SSH User"]]

        # read Stamper target specific config
        for t_inp in self.target_cfg["inputs"]["input_table"]:
            self.table_loadgen_1[0].append(t_inp["title"])
            self.table_loadgen_2[0].append(t_inp["title"])
            self.table_dut[0].append(t_inp["title"])
            self.table_external_host[0].append(t_inp["title"])

        print("Current configuration (to change enter 'change_general_cfg':")
        self.table_general = [["Target", "Mode", "Dupl. Scale", "Packet Gen"]]
        self.table_general.append([self.cfg["selected_target"], "Layer " + self.cfg["forwarding_mode"], self.cfg["multicast"], self.cfg["selected_loadgen"]])
        print(tabulate(self.table_general, tablefmt="fancy_grid"))

        print("LOADGENERATORS:")

        for server in self.cfg["loadgen_servers"]:
            add = []
            for t_inp in self.target_cfg["inputs"]["input_table"]:
                try:
                    add.append(server[t_inp["target_key"]])
                except:
                    add.append("")
            self.table_loadgen_1.append(["1." + str(server["id"]), server["ssh_ip"], server["ssh_user"], server["loadgen_iface"], server["loadgen_mac"], server["loadgen_ip"], server["real_port"], server["p4_port"]] + add)

        print(tabulate(self.table_loadgen_1, tablefmt="fancy_grid"))

        for client in self.cfg["loadgen_clients"]:
            add = []
            for t_inp in self.target_cfg["inputs"]["input_table"]:
                try:
                    add.append(client[t_inp["target_key"]])
                except:
                    add.append("")
            self.table_loadgen_2.append(["2." + str(client["id"]), client["ssh_ip"], client["ssh_user"], client["loadgen_iface"], client["loadgen_mac"], client["loadgen_ip"], client["real_port"], client["p4_port"]] + add)

        print(tabulate(self.table_loadgen_2, tablefmt="fancy_grid"))

        print("DUT:")
        add = {"dut1_": [], "dut2_": [], "ext_host_": []}
        for dut in ["dut1_", "dut2_", "ext_host_"]:
            for t_inp in self.target_cfg["inputs"]["input_table"]:
                try:
                    add[dut].append(self.cfg[dut + t_inp["target_key"]])
                except:
                    add[dut].append("")
        self.table_dut.append(["checked", self.cfg["dut1_real"], self.cfg["dut1"], self.cfg["dut_1_outgoing_stamp"]] + add["dut1_"])
        self.table_dut.append([self.cfg["dut_2_use_port"], self.strike(self.cfg["dut2_real"]), self.strike(self.cfg["dut2"]), self.strike(self.cfg["dut_2_outgoing_stamp"])] + self.strike(add["dut2_"]))
        print(tabulate(self.table_dut, tablefmt="fancy_grid"))

        print("EXTERNAL HOST:")
        self.table_external_host.append([self.cfg["ext_host_ssh"], self.cfg["ext_host_user"], self.cfg["ext_host_if"], self.cfg["ext_host_real"], self.cfg["ext_host"]] + add["ext_host_"])
        print(tabulate(self.table_external_host, tablefmt="fancy_grid"))

        print("STAMPER:")
        self.table_stamper.append([self.cfg["p4_dev_ssh"], self.cfg["p4_dev_user"]])
        print(tabulate(self.table_stamper, tablefmt="fancy_grid"))


    def do_change_general_cfg(self, args):
        """Opens the environment to change the config (e.g. Stamper-target, duplication downscale factor, packet generator and forwarding mode."""
        ChangeGeneralConfig().cmdloop()
        self.target_cfg = core_conn.root.get_target_cfg()

    def group_type(self, type):
        add_to = ""
        if type == "1":
            add_to = "loadgen_servers"
        elif type == "2":
            add_to = "loadgen_clients"
        return add_to

    def get_target_specific_description(self):
        self.target_cfg = core_conn.root.get_target_cfg()
        answer = ""
        for t_inp in self.target_cfg["inputs"]["input_table"]:
            try:
                answer = answer + " " + t_inp["title"] + "(" + t_inp["description"] + ")"
            except Exception as e:
                pass
        return answer

#args = group, ssh_ip, ssh_user, load_iface, load_mac, load_ip, port, link
    def do_add_loadgen(self, args):
        """Add a loadgenerator: 'add_loadgen group ssh_ip ssh_username load_interface mac_adress load_ip custom_target_opt'"""
        def error():
            print("\nPlease use the following format:")
            print("add_loadgen group ssh_ip ssh_user load_iface load_mac load_ip port link" + self.get_target_specific_description())

            print("e.g.: add_loadgen 1 172.1.1.10 mmustermann eth1 11:22:33:44:55:66 10.10.10.1 1/1" + self.get_target_specific_description())

        arg_list = args.split()
        if len(arg_list) >= 7:
            add_to = self.group_type(arg_list[0])
            if add_to != "":
                ports = core_conn.root.get_ports()
                real_ports = ports["real_ports"]
                logical_ports = ports["logical_ports"]
                try:
                    all_ids = [] # store all ids to select the next as new id
                    for host in self.cfg[add_to]:
                        all_ids.append(int(host["id"]))
                    try:
                        new_p4_port = logical_ports[real_ports.index(arg_list[6])].strip("\n")
                    except:
                        print("\nSure you entered the right port syntax for the selected target (" + self.cfg["selected_target"] + ") ?\n")
                        raise Exception

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
                        except:
                            pass
                        ind = ind + 1

                    self.cfg[add_to].append(dict_add)
                    P4STA_utils.write_config(self.cfg)
                    self.do_show("")
                except Exception as e:
                    print(e)
                    error()
        else:
            error()

    def do_delete_loadgen(self, args):
        """Delete a loadgenerator: 'delete_loadgen loadgen_group receiver/sender_id'"""
        def error():
            print("\nPlease use the following format:")
            print("delete_loadgen loadgen_group receiver/sender_id")
            print("e.g. to delete Sender 1 of group Loadgens 2: delete_loadgen 2 1\n")

        arg_list = args.split()
        if len(arg_list) == 2:
            add_to = self.group_type(arg_list[0])
            try:
                deleted = False
                for loadgen in self.cfg[add_to]:
                    if str(loadgen["id"]) == arg_list[1]:
                        self.cfg[add_to].remove(loadgen)
                        deleted = True
                if deleted:
                    if len(self.cfg["loadgen_servers"]) > 0:
                        P4STA_utils.write_config(self.cfg)
                        self.do_show("")
                    else:
                        print("There must be at least one server in group 1.")
                else:
                    print("Group " + arg_list[0] + " | Loadgen " + arg_list[1] + " not found - nothing changed.")
            except Exception as e:
                print(e)
                error()
        else:
            error()

    def do_change_dut(self, args):
        """Changes Device under Test config: 'change_dut dut1_port target_specific dut1_stamp(Flow leaving stamper at dut1 port) dut2_port target_specific dut2_stamp' to set or unset use: change_dut uncheck/check 2 (only dut2 is changeable)"""
        arg_list = args.split()
        if len(arg_list) == 2:
            try:
                if (arg_list[0] == "unchecked" or arg_list[0] == "checked") and self.cfg["selected_target"] is not "bmv2":
                    if int(arg_list[1]) == 2:
                        self.cfg["dut_2_use_port"] = arg_list[0]
                        if self.cfg["dut_2_use_port"] == "unchecked":
                            self.cfg["dut2_real"] = self.cfg["dut1_real"]
                            self.cfg["dut2"] = self.cfg["dut1"]
                            if "dut1_speed" in self.cfg:
                                self.cfg["dut2_speed"] = self.cfg["dut1_speed"]
                        P4STA_utils.write_config(self.cfg)
                else:
                    raise Exception
            except:
                print("Please use one of the following formats: \n change_dut unchecked/checked 2 (only dut2 is changeable)")
                print("change_dut dut1_port" + self.get_target_specific_description() + " dut1_duplicate(Duplicate Flow which comes in) dut2_port " + self.get_target_specific_description() + " dut2_duplicate")
        else:
            try:
                tar = len(self.target_cfg["inputs"]["input_table"])
                print(arg_list)
                if len(arg_list) == 4+(tar*2) and (arg_list[1+tar] == "checked" or arg_list[1+tar] == "unchecked") and (arg_list[3+(2*tar)] == "checked" or arg_list[3+(2*tar)] == "unchecked"):
                    ports = core_conn.root.get_ports()
                    real_ports = ports["real_ports"]
                    logical_ports = ports["logical_ports"]

                    c = 1
                    end = 2 + len(self.target_cfg["inputs"]["input_table"])
                    for i in [0, end]:
                        self.cfg["dut" + str(c) + "_real"] = arg_list[i]
                        try:
                            self.cfg["dut" + str(c)] = logical_ports[real_ports.index(arg_list[i])].strip("\n")
                        except:
                            print("\nSure you entered the right port syntax for the selected target (" + self.cfg["selected_target"] + ") ?\n")
                            raise Exception

                        self.cfg["dut_" + str(c) + "_outgoing_stamp"] = arg_list[i+1]
                        index = 2
                        for t_inp in self.target_cfg["inputs"]["input_table"]:
                            try:
                                self.cfg["dut" + str(c) + "_" + t_inp["target_key"]] = arg_list[i + index]
                            except Exception as e:
                                print("Error:" + str(e))
                            index = index + 1
                        c = c + 1

                    P4STA_utils.write_config(self.cfg)
                    self.do_show("")
                else:
                    raise Exception
            except Exception as e:
                print("Please enter a valid dut configuration like:")
                print("\"change_dut 57/0" + self.get_target_specific_description() + " checked 58/0" + self.get_target_specific_description() + " unchecked\"")
                print("\"change_dut unchecked/checked 2\" (only dut2 is changeable and for bmv2 both dut ports are needed.)")

    def do_change_external_host(self, args):
        """Changes external host config: 'change_external_host ssh_ip ssh_user load_iface port target_specific'"""
        arg_list = args.split()
        try:
            if len(arg_list) >= 5:
                ports = core_conn.root.get_ports()
                real_ports = ports["real_ports"]
                logical_ports = ports["logical_ports"]

                self.cfg["ext_host_ssh"] = arg_list[0]
                self.cfg["ext_host_user"] = arg_list[1]
                self.cfg["ext_host_if"] = arg_list[2]
                self.cfg["ext_host_real"] = arg_list[3]
                try:
                    self.cfg["ext_host"] = logical_ports[real_ports.index(arg_list[3])].strip("\n")
                except Exception as e:
                    print(e)
                    print("\nSure you entered the right port syntax for the selected target (" + self.cfg["selected_target"] + ") ?\n")
                    raise Exception

                i = 4
                for t_inp in self.target_cfg["inputs"]["input_table"]:
                    try:
                        self.cfg["ext_host_" + t_inp["target_key"]] = arg_list[i]
                    except Exception as e:
                        print("Error:" + str(e))
                    i = i + 1

                P4STA_utils.write_config(self.cfg)
                self.do_show("")
            else:
                raise Exception
        except:
            print("Please enter a valid external host configuration: ssh_ip username interface " + self.get_target_specific_description())
            print("\"e.g.: change_external_host 172.1.1.99 mmustermann eth0 5/0 " + self.get_target_specific_description())

    def do_change_stamper(self, args):
        """Changes p4-stamper config: 'change_stamper ssh_ip ssh_user'"""
        arg_list = args.split()
        try:
            if len(arg_list) == 2:
                self.cfg["p4_dev_ssh"] = arg_list[0]
                self.cfg["p4_dev_user"] = arg_list[1]

                P4STA_utils.write_config(self.cfg)
                self.do_show("")
            else:
                raise Exception
        except:
            print("Please enter a valid stamper configuration [ssh_ip, username]: ")
            print("\"e.g.: change_stamper 172.1.1.100 mmustermann")


# sub cmd for changing general config (p4 prog, target, loadgen software etc)
class ChangeGeneralConfig(Cmd):
    prompt = "#P4STA_general_config: "

    def __init__(self):
        super().__init__()
        self.cfg = P4STA_utils.read_current_cfg()
        self.target_cfg = core_conn.root.get_target_cfg()
        self.all_cfgs = core_conn.root.get_available_cfg_files()

        print("Available targets: " + ", ".join( core_conn.root.get_all_targets() ))
        print("Available forwarding modes (Layer): 1 (1 to 1 loadgen only), 2, 3")
        print("Available packet generators: " + ",".join(self.cfg["available_loadgens"]))

        self.show()

    def show(self):
        """Shows the current general config (like target, forwarding mode, packet generator)"""
        print("Current configuration:")
        table_general = [["Target", "Mode", "Dupl. Scale", "Packet Gen"],
                         [self.cfg["selected_target"], "Layer " + self.cfg["forwarding_mode"],
                          self.cfg["multicast"], self.cfg["selected_loadgen"]]]
        table_specific = [[],[]]
        for tbl_inp in self.target_cfg["inputs"]["input_individual"]:
            table_specific[0].append(tbl_inp["title"])
            table_specific[1].append(self.cfg[tbl_inp["target_key"]])

        print(tabulate(table_general, tablefmt="fancy_grid"))
        print("Stamp TCP packets: " + ("True" if (self.cfg["stamp_tcp"] == "checked")  else "False"))
        print("Stamp UDP packets: " + ("True" if (self.cfg["stamp_udp"] == "checked")  else "False"))
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
                answer = answer + " " + t_inp["title"] + " (" + t_inp["description"] + ")\n"
            except Exception as e:
                pass
        return answer

    def do_change_specific(self, args):
        """Changes Stamper target specific settings: 'change_specific arg1 arg2 ..'"""
        arg_list = args.split()
        if len(arg_list) == len(self.target_cfg["inputs"]["input_individual"]):
            c = 0
            for tbl_inp in self.target_cfg["inputs"]["input_individual"]:
                self.cfg[tbl_inp["target_key"]] = arg_list[c]
                c = c + 1
            self.update_and_show()
        else:
            print("Please enter a valid setting like: change_specific SETTING VALUE\n Available target specific settings are:\n" + self.get_stamper_target_specific_description())

### TODO load/store cfg
    def do_save_config(self, args):
        """Save the current configuration"""
        arg_list = args.split()
        if len(arg_list) == 0:
            cfg = P4STA_utils.read_current_cfg()
            time_created = time.strftime('%d.%m.%Y-%H:%M:%S', time.localtime())
            file_name = cfg["selected_target"]+ "_" + str(time_created) + ".json"
            P4STA_utils.write_config(cfg, file_name)
            print(file_name)
        else:
            print("No arguements needed")

    def do_create_new_cfg_from_template(self,args):
        """"Create a new config based on a target template"""
        arg_list = args.split()
        if len(arg_list) == 1:
            path = core_conn.root.get_template_cfg_path(arg_list[0])
            with open(path, "r") as f:
                cfg = json.load(f)
                P4STA_utils.write_config(cfg)
        else:
            print ("Use: create_new_cfg_from_template <bmv2, ...>")

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
                print(arg_list[0] + " not found! Please enter a correct name of the following:")
                for line in self.all_cfgs:
                    print("-> " + line)
        else:
            self.do_show_available_stamper_targets("")
            print("Use: open_config <file_name>")
    
    def do_delete_config(self, args):
        """"Delete Configuration, e.g.: delete_config bmv2_12.07.2019-11:21:05.json"""
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
        except:
            print("Please enter a correct forwarding mode. E.g. \"change_forwarding_mode 2\" to apply layer 2 forwarding.")

    def do_change_duplication_downscale(self, args):
        """Change duplication downscale factor (20 = every 20th packet gets duplicated): 'change_duplication_downscale dwn_factor'"""
        arg_list = args.split()
        try:
            int_scale = int(arg_list[0])
            if len(arg_list) == 1 and int_scale > 0:
                self.cfg["multicast"] = arg_list[0]
                self.update_and_show()
            else:
                raise Exception
        except:
            print("Please enter a correct multicast duplication downscale factor. E.g. \"change_duplication_downscale 20\" to apply that every 20th packet gets duplicated.")

    def do_change_packet_generator(self, args):
        """Change the packet generator: 'change_packet_generator pg_name'"""
        arg_list = args.split()
        if len(arg_list) == 1 and arg_list[0] in self.cfg["available_loadgens"]:
            self.cfg["selected_target"] = arg_list[0]
            self.update_and_show()
        else:
            print("Please enter a correct packet generator which is available. E.g. change_packet_generator iperf3")


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
        p4_dev_status = rpyc.timed(core_conn.root.p4_dev_status, 15)
        p4_dev_status_job = p4_dev_status()
        try:
            p4_dev_status_job.wait()
        except Exception as e:
            print(e)
            return

        self.cfg, lines_pm, running, dev_status = p4_dev_status_job.value

        if running:
            print(self.green("P4 device is running."))
            print(dev_status + "\n\n")
            for line in lines_pm:
                print(line)
            print("\n\n")
            self.ready_to_deploy = True
        else:
            print(self.red("P4 device is not running.")) #red and than white again
            print("Please enter 'start_device' to start P4 device.\n")
            self.ready_to_deploy = False

        for server in self.cfg["loadgen_servers"]:
            if server["reachable"]:
                print("Server " + server["ssh_ip"] + " is currently " + self.green("reachable") + " and" + server["loadgen_iface"] + "(" + server["loadgen_ip"] + "]" + " is: " + server["link"])
            else:
                print("Server " + server["ssh_ip"] + " is currently " + self.red(" not reachable"))
                print("Enter 'refresh_links' to automatically refresh the network interfaces.")

        for client in self.cfg["loadgen_clients"]:
            if client["reachable"]:
                print("Client " + client["ssh_ip"] + " is currently " + self.green("reachable") + " and" + client["loadgen_iface"] + "(" + client["loadgen_ip"] + "]" + " is: " + client["link"])
            else:
                print("Client " + client["ssh_ip"] + " is currently" + self.red(" not reachable"))
                print("Enter 'refresh_links' to automatically refresh the network interfaces.")

    def do_start_device(self, args):
        """Starts P4 device, after this you can deploy your config to the device."""
        answer = core_conn.root.start_p4_dev_software() 
        print("Started P4 device. Please check the status by entering 'status'")
        self.wait(50)
        #self.do_status("")

    def do_show_log(self, args):
        """"Shows P4 device startup log."""
        if self.ready_to_deploy:
            try:
                log = core_conn.root.get_p4_dev_startup_log()
                log = P4STA_utils.flt(log)
                for l in log:
                    print(l)
            except Exception as e:
                print("error: "+str(e))
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
            answer = core_conn.root.stop_p4_dev_software()
            print("Stopped P4 device. Please check the status by entering 'status'")
        except Exception as e:
            print("error: "+str(e))

        self.wait(20)
        #self.do_status("")

    def do_deploy_to_device(self, args):
        """Deploy config to P4 device. This activates the ports and configures the P4 runtime tables."""
        if self.ready_to_deploy:
            try:
                deploy = rpyc.timed(core_conn.root.deploy, 20)
                answer = deploy()
                answer.wait()
                deploy_error = answer.value

                if len(deploy_error) < 2:
                    print("deployed successfully")
            except Exception as e:
                print(traceback.format_exc())
        else:
            print("P4-device seems not to be ready to deploy. Please check 'status' to see if it is ready and start it with 'start_device'.")

    def do_refresh_link(self, args):
        """Refresh links at the loadgenerators. Ethtool needs to be installed on the loadgenerators."""
        core_conn.root.refresh_links()
        print("Refreshing all links on all packet generators started. Please check the status by entering 'status'")

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
            print("error: "+str(e))
            return

        if self.ext_running:
            if len(errors) > 0:
                for err in errors:
                    print(err)
                print("Starting of external host aborted!")
            else:
                print("External host started listening successfully.")
        else:
            print("Target (P4 device) is not running. Please go back and then to deploy to start the target.")

    def do_stop_external(self, args):
        """Stop the external host. Not needed if run_load is executed as it is stopped automatically after load generation."""
        try:
            stop_external = rpyc.timed(core_conn.root.stop_external, 45) 
            stoppable = stop_external()
            stoppable.wait()
            self.ext_running = False
            print("Stopped external host successfully.")
        except Exception as e:
            print("error: "+str(e))


    def do_reset_registers(self, args):
        print("Resetting registers at P4 device...")
        answer = core_conn.root.reset()
        print("Registers resetted successfully.")

    def do_run_load(self, args):
        """Start the load generator with its configured configuration for chosen duration: run_load 15 tcp 1500-> run for 15 seconds in TCP mode with 1500 Byte Packet Size (MTU)"""
        arg_list = args.split()
        try:
            if len(arg_list) == 3 and arg_list[0].isdigit():
                duration = int(arg_list[0])
                if arg_list[1].lower() == "tcp" or arg_list[1].lower() == "udp":
                    l4_type = arg_list[1].lower()
                else:
                    raise Exception

                if arg_list[2].isdigit(): # to check if string contains only digits
                    if 199 < int(arg_list[2]) < 1501:
                        mtu = arg_list[2]
                    else:
                        print("Please use a packet size between 200 and 1500 Bytes!")
                        raise Exception
                else:
                    raise Exception

                if not self.ext_running:
                    answer = input("External host is not running. Do you want to start it now?. Y/N: ")
                    if answer == "Y" or answer == "y":
                        self.do_start_external("")

                answer = input("Do you want to reset the registers at P4 device? If not, old values could influence current measurement. Y/N:")
                if answer == "Y" or answer == "y":
                    self.do_reset_registers("")

                if self.ext_running:
                    print("Start execution of load generators, please wait up to " + str(duration+5) + " seconds...")
                    t_timeout = round(duration*1.5 + 20)
                    start_loadgens = rpyc.timed(core_conn.root.start_loadgens, t_timeout)
                    file_id = start_loadgens(duration, l4_type, mtu)
                    file_id.wait()

                    process_loadgens = rpyc.timed(core_conn.root.process_loadgens, duration*2)
                    results = process_loadgens(file_id.value)
                    results.wait()
                    output, total_bits, error, total_retransmits, total_byte, custom_attr, to_plot = results.value

                    DisplayResultsPasta.show_loadgen_results(output, total_bits, error, total_retransmits, total_byte, custom_attr, to_plot)

                    if not error:
                        print("\n Load generators finished, trying to stop external host (if started) and retrieving data from P4-target registers ...")
                        self.do_stop_external("")

                else:
                    print("Run loadgenerators aborted because external host is not running.")
                    if self.ext_running:
                        print("External host still seems to be running. Try 'stop_external' to stop it.")
            else:
                raise Exception
        except:
            print(traceback.format_exc())
            print("Please use the following format: run_loadgen time_in_sec l4_type packet_size; e.g.: 'run_loadgen 10 tcp 1500'")

class DisplayResultsPasta(Cmd):
    selected_run_id = core_conn.root.getLatestMeasurementId()
    prompt = "#P4STA_results: "
    def __init__(self):
        super().__init__()
        self.cfg = P4STA_utils.read_current_cfg()
        self.ext_running = False
        print("\nSelected dataset with ID " + self.selected_run_id + " (" + time.strftime('%H:%M:%S %d.%m.%Y', time.localtime(int(self.selected_run_id))) + ")")
        print("To change the selected dataset call show_datasets and follow the instructions.")

    @staticmethod
    def show_loadgen_results(output, total_bits, error, total_retransmits, total_byte, custom_attr, to_plot):
        if error:
            print("An error occurred during processing load generators. Please try again.")
            for out in output:
                print(out)
        else:
            tot_bits = calculate.find_unit_bit_byte(total_bits, "bit")
            print("Load generators total average throughput speed: " + str(tot_bits[0]) + " " + tot_bits[1] + "/s")
            tot_byte = calculate.find_unit_bit_byte(total_byte, "byte")
            print("Load generators total transmitted data: " + str(tot_byte[0]) + " " + tot_byte[1])
            print("Load generators total retransmitted packets: " + str(total_retransmits))
            #print("Load generators mean RTT: " + str(mean_rtt) + "(microsec) with min RTT of " + str(min_rtt) + " and max RTT of " + str(max_rtt))
            for key, value in custom_attr["elems"].items():
                try:
                    print(value)
                except:
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
            time_created = time.strftime('%H:%M:%S %d.%m.%Y', time.localtime(int(f)))
            if f == self.selected_run_id and display:
                print(DeployPasta.green(str(count) + ") " + time_created + " <-- current selected"))
            elif display:
                print(str(count) + ") " + time_created)
            count = count + 1

        return found

    def do_show_datasets(self, args):
        found = self.show_datasets()
        print("Use 'select_dataset or 'delete_dataset' to select or delete a dataset.")

    def do_select_dataset(self, args):
        def set_new_id(answer):
            new_id = found[int(answer)-1]
            self.selected_run_id = new_id ###TODO
            print("Now selected: " + time.strftime('%H:%M:%S %d.%m.%Y', time.localtime(int(new_id))))

        arg_list = args.split()
        found = self.show_datasets(display=(len(arg_list) < 1))
        if len(arg_list) < 1:
            run = True
            while run:
                answer = input("To select a data set enter the data set id (id could be 1, 2 ..): ")
                if answer == "exit" or answer == "back":
                    run = False
                if run:
                    try:
                        set_new_id(answer)
                        run = False
                    except:
                        print("Please enter a correct id or 'back'")
        else:
            try:
                set_new_id(arg_list[0])
                found = self.show_datasets()
            except:
                print("Please enter a correct id 'select_dataset ID' or 'select_dataset' without id to get more information.")

    def do_delete_dataset(self, args):
        arg_list = args.split()
        found = self.show_datasets(display=(len(arg_list) < 1))

        def delete_by_id(sel_index):
            id_to_delete = found[int(sel_index) - 1]
            core_conn.root.delete_by_id(id_to_delete)
            print("Deleted: " + time.strftime('%H:%M:%S %d.%m.%Y', time.localtime(int(id_to_delete))) + " successfully.")

        if len(arg_list) < 1:
            run = True
            while run:
                answer = input("To delete a data set enter the data set id (id could be 1, 2 ..): ")
                if answer == "exit" or answer == "back":
                    run = False
                if run:
                    try:
                        delete_by_id(answer)
                        run = False
                    except:
                        print("Please enter a correct id or 'back'")
        else:
            try:
                delete_by_id(arg_list[0])
            except:
                print("Please enter a correct id 'delete_dataset ID' or 'delete_dataset' without id to get more information.")

    def do_show_p4_dev_results(self, args):
        sw = core_conn.root.p4_dev_results(self.selected_run_id)

        print("\n##### RESULTS FROM P4 TARGET REGISTERS ####\n")
        print("Average latency: " + str(sw["average"][0][0]) + " " + str(sw["average"][1]))
        print("Minimum latency: " + str(sw["min_delta"][0][0]) + " " + str(sw["min_delta"][1]))
        print("Maximum latency: " + str(sw["max_delta"][0][0]) + " " + str(sw["max_delta"][1]))
        print("Range: " + str(sw["range"][0][0]) + " " + str(sw["range"][1]))

        print("\nMeasured for _all_ packets per DUT-port:")
        print("  Packetloss " + str(sw["dut1_real"]) + " <--> " + str(sw["dut2_real"]) + ": " + str(sw["packet_loss_1"]) + " packets, " + str(sw["packet_loss_1_percent"]) + "% (total: " + str(sw["dut1_num_egress_packets"]) + ")")
        print("  Packetloss " + str(sw["dut2_real"]) + " <--> " + str(sw["dut1_real"]) + ": " + str(sw["packet_loss_2"]) + " packets, " + str(sw["packet_loss_2_percent"]) + "% (total: " + str(sw["dut2_num_egress_packets"]) + ")")

        print("\nMeasured only for _timestamped_ packets per DUT-port:")
        print("  Packetloss " + str(sw["dut1_real"]) + " <--> " + str(sw["dut2_real"]) + ": " + str(sw["packet_loss_stamped_1"]) + " packets, " + str(sw["packet_loss_stamped_1_percent"]) + "% (total: " + str(sw["dut1_num_egress_stamped_packets"]) + ")")
        print("  Packetloss " + str(sw["dut2_real"]) + " <--> " + str(sw["dut1_real"]) + ": " + str(sw["packet_loss_stamped_2"]) + " packets, " + str(sw["packet_loss_stamped_2_percent"]) + "% (total: " + str(sw["dut2_num_egress_stamped_packets"]) + ")")

        table = [["In\nport", "Volume\ndata", "Volume\npackets", "Average\nPacket-\nsize\n(Bytes)", "->", "Volume\ndata", "Volume\npackets", "Average\nPacket-\nsize\n(Bytes)", "Out\nport"]]
        for server in sw["loadgen_servers"]:
            ingress_byte = calculate.find_unit_bit_byte(server["num_ingress_bytes"], "byte")
            egress_byte = calculate.find_unit_bit_byte(sw["dut1_num_egress_bytes"], "byte")
            table.append([server["real_port"], str(ingress_byte[0]) + "\n" + ingress_byte[1], str(server["num_ingress_packets"]), str(server["avg_packet_size_ingress"]), "->",
                          str(egress_byte[0]) + "\n" + egress_byte[1], str(sw["dut1_num_egress_packets"]), str(sw["dut1_avg_packet_size_egress"]), sw["dut1_real"]])

        for client in sw["loadgen_clients"]:
            ingress_byte = calculate.find_unit_bit_byte(sw["dut2_num_ingress_bytes"], "byte")
            egress_byte = calculate.find_unit_bit_byte(client["num_egress_bytes"], "byte")
            table.append([sw["dut2_real"], str(ingress_byte[0]) + "\n" + ingress_byte[1], str(sw["dut2_num_ingress_packets"]), str(sw["dut2_avg_packet_size_ingress"]), "->",
                          str(egress_byte[0]) + "\n" + egress_byte[1], str(client["num_egress_packets"]), str(client["avg_packet_size_egress"]), client["real_port"]])

        for client in sw["loadgen_clients"]:
            ingress_byte = calculate.find_unit_bit_byte(client["num_ingress_bytes"], "byte")
            egress_byte = calculate.find_unit_bit_byte(sw["dut2_num_egress_bytes"], "byte")
            table.append([client["real_port"], str(ingress_byte[0]) + "\n" + ingress_byte[1], str(client["num_ingress_packets"]),str(client["avg_packet_size_ingress"]), "->",
                 str(egress_byte[0]) + "\n" + egress_byte[1], str(sw["dut2_num_egress_packets"]), str(sw["dut2_avg_packet_size_egress"]), sw["dut2_real"]])

        for server in sw["loadgen_servers"]:
            ingress_byte = calculate.find_unit_bit_byte(sw["dut1_num_ingress_bytes"], "byte")
            egress_byte = calculate.find_unit_bit_byte(server["num_egress_bytes"], "byte")
            table.append([sw["dut1_real"], str(ingress_byte[0]) + "\n" + ingress_byte[1], str(sw["dut1_num_ingress_packets"]), str(sw["dut1_avg_packet_size_ingress"]), "->",
                 str(egress_byte[0]) + "\n" + egress_byte[1], str(server["num_egress_packets"]), str(server["avg_packet_size_egress"]), server["real_port"]])

        print("\n\n              INGRESS PIPELINE                         EGRESS PIPELINE")
        print(tabulate(table, tablefmt="fancy_grid"))

        print("\n###########################################")

    def do_show_external_results(self, args):

        cfg = P4STA_utils.read_result_cfg(self.selected_run_id)

        extH_results = calculate.main(str(self.selected_run_id), cfg["multicast"], P4STA_utils.get_results_path(selected_run_id)) 
        ipdv_range = extH_results["max_ipdv"] - extH_results["min_ipdv"]
        pdv_range = extH_results["max_pdv"] - extH_results["min_pdv"]
        rate_jitter_range = extH_results["max_packets_per_second"] - extH_results["min_packets_per_second"]
        latency_range = extH_results["max_latency"] - extH_results["min_latency"]


        print("\n\nShowing results from external host for id: " + self.selected_run_id + " from " + time.strftime('%H:%M:%S %d.%m.%Y', time.localtime(int(self.selected_run_id))))
        print("Results from external Host for every " + str(cfg["multicast"] + ". packet") + "\n")
        print("Raw packets: " + str(extH_results["num_raw_packets"]) + " Processed packets: " + str(
            extH_results["num_processed_packets"]) + " Total throughput: " + str(
            extH_results["total_throughput"]) + " Megabytes \n")
        print("Min latency: " + str(calculate.find_unit(extH_results["min_latency"])[0][0]) + " " + str(
            calculate.find_unit(extH_results["min_latency"])[1]))

        print("Max latency: " + str(calculate.find_unit(extH_results["max_latency"])[0][0]) + " " + str(
            calculate.find_unit(extH_results["max_latency"])[1]))
        print("Average latency: " + str(calculate.find_unit(extH_results["avg_latency"])[0][0]) + " " + str(
            calculate.find_unit(extH_results["avg_latency"])[1]) + "\n")
        print("Min IPDV: " + str(calculate.find_unit(extH_results["min_ipdv"])[0][0]) + " " + str(
            calculate.find_unit(extH_results["min_ipdv"])[1]))
        print("Max IPDV: " + str(calculate.find_unit(extH_results["max_ipdv"])[0][0]) + " " + str(
            calculate.find_unit(extH_results["max_ipdv"])[1]))
        print("Average IPDV: " + str(calculate.find_unit(extH_results["avg_ipdv"])[0][0]) + " " + str(
            calculate.find_unit(extH_results["avg_ipdv"])[1])
                + " and abs(): " + str(calculate.find_unit(extH_results["avg_abs_ipdv"])[0][0]) + " " + str(
            calculate.find_unit(extH_results["avg_abs_ipdv"])[1]) + "\n")
        print("Min PDV: " + str(calculate.find_unit(extH_results["min_pdv"])[0][0]) + " " + str(
            calculate.find_unit(extH_results["min_pdv"])[1]))
        print("Max PDV: " + str(calculate.find_unit(extH_results["max_pdv"])[0][0]) + " " + str(
            calculate.find_unit(extH_results["max_pdv"])[1]))
        print("Average PDV: " + str(calculate.find_unit(extH_results["avg_pdv"])[0][0]) + " " + str(
            calculate.find_unit(extH_results["avg_pdv"])[1]) + "\n")
        print("Min packet/s: " + str(extH_results["min_packets_per_second"]))
        print("Max packet/s: " + str(extH_results["max_packets_per_second"]))
        print("Average packet/s: " + str(extH_results["avg_packets_per_second"]) + "\n")

    def do_show_loadgen_results(self, args):
        print("\nShowing results of loadgen for id: " + self.selected_run_id + " from " + time.strftime('%H:%M:%S %d.%m.%Y', time.localtime(int(self.selected_run_id))) + "\n")
        # True = not first run, just reading results again
        process_loadgens = rpyc.timed(core_conn.root.process_loadgens, 60)
        results = process_loadgens(self.selected_run_id)
        results.wait()
        output, total_bits, error, total_retransmits, total_byte, custom_attr, to_plot = results.value

        self.show_loadgen_results(output, total_bits, error, total_retransmits, total_byte, custom_attr, to_plot)


PastaMenu().cmdloop()



