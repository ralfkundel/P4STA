import copy
import csv
import ptf
import ptf.testutils as testutils
import time
import os
import subprocess
import sys

from ptf.base_tests import BaseTest
from ptf.mask import Mask
from ptf.testutils import *
from scapy.all import Ether, IP, TCP, Raw, RandString

sys.path.append("tests/ptf")
sys.path.append("stamper_targets/Wedge100B65/")
sys.path.append("core/")
try:
    from cfg import cfg
    import tofino1_65p_stamper_v1_2_0
    import p4sta_ptf_base_tcp
    import p4sta_ptf_base_udp
    import p4sta_ptf_encap_tcp
    import p4sta_ptf_encap_udp
except Exception as e:
    print(e)

target_cfg = {"p4_ports": [], "nr_ports": 18}
for i in range(17):
    target_cfg["p4_ports"].append(str(i))
target_cfg["p4_ports"].append("64")

target_tofino = tofino1_65p_stamper_v1_2_0.TargetImpl(target_cfg)

cfg = {
    "available_loadgens": [
        "iperf3"
    ],
    "dut_ports": [
        {
            "an": "default",
            "fec": "NONE",
            "id": 1,
            "p4_port": "3",
            "real_port": "1/3",
            "shape": "",
            "speed": "10G",
            "stamp_outgoing": "checked",
            "use_port": "checked",
            "dataplane_duplication": "0"
        },
        {
            "an": "default",
            "fec": "NONE",
            "id": 2,
            "p4_port": "4",
            "real_port": "2/0",
            "shape": "",
            "speed": "10G",
            "stamp_outgoing": "checked",
            "use_port": "checked",
            "dataplane_duplication": "0"
        }
    ],
    "ext_host": "5",
    "ext_host_an": "default",
    "ext_host_fec": "NONE",
    "ext_host_if": "na",
    "ext_host_real": "2/1",
    "ext_host_shape": "",
    "ext_host_speed": "10G",
    "ext_host_ssh": "",
    "ext_host_user": "root",
    "forwarding_mode": "2",
    "loadgen_groups": [
        {
            "group": 1,
            "loadgens": [
                {
                    "an": "default",
                    "fec": "NONE",
                    "id": 1,
                    "loadgen_iface": "na",
                    "loadgen_ip": "10.0.1.3",
                    "loadgen_mac": "22:22:22:22:22:22",
                    "p4_port": "1",
                    "real_port": "1",
                    "shape": "",
                    "speed": "10G",
                    "ssh_ip": "0.0.0.0",
                    "ssh_user": "root"
                }
            ],
            "use_group": "checked"
        },
        {
            "group": 2,
            "loadgens": [
                {
                    "an": "default",
                    "fec": "NONE",
                    "id": 1,
                    "loadgen_iface": "na",
                    "loadgen_ip": "10.0.2.4",
                    "loadgen_mac": "22:22:22:33:33:33",
                    "p4_port": "2",
                    "real_port": "1/2",
                    "shape": "",
                    "speed": "10G",
                    "ssh_ip": "0.0.0.0",
                    "ssh_user": "root"
                },
                {
                    "an": "default",
                    "fec": "NONE",
                    "id": 2,
                    "loadgen_iface": "na",
                    "loadgen_ip": "10.0.2.5",
                    "loadgen_mac": "22:22:22:33:33:34",
                    "p4_port": "6",
                    "real_port": "2/2",
                    "shape": "",
                    "speed": "10G",
                    "ssh_ip": "0.0.0.0",
                    "ssh_user": "root"
                }
            ],
            "use_group": "checked"
        }
    ],
    "multicast": "1",
    "stamper_ssh": "0.0.0.0",
    "stamper_user": "root",
    "program": "tofino_stamper_v1_2_0",
    "sde": "/opt/bf-sde-9.13.0",
    "selected_extHost": "PythonExtHost",
    "selected_loadgen": "iperf3",
    "selected_target": "tofino_model",
    "stamp_tcp": "checked",
    "stamp_udp": "checked"
}


