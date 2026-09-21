import ipaddress

from ptf.base_tests import BaseTest
from ptf.mask import Mask
from ptf.testutils import *
from scapy.all import Ether, IP, TCP, Raw, RandString, UDP
from scapy.contrib import gtp
from scapy_patches.ppp import PPPoE, PPP  # Needed due to https://github.com/secdev/scapy/commit/3e6900776698cd5472c5405294414d5b672a3f18
import ptf
import ptf.testutils as testutils

from ext_host_header_scapy import Exthost


# Returns a dictionary which includes all your parameters
# {"mode": "pppoe" or "gtpu"} with flag --test-params="mode=pppoe"
test_params = testutils.test_params_get()
print("############## TEST_PARAMS: " + str(test_params))


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

        if test_params["pppoe"]:
            # inport 2
            send_packet(self, 2, pppoe1)
            m3 = Mask(exp_pkt_pppoe)
            m3.set_do_not_care_scapy(UDP, "chksum")
            # timestamp1 is 6 byte long, starts at bit 448 + offset of pppoe header (starting from Eth Hdr)
            offset = 8 * 8 # 8 byte header in bit
            m3.set_do_not_care(352+offset, 48)
            verify_packets(self, m3, ports=[4])

        if test_params["gtpu"]:
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


class Encap_Dut1ToGroup1(BaseTest):
    def setUp(self):
        BaseTest.setUp(self)

        # shows how to use a filter on all our tests
        testutils.add_filter(testutils.not_ipv6_filter)

        self.dataplane = ptf.dataplane_instance
        self.dataplane.flush()

        self.dataplane_duplication = 0

        self.check_ext_host = True

    def tearDown(self):
        testutils.reset_filters()
        BaseTest.tearDown(self)

    def runTest(self):
        random_load = str(RandString(size=1400))

        empty_tstamps = chr(0x0f) + chr(0x10)
        for i in range(6):
            empty_tstamps = empty_tstamps + chr(0xaa)
        empty_tstamps = empty_tstamps + chr(0x0) + chr(0x0)
        for i in range(6):
            empty_tstamps = empty_tstamps + chr(0xbb)
        with_tstamps = empty_tstamps + random_load[16:]

        if test_params["pppoe"]:
            #######
            # PPPOE
            #######
            pppoe1 = Ether(dst="22:22:22:22:22:22", src="aa:aa:aa:aa:ff:01") / PPPoE(sessionid=42) /PPP() / IP(
                src="10.0.2.4", dst="10.0.1.3") / UDP(
                sport=0xeeff, dport=50000) / Raw(load=with_tstamps)

            # Timestamps are in the inner UDP payload, not in a TCP option.
            exp_pkt_pppoe = Ether(dst="22:22:22:22:22:22", src="aa:aa:aa:aa:ff:01") / PPPoE(sessionid=42) /PPP() / IP(
                src="10.0.2.4", dst="10.0.1.3") / UDP(
                sport=0xeeff, dport=50000) / Raw(load=with_tstamps)

            exp_pkt_pppoe_ext_host = (
                Ether(dst="55:14:df:9f:03:af", src="aa:aa:aa:aa:ff:01")
                / IP(src="10.11.12.100", dst="10.11.12.99", len=50) # len 50 as set in P4, src is set as dst x.y.z.100 always
                / UDP(sport=41111, dport=41111, chksum=0, len=30)
                / Exthost(len=len(pppoe1), session_id=42)
                / Raw(load=with_tstamps)
            )

            send_packet(self, 3, pppoe1)

            offset = 8 * 8 # 8 byte pppoe header in bit

            m = Mask(exp_pkt_pppoe)
            m.set_do_not_care_scapy(UDP, "chksum")
            # timestamp2 is 6 byte long and starts in the UDP payload.
            m.set_do_not_care(352 + (8 * 8) + offset, 48)
            verify_packet(self, m, port_id=1)

            # check duplicated packet at ext host
            if self.check_ext_host:
                m2 = Mask(exp_pkt_pppoe_ext_host)
                m2.set_do_not_care_scapy(UDP, "chksum")
                # timestamp2 is 6 byte long, starts at bit 512 (starting from Eth Hdr) + 48 ext host hdr
                m2.set_do_not_care(352 + 48 + (8 * 8), 48)
                verify_packet(self, m2, port_id=5)

            # verify_no_other_packets(self)

        if test_params["gtpu"]:
            #######
            # GTP-U
            #######
            gtpu1 = Ether(dst="22:22:22:22:22:22", src="aa:aa:aa:aa:ff:01") / IP(src="11.8.3.3", dst="7.7.8.8")/ UDP(sport=2152, dport=2152) / gtp.GTPHeader(
                gtp_type=255, teid=1, E=1, next_ex=0x85) /gtp.GTPPDUSessionContainer(
                    ExtHdrLen=1, type=1, QFI=1) / IP(src="10.0.2.4", dst="10.0.1.3") / UDP(
                        sport=0xeeff, dport=50000) / Raw(load=with_tstamps)

            exp_pkt_gtpu = Ether(dst="22:22:22:22:22:22", src="aa:aa:aa:aa:ff:01") / IP(src="11.8.3.3", dst="7.7.8.8")/ UDP(sport=2152, dport=2152, chksum=0) / gtp.GTPHeader(
                gtp_type=255, teid=1, E=1, next_ex=0x85) /gtp.GTPPDUSessionContainer(
                    ExtHdrLen=1, type=1, QFI=1) / IP(
                        src="10.0.2.4", dst="10.0.1.3") / UDP(
                            sport=0xeeff, dport=50000) / Raw(load=with_tstamps)

            exp_pkt_gtpu_ext_host = (
                Ether(dst="55:14:df:9f:03:af", src="aa:aa:aa:aa:ff:01")
                / IP(src="10.11.12.100", dst="10.11.12.99", len=50) # len 50 as set in P4, src is set as dst x.y.z.100 always
                / UDP(sport=41111, dport=41111, chksum=0, len=30)
                / Exthost(len=len(gtpu1), session_id=1)
                / Raw(load=with_tstamps)
            )

            send_packet(self, 3, gtpu1)

            offset = (20+8+16) * 8 # IP + outer UDP + GTP-U headers in bit

            m3 = Mask(exp_pkt_gtpu)
            m3.set_do_not_care_scapy(UDP, "chksum")
            # inner UDP checksum
            m3.set_do_not_care(320 + offset, 16)
            # timestamp2 is 6 byte long and starts in the inner UDP payload.
            m3.set_do_not_care(352 + (8 * 8) + offset, 48)
            verify_packet(self, m3, port_id=1)

            # check duplicated packet at ext host
            if self.check_ext_host:
                m4 = Mask(exp_pkt_gtpu_ext_host)
                m4.set_do_not_care_scapy(UDP, "chksum")
                # timestamp2 is 6 byte long, starts at bit 512 (starting from Eth Hdr) + 48 ext host hdr
                m4.set_do_not_care(352 + 48 + (8 * 8), 48)
                verify_packet(self, m4, port_id=5)

                verify_no_other_packets(self)


