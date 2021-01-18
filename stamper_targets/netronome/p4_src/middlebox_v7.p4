/*
# Copyright 2020-present Ralf Kundel, Moritz Jordan
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
*/

#define CSUM_OFFLOADING 1


#include <core.p4>
#include <v1model.p4>
#include <nfp_target.p4>
#include "middlebox_v7_header.p4"

/***************** C O N S T A N T S *********************/
const bit<16> ETHERTYPE_IPV4 = 0x0800;
const bit<8>  IPPROT_TCP = 0x06;
const bit<8>  IPPROT_UDP = 0x11;
const bit<8>  TCP_OPT_TS = 0x0F;
const bit<8>  TCP_OPT_TS_LEN = 0x10;

const bit<32> PORT_NUMBER_ALL = 8;
const bit<32> PORT_NUMBER_PHY = 4;

/*********** P A R S E R S and C O N T R O L S ***********/
action nop() {
}

parser MyParser(packet_in                 packet,
                out   my_headers_t        hdr,
                inout my_metadata_t       meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        meta.hdr_valid.nfp_mac_eg_cmd = 0;
        meta.hdr_valid.ipv4 = 0;
        meta.hdr_valid.tcp = 0;
        meta.hdr_valid.udp = 0;
        meta.hdr_valid.tcp_opt_ts = 0;
        packet.extract(hdr.ethernet);

        transition select(hdr.ethernet.etherType) {
            ETHERTYPE_IPV4: parse_ipv4;
            default:        accept;
        }
    }

    state parse_ipv4 {
        meta.hdr_valid.ipv4 = 1;

        packet.extract(hdr.ipv4);

        transition select(hdr.ipv4.protocol) {
            IPPROT_TCP: parse_tcp_1;
            IPPROT_UDP: parse_udp_1;
            default:    accept;
        }
    }

    state parse_tcp_1 {
        meta.hdr_valid.tcp = 1;

        packet.extract(hdr.tcp);

        // only look for options if header is long enough for options
        transition select(hdr.tcp.dataOffset) {
            4w0x0 &&& 4w0xc:    accept; // 0x0 - 0x3
            4w0x4 &&& 4w0xe:    accept; // 0x4 - 0x5
            default:            parse_tcp_2;
        }
    }

    state parse_tcp_2 {
        transition select(packet.lookahead<bit<16>>()) {
            TCP_OPT_TS ++ TCP_OPT_TS_LEN:       parse_tcp_opt_ts;
            default:                            accept;
        }
    }

    state parse_udp_1 {
        meta.hdr_valid.udp = 1;

        packet.extract(hdr.udp);

        // only parse further if package is long enough to hold timestamps
        transition select(hdr.udp.len) {
            16w0x0 &&& 16w0xfff0:       accept; // 0x0 - 0xf
            16w0x10 &&& 16w0xfff8:      accept; // 0x10 - 0x17
            default:                    parse_udp_2;
        }
    }

    state parse_udp_2 {
        transition select(packet.lookahead<bit<16>>()) {
            TCP_OPT_TS ++ TCP_OPT_TS_LEN:       parse_tcp_opt_ts; // unsafe match
            default:                            parse_udp_data_128bit;
        }
    }

    state parse_tcp_opt_ts {
        meta.hdr_valid.tcp_opt_ts = 1;

        packet.extract(hdr.tcp_opt_ts);

        meta.meta.udp_fake_opt_ts = 0;

        transition accept;
    }

    state parse_udp_data_128bit {
        meta.hdr_valid.tcp_opt_ts = 1;

        packet.extract(hdr.tcp_opt_ts);

        meta.meta.udp_fake_opt_ts = 1;

        transition accept;
    }
}

control MyVerifyChecksum(inout my_headers_t hdr,
                         inout my_metadata_t meta) {
    apply { }
}

