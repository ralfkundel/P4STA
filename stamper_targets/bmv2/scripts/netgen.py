#!/usr/bin/python
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
import datetime
import json
import math
import os
import re
import setproctitle
import signal
import sys
import time

from mininet.net import Mininet
from mininet.topo import Topo
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.node import Node
from mininet.util import waitListening, dumpPorts


# encodes unicode json
def byteify(input):
    if isinstance(input, dict):
        return {byteify(key): byteify(value)
                for key, value in input.iteritems()}
    elif isinstance(input, list):
        return [byteify(elem) for elem in input]
    elif isinstance(input, unicode):
        return input.encode('utf-8')
    else:
        return input


directory = os.path.dirname(os.path.realpath(__file__))
config_path = directory[0:directory.find("stamper")] + "config.json"

# load config entered by user
with open(config_path, "r") as config:
    cfg = byteify(json.load(config))

if "bmv2_dir" in cfg:
    sys.path.append(cfg["bmv2_dir"] + "/mininet/")
    from p4_mininet import P4Switch, P4Host
else:
    print("##################################")
    print("BMV2 dir not set! Please set BMV2 dir.")
    print("##################################")


go = True
# sets the process name for identification
setproctitle.setproctitle("target_bmv2_mininet_module")


# handles SIGTERM and SIGINT signals to stop mininet correctly
def stop_signals_handler(signum, frame):
    global go
    go = False


signal.signal(signal.SIGINT, stop_signals_handler)
signal.signal(signal.SIGTERM, stop_signals_handler)


class LinuxRouter(Node):
    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        # Enable forwarding on the router
        self.cmd("sysctl net.ipv4.ip_forward=1")
        self.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
        self.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")
        self.cmd("sysctl -w net.ipv6.conf.lo.disable_ipv6=1")

    def terminate(self):
        self.cmd("sysctl net.ipv4.ip_forward=0")
        super(LinuxRouter, self).terminate()


class ReturnIngress(Node):
    def config(self, **params):
        super(ReturnIngress, self).config(**params)
        # start script which returns all incoming packets
        self.pid_to_kill = self.cmd(
            "sudo " + directory +
            "/return_ingress.py --interface f1-eth1 & echo $!")
        print("PID of ReturnIngress: " + str(self.pid_to_kill))

    def terminate(self):
        self.cmd("sudo kill " + str(self.pid_to_kill))
        super(ReturnIngress, self).terminate()


class MyTopo(Topo):
    def __init__(self, sw_path, json_path, **opts):
        # Initialize topology and default options
        Topo.__init__(self, **opts)
        # Initialize managementSwitch (for SSH) and switch (for P4 code)
        managementSwitch = self.addSwitch("s99")
        switch = self.addSwitch("s1",
                                cls=P4Switch,
                                sw_path=sw_path,
                                json_path=json_path,
                                thrift_port=22223,
                                pcap_dump=False,
                                log_console=False,
                                device_id=1)
        use_port_counter = 0
        for dut in cfg["dut_ports"]:
            if dut["use_port"] == "checked":
                use_port_counter = use_port_counter + 1
        # simulates our DUT and routes packets from one port to another
        if use_port_counter > 1 \
                and cfg["dut_ports"][0]["use_port"] == "checked":
            self.addNode(
                "f1", cls=LinuxRouter,
                ip="10.0.1.1/24", mac="aa:aa:aa:aa:ff:01")
            # regex filters for numbers just in case special chars made it to
            # the config file. Mininet will crash otherwise.
            stamper_port = 1
            for dut in cfg["dut_ports"]:
                if dut["use_port"] == "checked":
                    self.addLink(
                        "f1", "s1", stamper_port,
                        int(re.findall(r'\d+', dut["p4_port"])[0]))
                    stamper_port = stamper_port + 1
        else:
            print("Only one Dut port used ... "
                  "Starting 'ReturnIngress' virtual DUT")
            # one port DUT which returns the ingress packets
            # directly without change
            for dut in cfg["dut_ports"]:
                if dut["use_port"] == "checked":
                    self.addNode(
                        "f1", cls=ReturnIngress,
                        ip="10.0." + str(dut["id"]) + ".1/24",
                        mac="aa:aa:aa:aa:ff:01")
                    self.addLink("f1", "s1", 1, int(
                        re.findall(r'\d+', dut["p4_port"])[0]))
                    break  # because only one dut is "checked"

        # external host which receives the duplicates
        self.addHost("extH", ip=cfg["ext_host_ssh"])
        self.addLink("extH", "s99")
        self.addLink("extH", "s1", 1, int(
            re.findall(r'\d+', cfg["ext_host"])[0]))

        counter = 1
        for loadgen_grp in cfg["loadgen_groups"]:
            if loadgen_grp["use_group"] == "checked":
                # rounds up to next 10 step
                counter = int(math.ceil(float(counter)/10)*10)
                # if all loadgen groups are less than 10 hosts
                # group 1 gets h10, h11 ... group 2 gets h20, h21..
                for host in loadgen_grp["loadgens"]:
                    self.addHost(
                        "h" + str(counter), ip=str(host["ssh_ip"]) + "/24")
                    self.addLink("h" + str(counter), "s99")  # management
                    # overwrite user ip input
                    # ip 1 is saved for DUT(router)
                    host["loadgen_ip"] = "10.0." + str(loadgen_grp["group"]) \
                                         + "." + str(host["id"] + 1)
                    print("Setting Group " + str(
                        loadgen_grp["group"]) + " | Host " + str(
                        host["id"]) + " to IP " + host["loadgen_ip"])
                    self.addLink("h" + str(counter), "s1", 1, int(
                        re.findall(r'\d+', host["p4_port"])[0]),
                                 params1={"ip": host["loadgen_ip"] + "/24"})
                    host["mn_name"] = "h" + str(counter)
                    counter = counter + 1


