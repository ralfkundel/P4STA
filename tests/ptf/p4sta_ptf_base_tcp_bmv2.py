from ptf.base_tests import BaseTest
from ptf.mask import Mask
from ptf.testutils import *
from scapy.all import Ether, IP, TCP, Raw, RandString, UDP
import ptf
import ptf.testutils as testutils


class Group2ToDut2(BaseTest):
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
        pkt1 = Ether(dst="aa:aa:aa:aa:ff:02", src="22:22:22:33:33:33") / IP(
            src="10.0.2.4", dst="10.0.1.3") / TCP(
            sport=0xeeff, dport=50000) / Raw(load=random_load)
        pkt2 = Ether(dst="aa:aa:aa:aa:ff:02", src="22:22:22:33:33:34") / IP(
            src="10.0.2.5", dst="10.0.1.3") / TCP(
            sport=0xeeff, dport=50000) / Raw(load=random_load)

        # 12 bytes * 0xaa = placeholder and gets ignored by set_do_not_care
        exp_pkt1 = Ether(dst="aa:aa:aa:aa:ff:02", src="22:22:22:33:33:33")/IP(
            src="10.0.2.4", dst="10.0.1.3")/TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\x00\x00\x00\x00\x00\x00"
            )])/Raw(load=random_load)

        exp_pkt2 = Ether(dst="aa:aa:aa:aa:ff:02", src="22:22:22:33:33:34")/IP(
            src="10.0.2.5", dst="10.0.1.3")/TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\x00\x00\x00\x00\x00\x00"
            )]) / Raw(load=random_load)

        send_packet(self, 2, pkt1)
        m = Mask(exp_pkt1)
        m.set_do_not_care_scapy(TCP, "chksum")
        # timestamp1 is 6 byte long at starts at bit 448
        # (starting from Ethernet Header)
        m.set_do_not_care(448, 48)
        verify_packets(self, m, ports=[4])

        send_packet(self, 6, pkt2)
        m2 = Mask(exp_pkt2)
        m2.set_do_not_care_scapy(TCP, "chksum")
        # timestamp1 is 6 byte long, starts at bit 448 (starting from Eth Hdr)
        m2.set_do_not_care(448, 48)
        verify_packets(self, m2, ports=[4])


class Dut1ToGroup1(BaseTest):
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
        pkt = Ether(dst="22:22:22:22:22:22", src="aa:aa:aa:aa:ff:01") / IP(
            src="10.0.2.4", dst="10.0.1.3") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
            )]) / Raw(load=random_load)

        # 12 bytes * 0xbb = placeholder and gets ignored by set_do_not_care
        exp_pkt = Ether(dst="22:22:22:22:22:22", src="aa:aa:aa:aa:ff:01") / IP(
            src="10.0.2.4", dst="10.0.1.3") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
            )]) / Raw(load=random_load)

        exp_pkt_ext_host = Ether(
            dst="ff:ff:ff:ff:ff:ff", src="aa:aa:aa:aa:ff:01") / IP(
            src="10.0.2.4", dst="10.0.1.3") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
            )]) / Raw(load=random_load)

        send_packet(self, 3, pkt)

        m = Mask(exp_pkt)
        m.set_do_not_care_scapy(TCP, "chksum")
        # timestamp2 is 6 byte long, starts at bit 512 (starting from Eth Hdr)
        m.set_do_not_care(448 + (8 * 8), 48)
        verify_packet(self, m, port_id=1)

        # check duplicated packet at ext host
        m2 = Mask(exp_pkt_ext_host)
        m2.set_do_not_care_scapy(TCP, "chksum")
        # timestamp2 is 6 byte long, starts at bit 512 (starting from Eth Hdr)
        m2.set_do_not_care(448 + (8 * 8), 48)
        verify_packet(self, m2, port_id=5)

        pkt_dup = Ether(dst="22:22:22:22:22:22", src="aa:aa:aa:aa:ff:01") / IP(
            src="10.0.2.4", dst="10.0.1.3") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\x00\x00\x00\x00\x00\x01"
            )]) / Raw(load=random_load)

        if self.dataplane_duplication > 0:
            send_packet(self, 3, pkt_dup)
            # should only be forwarded to ext host
            verify_packet(self, m2, port_id=5)

        verify_no_other_packets(self)


