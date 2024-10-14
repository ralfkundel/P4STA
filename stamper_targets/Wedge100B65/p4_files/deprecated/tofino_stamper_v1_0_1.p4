#include <core.p4>
#include <tna.p4>

#define MAC_STAMPING

#include "header_tofino_stamper_v1_0_1.p4"

////////////////// PARSER START ///////////////////////////

// taken from util.p4
parser TofinoIngressParser(
        packet_in pkt,
        out ingress_intrinsic_metadata_t ig_intr_md) {
    state start {
        pkt.extract(ig_intr_md);
        transition select(ig_intr_md.resubmit_flag) {
            1 : parse_resubmit;
            0 : parse_port_metadata;
        }
    }

    state parse_resubmit {
        // Parse resubmitted packet here.
        transition reject;
    }

    state parse_port_metadata {
        pkt.advance(64);
        transition accept;
    }
}

parser SwitchIngressParser(packet_in packet, out headers_t hdr, out my_metadata_t meta, out ingress_intrinsic_metadata_t ig_intr_md) {

	TofinoIngressParser() tofino_parser;
	Checksum() tcp_checksum;
	Checksum() udp_checksum;

	state start {
		tofino_parser.apply(packet, ig_intr_md);
		meta.l4_metadata.updateChecksum = 0;
		meta.l4_metadata.do_multicast = 0;
		meta.l4_metadata.added_empty_header = 0;
		meta.l4_metadata.updateChecksum = 0;
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
		tcp_checksum.subtract({hdr.ipv4.paketlen});
		transition select(hdr.ipv4.protocol) {
			8w0x6: parse_tcp;
			8w0x11: parse_udp;
			default: accept;
		}
	}

	state parse_tcp {
		packet.extract(hdr.tcp);
		tcp_checksum.subtract({hdr.tcp.checksum});
		tcp_checksum.subtract({hdr.tcp.dataOffset, hdr.tcp.res, hdr.tcp.flags}); //actually not all needed but 8bit steps necessary
		tcp_checksum.subtract({hdr.tcp.srcPort});
		meta.l4_metadata.checksum_l4_tmp = tcp_checksum.get();
		transition select(hdr.tcp.dataOffset) {
			// timestamps can start at 0x9 = 0x5 (no options) + 128bit (0x4*32bit) timestamps and end at 0xF (0x5 + 0x4 timestamps + 0x6 existing tcp options)
			// timestamp header could be in options for offsets 0x9 to 0xf
			// timestamp header is always FIRST tcp option! 
			0x9 : parse_tcp_options_128bit_custom;
			0xA : parse_tcp_options_128bit_custom;
			0xB : parse_tcp_options_128bit_custom;
			0xC : parse_tcp_options_128bit_custom;
			0xD : parse_tcp_options_128bit_custom;
			0xE : parse_tcp_options_128bit_custom;
			0xF : parse_tcp_options_128bit_custom;
			default : accept;
		}
	}

	state parse_tcp_options_128bit_custom {
		// ensure that the first tcp option is the timestamp header
		// if not end parsing here and timestamps are automatically added as first tcp option
		transition select(packet.lookahead<bit<16>>()) {
			0x0f10: parse_tcp_options_128bit_custom_exec;
			default: accept;
		}
	}

	state parse_tcp_options_128bit_custom_exec {
		packet.extract(hdr.tcp_options_128bit_custom);
		transition accept;
	}

	state parse_udp {
		packet.extract(hdr.udp);
		udp_checksum.subtract({hdr.udp.checksum});

		//verify(hdr.udp.len >=24, error.PacketTooShort);

		packet.extract(hdr.tcp_options_128bit_custom);
		udp_checksum.subtract({hdr.tcp_options_128bit_custom});
		meta.l4_metadata.checksum_l4_tmp = udp_checksum.get();
		transition accept;
	}
}

////////////////// PARSER END ///////////////////////////

struct delta_high_operator {
	bit<32> old_low;
	bit<32> high_delta;
}



////////////////// INGRESS START ////////////////////////
control SwitchIngress(
		inout headers_t hdr,
		inout my_metadata_t meta,
		in ingress_intrinsic_metadata_t ig_intr_md,
		in ingress_intrinsic_metadata_from_parser_t ig_intr_parser_md,
		inout ingress_intrinsic_metadata_for_deparser_t ig_intr_md_for_dprsr,
		inout ingress_intrinsic_metadata_for_tm_t ig_intr_tm_md) {

	Counter<bit<32>, PortId_t>(512, CounterType_t.PACKETS_AND_BYTES) ingress_counter;
	Counter<bit<32>, PortId_t>(512, CounterType_t.PACKETS_AND_BYTES) ingress_stamped_counter;

	Register<bit<32>, bit<32>>(32w1) delta_register;
	RegisterAction<bit<32>, bit<32>, bit<32>>(delta_register) delta_register_action = {
		void apply(inout bit<32> value, out bit<32> output){
			value = (value + meta.timestamp_metadata.delta);
			output = value;
		}
	};


	Register<delta_high_operator, bit<32>>(32w1) delta_register_high;
	RegisterAction<delta_high_operator, bit<32>, bit<32>>(delta_register_high) delta_register_high_action = {
		void apply(inout delta_high_operator op, out bit<32> output){
			if(op.old_low >  meta.timestamp_metadata.delta_sum_low){
				op.high_delta = op.high_delta + 1;
			}
			op.old_low = meta.timestamp_metadata.delta_sum_low;
			output = 0;
		}
	};




	Register<bit<32>, bit<32>>(32w1) delta_register_pkts;
	RegisterAction<bit<32>, bit<32>, bit<32>>(delta_register_pkts) delta_register_pkts_action = {
			void apply(inout bit<32> value, out bit<32> read_value){
			value = value + 32w0x1;
		}
	};

	Register<bit<32>, bit<32>>(32w1) min_register;
	RegisterAction<bit<32>, bit<32>, bit<32>>(min_register) min_register_action = {
			void apply(inout bit<32> min_value, out bit<32> unused){
			if(min_value == 0){
				min_value = meta.timestamp_metadata.delta;		
			} else if(meta.timestamp_metadata.delta < min_value) {
				min_value = meta.timestamp_metadata.delta;
			}
		}
	};

	Register<bit<32>, bit<32>>(32w1) max_register;
	RegisterAction<bit<32>, bit<32>, bit<32>>(max_register) max_register_action = {
			void apply(inout bit<32> max_value, out bit<32> unused){
			if (meta.timestamp_metadata.delta > max_value) {
				max_value = meta.timestamp_metadata.delta;
			}
		}
	};

	Register< bit<32>, bit<32>> (32w1) multi_counter_register;

	RegisterAction<bit<32>, bit<32>, bit<1> >(multi_counter_register) multi_counter_register_action = {
		
		void apply(inout bit<32> counter, out bit<1> read_value){
			if(counter >= (bit<32>)meta.l4_metadata.threshold_multicast) {
				read_value = 1w0x1;
				counter = 32w0x0;
			} else {
				read_value = 1w0x0;
				counter = counter + 1;
			}
		}

	};

	action send(bit<9> egress_port) {
		ig_intr_tm_md.ucast_egress_port = egress_port;
	}

	action no_op() {
	}

	action add_timestamp_header_tcp(){
		hdr.tcp_options_128bit_custom.setValid();
		hdr.tcp_options_128bit_custom.myType = 16w0x0f11;
		hdr.tcp_options_128bit_custom.empty = 16w0x0;
		//hdr.tcp.dataOffset = hdr.tcp.dataOffset + 4w0x4; // e.g. 0x5 -> 0x9
		// workaround .. tcp offset is set in control sequence from new_offset metadata
		meta.l4_metadata.new_offset = (bit<4>)(hdr.tcp.dataOffset + 4w0x4); //0x8;//new_offset;
		hdr.ipv4.paketlen = hdr.ipv4.paketlen + 16w0x10; // + 16 byte payload (tcp header + payload)
		meta.l4_metadata.added_empty_header = 1w0x1;
		meta.l4_metadata.updateChecksum = 1w0x1;		
	}

	action add_timestamp2_tcp(bit<16> threshold) {
		meta.l4_metadata.threshold_multicast = threshold;  // threshold for multicast how many packets get replicated
		
		#ifdef MAC_STAMPING
		hdr.tcp_options_128bit_custom.timestamp2 = ig_intr_md.ingress_mac_tstamp;  // add timestamp 2 to packet
		meta.timestamp_metadata.delta = (bit<32>)(ig_intr_md.ingress_mac_tstamp - hdr.tcp_options_128bit_custom.timestamp1);
		#else
		hdr.tcp_options_128bit_custom.timestamp2 = ig_intr_parser_md.global_tstamp;
		meta.timestamp_metadata.delta = (bit<32>)(ig_intr_parser_md.global_tstamp - hdr.tcp_options_128bit_custom.timestamp1);
		#endif
		
		meta.l4_metadata.updateChecksum = 1w0x1;
		meta.l4_metadata.timestamp2 = 1w0x1;
	}

	action add_timestamp_header_udp() {
		// no need to really add a header just use the parsed first bytes of payload
		hdr.tcp_options_128bit_custom.myType = 16w0x0f11;
		hdr.tcp_options_128bit_custom.timestamp1 = 48w0x0;
		hdr.tcp_options_128bit_custom.empty = 16w0x0;
		hdr.tcp_options_128bit_custom.timestamp2 = 48w0x0;
		meta.l4_metadata.added_empty_header = 1w0x1;
		meta.l4_metadata.updateChecksum = 1w0x1;
	}

	action add_timestamp2_udp(bit<16> threshold) {
		meta.l4_metadata.threshold_multicast = threshold;

		#ifdef MAC_STAMPING
		hdr.tcp_options_128bit_custom.timestamp2 = ig_intr_md.ingress_mac_tstamp;  // add timestamp 2 to packet
		meta.timestamp_metadata.delta = (bit<32>)(ig_intr_md.ingress_mac_tstamp - hdr.tcp_options_128bit_custom.timestamp1);
		#else
		hdr.tcp_options_128bit_custom.timestamp2 = ig_intr_parser_md.global_tstamp;
		meta.timestamp_metadata.delta = (bit<32>)(ig_intr_parser_md.global_tstamp - hdr.tcp_options_128bit_custom.timestamp1);
		#endif
		meta.l4_metadata.timestamp2 = 1w0x1;
		meta.l4_metadata.updateChecksum = 1w0x1;
	}

	action send_to_mc_group(bit<16>group) {
		ig_intr_tm_md.mcast_grp_a = group;
	}

	action count_all_ingress() {
		ingress_counter.count(ig_intr_md.ingress_port); // ingress port = index in counter array
	}

	action count_stamped_ingress() {
		ingress_stamped_counter.count(ig_intr_md.ingress_port); // ingress port = index in counter array; PortId_t = bit<9>
	}

	action check_udp_size(){
		meta.l4_metadata.udp_length_cutted = (bit<8>)(hdr.udp.len >> 5); // ignore first 5 bits, 6th bit = 32byte size = if rest is bigger than 0 udp packet is bigger than 32 byte
	}
	
	action duplicate_to_dut(bit<16>group) {
		ig_intr_tm_md.mcast_grp_a = group;
	}


///////// tables /////////

	table t_l1_forwarding {
		key = {
			ig_intr_md.ingress_port : exact;
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
			ig_intr_md.ingress_port : exact;
			hdr.ethernet.dstAddr : exact;
		}
		actions = {
			no_op;
			send;
			send_to_mc_group;
		}
		default_action = no_op;
		size = 64;
	}

	table t_l3_forwarding {
		key = {
			ig_intr_md.ingress_port : exact;
			hdr.ipv4.dstAddr: exact;
		}
		actions = {
			send;
		}
		size = 64;
	}

	table t_add_empty_timestamp_tcp {
		key = {
			hdr.tcp.dataOffset : exact;
			ig_intr_tm_md.ucast_egress_port : exact;
		}
		actions = {
			add_timestamp_header_tcp;
		}
		size = 8;
	}

	table t_timestamp2_tcp {
		key = {
			hdr.tcp.dataOffset : exact;
			hdr.tcp_options_128bit_custom.myType : exact;
			ig_intr_md.ingress_port : exact;
		}
		actions = {
			add_timestamp2_tcp;
		}
		size = 64;
	}

	table t_add_empty_timestamp_udp {
		key = {
			ig_intr_tm_md.ucast_egress_port : exact;
		}
		actions = {
			add_timestamp_header_udp;
		}
		size = 64;
	}

	table t_timestamp2_udp {
		key = {
			hdr.tcp_options_128bit_custom.myType : exact;
			ig_intr_md.ingress_port : exact;
		}
		actions = {
			add_timestamp2_udp;
		}
		size = 8;
	}
	
	table t_duplicate_to_dut {
		key =  {
			ig_intr_tm_md.ucast_egress_port : exact;
		}
		actions = {
			duplicate_to_dut;
		}
		size = 8;
	}


	apply {
		count_all_ingress();
		// only allow normal forwarding tables if tstamp2 is not 1 [which indicates a duplicated packet]
		if((bit<32>)hdr.tcp_options_128bit_custom.timestamp2 != 0x1){
			t_l1_forwarding.apply();
			t_l2_forwarding.apply();
		}
		if(hdr.ipv4.isValid()) {
			if((bit<32>)hdr.tcp_options_128bit_custom.timestamp2 != 0x1){
				t_l3_forwarding.apply();
			}
			if(hdr.tcp.isValid()) {
				// tcp offset 0xB + 0x4 = 0xF which is the highest offset allowed by TCP spec
				if(hdr.tcp.dataOffset <= 0xB){
					t_add_empty_timestamp_tcp.apply();
					if(meta.l4_metadata.new_offset > 0){
						// setting the dataOffset field in action t_add_empty_timestamp_tcp is too much
						hdr.tcp.dataOffset = meta.l4_metadata.new_offset;
					}
				}
				if(hdr.tcp_options_128bit_custom.myType == 16w0x0f10 && meta.l4_metadata.added_empty_header == 0){
					t_timestamp2_tcp.apply();	
				}
			} else if (hdr.udp.isValid()) {
				check_udp_size();
				// udp size (header + payload) must be over 24 bytes
				if(meta.l4_metadata.udp_length_cutted >= 1) {
					t_add_empty_timestamp_udp.apply();
				}
				if(hdr.tcp_options_128bit_custom.myType == 16w0x0f10 && meta.l4_metadata.added_empty_header == 0){
					t_timestamp2_udp.apply();		
				}
					
			}

			if(meta.l4_metadata.added_empty_header == 1w0x1 || meta.l4_metadata.timestamp2 == 1w0x1){
				count_stamped_ingress();
			}

			if(meta.l4_metadata.timestamp2 == 1w0x1){

				meta.timestamp_metadata.delta_sum_low = delta_register_action.execute(0);
				delta_register_high_action.execute(0);

				delta_register_pkts_action.execute(0);

				min_register_action.execute(0);
				max_register_action.execute(0);
				meta.l4_metadata.do_multicast = multi_counter_register_action.execute(0);

				if(meta.l4_metadata.do_multicast == 0x1){
					send_to_mc_group(1);
				}

			}

		}
		if(meta.l4_metadata.added_empty_header == 1w0x1){
			t_duplicate_to_dut.apply();
		}
	}
}


control SwitchIngressDeparser(packet_out packet, inout headers_t hdr, in my_metadata_t meta, in ingress_intrinsic_metadata_for_deparser_t ig_dprsr_md) {
	Checksum() ipv4_checksum;
	Checksum() tcp_checksum;
	Checksum() udp_checksum;
	apply {
		if(meta.l4_metadata.updateChecksum == 1w0x1){
			hdr.ipv4.header_checksum = ipv4_checksum.update({
				hdr.ipv4.version,
				hdr.ipv4.ihl,
				hdr.ipv4.diffServ,
				hdr.ipv4.paketlen,
				hdr.ipv4.id,
				hdr.ipv4.flags,
				hdr.ipv4.fragOffset,
				hdr.ipv4.ttl,
				hdr.ipv4.protocol,
				hdr.ipv4.srcAddr,
				hdr.ipv4.dstAddr
			});
		
			hdr.tcp.checksum = tcp_checksum.update({
				hdr.ipv4.paketlen,
				hdr.tcp.dataOffset,
				hdr.tcp.res,
				hdr.tcp.flags,
				hdr.tcp.srcPort,
				meta.l4_metadata.checksum_l4_tmp,
				hdr.tcp_options_128bit_custom
			});

			hdr.udp.checksum = udp_checksum.update(data = {
				hdr.tcp_options_128bit_custom,
				meta.l4_metadata.checksum_l4_tmp
			}, zeros_as_ones = true);
		}
		packet.emit(hdr);
	}
}

