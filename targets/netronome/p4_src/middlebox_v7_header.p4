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

header ethernet_t {
    bit<48> dstAddr;
    bit<48> srcAddr;
    bit<16> etherType;
}

header ipv4_t {
    bit<4>  version;
    bit<4>  ihl;
    bit<8>  diffserv;
    bit<16> totalLen;
    bit<16> identification;
    bit<3>  flags;
    bit<13> fragOffset;
    bit<8>  ttl;
    bit<8>  protocol;
    bit<16> hdrChecksum;
    bit<32> srcAddr;
    bit<32> dstAddr;
}

header tcp_t {
    bit<16> srcPort;
    bit<16> dstPort;
    bit<32> seqNum;
    bit<32> ackNum;
    bit<4>  dataOffset;
    bit<12> opts;
    bit<16> winSize;
    bit<16> checksum;
    bit<16> urgPtr;
}

header udp_t {
    bit<16> srcPort;
    bit<16> dstPort;
    bit<16> len;
    bit<16> checksum;
}

header tcp_opt_ts_t {
    bit<8>  kind;
    bit<8>  len;
    bit<48> ts1;
    bit<16> zero;
    bit<48> ts2;
}

header nfp_mac_eg_cmd_t {
    bit     en_csum;               //enable IPv4 checksum
    bit     en_ip4_csum;            // enable UDP/TCP checksum
    bit     en_tcp_csum;            //unknown
    bit     en_udp_csum;            //unknown
    bit     en_vlan;                //unknown
    bit     en_lso;                 //unknon
    bit     en_encap;               //unknown
    bit     en_o_ip4_csum;          //unknown
    bit<16> zero;                   //unknown
    bit<8>  ts_off_byte;            ///1588 timestamp offset - timestamp will not update the checksum!
}

struct my_headers_t {
    nfp_mac_eg_cmd_t    nfp_mac_eg_cmd;
    ethernet_t          ethernet;
    ipv4_t              ipv4;
    tcp_t               tcp;
    udp_t               udp;
    tcp_opt_ts_t        tcp_opt_ts;
}

header intrinsic_metadata_t {
    bit<64> ingress_global_timestamp;
    bit<64> current_global_timestamp;
}

header meta_t {
    bit extHost; // should be send to external Host
    bit ingressStamped; // was stamped in ingress
    bit udp_fake_opt_ts; // is set to 1 if no real tcp_opt_ts was parsed in udp
}

// A hack because header.isValid() does not seem to work
header hdr_valid_t {
    bit nfp_mac_eg_cmd;
    bit ipv4;
    bit tcp;
    bit udp;
    bit tcp_opt_ts;
}

struct my_metadata_t {
    intrinsic_metadata_t intrinsic_metadata;
    meta_t               meta;
    hdr_valid_t          hdr_valid;
}

// vim: set tabstop=4 softtabstop=0 expandtab shiftwidth=4 smarttab:
