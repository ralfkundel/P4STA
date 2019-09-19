#include "header_middlebox_16.p4"
#include "checksum_16.p4"

parser parserImpl(packet_in packet, out headers_t hdr, inout metadata_t meta, inout standard_metadata_t standard_metadata) {

	state start {
        transition parse_ethernet;
    }
	
    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            16w0x0800: parse_ipv4;
            default: accept;
        }
    }
	
    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        meta.l4_metadata.tcpLength = hdr.ipv4.paketlen - 16w20;
		transition select(hdr.ipv4.protocol) {
			8w0x6: parse_tcp;
			8w0x11: parse_udp;
			default: accept;
		}
    }
	
	state parse_tcp {
		packet.extract(hdr.tcp);
		transition select(hdr.tcp.dataOffset) {
			4w0x8: parse_tcp_options_96bit;                 //Offset 8*32bit = 32 byte = 12 Byte present options + 20 Byte remaining TCP header
			4w0x9: parse_tcp_options_128bit_custom;         //Offset 9*32bit = 16 custom Bytes + 20 Bytes remaining TCP header
			4w0xC: parse_tcp_options_96_and_128bit_custom;  //Offset 10*32bit =	we have 12 Byte present options and our 16 custom Bytes + 20 Bytes remaining tcp header
			default: accept;
		}
	}
	
	state parse_tcp_options_96bit {
		packet.extract(hdr.tcp_options_96bit);
		transition accept;
	}
	
	state parse_tcp_options_96_and_128bit_custom {
		packet.extract(hdr.tcp_options_96bit);
		transition select(hdr.tcp_options_96bit.options) {
			default: parse_tcp_options_128bit_custom;
		}
	}
	
	state parse_tcp_options_128bit_custom {
		packet.extract(hdr.tcp_options_128bit_custom);
		transition accept;
	}

	state parse_udp {
		packet.extract(hdr.udp);
		packet.extract(hdr.tcp_options_128bit_custom);
		transition accept;
	}
}