////////////////// INGRESS END ////////////////////////


////////////////// EGRESS START ////////////////////////

parser TofinoEgressParser(packet_in pkt, out egress_intrinsic_metadata_t eg_intr_md) {
    state start {
        pkt.extract(eg_intr_md);
        transition accept;
    }
}


parser SwitchEgressParser(packet_in packet, out headers_t hdr, out my_metadata_t meta, out egress_intrinsic_metadata_t eg_intr_md) {

	TofinoEgressParser() tofino_parser;
	Checksum() tcp_checksum;
    Checksum() udp_checksum;

	state start {
		tofino_parser.apply(packet, eg_intr_md);
		meta.l4_metadata.updateChecksum = 0;
		meta.l4_metadata.do_multicast = 0;
		meta.l4_metadata.updateChecksum = 0;
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
		tcp_checksum.subtract({hdr.ipv4.paketlen});
		transition select(hdr.ipv4.protocol) {
			8w0x6: parse_tcp;
			8w0x11: parse_udp;
			default: accept;
		}
	}

	state parse_tcp {
		packet.extract(hdr.tcp);
		tcp_checksum.subtract({hdr.tcp.checksum});
		tcp_checksum.subtract({hdr.tcp.dataOffset, hdr.tcp.res, hdr.tcp.flags}); //actually not all needed but 8bit steps necessary
		tcp_checksum.subtract({hdr.tcp.srcPort});
		meta.l4_metadata.checksum_l4_tmp = tcp_checksum.get();
		transition select(hdr.tcp.dataOffset) {
			// timestamps can start at 0x9 = 0x5 (no options) + 128bit (0x4*32bit) timestamps and end at 0xF (0x5 + 0x4 timestamps + 0x6 existing tcp options)
			// timestamp header could be in options for offsets 0x9 to 0xf
			// timestamp header is always FIRST option! 
			0x9 : parse_tcp_options_128bit_custom;
			0xA : parse_tcp_options_128bit_custom;
			0xB : parse_tcp_options_128bit_custom;
			0xC : parse_tcp_options_128bit_custom;
			0xD : parse_tcp_options_128bit_custom;
			0xE : parse_tcp_options_128bit_custom;
			0xF : parse_tcp_options_128bit_custom;
			default : accept;
		}
	}

	state parse_tcp_options_128bit_custom {
		// ensure that the first tcp option is the timestamp header (0x0f11 indicates that header was added in ingress)
		transition select(packet.lookahead<bit<16>>()) {
			0x0f10: parse_tcp_options_128bit_custom_exec;
			0x0f11: parse_tcp_options_128bit_custom_exec;
			default: accept;
		}
	}

	state parse_tcp_options_128bit_custom_exec {
		packet.extract(hdr.tcp_options_128bit_custom);
		transition accept;
	}

	state parse_udp {
		packet.extract(hdr.udp);
		udp_checksum.subtract({hdr.udp.checksum});

		//verify(hdr.udp.len >=24, error.PacketTooShort);

		packet.extract(hdr.tcp_options_128bit_custom);
		udp_checksum.subtract({hdr.tcp_options_128bit_custom});
		meta.l4_metadata.checksum_l4_tmp = udp_checksum.get();
		transition accept;
	}
}

