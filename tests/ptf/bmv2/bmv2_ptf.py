import copy
import ptf
import ptf.testutils as testutils
import sys

from ptf.base_tests import BaseTest
from ptf.mask import Mask
from ptf.testutils import *
from scapy.all import Ether, IP, TCP, Raw, RandString

sys.path.append("tests/ptf")
sys.path.append("stamper_targets/bmv2/")
sys.path.append("core/")
try:
    import bmv2_stamper_v1_0_0
    from cfg import cfg
    import p4sta_ptf_base_tcp
    import p4sta_ptf_base_udp
except Exception as e:
    print(e)

target_bmv2 = bmv2_stamper_v1_0_0.TargetImpl({})


########################################
# BMV2 Group2ToDut2
class BMV2_L1_Group2ToDut2_TCP(p4sta_ptf_base_tcp.Group2ToDut2):
    def setUp(self):
        p4sta_ptf_base_tcp.Group2ToDut2.setUp(self)
        cfg["forwarding_mode"] = "1"
        target_bmv2.deploy(cfg)


class BMV2_L1_Group2ToDut2_UDP(p4sta_ptf_base_udp.Group2ToDut2):
    def setUp(self):
        p4sta_ptf_base_udp.Group2ToDut2.setUp(self)
        cfg["forwarding_mode"] = "1"
        target_bmv2.deploy(cfg)


class BMV2_L2_Group2ToDut2_TCP(p4sta_ptf_base_tcp.Group2ToDut2):
    def setUp(self):
        p4sta_ptf_base_tcp.Group2ToDut2.setUp(self)
        cfg["forwarding_mode"] = "2"
        target_bmv2.deploy(cfg)


class BMV2_L2_Group2ToDut2_UDP(p4sta_ptf_base_udp.Group2ToDut2):
    def setUp(self):
        p4sta_ptf_base_udp.Group2ToDut2.setUp(self)
        cfg["forwarding_mode"] = "2"
        target_bmv2.deploy(cfg)


class BMV2_L3_Group2ToDut2_TCP(p4sta_ptf_base_tcp.Group2ToDut2):
    def setUp(self):
        p4sta_ptf_base_tcp.Group2ToDut2.setUp(self)
        cfg["forwarding_mode"] = "3"
        target_bmv2.deploy(cfg)


class BMV2_L3_Group2ToDut2_UDP(p4sta_ptf_base_udp.Group2ToDut2):
    def setUp(self):
        p4sta_ptf_base_udp.Group2ToDut2.setUp(self)
        cfg["forwarding_mode"] = "3"
        target_bmv2.deploy(cfg)


