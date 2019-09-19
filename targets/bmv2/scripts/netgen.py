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
import argparse
import os
import subprocess
import time
import json
import sys
import signal
import setproctitle
import re

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
path = directory[0:directory.find("targets")] + "data/config.json"

# load config entered by user
with open(path, "r") as config:
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

parser = argparse.ArgumentParser(description="Mininet demo")
parser.add_argument("--switch", help="Path to the switch which should be used in this exercise", type=str, action="store", required=True)
parser.add_argument("--cli", help="Path to BM CLI", type=str, action="store", required=True)
args = parser.parse_args()


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
        self.cmd("sudo " + directory + "/return_ingress.py --interface f1-eth1 &")

    def terminate(self):
        self.cmd("sudo killall raw_socket_returner")
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
        # simulates our DUT and routes packets from one port to another
        if cfg["dut1"] != cfg["dut2"]:
            self.addNode("f1", cls=LinuxRouter, ip="10.0.1.1/24", mac="aa:aa:aa:aa:ff:01")
            # regex filters for numbers just in case special chars made it to the config file. Mininet will crash otherwise.
            self.addLink("f1", "s1", 1, int(re.findall(r'\d+', cfg["dut1"])[0]))
            self.addLink("f1", "s1", 2, int(re.findall(r'\d+', cfg["dut2"])[0]))
        else:
            # one port DUT which returns the ingress packets directly without change
            self.addNode("f1", cls=ReturnIngress, ip="10.0.1.1/24", mac="aa:aa:aa:aa:ff:01")
            self.addLink("f1", "s1", 1, int(re.findall(r'\d+', cfg["dut1"])[0]))

        # external host which receives the duplicates
        self.addHost("extH", ip=cfg["ext_host_ssh"])
        self.addLink("extH", "s99")
        self.addLink("extH", "s1", 1, int(re.findall(r'\d+', cfg["ext_host"])[0]))

        counter = 1
        for host in (cfg["loadgen_servers"]):
            self.addHost("h" + str(counter), ip=str(host["ssh_ip"]) + "/24")
            self.addLink("h" + str(counter), "s99")  # management
            self.addLink("h" + str(counter), "s1", 1, int(re.findall(r'\d+', host["p4_port"])[0]), params1={"ip": host["loadgen_ip"] + "/24"})  # load
            host["mn_name"] = "h" + str(counter)
            counter = counter + 1

        counter = 51
        for host in (cfg["loadgen_clients"]):
            self.addHost("h" + str(counter), ip=str(host["ssh_ip"]) + "/24")
            self.addLink("h" + str(counter), "s99")  # management
            self.addLink("h" + str(counter), "s1", 1, int(re.findall(r'\d+', host["p4_port"])[0]), params1={"ip": host["loadgen_ip"] + "/24"})  # load
            host["mn_name"] = "h" + str(counter)
            counter = counter + 1


def main():
    json_path = directory[0:directory.find("scripts")] + "data/" + cfg["program"] + ".json"

    topo = MyTopo(sw_path=args.switch, json_path=json_path)
    net = Mininet(topo=topo, host=P4Host, link=TCLink, autoStaticArp=True)
    ssh_ips = []
    for host in cfg["loadgen_servers"]:
        host["mn_host_object"] = net.get(host["mn_name"])
        if host["loadgen_mac"] == "": # auto gen mac if no mac adress is set by user
            host["loadgen_mac"] = "22:22:22:22:22:2" + host["mn_name"][-1:]
        host["mn_host_object"].intf(host["mn_name"] + "-eth1").setMAC(host["loadgen_mac"])
        host["mn_host_object"].cmd("ip route add 10.0.2.0/24 via 10.0.1.1 dev " + host["mn_name"] + "-eth1")
        ssh_ips.append(host["ssh_ip"].split("."))

    for host in cfg["loadgen_clients"]:
        host["mn_host_object"] = net.get(host["mn_name"])
        if host["loadgen_mac"] == "": # auto gen mac if no mac adress is set by user
            host["loadgen_mac"] = "22:22:22:33:33:3" + host["mn_name"][-1:]
        host["mn_host_object"].intf(host["mn_name"] + "-eth1").setMAC(host["loadgen_mac"])
        host["mn_host_object"].cmd("ip route add 10.0.1.0/24 via 10.0.2.1 dev " + host["mn_name"] + "-eth1")
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

    f1 = net.get("f1")
    f1.intf("f1-eth1").setMAC("aa:aa:aa:aa:ff:01")
    f1.intf("f1-eth1").setIP("10.0.1.1/24")
    if cfg["dut1"] != cfg["dut2"]:
        f1.intf("f1-eth2").setMAC("aa:aa:aa:aa:ff:02")
        f1.intf("f1-eth2").setIP("10.0.2.1/24")

    log = []
    links = topo.links(withInfo=True)

    for link in links:
        tmp = link[2]
        if tmp["node2"] is not "s99":
            line = tmp["node1"] + " || " + str(tmp["port1"]) + " <--> " + str(tmp["port2"]) + " || " + tmp["node2"] + "\n"
            log.append(line)

    log.append("Management network for SSH connections: \n")
    for link in links:
        tmp = link[2]
        if tmp["node2"] is not "s1":
            line = tmp["node1"] + " || " + str(tmp["port1"]) + " <--> " + str(tmp["port2"]) + " || " + tmp["node2"] + "\n"
            log.append(line)
    log.append("\n")
    log.append("PID ext. host: " + external_host.cmd("echo $$"))
    log.append("PID dut f1: " + f1.cmd("echo $$"))

    with open(directory[0:directory.find("scripts")] + "data/mn.log", "wr") as f:
        f.writelines(log)

    s1 = net.get("s1")
    s1.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
    s1.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")
    s1.cmd("sysctl -w net.ipv6.conf.lo.disable_ipv6=1")

    lag = "SimplePreLAG"
    cmd = [args.cli, "--pre", lag, "--json", json_path, "--thrift-port", str(22223)]
    with open(directory[0:directory.find("scripts")] + "data/" + "commands1_middlebox1.txt", "r") as f:
        try:
            output = subprocess.check_output(cmd, stdin=f)
        except subprocess.CalledProcessError as e:
            print (e)

    print("Ready !")

    #CLI(net) # cli is not needed because of GUI

    while go:
        time.sleep(0.2)

    # stop all sshd servers and stop mininet instance
    for host in net.hosts:
        host.cmd("kill %" + "/usr/sbin/sshd")
    net.stop()


def sshd(network, cmd="/usr/sbin/sshd", opts="-D", ip="10.99.99.1/32", routes=None, switch=None):
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