control ingress(inout headers_t hdr, inout metadata_t meta, inout standard_metadata_t standard_metadata) {
	register<bit<48>>(2) time_average;       					// stores all deltas added together in [0] and in [1] amount of processed time-deltas (latency of packet)
	register<bit<32>>(2) time_delta_min_max; 					// time_delta_min_max[0] = min; time_delta_min_max[1] = max
	register<bit<16>>(2) multi_counter_r;    					// stores the current counter for paket duplication to external host
	counter(64, CounterType.packets_and_bytes) ingress_counter;
	counter(64, CounterType.packets_and_bytes) ingress_stamped_counter;
	counter(2, CounterType.packets_and_bytes) c_add_second_timestamp;
	
	///////// actions /////////
	action send(bit<9> egress_port) {
		standard_metadata.egress_spec = egress_port;
	}
	
	action no_op() {
	}
	
	action send_to_mc_grp(bit<16> grp) {
		standard_metadata.mcast_grp = grp;
	}
	
	action add_timestamp2(bit<16> threshold, bit<1> direction) {
		meta.l4_metadata.threshold_multicast = (bit<16>)threshold; // threshold for multicast how many packets get replicated
		hdr.tcp_options_128bit_custom.timestamp2 = (bit<48>)standard_metadata.ingress_global_timestamp;
		meta.l4_metadata.added_timestamp2 = 1;
		meta.timestamp_metadata.delta = (bit<48>)standard_metadata.ingress_global_timestamp - hdr.tcp_options_128bit_custom.timestamp1;
		meta.timestamp_metadata.ave_temp = meta.timestamp_metadata.ave_temp + (bit<48>)meta.timestamp_metadata.delta;
		meta.timestamp_metadata.count_temp = meta.timestamp_metadata.count_temp + 1;
		meta.l4_metadata.flow_direction = direction;
		c_add_second_timestamp.count((bit<32>) direction);
	}
	
	action add_timestamp_header(bit<4> new_offset, bit<1> direction) {
		hdr.tcp_options_128bit_custom.setValid();
		hdr.tcp.dataOffset = new_offset;
		hdr.ipv4.paketlen = hdr.ipv4.paketlen + 16w0x10;
		hdr.tcp_options_128bit_custom.myType = 16w0x0f10;
		meta.l4_metadata.tcpLen = meta.l4_metadata.tcpLen + 16w0x10;
		meta.l4_metadata.flow_direction = direction;
		meta.l4_metadata.added_empty_header = 1;
	}

	action add_timestamp_header_udp(bit<1> direction) {
		hdr.tcp_options_128bit_custom.myType = 16w0x0f10;
		meta.l4_metadata.flow_direction = direction;
		meta.l4_metadata.added_empty_header = 1;
	}

	action count_all_ingress() {
		ingress_counter.count((bit<32>) standard_metadata.ingress_port); // ingress port = index in counter array
	}

	action count_stamped_ingress() {
		ingress_stamped_counter.count((bit<32>) standard_metadata.ingress_port); // ingress port = index in counter array
	}

	///////// tables /////////
	table t_l1_forwarding {
		key = {
			standard_metadata.ingress_port : exact;
		}
		actions = {
			no_op;
			send;
		}
		default_action = no_op;
		size = 64;
	}
	
	table t_l2_forwarding {
		key =  {
			standard_metadata.ingress_port : exact;
			hdr.ethernet.dstAddr : exact;
		}
		actions = {
			no_op;
			send;
			send_to_mc_grp;
		}
		default_action = no_op;
		size = 64;
		}
		
	table t_l3_forwarding {
		key = {
			standard_metadata.ingress_port : exact;
			hdr.ipv4.dstAddr: exact;
		}
		actions = {
			send;
		}
		size = 64;
	}
	
	table t_add_timestamp_header {
		key = {
			hdr.tcp.dataOffset : exact;
			standard_metadata.egress_spec : exact;
		}
		actions = {
			add_timestamp_header;
		}
		size = 4;
	}
	
	table timestamp2 {
		key = {
			hdr.tcp.dataOffset : exact;
			hdr.tcp_options_128bit_custom.myType : exact;
			standard_metadata.ingress_port : exact;
		}
		actions = {
			add_timestamp2;
		}
		size = 4;
	}

	table t_add_timestamp_header_udp {
		key = {
			standard_metadata.egress_spec : exact;
		}
		actions = {
			add_timestamp_header_udp;
		}
		size = 4;
	}
	
	table timestamp2_udp {
		key = {
			hdr.tcp_options_128bit_custom.myType : exact;
			standard_metadata.ingress_port : exact;
		}
		actions = {
			add_timestamp2;
		}
		size = 4;
	}
	
	table multicast {
		key = {
			//hdr.tcp.dataOffset : exact;
			standard_metadata.ingress_port : exact;
			standard_metadata.egress_spec : exact;
		}
		actions = {
			send_to_mc_grp;
		}
		size = 64;
	}
	
	apply {
		count_all_ingress();
		t_l1_forwarding.apply();
		t_l2_forwarding.apply();
		if(hdr.ipv4.isValid()) {
			t_l3_forwarding.apply();
			if(hdr.tcp.isValid() || hdr.udp.isValid()) {
				time_average.read(meta.timestamp_metadata.ave_temp, 0);
				time_average.read(meta.timestamp_metadata.count_temp, 1);
				time_delta_min_max.read(meta.timestamp_metadata.min_temp, 0);
				time_delta_min_max.read(meta.timestamp_metadata.max_temp, 1);
				
			}

			if(hdr.tcp.isValid()) {
				t_add_timestamp_header.apply();
				if(hdr.tcp_options_128bit_custom.myType == 16w0x0f10){
					count_stamped_ingress();
				}
				//time_average.read(meta.timestamp_metadata.ave_temp, 0);
				//time_average.read(meta.timestamp_metadata.count_temp, 1);
				//time_delta_min_max.read(meta.timestamp_metadata.min_temp, 0);
				//time_delta_min_max.read(meta.timestamp_metadata.max_temp, 1);
				timestamp2.apply();
				//time_average.write(0, meta.timestamp_metadata.ave_temp);
				//time_average.write(1, meta.timestamp_metadata.count_temp);
				//if((bit<48>)meta.timestamp_metadata.min_temp > meta.timestamp_metadata.delta) {
				//	if(meta.timestamp_metadata.delta > 0){
				//		time_delta_min_max.write(0, (bit<32>)meta.timestamp_metadata.delta);
				//	}
				//}
				//else if((bit<48>)meta.timestamp_metadata.min_temp == 0) {
				//	time_delta_min_max.write(0, (bit<32>)meta.timestamp_metadata.delta);
				//}
				//if((bit<48>)meta.timestamp_metadata.max_temp < meta.timestamp_metadata.delta) {
				//	time_delta_min_max.write(1, (bit<32>)meta.timestamp_metadata.delta);
				//}

				//if(meta.l4_metadata.added_timestamp2 == 1){
				//	multi_counter_r.read(meta.l4_metadata.multi_counter, (bit<32>)meta.l4_metadata.flow_direction);
				//	if(meta.l4_metadata.multi_counter >= meta.l4_metadata.threshold_multicast){
				//		multicast.apply();
				//		meta.l4_metadata.multi_counter = 0;
				//		multi_counter_r.write( (bit<32>) meta.l4_metadata.flow_direction, meta.l4_metadata.multi_counter);
				//	} else {
				//		meta.l4_metadata.multi_counter = meta.l4_metadata.multi_counter + 1;
				//		multi_counter_r.write( (bit<32>) meta.l4_metadata.flow_direction, meta.l4_metadata.multi_counter);
				//	}
				//}

			}
			else if(hdr.udp.isValid()) {
				if(hdr.udp.len >= 0x18) { // udp size (header + payload) must be over 24 bytes
					t_add_timestamp_header_udp.apply();
					if(hdr.tcp_options_128bit_custom.myType == 16w0x0f10){
						count_stamped_ingress();
					}
					timestamp2_udp.apply();
				}
			}
			
			if(hdr.tcp.isValid() || hdr.udp.isValid()) {
				time_average.write(0, meta.timestamp_metadata.ave_temp);
				time_average.write(1, meta.timestamp_metadata.count_temp);	
				if((bit<48>)meta.timestamp_metadata.min_temp > meta.timestamp_metadata.delta) {
					if(meta.timestamp_metadata.delta > 0){
						time_delta_min_max.write(0, (bit<32>)meta.timestamp_metadata.delta);
					}
				}
				else if((bit<48>)meta.timestamp_metadata.min_temp == 0) {
					time_delta_min_max.write(0, (bit<32>)meta.timestamp_metadata.delta);
				}
				if((bit<48>)meta.timestamp_metadata.max_temp < meta.timestamp_metadata.delta) {
					time_delta_min_max.write(1, (bit<32>)meta.timestamp_metadata.delta);
				}

				if(meta.l4_metadata.added_timestamp2 == 1){
					multi_counter_r.read(meta.l4_metadata.multi_counter, (bit<32>)meta.l4_metadata.flow_direction);
					if(meta.l4_metadata.multi_counter >= meta.l4_metadata.threshold_multicast){
						multicast.apply();
						meta.l4_metadata.multi_counter = 0;
						multi_counter_r.write( (bit<32>) meta.l4_metadata.flow_direction, meta.l4_metadata.multi_counter);
					} else {
						meta.l4_metadata.multi_counter = meta.l4_metadata.multi_counter + 1;
						multi_counter_r.write( (bit<32>) meta.l4_metadata.flow_direction, meta.l4_metadata.multi_counter);
					}
				}	
			}
		}
	}
}