def main():
    json_path = directory[0:directory.find(
        "scripts")] + "data/" + cfg["program"] + ".json"
    switch_path = cfg["bmv2_dir"] + "/targets/simple_switch/simple_switch"
    topo = MyTopo(sw_path=switch_path, json_path=json_path)
    net = Mininet(topo=topo, host=P4Host, link=TCLink, autoStaticArp=True)
    ssh_ips = []
    route_to = ".".join(cfg["stamper_ssh"].split(".")[:3]) + ".0/24"
    route_via = ".".join(cfg["ext_host_ssh"].split(".")[:3]) + ".1"

    for loadgen_grp in cfg["loadgen_groups"]:
        if loadgen_grp["use_group"] == "checked":
            for host in loadgen_grp["loadgens"]:
                host["mn_host_object"] = net.get(host["mn_name"])
                # always autogen MAC
                host["loadgen_mac"] = "22:22:22:22:" + \
                                      format(loadgen_grp["group"], "02d") + \
                                      ":" + format(host["id"], "02d")
                host["mn_host_object"].intf(host["mn_name"] + "-eth1").setMAC(
                    host["loadgen_mac"])
                # if bmv2 docker is used, IP must be set here
                host["mn_host_object"].intf(host["mn_name"] + "-eth1").setIP(
                    host["loadgen_ip"] + "/24")
                for loadgen_grp2 in cfg["loadgen_groups"]:
                    if loadgen_grp["group"] != loadgen_grp2["group"] \
                            and loadgen_grp2["use_group"] == "checked":
                        host["mn_host_object"].cmd(
                            "ip route add 10.0." +
                            str(loadgen_grp2["group"]) + ".0/24 via 10.0." +
                            str(loadgen_grp["group"]) + ".1 dev " +
                            host["mn_name"] + "-eth1"
                        )
                        print("ip route add 10.0." +
                              str(loadgen_grp2["group"]) +
                              ".0/24 via 10.0." + str(loadgen_grp["group"]) +
                              ".1 dev " + host["mn_name"] + "-eth1"
                              )
                host["mn_host_object"].cmd("ip route add " + route_to +
                                           " via " + route_via + " dev eth0")
                print("ip route add " + route_to + " via " + route_via +
                      " dev eth0")
                ssh_ips.append(host["ssh_ip"].split("."))

    # check if all user chosen ssh ips are in the same /24 subnet.
    success = 0
    for i in range(len(ssh_ips)):
        if i > 0:
            if ssh_ips[i][0:3] == ssh_ips[i-1][0:3]:
                success = success + 1
    root_eth = "10.99.99.1/32"
    routes = ["10.99.99.0/24"]
    if success == len(ssh_ips) - 1:
        root_eth = ".".join(ssh_ips[0][0:3]) + ".1/32"
        routes = [".".join(ssh_ips[0][0:3]) + ".0/24"]
        print("Use " + root_eth + " as IP for root-eth.")

    sshd(net, switch=net['s99'], ip=root_eth, routes=routes)

    external_host = net.get("extH")
    external_host.cmd(
        "ip route add " + route_to + " via " + route_via + " dev eth0")

    f1 = net.get("f1")
    f1.intf("f1-eth1").setMAC("aa:aa:aa:aa:ff:01")
    f1.intf("f1-eth1").setIP("10.0.1.1/24")

    for dut in cfg["dut_ports"]:
        if dut["use_port"] == "checked" and int(dut["id"]) != 1:
            f1.intf("f1-eth" + str(dut["id"])).setMAC(
                "aa:aa:aa:aa:ff:" + format(dut["id"], "02d"))
            f1.intf("f1-eth" + str(dut["id"])).setIP(
                "10.0." + str(dut["id"]) + ".1/24")

    log = [str(datetime.datetime.now()) + "\n"]
    links = topo.links(withInfo=True)

    for link in links:
        tmp = link[2]
        if tmp["node2"] is not "s99":
            line = tmp["node1"] + " || " + str(tmp["port1"]) + " <--> " + \
                   str(tmp["port2"]) + " || " + tmp["node2"] + "\n"
            log.append(line)

    log.append("\nConfig:\n")
    for loadgen_grp in cfg["loadgen_groups"]:
        if loadgen_grp["use_group"] == "checked":
            log.append("Loadgen Group: " + str(loadgen_grp["group"]) + "\n")
            for host in loadgen_grp["loadgens"]:
                log.append("Host " + str(host["id"]) + ": " + host["mn_name"] +
                           " | " + host["loadgen_iface"] + " " +
                           host["loadgen_ip"] + " " + host["loadgen_mac"] +
                           "\n")

    log.append("Mininet IP config:\n")
    for link in links:
        if "params1" in link[2]:
            log.append(link[0] + ": " + link[2]["params1"]["ip"] + "\n")

    log.append("Management network for SSH connections: \n")
    for link in links:
        tmp = link[2]
        if tmp["node2"] is not "s1":
            line = tmp["node1"] + " || " + str(tmp["port1"]) + " <--> " + \
                   str(tmp["port2"]) + " || " + tmp["node2"] + "\n"
            log.append(line)
    log.append("\n")
    log.append("PID ext. host: " + external_host.cmd("echo $$"))
    log.append("PID dut f1: " + f1.cmd("echo $$"))

    with open(
            directory[0:directory.find("scripts")] + "data/mn.log", "wr") as f:
        f.writelines(log)

    s1 = net.get("s1")
    s1.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
    s1.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")
    s1.cmd("sysctl -w net.ipv6.conf.lo.disable_ipv6=1")

    print("Ready !")

    # cli is not needed because of HTML GUI
    # CLI(net)

    while go:
        time.sleep(0.2)

    # stop all sshd servers and stop mininet instance
    for host in net.hosts:
        host.cmd("kill %" + "/usr/sbin/sshd")
    net.stop()