control SwitchEgress(
    inout headers_t hdr,
	inout my_metadata_t meta,
	in egress_intrinsic_metadata_t eg_intr_md,
	in egress_intrinsic_metadata_from_parser_t eg_intr_parser_md,
	inout egress_intrinsic_metadata_for_deparser_t eg_intr_md_for_dprsr,
	inout egress_intrinsic_metadata_for_output_port_t eg_intr_md_for_oport) {

	Counter<bit<32>, PortId_t>(512, CounterType_t.PACKETS_AND_BYTES) egress_counter;
	Counter<bit<32>, PortId_t>(512, CounterType_t.PACKETS_AND_BYTES) egress_stamped_counter;

	action change_mac(bit<48> dst) { // changes mac destination, used for multicast to set to ff:ff:..
		hdr.ethernet.dstAddr = dst;
	}

	action add_timestamp1_tcp() {
		#ifdef MAC_STAMPING
		hdr.tcp_options_128bit_custom.setInvalid();
		hdr.tcp_options_128bit_custom_without.setValid(); // add header for timestamp2 only because tofino inserts (not updates!) timestamp1 at given position
		hdr.tcp_options_128bit_custom_without.myType = 16w0x0f10;
		hdr.tcp_options_128bit_custom_without.timestamp2 = 48w0x0;
		hdr.ptp.setValid();
		hdr.ptp.udp_cksum_byte_offset = 8w50; //This is dangerous for additinal headers ...
		hdr.ptp.cf_byte_offset = 8w56; //it's okay to set fixed offset because timestamps are always first tcp option and IPv6 is not supported currently
		hdr.ptp.updated_cf = 48w0;
		eg_intr_md_for_oport.update_delay_on_tx = 1w1;
		#else
		hdr.tcp_options_128bit_custom.timestamp1 = eg_intr_parser_md.global_tstamp; //tstamp (ns) ARRIVAL at egress -> MAC more accurate
		#endif
		meta.l4_metadata.updateChecksum = 1w0x1;
	}

	action add_timestamp1_udp() {
		#ifdef MAC_STAMPING
		hdr.tcp_options_128bit_custom.setInvalid();
		hdr.tcp_options_128bit_custom_without.setValid(); // add header for timestamp2 only because tofino inserts (not updates!) timestamp1 at given position
		hdr.tcp_options_128bit_custom_without.myType = 16w0x0f10;
		hdr.tcp_options_128bit_custom_without.timestamp2 = 48w0x0;
		hdr.ptp.setValid();
		hdr.ptp.udp_cksum_byte_offset = 8w40;
		hdr.ptp.cf_byte_offset = 8w44; //it's okay to set fixed offset because timestamps are always first bytes in udp payload and IPv6 is not supported currently
		hdr.ptp.updated_cf = 48w0x0;
		eg_intr_md_for_oport.update_delay_on_tx = 1w1;
		#else
		hdr.tcp_options_128bit_custom.timestamp1 = eg_intr_parser_md.global_tstamp;
		#endif
		meta.l4_metadata.updateChecksum = 1w0x1;
	}

	action count_all_egress() {
		egress_counter.count(eg_intr_md.egress_port); // egress port = index in counter array
	}

	action count_stamped_egress() {
		egress_stamped_counter.count(eg_intr_md.egress_port); // egress port = index in counter array; PortId_t = bit<9>
	}
	
	action change_empty_field() {
		//hdr.ipv4.ttl = 8w42;
		#ifdef MAC_STAMPING
		hdr.tcp_options_128bit_custom_without.timestamp2 = 0x1;
		#else
		hdr.tcp_options_128bit_custom.timestamp2 = 0x1;
		#endif
	}


///////// tables /////////
	table broadcast_mac {
		key = {
			eg_intr_md.egress_port : exact;
		}
		actions = {
			change_mac;
		}
		size = 32;
	}
	
	table t_mark_duplicate {
		key = {
			eg_intr_md.egress_port : exact;
		}
		actions = {
			change_empty_field;
		}
		size = 8;
	}

	apply {
		broadcast_mac.apply();
		if(hdr.ipv4.isValid()) {
			// 0x0f11 indicates that timestamp header was added in ingress pipeline, change to correct type
			if(hdr.tcp_options_128bit_custom.isValid() && hdr.tcp_options_128bit_custom.myType == 16w0x0f11){
				hdr.tcp_options_128bit_custom.myType = 16w0x0f10;
		 		if(hdr.tcp.isValid()) {
		 			add_timestamp1_tcp();
		 		} else if (hdr.udp.isValid()) {
		 			add_timestamp1_udp();
		 		}
		 		if(eg_intr_md.egress_rid != 0){
		 			t_mark_duplicate.apply();
		 		}
			}

			#ifdef MAC_STAMPING
			if( (hdr.tcp_options_128bit_custom.isValid() && hdr.tcp_options_128bit_custom.myType == 16w0x0f10) || ( hdr.tcp_options_128bit_custom_without.isValid() && hdr.tcp_options_128bit_custom_without.myType == 16w0x0f10)){
				count_stamped_egress();
			}
			#else
			if( hdr.tcp_options_128bit_custom.isValid() && hdr.tcp_options_128bit_custom.myType == 16w0x0f10 ){
				count_stamped_egress();
			}
			#endif
			
		}
		count_all_egress();

		
	}
}