control MyIngress(inout my_headers_t     hdr,
                  inout my_metadata_t    meta,
                  inout standard_metadata_t standard_metadata) {

    // direct counters are not yet supported
    counter(PORT_NUMBER_ALL + 1, CounterType.packets_and_bytes) c_throughput_ingress;
    counter(PORT_NUMBER_ALL + 1, CounterType.packets_and_bytes) c_stamped_throughput_ingress; // 2 changed PORT_NUMBER_ALL

    register<bit<32>>(1) r_extHost_max;
    register<bit<32>>(1) r_extHost_count;
    register<bit<64>>(1) r_delta_sum;
    register<bit<32>>(1) r_delta_count;
    register<bit<32>>(1) r_delta_min;
    register<bit<32>>(1) r_delta_max;

    action c_throughput_ingress_count(bit<32> index) {
        c_throughput_ingress.count(index);
    }
    action c_stamped_throughput_ingress_count(bit<32> index) {
        c_stamped_throughput_ingress.count(index);
    }

    action send(bit<16> spec) {
        standard_metadata.egress_spec = spec;
    }

    action timestamp2_tcp() {
        hdr.tcp_opt_ts.ts2[31:0] = meta.intrinsic_metadata.ingress_global_timestamp[31:0];

        // checksum incremental update (RFC 1624): tcp_opt_ts.ts2
        bit<32> tmp;

        //dirty workaround as egress mac is unable to update csum (or we don't know how to do)
        tmp = (bit<32>) hdr.tcp.checksum - (bit<32>) hdr.tcp_opt_ts.ts1[47:32] - (bit<32>) hdr.tcp_opt_ts.ts1[31:16] - (bit<32>) hdr.tcp_opt_ts.ts1[15:0];
        hdr.tcp.checksum = tmp[15:0] - (~ tmp[31:16]) - 1;

        tmp = (bit<32>) hdr.tcp.checksum - (bit<32>) hdr.tcp_opt_ts.ts2[47:32] - (bit<32>) hdr.tcp_opt_ts.ts2[31:16] - (bit<32>) hdr.tcp_opt_ts.ts2[15:0];
        hdr.tcp.checksum = tmp[15:0] - (~ tmp[31:16]) - 1;


        meta.meta.ingressStamped = 1;
    }

    action timestamp2_udp() {
        hdr.tcp_opt_ts.ts2[31:0] = meta.intrinsic_metadata.ingress_global_timestamp[31:0];

        if(hdr.udp.checksum != 0x0) {
            // checksum incremental update (RFC 1624): tcp_opt_ts.ts2
            bit<32> tmp;
            //workaround as egress mac is unable to update csum after timestamping (or we don't know how to do)
            tmp = (bit<32>) hdr.udp.checksum - (bit<32>) hdr.tcp_opt_ts.ts1[47:32] - (bit<32>) hdr.tcp_opt_ts.ts1[31:16] - (bit<32>) hdr.tcp_opt_ts.ts1[15:0];
            hdr.udp.checksum = tmp[15:0] - (~ tmp[31:16]) - 1;

            tmp = (bit<32>) hdr.udp.checksum - (bit<32>) hdr.tcp_opt_ts.ts2[47:32] - (bit<32>) hdr.tcp_opt_ts.ts2[31:16] - (bit<32>) hdr.tcp_opt_ts.ts2[15:0];
            hdr.udp.checksum = tmp[15:0] - (~ tmp[31:16]) - 1;
        }

        meta.meta.ingressStamped = 1;
    }

    // workaround for flowcache
    action send_if_extHost(bit<16> spec) {
        if(meta.meta.extHost == 1) {
            standard_metadata.egress_spec = spec;
        }
    }


    table t_throughput_ingress {
        key = {
            standard_metadata.ingress_port: exact;
        }
        actions = {
            c_throughput_ingress_count;
        }
        default_action = c_throughput_ingress_count(0);
        size = PORT_NUMBER_ALL;
    }

    table t_l1_forwarding {
        key = {
            standard_metadata.ingress_port: exact;
        }
        actions = {
            nop;
            send;
        }
        default_action = nop();
        size = PORT_NUMBER_ALL;
    }

    table t_bcast_forwarding {
        key = {
            hdr.ethernet.dstAddr: exact;
        }
        actions = {
            nop;
            send;
        }
        default_action = nop();
        size = PORT_NUMBER_ALL;
    }


    table t_l2_forwarding {
        key = {
            standard_metadata.ingress_port: exact;
            hdr.ethernet.dstAddr: exact;
        }
        actions = {
            nop;
            send;
        }
        default_action = nop();
        size = PORT_NUMBER_ALL;
    }

    table t_l3_forwarding {
        key = {
            standard_metadata.ingress_port: exact;
            hdr.ipv4.dstAddr: exact;
        }
        actions = {
            nop;
            send;
        }
        default_action = nop();
        size = PORT_NUMBER_ALL;
    }

    table t_timestamp2 {
        key = {
            standard_metadata.ingress_port: exact;
            hdr.ipv4.protocol: exact;
        }
        actions = {
            timestamp2_tcp;
            timestamp2_udp;
        }
        size = 4;
    }

    table t_stamped_throughput_ingress {
        key = {
            standard_metadata.ingress_port: exact;
        }
        actions = {
            c_stamped_throughput_ingress_count;
        }
        size = 2;
    }

    table t_extHost {
        key = {
            standard_metadata.ingress_port: exact;
        }
        actions = {
            send_if_extHost;
        }
        size = 8;
    }

    action check_for_extHost() {
        bit<32> count;
        bit<32> max;
        r_extHost_count.read(count, 0);
        r_extHost_max.read(max, 0);
        if(count < max) {
            count = count + 1;
        } else {
            count = 0;
            meta.meta.extHost = 1;
        }
        r_extHost_count.write(0, count);
    }

    action delta_calculation() {
        bit<32> delta;
        bit<32> tmp;

        // Overflow detection
        if(hdr.tcp_opt_ts.ts2[31:0] < hdr.tcp_opt_ts.ts1[31:0])
            hdr.tcp_opt_ts.ts2[32:32] = 0x1;
        // For TimeStampFrc=0x0
        //if(hdr.tcp_opt_ts.ts2[31:0] < hdr.tcp_opt_ts.ts1[31:0])
        //    hdr.tcp_opt_ts.ts2[31:0] = hdr.tcp_opt_ts.ts2[31:0] + 0x3b9aca00; // = 1s

        delta = (bit<32>) (hdr.tcp_opt_ts.ts2 - hdr.tcp_opt_ts.ts1);

        {
            bit<64> tmp64;
            r_delta_sum.read(tmp64, 0);
            r_delta_sum.write(0, tmp64 + (bit<64>) delta);
        }

        r_delta_count.read(tmp, 0);
        r_delta_count.write(0, tmp + 1);

        r_delta_min.read(tmp, 0);
        if (delta < tmp || tmp == 0) {
            tmp = delta;
        }
        r_delta_min.write(0, tmp);

        r_delta_max.read(tmp, 0);
        if (delta > tmp) {
            tmp = delta;
        }
        r_delta_max.write(0, tmp);
    }

    apply {
        t_throughput_ingress.apply();

        t_bcast_forwarding.apply();
        t_l1_forwarding.apply();
        t_l2_forwarding.apply();


        if(meta.hdr_valid.ipv4 == 1) {
            t_l3_forwarding.apply();

            if(meta.hdr_valid.tcp_opt_ts == 1 && meta.meta.udp_fake_opt_ts == 0) {
                t_timestamp2.apply();

                if(meta.meta.ingressStamped == 1) {
                    delta_calculation();

                    check_for_extHost();
                    t_extHost.apply();

                    t_stamped_throughput_ingress.apply();
                }
            }
        }
    }
}