class Group1ToDut1(BaseTest):
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

        verify_no_other_packets(self)


class Dut2ToGroup2(BaseTest):
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

        exp_pkt_ext_host_1 = Ether(
            dst="ff:ff:ff:ff:ff:ff", src="aa:aa:aa:aa:ff:02") / IP(
            src="10.0.1.3", dst="10.0.2.4") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
            )]) / Raw(load=random_load)

        exp_pkt_ext_host_2 = Ether(
            dst="ff:ff:ff:ff:ff:ff", src="aa:aa:aa:aa:ff:02") / IP(
            src="10.0.1.3", dst="10.0.2.5") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
            )]) / Raw(load=random_load)

        send_packet(self, 4, pkt1)

        m = Mask(exp_pkt_1)
        m.set_do_not_care_scapy(TCP, "chksum")
        # timestamp2 is 6 byte long, starts at bit 512 (starting from Eth Hdr)
        m.set_do_not_care(448 + (8 * 8), 48)
        verify_packet(self, m, port_id=2)

        m = Mask(exp_pkt_ext_host_1)
        m.set_do_not_care_scapy(TCP, "chksum")
        # timestamp2 is 6 byte long, starts at bit 512 (starting from Eth Hdr)
        m.set_do_not_care(448 + (8 * 8), 48)
        verify_packet(self, m, port_id=5)

        verify_no_other_packets(self)

        if not self.l1:
            send_packet(self, 4, pkt2)

            m = Mask(exp_pkt_2)
            m.set_do_not_care_scapy(TCP, "chksum")
            # timestamp2 is 6 byte long, starts bit 512 (starting from Eth Hdr)
            m.set_do_not_care(448 + (8 * 8), 48)
            verify_packet(self, m, port_id=6)

            m = Mask(exp_pkt_ext_host_2)
            m.set_do_not_care_scapy(TCP, "chksum")
            # timestamp2 is 6 byte long, starts bit 512 (starting from Eth Hdr)
            m.set_do_not_care(448 + (8 * 8), 48)
            verify_packet(self, m, port_id=5)

            verify_no_other_packets(self)


class Only1DUTGroup1ToDut1(BaseTest):
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
        pkt = Ether(dst="22:22:22:22:22:23", src="22:22:22:22:22:22") / IP(
            src="10.0.1.3", dst="10.0.1.4") / TCP(
            sport=0xeeff, dport=50000) / Raw(load=random_load)

        pkt2 = Ether(dst="22:22:22:22:22:22", src="22:22:22:22:22:23") / IP(
            src="10.0.1.4", dst="10.0.1.3") / TCP(
            sport=0xeeff, dport=50000) / Raw(load=random_load)

        # 12 bytes * 0xaa = placeholder and gets ignored by set_do_not_care
        exp_pkt = Ether(dst="22:22:22:22:22:23", src="22:22:22:22:22:22") / IP(
            src="10.0.1.3", dst="10.0.1.4") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\x00\x00\x00\x00\x00\x00"
            )]) / Raw(load=random_load)

        exp_pkt2 = Ether(
            dst="22:22:22:22:22:22", src="22:22:22:22:22:23") / IP(
            src="10.0.1.4", dst="10.0.1.3") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\x00\x00\x00\x00\x00\x00"
            )]) / Raw(load=random_load)

        send_packet(self, 1, pkt)

        m = Mask(exp_pkt)
        m.set_do_not_care_scapy(TCP, "chksum")
        # timestamp1 is 6 byte long, starts at bit 448 (starting from Eth Hdr)
        m.set_do_not_care(448, 48)
        verify_packets(self, m, ports=[3])

        if not self.l1:
            send_packet(self, 2, pkt2)

            m = Mask(exp_pkt2)
            m.set_do_not_care_scapy(TCP, "chksum")
            m.set_do_not_care(448, 48)
            verify_packets(self, m, ports=[3])

            verify_no_other_packets(self)


