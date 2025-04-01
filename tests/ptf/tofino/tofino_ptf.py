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
    # import tofino1_65p_stamper_v1_2_1 as stamper
    import tofino1_65p_stamper_v1_3_0 as stamper
    import p4sta_ptf_base_tcp
    import p4sta_ptf_base_udp
    import p4sta_ptf_encap_tcp
    import p4sta_ptf_encap_udp
    import test_logger
    from ext_host_header_scapy import Exthost
except Exception as e:
    print(e)

target_cfg = {"p4_ports": [], "nr_ports": 18}
for i in range(17):
    target_cfg["p4_ports"].append(str(i))
target_cfg["p4_ports"].append("64")

logger = test_logger.create_logger("#ptf_tofino")
target_tofino = stamper.TargetImpl(target_cfg, logger)

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
    "ext_host_ip": "10.11.12.99",
    "ext_host_mac": "55:14:df:9f:03:af",
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
    "program": "tofino_stamper_v1_3_0",
    "sde": "/opt/bf-sde-9.13.0",
    "selected_extHost": "GoExtHostUdp",
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

        # exp_pkt_ext_host_1 = Ether(dst="ff:ff:ff:ff:ff:ff",
        #                            src="aa:aa:aa:aa:ff:02") / IP(
        #     src="10.0.1.3", dst="10.0.2.4") / TCP(
        #     sport=0xeeff, dport=50000, options=[(
        #         15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
        #     )]) / Raw(load=random_load)
        
        exp_pkt_ext_host_1 = (
            Ether(dst="55:14:df:9f:03:af", src="aa:aa:aa:aa:ff:02")
            / IP(src="10.11.12.100", dst="10.11.12.99", len=46) # len 46 as set in P4, .100 src set by stamper
            / UDP(sport=41111, dport=41111, chksum=0, len=26)
            / Exthost(len=len(pkt1)) 
            / Raw(load=b"\x0f\x10\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb")
            / Raw(load=random_load)
        )

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
        m.set_do_not_care_scapy(UDP, "len")
        # timestamp2 is 6 byte long
        m.set_do_not_care(432, 48)
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