control egress(inout headers_t hdr, inout metadata_t meta, inout standard_metadata_t standard_metadata) {
	
	counter(64, CounterType.packets_and_bytes) egress_counter;
	counter(64, CounterType.packets_and_bytes) egress_stamped_counter;
	counter(2, CounterType.packets_and_bytes) c_add_first_timestamp;

	///////// actions /////////
	action change_mac(bit<48> dst) { // changes mac destination, used for multicast to set to ff:ff:..
		hdr.ethernet.dstAddr = dst;
	}
	
	action add_timestamp1() {
		hdr.tcp_options_128bit_custom.timestamp1 = (bit<48>)standard_metadata.egress_global_timestamp;
		c_add_first_timestamp.count((bit<32>)meta.l4_metadata.flow_direction);
	}
	
	action count_all_egress() {
		egress_counter.count((bit<32>) standard_metadata.egress_port); // egress port = index in counter array
	}

	action count_stamped_egress() {
		egress_stamped_counter.count((bit<32>) standard_metadata.egress_port); // egress port = index in counter array
	}
	
	///////// tables /////////
	table broadcast_mac {
		key = {
			standard_metadata.egress_port : exact;
		}
		actions = {
			change_mac;
		}
		size = 32;
	}
	
    apply {
		broadcast_mac.apply();
		if(hdr.ipv4.isValid()) {
			if(meta.l4_metadata.added_empty_header == 1) {
				if(hdr.tcp.isValid() || hdr.udp.isValid()) {
					add_timestamp1();
					count_stamped_egress();
				}
		}
		count_all_egress();
		//if(hdr.tcp_options_128bit_custom.myType == 16w0x0f10){
		//	count_stamped_egress();
		//}
		}
	}
}

control DeparserImpl(packet_out packet, in headers_t hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
	packet.emit(hdr.tcp);
	packet.emit(hdr.tcp_options_96bit);
	packet.emit(hdr.udp);
	packet.emit(hdr.tcp_options_128bit_custom);
    }
}

V1Switch(parserImpl(), verifyChecksum(), ingress(), egress(), computeChecksum(), DeparserImpl()) main;