class Only1DUTDut1ToGroup1(BaseTest):
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
        pkt = Ether(dst="22:22:22:22:22:22", src="22:22:22:22:22:23") / IP(
            src="10.0.1.4", dst="10.0.1.3") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\x00\x00\x00\x00\x00\x00"
            )]) / Raw(load=random_load)

        pkt2 = Ether(dst="22:22:22:22:22:23", src="22:22:22:22:22:22") / IP(
            src="10.0.1.3", dst="10.0.1.4") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\x00\x00\x00\x00\x00\x00"
            )]) / Raw(load=random_load)

        # 12 bytes * 0xaa = placeholder and gets ignored by set_do_not_care
        exp_pkt = Ether(dst="22:22:22:22:22:22", src="22:22:22:22:22:23") / IP(
            src="10.0.1.4", dst="10.0.1.3") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
            )]) / Raw(load=random_load)

        exp_pkt2 = Ether(
            dst="22:22:22:22:22:23", src="22:22:22:22:22:22") / IP(
            src="10.0.1.3", dst="10.0.1.4") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
            )]) / Raw(load=random_load)

        exp_pkt_ext_host = Ether(
            dst="ff:ff:ff:ff:ff:ff", src="22:22:22:22:22:23") / IP(
            src="10.0.1.4", dst="10.0.1.3") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
            )]) / Raw(load=random_load)

        exp_pkt_ext_host2 = Ether(
            dst="ff:ff:ff:ff:ff:ff", src="22:22:22:22:22:22") / IP(
            src="10.0.1.3", dst="10.0.1.4") / TCP(
            sport=0xeeff, dport=50000, options=[(
                15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
            )]) / Raw(load=random_load)

        send_packet(self, 3, pkt)

        m = Mask(exp_pkt)
        m.set_do_not_care_scapy(TCP, "chksum")
        # timestamp2 is 6 byte long, starts at bit 512 (starting from Eth Hdr)
        m.set_do_not_care(448 + (8 * 8), 48)
        verify_packet(self, m, port_id=1)

        # check duplicated packet at ext host
        m2 = Mask(exp_pkt_ext_host)
        m2.set_do_not_care_scapy(TCP, "chksum")
        # timestamp2 is 6 byte long, starts at bit 512 (starting from Eth Hdr)
        m2.set_do_not_care(448 + (8 * 8), 48)
        verify_packet(self, m2, port_id=5)

        if not self.l1:
            send_packet(self, 3, pkt2)

            m3 = Mask(exp_pkt2)
            m3.set_do_not_care_scapy(TCP, "chksum")
            m3.set_do_not_care(448 + (8 * 8), 48)
            verify_packet(self, m3, port_id=2)

            # check duplicated packet at ext host
            m4 = Mask(exp_pkt_ext_host2)
            m4.set_do_not_care_scapy(TCP, "chksum")
            # timestamp2 is 6 byte long, starts bit 512 (starting from Eth Hdr)
            m4.set_do_not_care(448 + (8 * 8), 48)
            verify_packet(self, m4, port_id=5)

        verify_no_other_packets(self)






# from ptf.base_tests import BaseTest
# from ptf.mask import Mask
# from ptf.testutils import *
# from scapy.all import Ether, IP, TCP, Raw, RandString, UDP
# import ptf
# import ptf.testutils as testutils

# from ext_host_header_scapy import Exthost


# class Group2ToDut2(BaseTest):
#     def setUp(self):
#         BaseTest.setUp(self)

#         # shows how to use a filter on all our tests
#         testutils.add_filter(testutils.not_ipv6_filter)

#         self.dataplane = ptf.dataplane_instance
#         self.dataplane.flush()

#     def tearDown(self):
#         testutils.reset_filters()
#         BaseTest.tearDown(self)

#     def runTest(self):
#         random_load = str(RandString(size=1400))
#         pkt1 = Ether(dst="aa:aa:aa:aa:ff:02", src="22:22:22:33:33:33") / IP(
#             src="10.0.2.4", dst="10.0.1.3") / TCP(
#             sport=0xeeff, dport=50000) / Raw(load=random_load)
#         pkt2 = Ether(dst="aa:aa:aa:aa:ff:02", src="22:22:22:33:33:34") / IP(
#             src="10.0.2.5", dst="10.0.1.3") / TCP(
#             sport=0xeeff, dport=50000) / Raw(load=random_load)

#         # 12 bytes * 0xaa = placeholder and gets ignored by set_do_not_care
#         exp_pkt1 = Ether(dst="aa:aa:aa:aa:ff:02", src="22:22:22:33:33:33")/IP(
#             src="10.0.2.4", dst="10.0.1.3")/TCP(
#             sport=0xeeff, dport=50000, options=[(
#                 15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\x00\x00\x00\x00\x00\x00"
#             )])/Raw(load=random_load)

#         exp_pkt2 = Ether(dst="aa:aa:aa:aa:ff:02", src="22:22:22:33:33:34")/IP(
#             src="10.0.2.5", dst="10.0.1.3")/TCP(
#             sport=0xeeff, dport=50000, options=[(
#                 15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\x00\x00\x00\x00\x00\x00"
#             )]) / Raw(load=random_load)

#         send_packet(self, 2, pkt1)
#         m = Mask(exp_pkt1)
#         m.set_do_not_care_scapy(TCP, "chksum")
#         # timestamp1 is 6 byte long at starts at bit 448
#         # (starting from Ethernet Header)
#         m.set_do_not_care(448, 48)
#         verify_packets(self, m, ports=[4])

#         send_packet(self, 6, pkt2)
#         m2 = Mask(exp_pkt2)
#         m2.set_do_not_care_scapy(TCP, "chksum")
#         # timestamp1 is 6 byte long, starts at bit 448 (starting from Eth Hdr)
#         m2.set_do_not_care(448, 48)
#         verify_packets(self, m2, ports=[4])


# class Dut1ToGroup1(BaseTest):
#     def setUp(self):
#         BaseTest.setUp(self)

#         # shows how to use a filter on all our tests
#         testutils.add_filter(testutils.not_ipv6_filter)

#         self.dataplane = ptf.dataplane_instance
#         self.dataplane.flush()

#         self.dataplane_duplication = 0

#     def tearDown(self):
#         testutils.reset_filters()
#         BaseTest.tearDown(self)

#     def runTest(self):
#         random_load = str(RandString(size=1400))
#         pkt = Ether(dst="22:22:22:22:22:22", src="aa:aa:aa:aa:ff:01") / IP(
#             src="10.0.2.4", dst="10.0.1.3") / TCP(
#             sport=0xeeff, dport=50000, options=[(
#                 15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
#             )]) / Raw(load=random_load)

#         # 12 bytes * 0xbb = placeholder and gets ignored by set_do_not_care
#         exp_pkt = Ether(dst="22:22:22:22:22:22", src="aa:aa:aa:aa:ff:01") / IP(
#             src="10.0.2.4", dst="10.0.1.3") / TCP(
#             sport=0xeeff, dport=50000, options=[(
#                 15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
#             )]) / Raw(load=random_load)

#         # Ether() / IP () / remove 20 byte TCP header, add 8 byte UDP header() / 2 byte ext host header () / 14 byte timestamps()) / old tcp payload        
#         exp_pkt_ext_host = (
#             Ether(dst="55:14:df:9f:03:af", src="aa:aa:aa:aa:ff:01")
#             / IP(src="10.0.2.4", dst="10.11.12.99", len=46) # len 46 as set in P4
#             / UDP(sport=41111, dport=41111, chksum=0, len=26)
#             / Exthost(len=len(pkt)) 
#             / Raw(load=b"\x0f\x10\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb")
#             / Raw(load=random_load)
#         )

#         send_packet(self, 3, pkt)

#         m = Mask(exp_pkt)
#         m.set_do_not_care_scapy(TCP, "chksum")
#         # timestamp2 is 6 byte long, starts at bit 512 (starting from Eth Hdr)
#         m.set_do_not_care(448 + (8 * 8), 48)
#         verify_packet(self, m, port_id=1)

#         # check duplicated packet at ext host
#         m2 = Mask(exp_pkt_ext_host)
#         m2.set_do_not_care_scapy(UDP, "len")
#         # m2.set_do_not_care_scapy(TCP, "chksum")
#         # timestamp2 is 6 byte long
#         m2.set_do_not_care(432, 48)
#         verify_packet(self, m2, port_id=5)

#         pkt_dup = Ether(dst="22:22:22:22:22:22", src="aa:aa:aa:aa:ff:01") / IP(
#             src="10.0.2.4", dst="10.0.1.3") / TCP(
#             sport=0xeeff, dport=50000, options=[(
#                 15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\x00\x00\x00\x00\x00\x01"
#             )]) / Raw(load=random_load)

#         if self.dataplane_duplication > 0:
#             send_packet(self, 3, pkt_dup)
#             # should only be forwarded to ext host
#             verify_packet(self, m2, port_id=5)

#         verify_no_other_packets(self)


# class Group1ToDut1(BaseTest):
#     def setUp(self):
#         BaseTest.setUp(self)

#         # shows how to use a filter on all our tests
#         testutils.add_filter(testutils.not_ipv6_filter)

#         self.dataplane = ptf.dataplane_instance
#         self.dataplane.flush()

#         self.dataplane_duplication = 0

#     def tearDown(self):
#         testutils.reset_filters()
#         BaseTest.tearDown(self)

#     def runTest(self):
#         random_load = str(RandString(size=1400))
#         pkt = Ether(dst="aa:aa:aa:aa:ff:01", src="22:22:22:22:22:22") / IP(
#             src="10.0.1.3", dst="10.0.2.4") / TCP(
#             sport=0xeeff, dport=50000) / Raw(load=random_load)

#         # 12 bytes * 0xaa = placeholder and gets ignored by set_do_not_care
#         exp_pkt = Ether(dst="aa:aa:aa:aa:ff:01", src="22:22:22:22:22:22") / IP(
#             src="10.0.1.3", dst="10.0.2.4") / TCP(
#             sport=0xeeff, dport=50000, options=[(
#                 15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\x00\x00\x00\x00\x00\x00"
#             )]) / Raw(load=random_load)

#         send_packet(self, 1, pkt)

#         m = Mask(exp_pkt)
#         m.set_do_not_care_scapy(TCP, "chksum")
#         # timestamp1 is 6 byte long, starts at bit 448 (starting from Eth Hdr)
#         m.set_do_not_care(448, 48)
#         verify_packet(self, m, port_id=3)

#         exp_pkt_dup = Ether(
#             dst="aa:aa:aa:aa:ff:01", src="22:22:22:22:22:22") / IP(
#             src="10.0.1.3", dst="10.0.2.4") / TCP(
#             sport=0xeeff, dport=50000, options=[(
#                 15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\x00\x00\x00\x00\x00\x01"
#             )]) / Raw(load=random_load)
#         m = Mask(exp_pkt_dup)
#         m.set_do_not_care_scapy(TCP, "chksum")
#         # timestamp1 is 6 byte long, starts at bit 448 (starting from Eth Hdr)
#         m.set_do_not_care(448, 48)

#         for i in range(self.dataplane_duplication):
#             verify_packet(self, m, port_id=3)

#         verify_no_other_packets(self)


# class Dut2ToGroup2(BaseTest):
#     def setUp(self, l1=False):
#         BaseTest.setUp(self)
#         self.l1 = l1
#         # shows how to use a filter on all our tests
#         testutils.add_filter(testutils.not_ipv6_filter)

#         self.dataplane = ptf.dataplane_instance
#         self.dataplane.flush()

#     def tearDown(self):
#         testutils.reset_filters()
#         BaseTest.tearDown(self)

#     def runTest(self):
#         random_load = str(RandString(size=1400))
#         pkt1 = Ether(dst="22:22:22:33:33:33", src="aa:aa:aa:aa:ff:02") / IP(
#             src="10.0.1.3", dst="10.0.2.4") / TCP(
#             sport=0xeeff, dport=50000, options=[(
#                 15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
#             )]) / Raw(load=random_load)
#         if not self.l1:
#             pkt2 = Ether(
#                 dst="22:22:22:33:33:34", src="aa:aa:aa:aa:ff:02") / IP(
#                 src="10.0.1.3", dst="10.0.2.5") / TCP(
#                 sport=0xeeff, dport=50000, options=[(
#                     15,
#                     b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
#                 )]) / Raw(load=random_load)

#         # 12 bytes * 0xbb = placeholder and gets ignored by set_do_not_care
#         exp_pkt_1 = Ether(
#             dst="22:22:22:33:33:33", src="aa:aa:aa:aa:ff:02") / IP(
#             src="10.0.1.3", dst="10.0.2.4") / TCP(
#             sport=0xeeff, dport=50000, options=[(
#                 15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
#             )]) / Raw(load=random_load)

#         exp_pkt_2 = Ether(
#             dst="22:22:22:33:33:34", src="aa:aa:aa:aa:ff:02") / IP(
#             src="10.0.1.3", dst="10.0.2.5") / TCP(
#             sport=0xeeff, dport=50000, options=[(
#                 15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
#             )]) / Raw(load=random_load)

#         # exp_pkt_ext_host_1 = Ether(
#         #     dst="ff:ff:ff:ff:ff:ff", src="aa:aa:aa:aa:ff:02") / IP(
#         #     src="10.0.1.3", dst="10.0.2.4") / TCP(
#         #     sport=0xeeff, dport=50000, options=[(
#         #         15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
#         #     )]) / Raw(load=random_load)
        
#         # Ether() / IP () / remove 20 byte TCP header, add 8 byte UDP header() / 2 byte ext host header () / 14 byte timestamps()) / old tcp payload   
#         # Same for both pkt1 and pk2      
#         exp_pkt_ext_host = (
#             Ether(dst="55:14:df:9f:03:af", src="aa:aa:aa:aa:ff:02")
#             / IP(src="10.0.1.3", dst="10.11.12.99", len=46) # len 46 as set in P4
#             / UDP(sport=41111, dport=41111, chksum=0, len=26)
#             / Exthost(len=len(pkt1)) 
#             / Raw(load=b"\x0f\x10\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb")
#             / Raw(load=random_load)
#         )

#         send_packet(self, 4, pkt1)

#         m = Mask(exp_pkt_1)
#         m.set_do_not_care_scapy(TCP, "chksum")
#         # timestamp2 is 6 byte long, starts at bit 512 (starting from Eth Hdr)
#         m.set_do_not_care(448 + (8 * 8), 48)
#         verify_packet(self, m, port_id=2)

#         m = Mask(exp_pkt_ext_host)
#         m.set_do_not_care_scapy(UDP, "len")
#         # timestamp2 is 6 byte long
#         m.set_do_not_care(432, 48)
#         verify_packet(self, m, port_id=5)

#         verify_no_other_packets(self)

#         if not self.l1:
#             send_packet(self, 4, pkt2)

#             m = Mask(exp_pkt_2)
#             m.set_do_not_care_scapy(TCP, "chksum")
#             # timestamp2 is 6 byte long, starts bit 512 (starting from Eth Hdr)
#             m.set_do_not_care(448 + (8 * 8), 48)
#             verify_packet(self, m, port_id=6)