////////////////// EGRESS END ////////////////////////

control SwitchEgressDeparser(packet_out packet, inout headers_t hdr, in my_metadata_t meta, in egress_intrinsic_metadata_for_deparser_t eg_dprsr_md) {
	Checksum() tcp_checksum;
	Checksum() udp_checksum;
	/*Checksum() ipv4_checksum;*/

	apply {
		if(meta.l4_metadata.updateChecksum == 1w0x1){
			hdr.tcp.checksum = tcp_checksum.update({
				hdr.ipv4.paketlen,
				hdr.tcp.dataOffset,
				hdr.tcp.res,
				hdr.tcp.flags,
				hdr.tcp.srcPort,
				meta.l4_metadata.checksum_l4_tmp,
				#ifdef MAC_STAMPING
				hdr.tcp_options_128bit_custom_without
				#else
				hdr.tcp_options_128bit_custom//original so gings
				#endif
			});

		 	hdr.udp.checksum = udp_checksum.update(data = {
		 		#ifdef MAC_STAMPING
				hdr.tcp_options_128bit_custom_without,
				#else
				hdr.tcp_options_128bit_custom,//original so gings
				#endif
		 		meta.l4_metadata.checksum_l4_tmp
		 	}, zeros_as_ones = true);
		
		 }
		#ifdef MAC_STAMPING
		packet.emit(hdr.ptp);
		packet.emit(hdr.ethernet);
		packet.emit(hdr.ipv4);
		packet.emit(hdr.tcp);
		packet.emit(hdr.udp);
		packet.emit(hdr.tcp_options_128bit_custom_without); // when packet passes the first time through the switch custom_without is valid and custom is invalid
		packet.emit(hdr.tcp_options_128bit_custom); // when packet passes the second time through the switch custom is valid and custom_without is invalid
		#else
		packet.emit(hdr);
		#endif
		
	}
}

// there must be Parser/main/Deparser for both Ingress and Egress when using "Switch(pipe)" -> tofino TNA model
Pipeline(SwitchIngressParser(),
	SwitchIngress(),
	SwitchIngressDeparser(),
	SwitchEgressParser(), 
	SwitchEgress(),
	SwitchEgressDeparser()) pipe;

Switch(pipe) main;