########################################
# TOF Group2ToDut2
class TOF_L1_Group2ToDut2_TCP(p4sta_ptf_base_tcp.Group2ToDut2):
    def setUp(self):
        p4sta_ptf_base_tcp.Group2ToDut2.setUp(self)
        cfg["forwarding_mode"] = "1"
        target_tofino.deploy(cfg)


class TOF_L1_Group2ToDut2_UDP(p4sta_ptf_base_udp.Group2ToDut2):
    def setUp(self):
        p4sta_ptf_base_udp.Group2ToDut2.setUp(self)
        cfg["forwarding_mode"] = "1"
        target_tofino.deploy(cfg)


class TOF_L2_Group2ToDut2_TCP(p4sta_ptf_base_tcp.Group2ToDut2):
    def setUp(self):
        p4sta_ptf_base_tcp.Group2ToDut2.setUp(self)
        cfg["forwarding_mode"] = "2"
        target_tofino.deploy(cfg)


class TOF_L2_Group2ToDut2_UDP(p4sta_ptf_base_udp.Group2ToDut2):
    def setUp(self):
        p4sta_ptf_base_udp.Group2ToDut2.setUp(self)
        cfg["forwarding_mode"] = "2"
        target_tofino.deploy(cfg)


class TOF_L3_Group2ToDut2_TCP(p4sta_ptf_base_tcp.Group2ToDut2):
    def setUp(self):
        p4sta_ptf_base_tcp.Group2ToDut2.setUp(self)
        cfg["forwarding_mode"] = "3"
        target_tofino.deploy(cfg)


class TOF_L3_Group2ToDut2_UDP(p4sta_ptf_base_udp.Group2ToDut2):
    def setUp(self):
        p4sta_ptf_base_udp.Group2ToDut2.setUp(self)
        cfg["forwarding_mode"] = "3"
        target_tofino.deploy(cfg)