#             m = Mask(exp_pkt_ext_host)
#             # timestamp2 is 6 byte long
#             m.set_do_not_care(432, 48)
#             verify_packet(self, m, port_id=5)

#             verify_no_other_packets(self)


# class Only1DUTGroup1ToDut1(BaseTest):
#     def setUp(self, l1=False):
#         BaseTest.setUp(self)
#         self.l1 = l1
#         # shows how to use a filter on all our tests
#         testutils.add_filter(testutils.not_ipv6_filter)

#         self.dataplane = ptf.dataplane_instance
#         self.dataplane.flush()

#     def tearDown(self):
#         testutils.reset_filters()
#         BaseTest.tearDown(self)

#     def runTest(self):
#         random_load = str(RandString(size=1400))
#         pkt = Ether(dst="22:22:22:22:22:23", src="22:22:22:22:22:22") / IP(
#             src="10.0.1.3", dst="10.0.1.4") / TCP(
#             sport=0xeeff, dport=50000) / Raw(load=random_load)

#         pkt2 = Ether(dst="22:22:22:22:22:22", src="22:22:22:22:22:23") / IP(
#             src="10.0.1.4", dst="10.0.1.3") / TCP(
#             sport=0xeeff, dport=50000) / Raw(load=random_load)

#         # 12 bytes * 0xaa = placeholder and gets ignored by set_do_not_care
#         exp_pkt = Ether(dst="22:22:22:22:22:23", src="22:22:22:22:22:22") / IP(
#             src="10.0.1.3", dst="10.0.1.4") / TCP(
#             sport=0xeeff, dport=50000, options=[(
#                 15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\x00\x00\x00\x00\x00\x00"
#             )]) / Raw(load=random_load)

#         exp_pkt2 = Ether(
#             dst="22:22:22:22:22:22", src="22:22:22:22:22:23") / IP(
#             src="10.0.1.4", dst="10.0.1.3") / TCP(
#             sport=0xeeff, dport=50000, options=[(
#                 15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\x00\x00\x00\x00\x00\x00"
#             )]) / Raw(load=random_load)

#         send_packet(self, 1, pkt)

#         m = Mask(exp_pkt)
#         m.set_do_not_care_scapy(TCP, "chksum")
#         # timestamp1 is 6 byte long, starts at bit 448 (starting from Eth Hdr)
#         m.set_do_not_care(448, 48)
#         verify_packets(self, m, ports=[3])

#         if not self.l1:
#             send_packet(self, 2, pkt2)

#             m = Mask(exp_pkt2)
#             m.set_do_not_care_scapy(TCP, "chksum")
#             m.set_do_not_care(448, 48)
#             verify_packets(self, m, ports=[3])

#             verify_no_other_packets(self)


# class Only1DUTDut1ToGroup1(BaseTest):
#     def setUp(self, l1=False):
#         BaseTest.setUp(self)
#         self.l1 = l1
#         # shows how to use a filter on all our tests
#         testutils.add_filter(testutils.not_ipv6_filter)

#         self.dataplane = ptf.dataplane_instance
#         self.dataplane.flush()

#     def tearDown(self):
#         testutils.reset_filters()
#         BaseTest.tearDown(self)

#     def runTest(self):
#         random_load = str(RandString(size=1400))
#         pkt = Ether(dst="22:22:22:22:22:22", src="22:22:22:22:22:23") / IP(
#             src="10.0.1.4", dst="10.0.1.3") / TCP(
#             sport=0xeeff, dport=50000, options=[(
#                 15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\x00\x00\x00\x00\x00\x00"
#             )]) / Raw(load=random_load)

#         pkt2 = Ether(dst="22:22:22:22:22:23", src="22:22:22:22:22:22") / IP(
#             src="10.0.1.3", dst="10.0.1.4") / TCP(
#             sport=0xeeff, dport=50000, options=[(
#                 15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\x00\x00\x00\x00\x00\x00"
#             )]) / Raw(load=random_load)

