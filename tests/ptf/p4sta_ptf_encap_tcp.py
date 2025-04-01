from ptf.base_tests import BaseTest
from ptf.mask import Mask
from ptf.testutils import *
from scapy.all import Ether, IP, TCP, Raw, RandString, UDP
from scapy.contrib import gtp
from scapy_patches.ppp import PPPoE, PPP  # Needed due to https://github.com/secdev/scapy/commit/3e6900776698cd5472c5405294414d5b672a3f18
import ptf
import ptf.testutils as testutils

from ext_host_header_scapy import Exthost

## Logic: Flow starting from Group 2 to Dut 2 (tstamp1), then flowing throught DUT and leaving via Dut 1 to Group 1 (receiving tstamp2)
## Vice versa also possible (G1 to D1, D2 to G2) but not required to test => only difference would be the P4 ports
## Therefore: Access Network Downstream/Upstream definition not suitable => ptf packet entering stamper without tstamps or with stamp1 is the only test distinction required, when stamp1 ext host is also checked

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
            src="10.0.2.4", dst="10.0.1.3") / TCP(sport=0xeeff, dport=50000) / Raw(load=random_load)
        # Ether(src=self.mac, dst=self.ac_mac)/PPPoE(sessionid=self.sess_id)/PPP(proto=IPv4)/payload

        # GTP-U Test
        gtpu1 = Ether(dst="aa:aa:aa:aa:ff:02", src="22:22:22:33:33:33") / IP(src="11.8.3.3", dst="7.7.8.8")/UDP(sport=2152, dport=2152) /gtp.GTPHeader(gtp_type=255, teid=1, E=1, next_ex=0x85) /gtp.GTPPDUSessionContainer(ExtHdrLen=1, type=1, QFI=1) / IP(
            src="10.0.2.4", dst="10.0.1.3") / TCP(sport=0xeeff, dport=50000) / Raw(load=random_load)

        # 12 bytes * 0xaa = placeholder and gets ignored by set_do_not_care
        exp_pkt_pppoe = Ether(dst="aa:aa:aa:aa:ff:02", src="22:22:22:33:33:33")/PPPoE(sessionid=42)/PPP()/IP(
            src="10.0.2.4", dst="10.0.1.3")/TCP(
            sport=0xeeff, dport=50000, options=[( 15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\x00\x00\x00\x00\x00\x00"
            )])/Raw(load=random_load)
        
        exp_pkt_gtpu1 = Ether(dst="aa:aa:aa:aa:ff:02", src="22:22:22:33:33:33") / IP(src="11.8.3.3", dst="7.7.8.8")/UDP(sport=2152, dport=2152, chksum=0) /gtp.GTPHeader(gtp_type=255, teid=1, E=1, next_ex=0x85) /gtp.GTPPDUSessionContainer(ExtHdrLen=1, type=1, QFI=1) / IP(
            src="10.0.2.4", dst="10.0.1.3") / TCP(sport=0xeeff, dport=50000, options=[( 15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\x00\x00\x00\x00\x00\x00"
            )]) / Raw(load=random_load)

        if test_params["pppoe"]:
            send_packet(self, 2, pppoe1)
            m3 = Mask(exp_pkt_pppoe)
            m3.set_do_not_care_scapy(TCP, "chksum")
            # timestamp1 is 6 byte long, starts at bit 448 + offset of pppoe header (starting from Eth Hdr)
            offset = 8 * 8 # 8 byte header in bit
            m3.set_do_not_care(448+offset, 48)
            verify_packets(self, m3, ports=[4])
        elif test_params["gtpu"]:
            # in port 6 for variation
            send_packet(self, 6, gtpu1)
            m4 = Mask(exp_pkt_gtpu1)
            m4.set_do_not_care_scapy(TCP, "chksum")
            # timestamp1 is 6 byte long, starts at bit 448 + offset of IP+udp+gtp header
            offset = (20+8+16) * 8 # 8 byte header in bit
            m4.set_do_not_care(448+offset, 48)
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

        if test_params["pppoe"]:
            #######
            # PPPOE
            #######
            pppoe1 = Ether(dst="22:22:22:22:22:22", src="aa:aa:aa:aa:ff:01") / PPPoE(sessionid=42) /PPP() / IP(
                src="10.0.2.4", dst="10.0.1.3") / TCP(
                sport=0xeeff, dport=50000, options=[(
                    15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
                )]) / Raw(load=random_load)
            
            # 12 bytes * 0xbb = placeholder and gets ignored by set_do_not_care
            exp_pkt_pppoe = Ether(dst="22:22:22:22:22:22", src="aa:aa:aa:aa:ff:01") / PPPoE(sessionid=42) /PPP() / IP(
                src="10.0.2.4", dst="10.0.1.3") / TCP(
                sport=0xeeff, dport=50000, options=[(
                    15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
                )]) / Raw(load=random_load)
            
            exp_pkt_pppoe_ext_host = (
                Ether(dst="55:14:df:9f:03:af", src="aa:aa:aa:aa:ff:01")
                / IP(src="10.11.12.100", dst="10.11.12.99", len=46) # len 46 as set in P4, src is set as dst x.y.z.100 always
                / UDP(sport=41111, dport=41111, chksum=0, len=26)
                / Exthost(len=len(pppoe1))
                / Raw(load=b"\x0f\x10\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb")
                / Raw(load=random_load)
            )
            # --interface 0@veth1 --interface 1@veth3 --interface 2@veth5 --interface 3@veth7 --interface 4@veth9 --interface 5@veth11 --interface 6@veth13'
            send_packet(self, 3, pppoe1)

            offset = 8 * 8 # 8 byte pppoe header in bit

            m = Mask(exp_pkt_pppoe)
            m.set_do_not_care_scapy(TCP, "chksum")
            # timestamp2 is 6 byte long, starts at bit 512 (starting from Eth Hdr)
            m.set_do_not_care(448 + (8 * 8) + offset, 48)
            verify_packet(self, m, port_id=1)

            # check duplicated packet at ext host
            if self.check_ext_host:
                m2 = Mask(exp_pkt_pppoe_ext_host)
                m2.set_do_not_care_scapy(UDP, "len")
                # timestamp2 is 6 byte long
                m2.set_do_not_care(432, 48)
                verify_packet(self, m2, port_id=5)

            # verify_no_other_packets(self)

        if test_params["gtpu"]:
            #######
            # GTP-U
            #######
            gtpu1 = Ether(dst="22:22:22:22:22:22", src="aa:aa:aa:aa:ff:01") / IP(src="11.8.3.3", dst="7.7.8.8")/ UDP(sport=2152, dport=2152) / gtp.GTPHeader(
                gtp_type=255, teid=1, E=1, next_ex=0x85) /gtp.GTPPDUSessionContainer(
                    ExtHdrLen=1, type=1, QFI=1) / IP(src="10.0.2.4", dst="10.0.1.3") / TCP(
                        sport=0xeeff, dport=50000, options=[(
                            15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
                )]) / Raw(load=random_load)
            
            
            # 12 bytes * 0xbb = placeholder and gets ignored by set_do_not_care
            exp_pkt_gtpu = Ether(dst="22:22:22:22:22:22", src="aa:aa:aa:aa:ff:01") / IP(src="11.8.3.3", dst="7.7.8.8")/ UDP(sport=2152, dport=2152, chksum=0) / gtp.GTPHeader(
                gtp_type=255, teid=1, E=1, next_ex=0x85) /gtp.GTPPDUSessionContainer(
                    ExtHdrLen=1, type=1, QFI=1) / IP(
                        src="10.0.2.4", dst="10.0.1.3") / TCP(
                            sport=0xeeff, dport=50000, options=[(
                                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
                )]) / Raw(load=random_load)
            
            exp_pkt_gtpu_ext_host = (
                Ether(dst="55:14:df:9f:03:af", src="aa:aa:aa:aa:ff:01")
                / IP(src="10.11.12.100", dst="10.11.12.99", len=46) # len 46 as set in P4, src is set as dst x.y.z.100 always
                / UDP(sport=41111, dport=41111, chksum=0, len=26)
                / Exthost(len=len(gtpu1)) 
                / Raw(load=b"\x0f\x10\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb")
                / Raw(load=random_load)
            )

            send_packet(self, 3, gtpu1)

            offset = (20+8+16) * 8 # gtpu 8 byte header in bit

            m3 = Mask(exp_pkt_gtpu)
            m3.set_do_not_care_scapy(TCP, "chksum")
            # timestamp2 is 6 byte long, starts at bit 512 (starting from Eth Hdr)
            m3.set_do_not_care(448 + (8 * 8) + offset, 48)
            verify_packet(self, m3, port_id=1)

            # check duplicated packet at ext host
            if self.check_ext_host:
                m4 = Mask(exp_pkt_gtpu_ext_host)
                m4.set_do_not_care_scapy(UDP, "len")
                # timestamp2 is 6 byte long, starts at bit 512 (starting from Eth Hdr)
                m4.set_do_not_care(432, 48)
                verify_packet(self, m4, port_id=5)

                verify_no_other_packets(self)