########################################
# TOF Dut1ToGroup1
class TOF_L1_Dut1ToGroup1_TCP(p4sta_ptf_base_tcp.Dut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_tcp.Dut1ToGroup1.setUp(self)
        cfg["forwarding_mode"] = "1"
        target_tofino.deploy(cfg)


class TOF_L1_Dut1ToGroup1_UDP(p4sta_ptf_base_udp.Dut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_udp.Dut1ToGroup1.setUp(self)
        cfg["forwarding_mode"] = "1"
        target_tofino.deploy(cfg)


class TOF_L2_Dut1ToGroup1_TCP(p4sta_ptf_base_tcp.Dut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_tcp.Dut1ToGroup1.setUp(self)
        cfg["forwarding_mode"] = "2"
        target_tofino.deploy(cfg)


class TOF_L2_Dut1ToGroup1_UDP(p4sta_ptf_base_udp.Dut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_udp.Dut1ToGroup1.setUp(self)
        cfg["forwarding_mode"] = "2"
        target_tofino.deploy(cfg)


class TOF_L3_Dut1ToGroup1_TCP(p4sta_ptf_base_tcp.Dut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_tcp.Dut1ToGroup1.setUp(self)
        cfg["forwarding_mode"] = "3"
        target_tofino.deploy(cfg)


class TOF_L3_Dut1ToGroup1_UDP(p4sta_ptf_base_udp.Dut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_udp.Dut1ToGroup1.setUp(self)
        cfg["forwarding_mode"] = "3"
        target_tofino.deploy(cfg)


########################################
# TOF Group1ToDut1
class TOF_L1_Group1ToDut1_TCP(p4sta_ptf_base_tcp.Group1ToDut1):
    def setUp(self):
        p4sta_ptf_base_tcp.Group1ToDut1.setUp(self)
        cfg["forwarding_mode"] = "1"
        target_tofino.deploy(cfg)


class TOF_L1_Group1ToDut1_UDP(p4sta_ptf_base_udp.Group1ToDut1):
    def setUp(self):
        p4sta_ptf_base_udp.Group1ToDut1.setUp(self)
        cfg["forwarding_mode"] = "1"
        target_tofino.deploy(cfg)


class TOF_L2_Group1ToDut1_TCP(p4sta_ptf_base_tcp.Group1ToDut1):
    def setUp(self):
        p4sta_ptf_base_tcp.Group1ToDut1.setUp(self)
        cfg["forwarding_mode"] = "2"
        target_tofino.deploy(cfg)


class TOF_L2_Group1ToDut1_TCP_DP_DUP(p4sta_ptf_base_tcp.Group1ToDut1):
    def setUp(self):
        p4sta_ptf_base_tcp.Group1ToDut1.setUp(self)
        self.dataplane_duplication = 3
        cfg["forwarding_mode"] = "2"
        cfg["dut_ports"][0]["dataplane_duplication"] = "3"
        cfg["dut_ports"][1]["dataplane_duplication"] = "3"
        target_tofino.deploy(cfg)
        cfg["dut_ports"][0]["dataplane_duplication"] = "0"
        cfg["dut_ports"][1]["dataplane_duplication"] = "0"


class TOF_L2_Group1ToDut1_UDP(p4sta_ptf_base_udp.Group1ToDut1):
    def setUp(self):
        p4sta_ptf_base_udp.Group1ToDut1.setUp(self)
        cfg["forwarding_mode"] = "2"
        target_tofino.deploy(cfg)


class TOF_L3_Group1ToDut1_TCP(p4sta_ptf_base_tcp.Group1ToDut1):
    def setUp(self):
        p4sta_ptf_base_tcp.Group1ToDut1.setUp(self)
        cfg["forwarding_mode"] = "3"
        target_tofino.deploy(cfg)


class TOF_L3_Group1ToDut1_UDP(p4sta_ptf_base_udp.Group1ToDut1):
    def setUp(self):
        p4sta_ptf_base_udp.Group1ToDut1.setUp(self)
        cfg["forwarding_mode"] = "3"
        target_tofino.deploy(cfg)


########################################
# TOF Dut2ToGroup2

# L1 with 2 destination hosts can not work => cut to 1 host per group
class TOF_L1_Dut2ToGroup2_TCP(p4sta_ptf_base_tcp.Dut2ToGroup2):
    def setUp(self):
        p4sta_ptf_base_tcp.Dut2ToGroup2.setUp(self, l1=True)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "1"
        cfg2["loadgen_groups"][1]["loadgens"] = [
            cfg2["loadgen_groups"][1]["loadgens"][0]]
        target_tofino.deploy(cfg2)


# L1 with 2 destination hosts can not work => cut to 1 host per group
class TOF_L1_Dut2ToGroup2_UDP(p4sta_ptf_base_udp.Dut2ToGroup2):
    def setUp(self):
        p4sta_ptf_base_udp.Dut2ToGroup2.setUp(self, l1=True)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "1"
        cfg2["loadgen_groups"][1]["loadgens"] = [
            cfg2["loadgen_groups"][1]["loadgens"][0]]
        target_tofino.deploy(cfg2)


class TOF_L2_Dut2ToGroup2_TCP(p4sta_ptf_base_tcp.Dut2ToGroup2):
    def setUp(self):
        p4sta_ptf_base_tcp.Dut2ToGroup2.setUp(self)
        cfg["forwarding_mode"] = "2"
        target_tofino.deploy(cfg)


class TOF_L2_Dut2ToGroup2_UDP(p4sta_ptf_base_udp.Dut2ToGroup2):
    def setUp(self):
        p4sta_ptf_base_udp.Dut2ToGroup2.setUp(self)
        cfg["forwarding_mode"] = "2"
        target_tofino.deploy(cfg)


class TOF_L3_Dut2ToGroup2_TCP(p4sta_ptf_base_tcp.Dut2ToGroup2):
    def setUp(self):
        p4sta_ptf_base_tcp.Dut2ToGroup2.setUp(self)
        cfg["forwarding_mode"] = "3"
        target_tofino.deploy(cfg)


class TOF_L3_Dut2ToGroup2_UDP(p4sta_ptf_base_udp.Dut2ToGroup2):
    def setUp(self):
        p4sta_ptf_base_udp.Dut2ToGroup2.setUp(self)
        cfg["forwarding_mode"] = "3"
        target_tofino.deploy(cfg)


# test if NO timestamp header is added if dut_2_outgoing_stamp = unchecked
class TOF_L2_Group2ToDut2_TCP_no_stamp(p4sta_ptf_base_tcp.Group2ToDut2):
    def setUp(self):
        p4sta_ptf_base_tcp.Group2ToDut2.setUp(self)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "2"
        cfg2["dut_ports"][1]["stamp_outgoing"] = "unchecked"
        target_tofino.deploy(cfg2)

    def runTest(self):
        random_load = str(RandString(size=1400))
        pkt1 = Ether(dst="aa:aa:aa:aa:ff:02", src="22:22:22:33:33:33") / IP(
            src="10.0.2.4", dst="10.0.1.3") / TCP(sport=0xeeff,
                                                  dport=50000) / Raw(
            load=random_load)

        send_packet(self, 2, pkt1)

        verify_packets(self, pkt1, ports=[4])


# test if multicast counter works (5=every 5th packet duplicated to ext host)
class TOF_L2_Dut2ToGroup2_TCP_multicast_thresh_5(p4sta_ptf_base_tcp.
                                                 Dut2ToGroup2):
    def setUp(self):
        p4sta_ptf_base_tcp.Dut2ToGroup2.setUp(self)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "2"
        cfg2["multicast"] = "5"
        target_tofino.deploy(cfg2)

    def runTest(self):
        random_load = str(RandString(size=1400))
        pkt1 = Ether(dst="22:22:22:33:33:33", src="aa:aa:aa:aa:ff:02") / IP(
            src="10.0.1.3", dst="10.0.2.4") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
            )]) / Raw(load=random_load)

        # 12 bytes * 0xbb = placeholder and gets ignored by set_do_not_care
        exp_pkt_1 = Ether(
            dst="22:22:22:33:33:33", src="aa:aa:aa:aa:ff:02") / IP(
            src="10.0.1.3", dst="10.0.2.4") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
            )]) / Raw(load=random_load)

        exp_pkt_ext_host_1 = Ether(dst="ff:ff:ff:ff:ff:ff",
                                   src="aa:aa:aa:aa:ff:02") / IP(
            src="10.0.1.3", dst="10.0.2.4") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
            )]) / Raw(load=random_load)

        pkt1.show2()
        send_packet(self, 4, pkt1, 5)
        time.sleep(1)

        m = Mask(exp_pkt_1)
        m.set_do_not_care_scapy(TCP, "chksum")
        # timestamp2 is 6 byte long, starts at bit 512 (starting from Eth Hdr)
        m.set_do_not_care(448 + (8 * 8), 48)
        for i in range(5):
            print("Verify packet iter " + str(i))
            verify_packet(self, m, port_id=2, timeout=5)

        m = Mask(exp_pkt_ext_host_1)
        m.set_do_not_care_scapy(TCP, "chksum")
        # timestamp2 is 6 byte long, starts at bit 512 (starting from Eth Hdr)
        m.set_do_not_care(448 + (8 * 8), 48)
        verify_packet(self, m, port_id=5)

        verify_no_other_packets(self)