#         # 12 bytes * 0xaa = placeholder and gets ignored by set_do_not_care
#         exp_pkt = Ether(dst="22:22:22:22:22:22", src="22:22:22:22:22:23") / IP(
#             src="10.0.1.4", dst="10.0.1.3") / TCP(
#             sport=0xeeff, dport=50000, options=[(
#                 15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
#             )]) / Raw(load=random_load)

#         exp_pkt2 = Ether(
#             dst="22:22:22:22:22:23", src="22:22:22:22:22:22") / IP(
#             src="10.0.1.3", dst="10.0.1.4") / TCP(
#             sport=0xeeff, dport=50000, options=[(
#                 15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
#             )]) / Raw(load=random_load)

#         # exp_pkt_ext_host = Ether(
#         #     dst="ff:ff:ff:ff:ff:ff", src="22:22:22:22:22:23") / IP(
#         #     src="10.0.1.4", dst="10.0.1.3") / TCP(
#         #     sport=0xeeff, dport=50000, options=[(
#         #         15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
#         #     )]) / Raw(load=random_load)
        
#         exp_pkt_ext_host = (
#             Ether(dst="55:14:df:9f:03:af", src="22:22:22:22:22:23")
#             / IP(src="10.0.1.4", dst="10.11.12.99", len=46) # len 46 as set in P4
#             / UDP(sport=41111, dport=41111, chksum=0, len=26)
#             / Exthost(len=len(pkt)) 
#             / Raw(load=b"\x0f\x10\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb")
#             / Raw(load=random_load)
#         )

#         # exp_pkt_ext_host2 = Ether(
#         #     dst="ff:ff:ff:ff:ff:ff", src="22:22:22:22:22:22") / IP(
#         #     src="10.0.1.3", dst="10.0.1.4") / TCP(
#         #     sport=0xeeff, dport=50000, options=[(
#         #         15, b"\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb"
#         #     )]) / Raw(load=random_load)
        
#         exp_pkt_ext_host2 = (
#             Ether(dst="55:14:df:9f:03:af", src="22:22:22:22:22:22")
#             / IP(src="10.0.1.3", dst="10.11.12.99", len=46) # len 46 as set in P4
#             / UDP(sport=41111, dport=41111, chksum=0, len=26)
#             / Exthost(len=len(pkt2)) 
#             / Raw(load=b"\x0f\x10\xaa\xaa\xaa\xaa\xaa\xaa\x00\x00\xbb\xbb\xbb\xbb\xbb\xbb")
#             / Raw(load=random_load)
#         )

#         send_packet(self, 3, pkt)

#         m = Mask(exp_pkt)
#         m.set_do_not_care_scapy(TCP, "chksum")
#         # timestamp2 is 6 byte long, starts at bit 512 (starting from Eth Hdr)
#         m.set_do_not_care(448 + (8 * 8), 48)
#         verify_packet(self, m, port_id=1)

#         # check duplicated packet at ext host
#         m2 = Mask(exp_pkt_ext_host)
#         m2.set_do_not_care_scapy(UDP, "len")
#         # timestamp2 is 6 byte long, starts at bit 512 (starting from Eth Hdr)
#         m2.set_do_not_care(432, 48)
#         verify_packet(self, m2, port_id=5)

#         if not self.l1:
#             send_packet(self, 3, pkt2)

#             m3 = Mask(exp_pkt2)
#             m3.set_do_not_care_scapy(TCP, "chksum")
#             m3.set_do_not_care(448 + (8 * 8), 48)
#             verify_packet(self, m3, port_id=2)

#             # check duplicated packet at ext host
#             m4 = Mask(exp_pkt_ext_host2)
#             m4.set_do_not_care_scapy(UDP, "len")
#             # timestamp2 is 6 byte long
#             m4.set_do_not_care(432, 48)
#             verify_packet(self, m4, port_id=5)

#         verify_no_other_packets(self)