# to verify normal IP packets receive TSTAMP1 correctly with GTP/PPPoE compiled P4
class Encap_IPonly_Group1ToDut1(BaseTest):
    def setUp(self):
        BaseTest.setUp(self)

        # shows how to use a filter on all our tests
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
            src="10.0.1.3", dst="10.0.2.4") / TCP(
            sport=0xeeff, dport=50000) / Raw(load=random_load)

        # 12 bytes * 0xaa = placeholder and gets ignored by set_do_not_care
        exp_pkt = Ether(dst="aa:aa:aa:aa:ff:01", src="22:22:22:22:22:22") / IP(
            src="10.0.1.3", dst="10.0.2.4") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\x00\x00\x00\x00\x00\x00"
            )]) / Raw(load=random_load)

        send_packet(self, 1, pkt)

        m = Mask(exp_pkt)
        m.set_do_not_care_scapy(TCP, "chksum")
        # timestamp1 is 6 byte long, starts at bit 448 (starting from Eth Hdr)
        m.set_do_not_care(448, 48)
        verify_packet(self, m, port_id=3)

        exp_pkt_dup = Ether(
            dst="aa:aa:aa:aa:ff:01", src="22:22:22:22:22:22") / IP(
            src="10.0.1.3", dst="10.0.2.4") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\x00\x00\x00\x00\x00\x01"
            )]) / Raw(load=random_load)
        m = Mask(exp_pkt_dup)
        m.set_do_not_care_scapy(TCP, "chksum")
        # timestamp1 is 6 byte long, starts at bit 448 (starting from Eth Hdr)
        m.set_do_not_care(448, 48)

        for i in range(self.dataplane_duplication):
            verify_packet(self, m, port_id=3)



# to verify normal IP packets receive TSTAMP2 correctly with GTP/PPPoE compiled P4
class Encap_IPonly_Dut2ToGroup2(BaseTest):
    def setUp(self, l1=False):
        BaseTest.setUp(self)
        self.l1 = l1
        # shows how to use a filter on all our tests
        testutils.add_filter(testutils.not_ipv6_filter)

        self.dataplane = ptf.dataplane_instance
        self.dataplane.flush()

    def tearDown(self):
        testutils.reset_filters()
        BaseTest.tearDown(self)

    def runTest(self):
        random_load = str(RandString(size=1400))
        pkt1 = Ether(dst="22:22:22:33:33:33", src="aa:aa:aa:aa:ff:02") / IP(
            src="10.0.1.3", dst="10.0.2.4") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
            )]) / Raw(load=random_load)
        if not self.l1:
            pkt2 = Ether(
                dst="22:22:22:33:33:34", src="aa:aa:aa:aa:ff:02") / IP(
                src="10.0.1.3", dst="10.0.2.5") / TCP(
                sport=0xeeff, dport=50000, options=[(
                    15,
                    b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
                )]) / Raw(load=random_load)

        # 12 bytes * 0xbb = placeholder and gets ignored by set_do_not_care
        exp_pkt_1 = Ether(
            dst="22:22:22:33:33:33", src="aa:aa:aa:aa:ff:02") / IP(
            src="10.0.1.3", dst="10.0.2.4") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
            )]) / Raw(load=random_load)

        exp_pkt_2 = Ether(
            dst="22:22:22:33:33:34", src="aa:aa:aa:aa:ff:02") / IP(
            src="10.0.1.3", dst="10.0.2.5") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
            )]) / Raw(load=random_load)
        
        # Ether() / IP () / remove 20 byte TCP header, add 8 byte UDP header() / 2 byte ext host header () / 14 byte timestamps()) / old tcp payload   
        # Same for both pkt1 and pk2      
        exp_pkt_ext_host = (
            Ether(dst="55:14:df:9f:03:af", src="aa:aa:aa:aa:ff:02")
            / IP(src="10.11.12.100", dst="10.11.12.99", len=46) # len 46 as set in P4, src IP .100
            / UDP(sport=41111, dport=41111, chksum=0, len=26)
            / Exthost(len=len(pkt1)) 
            / Raw(load=b"\x0f\x10\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb")
            / Raw(load=random_load)
        )

        send_packet(self, 4, pkt1)

        m = Mask(exp_pkt_1)
        m.set_do_not_care_scapy(TCP, "chksum")
        # timestamp2 is 6 byte long, starts at bit 512 (starting from Eth Hdr)
        m.set_do_not_care(448 + (8 * 8), 48)
        verify_packet(self, m, port_id=2)

        m = Mask(exp_pkt_ext_host)
        m.set_do_not_care_scapy(UDP, "len")
        # timestamp2 is 6 byte long
        m.set_do_not_care(432, 48)
        verify_packet(self, m, port_id=5)

        verify_no_other_packets(self)

        if not self.l1:
            send_packet(self, 4, pkt2)

            m = Mask(exp_pkt_2)
            m.set_do_not_care_scapy(TCP, "chksum")
            # timestamp2 is 6 byte long, starts bit 512 (starting from Eth Hdr)
            m.set_do_not_care(448 + (8 * 8), 48)
            verify_packet(self, m, port_id=6)

            m = Mask(exp_pkt_ext_host)
            # timestamp2 is 6 byte long
            m.set_do_not_care(432, 48)
            verify_packet(self, m, port_id=5)

            verify_no_other_packets(self)