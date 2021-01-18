/*
# Copyright 2020-present Ralf Kundel, Fridolin Siegmund
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

#include <core.p4>
#include <v1model.p4>

header ethernet_t {
	bit<48> dstAddr;
	bit<48> srcAddr;
	bit<16> etherType;
}

header ipv4_t {
	bit<4>  version;
	bit<4>  ihl;
	bit<8>  diffServ;
	bit<16> paketlen;
	bit<16> id;
	bit<3>  flags;
	bit<13> fragOffset;
	bit<8>  ttl;
	bit<8>  protocol;
	bit<16> header_checksum;
	bit<32> srcAddr;
	bit<32> dstAddr;
}

header tcp_t {
	bit<16> srcPort;
	bit<16> dstPort;
	bit<32> seqNo;
	bit<32> ackNo;
	bit<4>  dataOffset;
	bit<4>  res;
	bit<8>  flags;
	bit<16> window;
	bit<16> checksum;
	bit<16> urgentPtr;
}

header udp_t {
	bit<16> srcPort;
	bit<16> dstPort;
	bit<16> len;
	bit<16> checksum;
}

header tcp_options_128bit_custom_t { // 128 bit matches the tcp-header requierement for n*32 bit length
	bit<16> myType;      // tcp options type and length (e.g. 0x0f for type 15 and 0x10 for length 16 => 0x0f10)
	bit<48> timestamp1;  // first timestamp
	bit<16> empty;
	bit<48> timestamp2;  // second timestamp when the packed passes the switch the second time
}

struct l4_metadata_t {
	//bit<16> tcpLen;               // stores the tcp length for tcp checksum calculation
	bit<1>  added_timestamp2;
	bit<16> threshold_multicast;  // a value of 49 means every 50th packet gets multicasted
	bit<16> multi_counter;        // 0 = no multicast; 1 = multicast
	bit<16> tcpLength;            // length of tcp header
	bit<1> added_empty_header;
	bit<1> flow_direction;		  //direction 0: comes in on port A of DUT, 1: comes in on port B of dut
}

struct timestamp_metadata_t {
	bit<48> delta;            // stores calculatet latency for packet
	bit<48> ave_temp;         // all deltas added together
	bit<48> count_temp;       // amount of processed packets with timestmaps
	bit<32> min_temp;         // min delta (latency)
	bit<32> max_temp;         // max delta (latency)
}

struct metadata_t {
	l4_metadata_t l4_metadata;
	timestamp_metadata_t timestamp_metadata;
}

struct headers_t {
	ethernet_t ethernet;
	ipv4_t ipv4;
	tcp_t tcp;
	udp_t udp;
	tcp_options_128bit_custom_t tcp_options_128bit_custom;
}
