from ptf.base_tests import BaseTest
from ptf.mask import Mask
from ptf.testutils import *
from scapy.all import Ether, IP, TCP, Raw, RandString, UDP
from scapy.contrib import gtp
from scapy_patches.ppp import PPPoE, PPP  # Needed due to https://github.com/secdev/scapy/commit/3e6900776698cd5472c5405294414d5b672a3f18
import ptf
import ptf.testutils as testutils


class Encap_Group2ToDut2(BaseTest):
    def setUp(self):
        BaseTest.setUp(self)

        # shows how to use a filter on all our tests
        testutils.add_filter(testutils.not_ipv6_filter)

        self.dataplane = ptf.dataplane_instance
        self.dataplane.flush()

    def tearDown(self):
        testutils.reset_filters()
        BaseTest.tearDown(self)

    def runTest(self):
        random_load = str(RandString(size=1400))

        # PPPoE Test
        pppoe1 = Ether(dst="aa:aa:aa:aa:ff:02", src="22:22:22:33:33:33") / PPPoE(sessionid=42) /PPP()/ IP(
            src="10.0.2.4", dst="10.0.1.3") / UDP(sport=0xeeff, dport=50000) / Raw(load=random_load)
        # Ether(src=self.mac, dst=self.ac_mac)/PPPoE(sessionid=self.sess_id)/PPP(proto=IPv4)/payload

        # GTP-U Test
        gtpu1 = Ether(dst="aa:aa:aa:aa:ff:02", src="22:22:22:33:33:33") / IP(src="11.8.3.3", dst="7.7.8.8")/UDP(sport=2152, dport=2152) /gtp.GTPHeader(gtp_type=255, teid=1, E=1, next_ex=0x85) /gtp.GTPPDUSessionContainer(ExtHdrLen=1, type=1, QFI=1) / IP(
            src="10.0.2.4", dst="10.0.1.3") / UDP(sport=0xeeff, dport=50000) / Raw(load=random_load)
        
        empty_tstamps = chr(0x0f) + chr(0x10)
        for i in range(14):
            empty_tstamps = empty_tstamps + chr(0x0)
        with_empty_tstamps = empty_tstamps + random_load[16:]

        # 12 bytes * 0xaa = placeholder and gets ignored by set_do_not_care
        exp_pkt_pppoe = Ether(dst="aa:aa:aa:aa:ff:02", src="22:22:22:33:33:33")/PPPoE(sessionid=42)/PPP()/IP(
            src="10.0.2.4", dst="10.0.1.3")/UDP(sport=0xeeff, dport=50000)/Raw(load=with_empty_tstamps)
        
        exp_pkt_gtpu1 = Ether(dst="aa:aa:aa:aa:ff:02", src="22:22:22:33:33:33") / IP(src="11.8.3.3", dst="7.7.8.8")/UDP(sport=2152, dport=2152, chksum=0) /gtp.GTPHeader(gtp_type=255, teid=1, E=1, next_ex=0x85) /gtp.GTPPDUSessionContainer(ExtHdrLen=1, type=1, QFI=1) / IP(
            src="10.0.2.4", dst="10.0.1.3") / UDP(sport=0xeeff, dport=50000) / Raw(load=with_empty_tstamps)

        # inport 2
        send_packet(self, 2, pppoe1)
        m3 = Mask(exp_pkt_pppoe)
        m3.set_do_not_care_scapy(UDP, "chksum")
        # timestamp1 is 6 byte long, starts at bit 448 + offset of pppoe header (starting from Eth Hdr)
        offset = 8 * 8 # 8 byte header in bit
        m3.set_do_not_care(352+offset, 48)
        verify_packets(self, m3, ports=[4])

        # in port 6 for variation
        send_packet(self, 6, gtpu1)
        m4 = Mask(exp_pkt_gtpu1)
        m4.set_do_not_care_scapy(UDP, "chksum")
        # timestamp1 is 6 byte long, starts at bit 448 + offset of IP+udp+gtp header
        offset = (20+8+16) * 8 # 8 byte header in bit

        # inner UDP checksum
        m4.set_do_not_care(320+offset, 16)

        # first timestamp
        m4.set_do_not_care(352+offset, 48)
        verify_packets(self, m4, ports=[4])