def sshd(network, cmd="/usr/sbin/sshd", opts="-D", ip="10.99.99.1/32",
         routes=None, switch=None):
    """Start a network, connect it to root ns, and run sshd on all hosts.
       ip: root-eth0 IP address in root namespace (10.123.123.1/32)
       routes: Mininet host networks to route to (10.0/24)
       switch: Mininet switch to connect to root namespace (s1)"""
    connectToRootNS(network, switch, ip, routes)
    for host in network.hosts:
        host.cmd(cmd + " " + opts + "&")
    info("*** Waiting for ssh daemons to start\n")
    for server in network.hosts:
        if server.name is not "f1":
            waitListening(server=server, port=22, timeout=5)
    info("\n*** Hosts are running sshd at the following addresses:\n")
    for host in network.hosts:
        if host.name is not "f1":
            info(host.name, host.IP(), "\n")


def connectToRootNS(network, switch, ip, routes):
    """Connect hosts to root namespace via switch. Starts network.
      network: Mininet() network object
      switch: switch to connect to root namespace
      ip: IP address for root namespace node
      routes: host networks to route to"""
    # Create a node in root namespace and link to switch 0
    root = Node("root", inNamespace=False)
    intf = network.addLink(root, switch).intf1
    root.setIP(ip, intf=intf)
    # Start network that now includes link to root namespace
    network.start()
    # Add routes from root ns to hosts
    for route in routes:
        root.cmd("route add -net " + route + " dev " + str(intf))


if __name__ == "__main__":
    setLogLevel("info")
    if cfg["selected_target"] == "bmv2":
        if "bmv2_dir" in cfg:
            main()
    else:
        print("Selected target is not bmv2!")