########################################
# BMV2 Dut1ToGroup1
class BMV2_L1_Dut1ToGroup1_TCP(p4sta_ptf_base_tcp.Dut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_tcp.Dut1ToGroup1.setUp(self)
        cfg["forwarding_mode"] = "1"
        target_bmv2.deploy(cfg)


class BMV2_L1_Dut1ToGroup1_UDP(p4sta_ptf_base_udp.Dut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_udp.Dut1ToGroup1.setUp(self)
        cfg["forwarding_mode"] = "1"
        target_bmv2.deploy(cfg)


class BMV2_L2_Dut1ToGroup1_TCP(p4sta_ptf_base_tcp.Dut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_tcp.Dut1ToGroup1.setUp(self)
        cfg["forwarding_mode"] = "2"
        target_bmv2.deploy(cfg)


class BMV2_L2_Dut1ToGroup1_UDP(p4sta_ptf_base_udp.Dut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_udp.Dut1ToGroup1.setUp(self)
        cfg["forwarding_mode"] = "2"
        target_bmv2.deploy(cfg)


class BMV2_L3_Dut1ToGroup1_TCP(p4sta_ptf_base_tcp.Dut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_tcp.Dut1ToGroup1.setUp(self)
        cfg["forwarding_mode"] = "3"
        target_bmv2.deploy(cfg)


class BMV2_L3_Dut1ToGroup1_UDP(p4sta_ptf_base_udp.Dut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_udp.Dut1ToGroup1.setUp(self)
        cfg["forwarding_mode"] = "3"
        target_bmv2.deploy(cfg)


########################################
# BMV2 Group1ToDut1
class BMV2_L1_Group1ToDut1_TCP(p4sta_ptf_base_tcp.Group1ToDut1):
    def setUp(self):
        p4sta_ptf_base_tcp.Group1ToDut1.setUp(self)
        cfg["forwarding_mode"] = "1"
        target_bmv2.deploy(cfg)


class BMV2_L1_Group1ToDut1_UDP(p4sta_ptf_base_udp.Group1ToDut1):
    def setUp(self):
        p4sta_ptf_base_udp.Group1ToDut1.setUp(self)
        cfg["forwarding_mode"] = "1"
        target_bmv2.deploy(cfg)


class BMV2_L2_Group1ToDut1_TCP(p4sta_ptf_base_tcp.Group1ToDut1):
    def setUp(self):
        p4sta_ptf_base_tcp.Group1ToDut1.setUp(self)
        cfg["forwarding_mode"] = "2"
        target_bmv2.deploy(cfg)


class BMV2_L2_Group1ToDut1_UDP(p4sta_ptf_base_udp.Group1ToDut1):
    def setUp(self):
        p4sta_ptf_base_udp.Group1ToDut1.setUp(self)
        cfg["forwarding_mode"] = "2"
        target_bmv2.deploy(cfg)


class BMV2_L3_Group1ToDut1_TCP(p4sta_ptf_base_tcp.Group1ToDut1):
    def setUp(self):
        p4sta_ptf_base_tcp.Group1ToDut1.setUp(self)
        cfg["forwarding_mode"] = "3"
        target_bmv2.deploy(cfg)


class BMV2_L3_Group1ToDut1_UDP(p4sta_ptf_base_udp.Group1ToDut1):
    def setUp(self):
        p4sta_ptf_base_udp.Group1ToDut1.setUp(self)
        cfg["forwarding_mode"] = "3"
        target_bmv2.deploy(cfg)


########################################
# BMV2 Dut2ToGroup2

# L1 with 2 destination hosts can not work => cut to 1 host per group
class BMV2_L1_Dut2ToGroup2_TCP(p4sta_ptf_base_tcp.Dut2ToGroup2):
    def setUp(self):
        p4sta_ptf_base_tcp.Dut2ToGroup2.setUp(self, l1=True)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "1"
        cfg2["loadgen_groups"][1]["loadgens"] = \
            cfg2["loadgen_groups"][1]["loadgens"][:1]
        target_bmv2.deploy(cfg2)


# L1 with 2 destination hosts can not work => cut to 1 host per group
class BMV2_L1_Dut2ToGroup2_UDP(p4sta_ptf_base_udp.Dut2ToGroup2):
    def setUp(self):
        p4sta_ptf_base_udp.Dut2ToGroup2.setUp(self, l1=True)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "1"
        cfg2["loadgen_groups"][1]["loadgens"] = \
            cfg2["loadgen_groups"][1]["loadgens"][:1]
        target_bmv2.deploy(cfg2)


class BMV2_L2_Dut2ToGroup2_TCP(p4sta_ptf_base_tcp.Dut2ToGroup2):
    def setUp(self):
        p4sta_ptf_base_tcp.Dut2ToGroup2.setUp(self)
        cfg["forwarding_mode"] = "2"
        target_bmv2.deploy(cfg)


class BMV2_L2_Dut2ToGroup2_UDP(p4sta_ptf_base_udp.Dut2ToGroup2):
    def setUp(self):
        p4sta_ptf_base_udp.Dut2ToGroup2.setUp(self)
        cfg["forwarding_mode"] = "2"
        target_bmv2.deploy(cfg)


class BMV2_L3_Dut2ToGroup2_TCP(p4sta_ptf_base_tcp.Dut2ToGroup2):
    def setUp(self):
        p4sta_ptf_base_tcp.Dut2ToGroup2.setUp(self)
        cfg["forwarding_mode"] = "3"
        target_bmv2.deploy(cfg)


class BMV2_L3_Dut2ToGroup2_UDP(p4sta_ptf_base_udp.Dut2ToGroup2):
    def setUp(self):
        p4sta_ptf_base_udp.Dut2ToGroup2.setUp(self)
        cfg["forwarding_mode"] = "3"
        target_bmv2.deploy(cfg)


# test if NO timestamp header is added if dut_2_outgoing_stamp = unchecked
class BMV2_L2_Group2ToDut2_TCP_no_stamp(p4sta_ptf_base_tcp.Group2ToDut2):
    def setUp(self):
        p4sta_ptf_base_tcp.Group2ToDut2.setUp(self)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "2"
        cfg2["dut_ports"][1]["stamp_outgoing"] = "unchecked"
        target_bmv2.deploy(cfg2)

    def runTest(self):
        random_load = str(RandString(size=1400))
        pkt1 = Ether(dst="aa:aa:aa:aa:ff:02", src="22:22:22:33:33:33") / IP(
            src="10.0.2.4", dst="10.0.1.3") / TCP(
            sport=0xeeff, dport=50000) / Raw(load=random_load)
        send_packet(self, 2, pkt1)
        verify_packets(self, pkt1, ports=[4])


# test if multicast counter works (10=every 10th packet duplicated to ext host)
class BMV2_L2_Dut2ToGroup2_TCP_multicast_thresh_10(p4sta_ptf_base_tcp.
                                                   Dut2ToGroup2):
    def setUp(self):
        p4sta_ptf_base_tcp.Dut2ToGroup2.setUp(self)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "2"
        cfg2["multicast"] = "10"
        target_bmv2.deploy(cfg2)

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

        exp_pkt_ext_host_1 = Ether(
            dst="ff:ff:ff:ff:ff:ff", src="aa:aa:aa:aa:ff:02") / IP(
            src="10.0.1.3", dst="10.0.2.4") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
            )]) / Raw(load=random_load)

        pkt1.show2()
        send_packet(self, 4, pkt1, 10)

        m = Mask(exp_pkt_1)
        m.set_do_not_care_scapy(TCP, "chksum")
        # timestamp2 is 6 byte long, starts at bit 512 (starting from Eth Hdr)
        m.set_do_not_care(448+(8*8), 48)
        for i in range(10):
            verify_packet(self, m, port_id=2)

        m = Mask(exp_pkt_ext_host_1)
        m.set_do_not_care_scapy(TCP, "chksum")
        # timestamp2 is 6 byte long, starts at bit 512 (starting from Eth Hdr)
        m.set_do_not_care(448+(8*8), 48)
        verify_packet(self, m, port_id=5)

        verify_no_other_packets(self)

########################################
# BMV2 Only1DUTGroup1ToDut1
# L1 forwarding does not work with one DUT port only!


class BMV2_L2_Only1DUTGroup1ToDut1_TCP(p4sta_ptf_base_tcp.
                                       Only1DUTGroup1ToDut1):
    def setUp(self):
        p4sta_ptf_base_tcp.Only1DUTGroup1ToDut1.setUp(self, l1=False)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "2"
        cfg2["loadgen_groups"] = cfg2["loadgen_groups"][:1]
        new_serv = {
          "id": 2,
          "loadgen_iface": "dontcare",
          "loadgen_ip": "10.0.1.4",
          "loadgen_mac": "22:22:22:22:22:23",
          "p4_port": "2",
          "real_port": "2",
          "ssh_ip": "10.99.66.4",
          "ssh_user": "root"
        }
        cfg2["loadgen_groups"][0]["loadgens"].append(new_serv)
        cfg2["dut_ports"][1]["use_port"] = "unchecked"
        target_bmv2.deploy(cfg2)


class BMV2_L2_Only1DUTGroup1ToDut1_UDP(p4sta_ptf_base_udp.
                                       Only1DUTGroup1ToDut1):
    def setUp(self):
        p4sta_ptf_base_udp.Only1DUTGroup1ToDut1.setUp(self, l1=False)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "2"
        cfg2["loadgen_groups"] = cfg2["loadgen_groups"][:1]
        new_serv = {
          "id": 2,
          "loadgen_iface": "dontcare",
          "loadgen_ip": "10.0.1.4",
          "loadgen_mac": "22:22:22:22:22:23",
          "p4_port": "2",
          "real_port": "2",
          "ssh_ip": "10.99.66.4",
          "ssh_user": "root"
        }
        cfg2["loadgen_groups"][0]["loadgens"].append(new_serv)
        cfg2["dut_ports"][1]["use_port"] = "unchecked"
        target_bmv2.deploy(cfg2)


class BMV2_L3_Only1DUTGroup1ToDut1_TCP(p4sta_ptf_base_tcp.
                                       Only1DUTGroup1ToDut1):
    def setUp(self):
        p4sta_ptf_base_tcp.Only1DUTGroup1ToDut1.setUp(self, l1=False)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "3"
        cfg2["loadgen_groups"] = cfg2["loadgen_groups"][:1]
        new_serv = {
          "id": 2,
          "loadgen_iface": "dontcare",
          "loadgen_ip": "10.0.1.4",
          "loadgen_mac": "22:22:22:22:22:23",
          "p4_port": "2",
          "real_port": "2",
          "ssh_ip": "10.99.66.4",
          "ssh_user": "root"
        }
        cfg2["loadgen_groups"][0]["loadgens"].append(new_serv)
        cfg2["dut_ports"][1]["use_port"] = "unchecked"
        target_bmv2.deploy(cfg2)


class BMV2_L3_Only1DUTGroup1ToDut1_UDP(p4sta_ptf_base_udp.
                                       Only1DUTGroup1ToDut1):
    def setUp(self):
        p4sta_ptf_base_udp.Only1DUTGroup1ToDut1.setUp(self, l1=False)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "3"
        cfg2["loadgen_groups"] = cfg2["loadgen_groups"][:1]
        new_serv = {
          "id": 2,
          "loadgen_iface": "dontcare",
          "loadgen_ip": "10.0.1.4",
          "loadgen_mac": "22:22:22:22:22:23",
          "p4_port": "2",
          "real_port": "2",
          "ssh_ip": "10.99.66.4",
          "ssh_user": "root"
        }
        cfg2["loadgen_groups"][0]["loadgens"].append(new_serv)
        cfg2["dut_ports"][1]["use_port"] = "unchecked"
        target_bmv2.deploy(cfg2)


########################################
# BMV2 Only1DUTDut1ToGroup1
# L1 forwarding does not work with one DUT port only!

class BMV2_L2_Only1DUTDut1ToGroup1_TCP(p4sta_ptf_base_tcp.
                                       Only1DUTDut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_tcp.Only1DUTDut1ToGroup1.setUp(self, l1=False)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "2"
        cfg2["loadgen_groups"] = cfg2["loadgen_groups"][:1]
        new_serv = {
          "id": 2,
          "loadgen_iface": "dontcare",
          "loadgen_ip": "10.0.1.4",
          "loadgen_mac": "22:22:22:22:22:23",
          "p4_port": "2",
          "real_port": "2",
          "ssh_ip": "10.99.66.4",
          "ssh_user": "root"
        }
        cfg2["loadgen_groups"][0]["loadgens"].append(new_serv)
        cfg2["dut_ports"][1]["use_port"] = "unchecked"
        target_bmv2.deploy(cfg2)


class BMV2_L2_Only1DUTDut1ToGroup1_UDP(p4sta_ptf_base_udp.
                                       Only1DUTDut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_udp.Only1DUTDut1ToGroup1.setUp(self, l1=False)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "2"
        cfg2["loadgen_groups"] = cfg2["loadgen_groups"][:1]
        new_serv = {
          "id": 2,
          "loadgen_iface": "dontcare",
          "loadgen_ip": "10.0.1.4",
          "loadgen_mac": "22:22:22:22:22:23",
          "p4_port": "2",
          "real_port": "2",
          "ssh_ip": "10.99.66.4",
          "ssh_user": "root"
        }
        cfg2["loadgen_groups"][0]["loadgens"].append(new_serv)
        cfg2["dut_ports"][1]["use_port"] = "unchecked"
        target_bmv2.deploy(cfg2)


class BMV2_L3_Only1DUTDut1ToGroup1_TCP(p4sta_ptf_base_tcp.
                                       Only1DUTDut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_tcp.Only1DUTDut1ToGroup1.setUp(self, l1=False)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "3"
        cfg2["loadgen_groups"] = cfg2["loadgen_groups"][:1]
        new_serv = {
          "id": 2,
          "loadgen_iface": "dontcare",
          "loadgen_ip": "10.0.1.4",
          "loadgen_mac": "22:22:22:22:22:23",
          "p4_port": "2",
          "real_port": "2",
          "ssh_ip": "10.99.66.4",
          "ssh_user": "root"
        }
        cfg2["loadgen_groups"][0]["loadgens"].append(new_serv)
        cfg2["dut_ports"][1]["use_port"] = "unchecked"
        target_bmv2.deploy(cfg2)


class BMV2_L3_Only1DUTDut1ToGroup1_UDP(p4sta_ptf_base_udp.
                                       Only1DUTDut1ToGroup1):
    def setUp(self):
        p4sta_ptf_base_udp.Only1DUTDut1ToGroup1.setUp(self, l1=False)
        cfg2 = copy.deepcopy(cfg)
        cfg2["forwarding_mode"] = "3"
        cfg2["loadgen_groups"] = cfg2["loadgen_groups"][:1]
        new_serv = {
          "id": 2,
          "loadgen_iface": "dontcare",
          "loadgen_ip": "10.0.1.4",
          "loadgen_mac": "22:22:22:22:22:23",
          "p4_port": "2",
          "real_port": "2",
          "ssh_ip": "10.99.66.4",
          "ssh_user": "root"
        }
        cfg2["loadgen_groups"][0]["loadgens"].append(new_serv)
        cfg2["dut_ports"][1]["use_port"] = "unchecked"
        target_bmv2.deploy(cfg2)