class Encap_IPonly_Group1ToDut1(BaseTest):
    def setUp(self):
        BaseTest.setUp(self)

        testutils.add_filter(testutils.not_ipv6_filter)

        self.dataplane = ptf.dataplane_instance
        self.dataplane.flush()

        self.dataplane_duplication = 0

    def tearDown(self):
        testutils.reset_filters()
        BaseTest.tearDown(self)

    def runTest(self):
        random_load = str(RandString(size=1400))
        pkt = Ether(dst="aa:aa:aa:aa:ff:01", src="22:22:22:22:22:22") / IP(
            src="10.0.1.3", dst="10.0.2.4") / UDP(
            sport=0xeeff, dport=50000) / Raw(load=random_load)

        empty_tstamps = chr(0x0f) + chr(0x10) + (chr(0x0) * 14)
        with_empty_tstamps = empty_tstamps + random_load[16:]

        dup_tstamps = (
            chr(0x0f) + chr(0x10) + (chr(0xaa) * 6)
            + (chr(0x0) * 7) + chr(0x1)
        )
        with_dup_tstamps = dup_tstamps + random_load[16:]

        exp_pkt = Ether(dst="aa:aa:aa:aa:ff:01", src="22:22:22:22:22:22") / IP(
            src="10.0.1.3", dst="10.0.2.4") / UDP(
            sport=0xeeff, dport=50000) / Raw(load=with_empty_tstamps)

        send_packet(self, 1, pkt)

        m = Mask(exp_pkt)
        m.set_do_not_care_scapy(UDP, "chksum")
        m.set_do_not_care(352, 48)
        verify_packet(self, m, port_id=3)

        exp_pkt_dup = Ether(
            dst="aa:aa:aa:aa:ff:01", src="22:22:22:22:22:22") / IP(
            src="10.0.1.3", dst="10.0.2.4") / UDP(
            sport=0xeeff, dport=50000) / Raw(load=with_dup_tstamps)

        m = Mask(exp_pkt_dup)
        m.set_do_not_care_scapy(UDP, "chksum")
        m.set_do_not_care(352, 48)

        for i in range(self.dataplane_duplication):
            verify_packet(self, m, port_id=3)

class Encap_IPonly_Dut2ToGroup2(BaseTest):
    def setUp(self, l1=False):
        BaseTest.setUp(self)
        self.l1 = l1

        testutils.add_filter(testutils.not_ipv6_filter)

        self.dataplane = ptf.dataplane_instance
        self.dataplane.flush()

    def tearDown(self):
        testutils.reset_filters()
        BaseTest.tearDown(self)

    def runTest(self):
        random_load = str(RandString(size=1400))

        tstamps = (
            chr(0x0f) + chr(0x10) + (chr(0xaa) * 6)
            + (chr(0x0) * 2) + (chr(0xbb) * 6)
        )
        with_tstamps = tstamps + random_load[16:]

        pkt1 = Ether(dst="22:22:22:33:33:33", src="aa:aa:aa:aa:ff:02") / IP(
            src="10.0.1.3", dst="10.0.2.4") / UDP(
            sport=0xeeff, dport=50000) / Raw(load=with_tstamps)
        if not self.l1:
            pkt2 = Ether(
                dst="22:22:22:33:33:34", src="aa:aa:aa:aa:ff:02") / IP(
                src="10.0.1.3", dst="10.0.2.5") / UDP(
                sport=0xeeff, dport=50000) / Raw(load=with_tstamps)

        exp_pkt_1 = Ether(
            dst="22:22:22:33:33:33", src="aa:aa:aa:aa:ff:02") / IP(
            src="10.0.1.3", dst="10.0.2.4") / UDP(
            sport=0xeeff, dport=50000) / Raw(load=with_tstamps)

        if not self.l1:
            exp_pkt_2 = Ether(
                dst="22:22:22:33:33:34", src="aa:aa:aa:aa:ff:02") / IP(
                src="10.0.1.3", dst="10.0.2.5") / UDP(
                sport=0xeeff, dport=50000) / Raw(load=with_tstamps)

        exp_pkt_ext_host = (
            Ether(dst="55:14:df:9f:03:af", src="aa:aa:aa:aa:ff:02")
            / IP(src="10.11.12.100", dst="10.11.12.99", len=50)
            / UDP(sport=41111, dport=41111, chksum=0, len=30)
            / Exthost(
                len=len(pkt1),
                session_id=int(ipaddress.IPv4Address("10.0.1.3")))
            / Raw(load=with_tstamps)
        )

        send_packet(self, 4, pkt1)

        m = Mask(exp_pkt_1)
        m.set_do_not_care_scapy(UDP, "chksum")
        m.set_do_not_care(352 + (8 * 8), 48)
        verify_packet(self, m, port_id=2)

        m = Mask(exp_pkt_ext_host)
        m.set_do_not_care_scapy(UDP, "chksum")
        m.set_do_not_care(352 + 48 + (8 * 8), 48)
        verify_packet(self, m, port_id=5)

        verify_no_other_packets(self)

        if not self.l1:
            send_packet(self, 4, pkt2)

            m = Mask(exp_pkt_2)
            m.set_do_not_care_scapy(UDP, "chksum")
            m.set_do_not_care(352 + (8 * 8), 48)
            verify_packet(self, m, port_id=6)

            m = Mask(exp_pkt_ext_host)
            m.set_do_not_care_scapy(UDP, "chksum")
            m.set_do_not_care(352 + 48 + (8 * 8), 48)
            verify_packet(self, m, port_id=5)

            verify_no_other_packets(self)