########################################
# TOF Only1DUTGroup1ToDut1
# L1 forwarding does not work with one DUT port only!


class TOF_L2_Only1DUTGroup1ToDut1_TCP(p4sta_ptf_base_tcp.Only1DUTGroup1ToDut1):
    def setUp(self):
        p4sta_ptf_base_tcp.Only1DUTGroup1ToDut1.setUp(self, l1=False)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "2"
        cfg2["loadgen_groups"] = [cfg2["loadgen_groups"][0]]
        new_serv = {
            "id": 2,
            "loadgen_iface": "dontcare",
            "loadgen_ip": "10.0.1.4",
            "loadgen_mac": "22:22:22:22:22:23",
            "p4_port": "2",
            "real_port": "1/2",
            "ssh_ip": "10.99.66.4",
            "ssh_user": "root",
            "speed": "10G",
            "shape": "",
            "fec": "NONE",
            "an": "default"
        }
        cfg2["loadgen_groups"][0]["loadgens"].append(new_serv)
        cfg2["dut_ports"][1]["use_port"] = "unchecked"
        target_tofino.deploy(cfg2)


class TOF_L2_Only1DUTGroup1ToDut1_UDP(p4sta_ptf_base_udp.Only1DUTGroup1ToDut1):
    def setUp(self):
        p4sta_ptf_base_udp.Only1DUTGroup1ToDut1.setUp(self, l1=False)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "2"
        cfg2["loadgen_groups"] = [cfg2["loadgen_groups"][0]]
        new_serv = {
            "id": 2,
            "loadgen_iface": "dontcare",
            "loadgen_ip": "10.0.1.4",
            "loadgen_mac": "22:22:22:22:22:23",
            "p4_port": "2",
            "real_port": "1/2",
            "ssh_ip": "10.99.66.4",
            "ssh_user": "root",
            "speed": "10G",
            "shape": "",
            "fec": "NONE",
            "an": "default"
        }
        cfg2["loadgen_groups"][0]["loadgens"].append(new_serv)
        cfg2["dut_ports"][1]["use_port"] = "unchecked"
        target_tofino.deploy(cfg2)


class TOF_L3_Only1DUTGroup1ToDut1_TCP(p4sta_ptf_base_tcp.Only1DUTGroup1ToDut1):
    def setUp(self):
        p4sta_ptf_base_tcp.Only1DUTGroup1ToDut1.setUp(self, l1=False)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "3"
        cfg2["loadgen_groups"] = [cfg2["loadgen_groups"][0]]
        new_serv = {
            "id": 2,
            "loadgen_iface": "dontcare",
            "loadgen_ip": "10.0.1.4",
            "loadgen_mac": "22:22:22:22:22:23",
            "p4_port": "2",
            "real_port": "1/2",
            "ssh_ip": "10.99.66.4",
            "ssh_user": "root",
            "speed": "10G",
            "shape": "",
            "fec": "NONE",
            "an": "default"
        }
        cfg2["loadgen_groups"][0]["loadgens"].append(new_serv)
        cfg2["dut_ports"][1]["use_port"] = "unchecked"
        target_tofino.deploy(cfg2)


class TOF_L3_Only1DUTGroup1ToDut1_UDP(p4sta_ptf_base_udp.Only1DUTGroup1ToDut1):
    def setUp(self):
        p4sta_ptf_base_udp.Only1DUTGroup1ToDut1.setUp(self, l1=False)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "3"
        cfg2["loadgen_groups"] = [cfg2["loadgen_groups"][0]]
        new_serv = {
            "id": 2,
            "loadgen_iface": "dontcare",
            "loadgen_ip": "10.0.1.4",
            "loadgen_mac": "22:22:22:22:22:23",
            "p4_port": "2",
            "real_port": "1/2",
            "ssh_ip": "10.99.66.4",
            "ssh_user": "root",
            "speed": "10G",
            "shape": "",
            "fec": "NONE",
            "an": "default"
        }
        cfg2["loadgen_groups"][0]["loadgens"].append(new_serv)
        cfg2["dut_ports"][1]["use_port"] = "unchecked"
        target_tofino.deploy(cfg2)


########################################
# TOF Only1DUTDut1ToGroup1
# L1 forwarding does not work with one DUT port only!

class TOF_L2_Only1DUTDut1ToGroup1_TCP(p4sta_ptf_base_tcp.Only1DUTDut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_tcp.Only1DUTDut1ToGroup1.setUp(self, l1=False)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "2"
        cfg2["loadgen_groups"] = [cfg2["loadgen_groups"][0]]
        new_serv = {
            "id": 2,
            "loadgen_iface": "dontcare",
            "loadgen_ip": "10.0.1.4",
            "loadgen_mac": "22:22:22:22:22:23",
            "p4_port": "2",
            "real_port": "1/2",
            "ssh_ip": "10.99.66.4",
            "ssh_user": "root",
            "speed": "10G",
            "shape": "",
            "fec": "NONE",
            "an": "default"
        }
        cfg2["loadgen_groups"][0]["loadgens"].append(new_serv)
        cfg2["dut_ports"][1]["use_port"] = "unchecked"
        target_tofino.deploy(cfg2)


class TOF_L2_Only1DUTDut1ToGroup1_TCP_DP_DUP(p4sta_ptf_base_tcp.
                                             Only1DUTDut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_tcp.Only1DUTDut1ToGroup1.setUp(self, l1=False)
        self.dataplane_duplication = 3
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "2"
        cfg2["loadgen_groups"] = [cfg2["loadgen_groups"][0]]
        new_serv = {
            "id": 2,
            "loadgen_iface": "dontcare",
            "loadgen_ip": "10.0.1.4",
            "loadgen_mac": "22:22:22:22:22:23",
            "p4_port": "2",
            "real_port": "1/2",
            "ssh_ip": "10.99.66.4",
            "ssh_user": "root",
            "speed": "10G",
            "shape": "",
            "fec": "NONE",
            "an": "default"
        }
        cfg2["loadgen_groups"][0]["loadgens"].append(new_serv)
        cfg2["dut_ports"][1]["use_port"] = "unchecked"
        cfg2["dut_ports"][0]["dataplane_duplication"] = "3"
        cfg2["dut_ports"][1]["dataplane_duplication"] = "3"
        target_tofino.deploy(cfg2)


class TOF_L2_Only1DUTDut1ToGroup1_UDP(p4sta_ptf_base_udp.Only1DUTDut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_udp.Only1DUTDut1ToGroup1.setUp(self, l1=False)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "2"
        cfg2["loadgen_groups"] = [cfg2["loadgen_groups"][0]]
        new_serv = {
            "id": 2,
            "loadgen_iface": "dontcare",
            "loadgen_ip": "10.0.1.4",
            "loadgen_mac": "22:22:22:22:22:23",
            "p4_port": "2",
            "real_port": "1/2",
            "ssh_ip": "10.99.66.4",
            "ssh_user": "root",
            "speed": "10G",
            "shape": "",
            "fec": "NONE",
            "an": "default"
        }
        cfg2["loadgen_groups"][0]["loadgens"].append(new_serv)
        cfg2["dut_ports"][1]["use_port"] = "unchecked"
        target_tofino.deploy(cfg2)


class TOF_L3_Only1DUTDut1ToGroup1_TCP(p4sta_ptf_base_tcp.Only1DUTDut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_tcp.Only1DUTDut1ToGroup1.setUp(self, l1=False)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "3"
        cfg2["loadgen_groups"] = [cfg2["loadgen_groups"][0]]
        new_serv = {
            "id": 2,
            "loadgen_iface": "dontcare",
            "loadgen_ip": "10.0.1.4",
            "loadgen_mac": "22:22:22:22:22:23",
            "p4_port": "2",
            "real_port": "1/2",
            "ssh_ip": "10.99.66.4",
            "ssh_user": "root",
            "speed": "10G",
            "shape": "",
            "fec": "NONE",
            "an": "default"
        }
        cfg2["loadgen_groups"][0]["loadgens"].append(new_serv)
        cfg2["dut_ports"][1]["use_port"] = "unchecked"
        target_tofino.deploy(cfg2)


class TOF_L3_Only1DUTDut1ToGroup1_UDP(p4sta_ptf_base_udp.Only1DUTDut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_udp.Only1DUTDut1ToGroup1.setUp(self, l1=False)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "3"
        cfg2["loadgen_groups"] = [cfg2["loadgen_groups"][0]]
        new_serv = {
            "id": 2,
            "loadgen_iface": "dontcare",
            "loadgen_ip": "10.0.1.4",
            "loadgen_mac": "22:22:22:22:22:23",
            "p4_port": "2",
            "real_port": "1/2",
            "ssh_ip": "10.99.66.4",
            "ssh_user": "root",
            "speed": "10G",
            "shape": "",
            "fec": "NONE",
            "an": "default"
        }
        cfg2["loadgen_groups"][0]["loadgens"].append(new_serv)
        cfg2["dut_ports"][1]["use_port"] = "unchecked"
        target_tofino.deploy(cfg2)


###########
#### ENCAP TESTS: PPPoE and GTP-U
####

### Group2ToDut2
# TCP
class TOF_L1_Group2ToDut2_ENCAP_TCP(p4sta_ptf_encap_tcp.Encap_Group2ToDut2):
    def setUp(self):
        p4sta_ptf_encap_tcp.Encap_Group2ToDut2.setUp(self)
        cfg["forwarding_mode"] = "1"
        target_tofino.deploy(cfg)

class TOF_L2_Group2ToDut2_ENCAP_TCP(p4sta_ptf_encap_tcp.Encap_Group2ToDut2):
    def setUp(self):
        p4sta_ptf_encap_tcp.Encap_Group2ToDut2.setUp(self)
        cfg["forwarding_mode"] = "2"
        target_tofino.deploy(cfg)

class TOF_L3_Group2ToDut2_ENCAP_TCP(p4sta_ptf_encap_tcp.Encap_Group2ToDut2):
    def setUp(self):
        p4sta_ptf_encap_tcp.Encap_Group2ToDut2.setUp(self)
        cfg["forwarding_mode"] = "3"
        target_tofino.deploy(cfg)
# UDP
class TOF_L1_Group2ToDut2_ENCAP_UDP(p4sta_ptf_encap_udp.Encap_Group2ToDut2):
    def setUp(self):
        p4sta_ptf_encap_udp.Encap_Group2ToDut2.setUp(self)
        cfg["forwarding_mode"] = "1"
        target_tofino.deploy(cfg)

class TOF_L2_Group2ToDut2_ENCAP_UDP(p4sta_ptf_encap_udp.Encap_Group2ToDut2):
    def setUp(self):
        p4sta_ptf_encap_udp.Encap_Group2ToDut2.setUp(self)
        cfg["forwarding_mode"] = "2"
        target_tofino.deploy(cfg)

class TOF_L3_Group2ToDut2_ENCAP_UDP(p4sta_ptf_encap_udp.Encap_Group2ToDut2):
    def setUp(self):
        p4sta_ptf_encap_udp.Encap_Group2ToDut2.setUp(self)
        cfg["forwarding_mode"] = "3"
        target_tofino.deploy(cfg)


### Group1ToDut1
# Case where pppoe/gtpu packets are encapsulated by DUT (UPF or BNG) and then go back into tofino => upstream
# TCP
class TOF_L1_Dut1ToGroup1_ENCAP_TCP(p4sta_ptf_encap_tcp.Encap_Dut1ToGroup1):
    def setUp(self):
        p4sta_ptf_encap_tcp.Encap_Dut1ToGroup1.setUp(self)
        cfg["forwarding_mode"] = "1"
        target_tofino.deploy(cfg)

class TOF_L2_Dut1ToGroup1_ENCAP_TCP(p4sta_ptf_encap_tcp.Encap_Dut1ToGroup1):
    def setUp(self):
        p4sta_ptf_encap_tcp.Encap_Dut1ToGroup1.setUp(self)
        cfg["forwarding_mode"] = "2"
        target_tofino.deploy(cfg)

class TOF_L3_Dut1ToGroup1_ENCAP_TCP(p4sta_ptf_encap_tcp.Encap_Dut1ToGroup1):
    def setUp(self):
        p4sta_ptf_encap_tcp.Encap_Dut1ToGroup1.setUp(self)
        cfg["forwarding_mode"] = "3"
        target_tofino.deploy(cfg)

## Skipping UDP test cases for now


### Group1ToDut1 Python Ext Host Tests (with real ext host running at port 5, not grabbed by PTF)
# TCP
class TOF_L1_Dut1ToGroup1_ENCAP_TCP_PY_EXT_HOST(p4sta_ptf_encap_tcp.Encap_Dut1ToGroup1):
    def setUp(self):
        p4sta_ptf_encap_tcp.Encap_Dut1ToGroup1.setUp(self)

        self.check_ext_host = False # ignore PTF check for ext host packet so python script can sniff packet
        
        cfg["forwarding_mode"] = "1"
        target_tofino.deploy(cfg)

        # receive at PTF iface 5 => --interface 5@veth11
        cmd = "killall external_host_python_receiver"
        subprocess.run(cmd, shell = True, executable="/bin/bash")
        print("Killed possible running external_host_python_receiver instance(s)")
        time.sleep(2)

        cmd = "cd /home/root/p4sta/externalHost/python/; nohup python3 pythonRawSocketExtHost.py --name PTF_L1_PPPOE_GTPU --interface veth11 --multi 1 --tsmax 281474976710655  --gtp --pppoe > foo.out 2> foo.err < /dev/null &"
        subprocess.run(cmd, shell = True, executable="/bin/bash")
        print("Start external_host_python_receiver")
        time.sleep(2)

    def runTest(self):
        p4sta_ptf_encap_tcp.Encap_Dut1ToGroup1.runTest(self)


        # Kill receiver to generate CSV files
        cmd = "killall external_host_python_receiver"
        subprocess.run(cmd, shell = True, executable="/bin/bash")

        time.sleep(2)

        def read_csv(name):
            temp = []
            with open(os.path.join("/home/root/p4sta/externalHost/python/" + name), "r") as csv_input:
                reader = csv.reader(csv_input, lineterminator="\n")
                for elem in reader:
                    temp.append(int(elem[0]))
            return temp
        
        timestamp1_list = read_csv("timestamp1_list_PTF_L1_PPPOE_GTPU.csv")
        if len(timestamp1_list) > 0:
            for ts1 in timestamp1_list:
                if int(ts1) != 0xaaaaaaaaaaaa:
                    self.fail("Test TOF_L1_Dut1ToGroup1_ENCAP_TCP_PY_EXT_HOST failed: Timestamp1 in packet not 0xaaaaaaaaaaaa")
        else:
            self.fail("Test TOF_L1_Dut1ToGroup1_ENCAP_TCP_PY_EXT_HOST failed: len(timestamp1_list) is 0 - should be > 0")

        timestamp2_list = read_csv("timestamp2_list_PTF_L1_PPPOE_GTPU.csv")
        if len(timestamp2_list) != len(timestamp1_list):
            self.fail("Test TOF_L1_Dut1ToGroup1_ENCAP_TCP_PY_EXT_HOST failed: len(timestamp1_list) is !=  len(timestamp2_list) " + str(len(timestamp1_list) + " != " + str(len(timestamp2_list))))
        if len(timestamp2_list) == 0:
            self.fail("Test TOF_L1_Dut1ToGroup1_ENCAP_TCP_PY_EXT_HOST failed: len(timestamp2list) is 0 - should be > 0")


        raw_packet_counter = read_csv("raw_packet_counter_PTF_L1_PPPOE_GTPU.csv")
        packet_counter = int(raw_packet_counter[0]) if len(raw_packet_counter) > 0 else 0
        if packet_counter > 0:
            if packet_counter > 1:
                print("Test TOF_L1_Dut1ToGroup1_ENCAP_TCP_PY_EXT_HOST: packet counter > 1 (" + str(packet_counter) + ") - expected 1 but not failing.")
        else:
            self.fail("Test TOF_L1_Dut1ToGroup1_ENCAP_TCP_PY_EXT_HOST failed: packet counter of external host is 0 - should be 1")

        # reaching here: passed :-)

    def tearDown(self):
        p4sta_ptf_encap_tcp.Encap_Dut1ToGroup1.tearDown(self)

        cmd = "killall external_host_python_receiver"
        subprocess.run(cmd, shell = True, executable="/bin/bash")