control MyEgress(inout my_headers_t     hdr,
                 inout my_metadata_t    meta,
                 inout standard_metadata_t standard_metadata) {

    // direct counters are not yet supported
    counter(PORT_NUMBER_ALL + 1, CounterType.packets_and_bytes) c_throughput_egress;
    counter(PORT_NUMBER_ALL + 1, CounterType.packets_and_bytes) c_stamped_throughput_egress; // 2 changed to PORT_NUMBER_ALL

    action c_throughput_egress_count(bit<32> index) {
        c_throughput_egress.count(index);
    }
    action c_stamped_throughput_egress_count(bit<32> index) {
        c_stamped_throughput_egress.count(index);
    }

    action change_mac(bit<48> dstAddr) {
        hdr.ethernet.dstAddr = dstAddr;
    }

    action add_empty_nfp_mac_eg_cmd() {
        hdr.nfp_mac_eg_cmd.setValid();
        meta.hdr_valid.nfp_mac_eg_cmd = 1;

        #ifdef CSUM_OFFLOADING
        hdr.nfp_mac_eg_cmd = { 0, 1, 0, 0, 0, 0, 0, 0, 0, 0x0 };
        if(meta.hdr_valid.tcp == 1){
            hdr.tcp.checksum = 0x0;
        }
        if(meta.hdr_valid.udp == 1){
            hdr.udp.checksum = 0x0;
        }
        #else
        hdr.nfp_mac_eg_cmd = { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0x0 };
        #endif
    }


    action timestamp1_tcp_mac() {
        hdr.tcp_opt_ts.setValid();
        hdr.nfp_mac_eg_cmd.setValid();
        meta.hdr_valid.tcp_opt_ts = 1;
        meta.hdr_valid.nfp_mac_eg_cmd = 1;
        hdr.tcp_opt_ts = { TCP_OPT_TS, TCP_OPT_TS_LEN, 0, 0, 0 };

        hdr.ipv4.totalLen = hdr.ipv4.totalLen + (bit<16>) TCP_OPT_TS_LEN;
        hdr.tcp.dataOffset = hdr.tcp.dataOffset + 0x4; //= TCP_OPT_TS_LEN / 4

        bit<32> tmp;

        // checksum incremental update (RFC 1624): ipv4.totalLen
        tmp = (bit<32>) hdr.ipv4.hdrChecksum - (bit<32>) TCP_OPT_TS_LEN;
        hdr.ipv4.hdrChecksum = tmp[15:0] - (~ tmp[31:16]) - 1;


        #ifdef CSUM_OFFLOADING
            hdr.nfp_mac_eg_cmd = {0, 1, 0, 0, 0, 0, 0, 0, 0x00, 0x3a };
            hdr.tcp.checksum = 0;
        #else
            hdr.nfp_mac_eg_cmd = {0, 0, 0, 0, 0, 0, 0, 0, 0x00, 0x3a };
            // checksum incremental update (RFC 1624): ipv4.totalLen, tcp.dataOffset, tcp_opt_ts.kind, tcp_opt_ts.len
            tmp = (bit<32>) hdr.tcp.checksum - (bit<32>) TCP_OPT_TS_LEN - (((bit<32>) 0x4) << 12) - (((bit<32>) hdr.tcp_opt_ts.kind) << 8) - (bit<32>) hdr.tcp_opt_ts.len;
            hdr.tcp.checksum = tmp[15:0] - (~ tmp[31:16]) - 1;
        #endif
    }

    action timestamp1_udp_mac() {
        hdr.tcp_opt_ts = { TCP_OPT_TS, TCP_OPT_TS_LEN, 0, 0, 0 };
        #ifdef CSUM_OFFLOADING
        hdr.nfp_mac_eg_cmd = { 0, 1, 0, 0, 0, 0, 0, 0, 0x00, 0x2e }; 
        hdr.udp.checksum = 0x0;
        #else
        hdr.nfp_mac_eg_cmd = { 0, 0, 0, 0, 0, 0, 0, 0, 0x00, 0x2e }; 
        #endif

    }

    table t_change_mac {
        key = {
            standard_metadata.egress_port: exact;
        }
        actions = {
            change_mac;
        }
        size = 1;
    }

    table t_add_empty_nfp_mac_eg_cmd {
        key = {
            standard_metadata.egress_port: exact;
        }
        actions = {
            nop;
            add_empty_nfp_mac_eg_cmd;
        }
        default_action = nop;
        size = PORT_NUMBER_PHY;
    }

    table t_throughput_egress {
        key = {
            standard_metadata.egress_port: exact;
        }
        actions = {
            c_throughput_egress_count;
        }
        default_action = c_throughput_egress_count(0);
        size = PORT_NUMBER_ALL;
    }

    table t_stamped_throughput_egress {
        key = {
            standard_metadata.egress_port: exact;
            hdr.ipv4.protocol: exact;
        }
        actions = {
            c_stamped_throughput_egress_count;
        }
        size = 12;
    }

    table t_timestamp1 {
        key = {
            standard_metadata.egress_port: exact;
            hdr.ipv4.protocol: exact;
        }
        actions = {
            timestamp1_tcp_mac;
            timestamp1_udp_mac;
        }
        size = 4;
    }

    apply {
        t_change_mac.apply();

        t_add_empty_nfp_mac_eg_cmd.apply();

        t_throughput_egress.apply();

        if((meta.hdr_valid.tcp == 1 && hdr.tcp.dataOffset < 0xc) || (meta.hdr_valid.udp == 1 && meta.hdr_valid.tcp_opt_ts == 1)) {
            t_timestamp1.apply();
        }
        if(meta.hdr_valid.tcp_opt_ts == 1 && hdr.tcp_opt_ts.kind == 0x0f && hdr.tcp_opt_ts.len == 0x10){
            t_stamped_throughput_egress.apply();
        }
    }

}

control MyComputeChecksum(inout my_headers_t hdr,
                          inout my_metadata_t meta) {
    apply { }
}

control MyDeparser(packet_out packet, in my_headers_t hdr) {
    apply {
        packet.emit(hdr);
    }
}

/*************** F U L L P A C K A G E *****************/
V1Switch(
    MyParser(),
    MyVerifyChecksum(),
    MyIngress(),
    MyEgress(),
    MyComputeChecksum(),
    MyDeparser()
) main;

// vim: set tabstop=4 softtabstop=0 expandtab shiftwidth=4 smarttab:
