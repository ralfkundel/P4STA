#include <core.p4>

#if __TARGET_TOFINO__ == 2
#include <t2na.p4>
#else
#include <tna.p4>
#endif

#define MAC_STAMPING

//#define GTP_ENCAP
//#define PPPOE_ENCAP

#include "header_tofino_stamper_v1_3_0.p4"

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
        pkt.advance(PORT_METADATA_SIZE);
        transition accept;
    }
}

parser SwitchIngressParser(packet_in packet, out headers_t hdr, out my_metadata_t meta, out ingress_intrinsic_metadata_t ig_intr_md) {

	TofinoIngressParser() tofino_parser;
	Checksum() tcp_checksum;
	Checksum() udp_checksum;
	Checksum() icmp_checksum;

	state start {
		tofino_parser.apply(packet, ig_intr_md);
		meta.l4_metadata.updateChecksum = 0;
		meta.l4_metadata.do_multicast = 0;
		meta.l4_metadata.added_empty_header = 0;

		// best way to check if packet has generation header is checking the ingress port
		transition select(ig_intr_md.ingress_port) {
			#if __TARGET_TOFINO__ == 2
			6:		parse_pktgen;
			134: 	parse_pktgen;
			262:	parse_pktgen;
			390:	parse_pktgen;
			#else
			68:		parse_pktgen;
            196: 	parse_pktgen;
			324: 	parse_pktgen;
			452: 	parse_pktgen;
			#endif
            default: parse_ethernet;
        }
	}

	// TOFINO 1
	// 	header pktgen_timer_header_t {
	//     @padding bit<3> _pad1;
	//     bit<2> pipe_id;                     // Pipe id
	//     bit<3> app_id;                      // Application id
	//     @padding bit<8> _pad2;

	//     bit<16> batch_id;                   // Start at 0 and increment to a
	//                                         // programmed number

	//     bit<16> packet_id;                  // Start at 0 and increment to a
	//                                         // programmed number
	// }

	// TOFINO 2
	// header pktgen_timer_header_t {
	//     @padding bit<2> _pad1;
	//     bit<2> pipe_id;                     // Pipe id
	//     bit<4> app_id;                      // Application id
	//     @padding bit<8> _pad2;

	//     bit<16> batch_id;                   // Start at 0 and increment to a
	//                                         // programmed number

	//     bit<16> packet_id;                  // Start at 0 and increment to a
	//                                         // programmed number
	// }


	state parse_pktgen{
        packet.extract(hdr.pkg_gen_timer);
        transition parse_ethernet;
    }

	state parse_ethernet {
		packet.extract(hdr.ethernet);
		transition select(hdr.ethernet.etherType) {
		#ifdef GTP_ENCAP
			16w0x0800: pre_parse_ip_prot;
		#else
			16w0x0800: parse_ipv4;
		#endif
			16w0x8100: parse_vlan;
		#ifdef PPPOE_ENCAP
			16w0x8864: parse_pppoe;
		#endif
			default: accept;
		}
	}

	#ifdef GTP_ENCAP

	state pre_parse_ip_prot {
		transition select(packet.lookahead<ipv4_udp_t>().protocol) {
			8w0x11:pre_parse_gtpu_srcport;
			default: parse_ipv4;
		}
	}
	
	state pre_parse_gtpu_srcport {
		// ipv4_udp_t combines both headers in one header for lookahead -> IP -> UDP.srcPort
		transition select(packet.lookahead<ipv4_udp_t>().srcPort) {
			16w0x868: pre_parse_gtpu_dstport; //UDP and src port 2152, indicates a GTP-U packet. Next parser step checks srcport also 2152
			default: parse_ipv4;
		}
	}

	state pre_parse_gtpu_dstport {
		// ipv4_udp_t combines both headers in one header for lookahead -> IP -> UDP.dstPort
		transition select(packet.lookahead<ipv4_udp_t>().dstPort) {
			16w0x868: parse_outer_ipv4; //UDP and dst port 2152, indicates a GTP-U packet. 
			default: parse_ipv4;
		}
	}

	state parse_outer_ipv4 {
		packet.extract(hdr.outer_ipv4);
		transition parse_outer_udpGtpu; //transition parse_outer_udpGtpu;
	}

	state parse_outer_udpGtpu {
		packet.extract(hdr.outer_udp);
		// hdr.outer_udp.checksum = 0; => compiler warning, move to apply block
		packet.extract(hdr.gtpu);
		transition select(hdr.gtpu.ex_flag) {
			1w0: parse_ipv4;
			1w1: parse_extension;
		}
	}

	state parse_extension {
		packet.extract(hdr.advance);
		packet.extract(hdr.extension);
		packet.extract(hdr.last_extension);
		transition parse_ipv4;
	}

	#endif   //GTP Parsing
	
	state parse_vlan {
		packet.extract(hdr.vlan);
		transition select(hdr.vlan.etherType) {
			16w0x0800: parse_ipv4;
			16w0x8100: parse_qinq_vlan;
			default: accept;
		}
	}

	state parse_qinq_vlan {
		packet.extract(hdr.vlan_qinq);
		transition select(hdr.vlan_qinq.etherType) {
			16w0x0800: parse_ipv4;
			default: accept;
		}
	}

	#ifdef PPPOE_ENCAP
	state parse_pppoe {
        packet.extract(hdr.pppoe);
        transition select(hdr.pppoe.protocol){
            16w0x0021: parse_ipv4;
            default: accept;
        }
    }
	#endif

	state parse_ipv4 {
		packet.extract(hdr.ipv4);
		tcp_checksum.subtract({hdr.ipv4.paketlen});
		transition select(hdr.ipv4.protocol) {
			8w0x6: parse_tcp;
			8w0x11: parse_udp;
			8w0x1: parse_icmp; //TODO: parse when in vlan pppoe gtpu
			default: accept;
		}
	}

	state parse_icmp {
		packet.extract(hdr.icmp);
		icmp_checksum.subtract({hdr.icmp.checksum});

		// we overwrite icmp payload with timestamps, similar to UDP, only suitable for integrated generation of icmp packets
		packet.extract(hdr.tcp_options_128bit_custom);
		icmp_checksum.subtract({hdr.tcp_options_128bit_custom});
		meta.l4_metadata.checksum_l4_tmp = icmp_checksum.get();

		transition accept;
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

struct delta_register_pkts_high_operator {
	bit<32> old_low;
	bit<32> high_pkts;
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

	// count pakets with timestamps

	Register<bit<32>, bit<32>>(32w1) delta_register_pkts;
	RegisterAction<bit<32>, bit<32>, bit<32>>(delta_register_pkts) delta_register_pkts_action = {
			void apply(inout bit<32> value, out bit<32> output){
				value = value + 32w0x1;
				output = value;
		}
	};

	Register<delta_register_pkts_high_operator, bit<32>>(32w1) delta_register_pkts_high;
	RegisterAction<delta_register_pkts_high_operator, bit<32>, bit<32>>(delta_register_pkts_high) delta_register_pkts_high_action = {
		void apply(inout delta_register_pkts_high_operator op, out bit<32> output){
			if(op.old_low >  meta.timestamp_metadata.register_pkts_sum_low){
				op.high_pkts = op.high_pkts + 1;
			}
			op.old_low = meta.timestamp_metadata.register_pkts_sum_low;
			output = 0;
		}
	};

	// end count

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

	action add_timestamp_header_icmp() {
		// tstamp header is between icmp header and icmp header data, if there is data
		// icmp echo response is
		hdr.tcp_options_128bit_custom.setValid();
		add_timestamp_header_udp();
		// hdr.ipv4.paketlen = hdr.ipv4.paketlen + 16; not required as timestamp replace icmp data
	}

	// action add_timestamp2_icmp(){
	// 	meta.l4_metadata.threshold_multicast = threshold;

	// }

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

	table t_l1_forwarding_generation {
		key = {
			ig_intr_md.ingress_port : exact;
			hdr.pkg_gen_timer.app_id : exact;
		}
		actions = {
			no_op;
			send;
			send_to_mc_group;
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
		size = 64;
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
		size = 64;
	}

	table t_add_empty_timestamp_icmp {
		key = {
			hdr.icmp.type : exact; // we only add timestamps to type=8 icmp echo request
			ig_intr_tm_md.ucast_egress_port : exact;
		}
		actions = {
			add_timestamp_header_icmp;
		}
		size = 64;
	}
	// no timestamp2 icmp table required as we can reuse t_timestamp2_udp
	
	table t_duplicate_to_dut {
		key =  {
			ig_intr_tm_md.ucast_egress_port : exact;
		}
		actions = {
			duplicate_to_dut; // rather duplicate_to_mcgroup
		}
		size = 8;
	}

	table t_duplicate_sniff_1 {
		key =  {
			ig_intr_tm_md.ucast_egress_port : exact;
		}
		actions = {
			duplicate_to_dut; // rather duplicate_to_mcgroup
		}
		size = 8;
	}

	table t_duplicate_sniff_2 {
		key =  {
			ig_intr_md.ingress_port : exact;
		}
		actions = {
			duplicate_to_dut; // rather duplicate_to_mcgroup
		}
		size = 8;
	}


	apply {
		count_all_ingress();
		t_duplicate_sniff_1.apply();
		t_duplicate_sniff_2.apply();
		// only allow normal forwarding tables if tstamp2 is not 1 [which indicates a duplicated packet]
		if((bit<32>)hdr.tcp_options_128bit_custom.timestamp2 != 0x1){
			if(hdr.pkg_gen_timer.isValid()){
				t_l1_forwarding_generation.apply();
			} else {
				t_l1_forwarding.apply();
				t_l2_forwarding.apply();
			}
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
				// udp size (header + payload) must be over 24 bytes, implemented check: > 32 byte (easier to check)
				if(meta.l4_metadata.udp_length_cutted >= 1) {
					t_add_empty_timestamp_udp.apply();
				}
				if(hdr.tcp_options_128bit_custom.myType == 16w0x0f10 && meta.l4_metadata.added_empty_header == 0){
					t_timestamp2_udp.apply();		
				}
			} else if (hdr.icmp.isValid()) {
				t_add_empty_timestamp_icmp.apply();
				if(hdr.tcp_options_128bit_custom.myType == 16w0x0f10 && meta.l4_metadata.added_empty_header == 0){
					// we can use t_timestamp2_udp table for icmp tstamp2 as well
					t_timestamp2_udp.apply();		
				}
			}

			if(meta.l4_metadata.added_empty_header == 1w0x1 || meta.l4_metadata.timestamp2 == 1w0x1){
				count_stamped_ingress();
			}

			if(meta.l4_metadata.timestamp2 == 1w0x1){
				meta.timestamp_metadata.delta_sum_low = delta_register_action.execute(0);
				delta_register_high_action.execute(0);

				meta.timestamp_metadata.register_pkts_sum_low = delta_register_pkts_action.execute(0);
				delta_register_pkts_high_action.execute(0);

				min_register_action.execute(0);
				max_register_action.execute(0);
				meta.l4_metadata.do_multicast = multi_counter_register_action.execute(0);

				if(meta.l4_metadata.do_multicast == 0x1){
					// mc_group 1 is reserved for external host
					send_to_mc_group(1);
				}

			}
		}

		if(meta.l4_metadata.added_empty_header == 1w0x1){
			#ifdef PPPOE_ENCAP
			if(hdr.pppoe.isValid()){
				if(!hdr.udp.isValid()){ //For UDP timestamps replace payload, no add
					hdr.pppoe.totalLength = hdr.pppoe.totalLength + 16w0x10; //moved from action add_timestamp_header_tcp
				}
			}
			#endif
			#ifdef GTP_ENCAP
			if(hdr.gtpu.isValid()){
				if(!hdr.udp.isValid()){ //For UDP timestamps replace payload, no add
					hdr.outer_ipv4.paketlen = hdr.outer_ipv4.paketlen + 16w0x10;
					hdr.outer_udp.len = hdr.outer_udp.len + 16w0x10;
					hdr.gtpu.msglen = hdr.gtpu.msglen + 16w0x10;
				}
				hdr.outer_udp.checksum = 0; // only inner udp checksum is calculated (not enough ressources), moved from parser to here
			}
			#endif
			t_duplicate_to_dut.apply();
		}
		// remove packet generator header to prevent parsing in egress (ingress_port metadata not available in egress)
		hdr.pkg_gen_timer.setInvalid();
	}
}


control SwitchIngressDeparser(packet_out packet, inout headers_t hdr, in my_metadata_t meta, in ingress_intrinsic_metadata_for_deparser_t ig_dprsr_md) {
	#ifdef GTP_ENCAP
	Checksum() outer_ipv4_checksum;
	#else
	Checksum() icmp_checksum;
	#endif
	Checksum() ipv4_checksum;
	Checksum() tcp_checksum;
	Checksum() udp_checksum;
	

	apply {
		if(meta.l4_metadata.updateChecksum == 1w0x1){
			#ifdef GTP_ENCAP
			//GTP-U case
			hdr.outer_ipv4.header_checksum = outer_ipv4_checksum.update({
				hdr.outer_ipv4.version,
				hdr.outer_ipv4.ihl,
				hdr.outer_ipv4.diffServ,
				hdr.outer_ipv4.paketlen,
				hdr.outer_ipv4.id,
				hdr.outer_ipv4.flags,
				hdr.outer_ipv4.fragOffset,
				hdr.outer_ipv4.ttl,
				hdr.outer_ipv4.protocol,
				hdr.outer_ipv4.srcAddr,
				hdr.outer_ipv4.dstAddr
			});
			#endif

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

			#ifndef GTP_ENCAP
			hdr.icmp.checksum = icmp_checksum.update(data = {
				hdr.tcp_options_128bit_custom,
				meta.l4_metadata.checksum_l4_tmp
			}, zeros_as_ones = true);
			#endif
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
	Checksum() icmp_checksum;

	state start {
		tofino_parser.apply(packet, eg_intr_md);
		meta.l4_metadata.updateChecksum = 0;
		meta.l4_metadata.do_multicast = 0;
		meta.l4_metadata.updateChecksum = 0;
		meta.header_offset = 0;

		transition parse_ethernet;
	}

	state parse_ethernet {
		packet.extract(hdr.ethernet);
		transition select(hdr.ethernet.etherType) {
		#ifdef GTP_ENCAP
			16w0x0800: pre_parse_ip_prot;
		#else
			16w0x0800: parse_ipv4;
		#endif
			16w0x8100: parse_vlan;
		#ifdef PPPOE_ENCAP
			16w0x8864: parse_pppoe;
		#endif
			default: accept;
		}
	}

	#ifdef GTP_ENCAP

	state pre_parse_ip_prot {
		transition select(packet.lookahead<ipv4_udp_t>().protocol) {
			8w0x11:pre_parse_gtpu_srcport;
			default: parse_ipv4;
		}
	}
	
	state pre_parse_gtpu_srcport {
		// ipv4_udp_t combines both headers in one header for lookahead -> IP -> UDP.srcPort
		transition select(packet.lookahead<ipv4_udp_t>().srcPort) {
			16w0x868: pre_parse_gtpu_dstport; //UDP and src port 2152, indicates a GTP-U packet. Next parser step checks srcport also 2152
			default: parse_ipv4;
		}
	}


	state pre_parse_gtpu_dstport {
		// ipv4_udp_t combines both headers in one header for lookahead -> IP -> UDP.dstPort
		transition select(packet.lookahead<ipv4_udp_t>().dstPort) {
			16w0x868: parse_outer_ipv4; //UDP and dst port 2152, indicates a GTP-U packet. 
			default: parse_ipv4;
		}
	}

	state parse_outer_ipv4 {
		packet.extract(hdr.outer_ipv4);
		meta.l4_metadata.outer_ipv4_paketlen_temp = hdr.outer_ipv4.paketlen;
		transition parse_outer_udpGtpu;
	}

	state parse_outer_udpGtpu {
		packet.extract(hdr.outer_udp);
		packet.extract(hdr.gtpu);
		// if parse_extension is not reached in case of 1w0; outer_ipv4 (20) + outer_udp (8) + gtpu (8) => 36 bytes
		meta.header_offset = 36;
		transition select(hdr.gtpu.ex_flag) {
			1w0: parse_ipv4;
			1w1: parse_extension;
		}
	}

	state parse_extension {
		meta.header_offset = 44; // outer_ipv4 (20) + outer_udp (8) + gtpu (8) + advance(3) + extension (4) + last_extension (1) => 44 bytes
		packet.extract(hdr.advance);
		packet.extract(hdr.extension);
		packet.extract(hdr.last_extension);
		transition parse_ipv4;
	}

	#endif   //GTP Parsing

	// state parse_vlan {
	// 	packet.extract(hdr.vlan);
	// 	meta.header_offset = 4; //TODO: what if e.g. vlan + PPPoE?
	// 	transition select(hdr.vlan.etherType) {
	// 		16w0x0800: parse_ipv4;
	// 		default: accept;
	// 	}
	// }

	state parse_vlan {
		packet.extract(hdr.vlan);
		meta.header_offset = 4; //TODO: what if e.g. vlan + PPPoE?
		transition select(hdr.vlan.etherType) {
			16w0x0800: parse_ipv4;
			16w0x8100: parse_qinq_vlan;
			default: accept;
		}
	}

	state parse_qinq_vlan {
		packet.extract(hdr.vlan_qinq);
		meta.header_offset = 8; //TODO: what if e.g. vlan + PPPoE?
		transition select(hdr.vlan_qinq.etherType) {
			16w0x0800: parse_ipv4;
			default: accept;
		}
	}

	#ifdef PPPOE_ENCAP
	state parse_pppoe {
        packet.extract(hdr.pppoe);
		meta.header_offset = 8;
        transition select(hdr.pppoe.protocol){
            16w0x0021: parse_ipv4;
            default: accept;
        }
    }
	#endif

	state parse_ipv4 {
		packet.extract(hdr.ipv4);
		tcp_checksum.subtract({hdr.ipv4.paketlen});
		meta.l4_metadata.ipv4_paketlen_temp = hdr.ipv4.paketlen;
		transition select(hdr.ipv4.protocol) {
			8w0x6: parse_tcp;
			8w0x11: parse_udp;
			8w0x1: parse_icmp; //TODO: parse when in vlan pppoe gtpu
			default: accept;
		}
	}


	// state parse_icmp {
	// 	packet.extract(hdr.icmp);
	// 	icmp_checksum.subtract({hdr.icmp.type});
	// 	icmp_checksum.subtract({hdr.icmp.code});
	// 	icmp_checksum.subtract({hdr.icmp.checksum});
	// 	icmp_checksum.subtract({hdr.icmp.identifier});
	// 	icmp_checksum.subtract({hdr.icmp.seqno});
	// 	meta.l4_metadata.checksum_l4_tmp = icmp_checksum.get();

	// 	transition parse_tcp_options_128bit_custom;
	// }

	state parse_icmp {
		packet.extract(hdr.icmp);
		icmp_checksum.subtract({hdr.icmp.checksum});

		// in egress should have tstamp headers always
		packet.extract(hdr.tcp_options_128bit_custom);
		icmp_checksum.subtract({hdr.tcp_options_128bit_custom});
		meta.l4_metadata.checksum_l4_tmp = icmp_checksum.get();

		transition accept;
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

	// is executed for UDP payload OR GTP-U packets which are encapsulated in UDP
	action prepare_exthost_packet_udp(bit<48> dst, bit<32> dstip, bit<32> srcip) {
		// src mac and ip doesnt matter for ext host
		hdr.ethernet.dstAddr = dst;
		// always set to IPv4 as possible PPPoE and VLAN header are removed in apply block later for ext host packets
		hdr.ethernet.etherType = 0x800;

		// remove unnecessary bytes in packet
		#ifdef GTP_ENCAP
		// use inner ipv4 with outer udp following to keep as only ipv4 header on purpose: length field is already correct
		// as we dont know how many GTP-U headers are added exactly we can't update ipv4 length field after truncating gtp-u headers
		hdr.ipv4.dstAddr = dstip;
		hdr.ipv4.srcAddr = srcip;
		hdr.ipv4.protocol = 0x11; //for non-gtpu its always 0x11, but the inner ipv4 we using here could be tcp
		hdr.ipv4.fragOffset = 0x0;
		hdr.ipv4.flags = 0x0;
		
		// => moved to apply block
		// hdr.vlan.setInvalid();
		// hdr.vlan_qinq.setInvalid();
		hdr.outer_ipv4.setInvalid();
		hdr.outer_udp.setInvalid();
		hdr.gtpu.setInvalid();
		hdr.advance.setInvalid();
		hdr.extension.setInvalid();
		hdr.last_extension.setInvalid();
		hdr.udp.setInvalid();
		hdr.tcp.setInvalid();

		// just to be sure
		hdr.ipv4.setValid();

		// correct calc but slow at ext: hdr.ipv4.paketlen = hdr.ipv4.paketlen - 18; // -20 byte ip header + 2 byte ext_host_stats
		hdr.ipv4.paketlen = 46; // 20 byte IPV4 header + 8 byte UDP + 2 byte p4sta metrics + 16 byte timestamps
		// tcp/udp header len subsctraction of ipv4.paketlen is done in apply block
		#else
		hdr.ipv4.dstAddr = dstip;
		hdr.ipv4.srcAddr = srcip;
		hdr.ipv4.fragOffset = 0x0;
		hdr.ipv4.flags = 0x0;
		// correct calc but slow at ext: hdr.ipv4.paketlen = hdr.ipv4.paketlen + 2; // + 2 byte ext_host_stats
		hdr.ipv4.paketlen = 46; // 20 byte IPV4 header + 8 byte UDP + 2 byte p4sta metrics + 16 byte timestamps
		hdr.udp.setInvalid();
		#endif

		// Set IPv4 paketlen truncated => problems with ubuntu 18
		// hdr.ipv4.paketlen = 46; // 20 byte IPV4 header + 8 byte UDP + 2 byte p4sta metrics + 16 byte timestamps

		hdr.exthost_udp.setValid();
		hdr.exthost_udp.srcPort = 41111; // just random sending port
		hdr.exthost_udp.dstPort = 41111; // ext host listens to that port in UDP
		hdr.exthost_udp.checksum = 0;
		//hdr.exthost_udp.len moved to apply block

		hdr.ext_host_stats.setValid();
		// hdr.ext_host_stats.paket_len = XX; moved to apply block
		
		meta.l4_metadata.updateEgressIPChecksum = 1w0x1;
	}
	
	// can possibly also be used for icmp
	action prepare_exthost_packet_tcp(bit<48> dst, bit<32> dstip, bit<32> srcip) {
		// src mac and ip doesnt matter for ext host
		hdr.ethernet.dstAddr = dst;
		// always set to IPv4, possible PPPoE and VLAN header are removed in apply block later
		hdr.ethernet.etherType = 0x800;


		// just to be sure, e.g. when compiled for GTP-U, the IP header is parsed as outer_ipv4 for non-GTP TCP packets
		hdr.outer_ipv4.setInvalid();
		hdr.ipv4.setValid();

		hdr.ipv4.dstAddr = dstip;
		hdr.ipv4.srcAddr = srcip;
		hdr.ipv4.protocol = 0x11; //instead of next header=TCP change to UDP to encapsulate TCP
		hdr.ipv4.fragOffset = 0x0;
		hdr.ipv4.flags = 0x0;


		// => moved to apply block
		// hdr.vlan.setInvalid();
		// hdr.vlan_qinq.setInvalid();
		// hdr.pppoe.setInvalid();
		// // remove unnecessary bytes in packet
		hdr.tcp.setInvalid(); // remove 160 bit (20 byte)
		// correct calculation but slower at ext: hdr.ipv4.paketlen = hdr.ipv4.paketlen - 10; // -20 byte tcp header and + 8 byte new udp header + 2 byte ext hos tstats
		hdr.ipv4.paketlen = 46;  // 20 byte IPV4 header + 8 byte UDP + 2 byte p4sta metrics + 16 byte timestamps

		hdr.exthost_udp.setValid();
		hdr.exthost_udp.srcPort = 41111; // just random sending port
		hdr.exthost_udp.dstPort = 41111; // ext host listens to that port in UDP
		hdr.exthost_udp.checksum = 0;
		// vxlen_udp.len is set in apply block

		// icmp case, can be applied here
		hdr.icmp.setInvalid();

		hdr.ext_host_stats.setValid();
		// hdr.ext_host_stats.paket_len = XX; moved to apply block
		// hdr.ext_host_stats.ingress_port = ig_intr_md.ingress_port;
		
		meta.l4_metadata.updateEgressIPChecksum = 1w0x1;
	}

	action add_timestamp1_tcp() {
		#ifdef MAC_STAMPING
		hdr.tcp_options_128bit_custom.setInvalid();
		hdr.tcp_options_128bit_custom_without.setValid(); // add header for timestamp2 only because tofino inserts (not updates!) timestamp1 at given position
		hdr.tcp_options_128bit_custom_without.myType = 16w0x0f10;
		hdr.tcp_options_128bit_custom_without.timestamp2 = 48w0x0;
		hdr.ptp.setValid();
		hdr.ptp.udp_cksum_byte_offset = 8w50 + meta.header_offset; //header_offset is defined in parser
		hdr.ptp.cf_byte_offset = 8w56 + meta.header_offset; //header_offset is defined in parser
		hdr.ptp.updated_cf = 48w0;
		eg_intr_md_for_oport.update_delay_on_tx = 1w1;
		#else
		hdr.tcp_options_128bit_custom.timestamp1 = eg_intr_parser_md.global_tstamp; //tstamp (ns) ARRIVAL at egress -> MAC more accurate
		#endif
		meta.l4_metadata.updateChecksum = 1w0x1;
	}

	// also for icmp, both have 8 byte headers with timestamping header following directly
	action add_timestamp1_udp() {
		#ifdef MAC_STAMPING
		hdr.tcp_options_128bit_custom.setInvalid();
		hdr.tcp_options_128bit_custom_without.setValid(); // add header for timestamp2 only because tofino inserts (not updates!) timestamp1 at given position
		hdr.tcp_options_128bit_custom_without.myType = 16w0x0f10;
		hdr.tcp_options_128bit_custom_without.timestamp2 = 48w0x0;
		hdr.ptp.setValid();
		hdr.ptp.udp_cksum_byte_offset = 8w40 + meta.header_offset; //header_offset is defined in parser
		hdr.ptp.cf_byte_offset = 8w44 + meta.header_offset; //header_offset is defined in parser
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
			//hdr.ethernet.etherType : exact;
			hdr.ipv4.protocol : exact;
		}
		actions = {
			prepare_exthost_packet_udp;
			prepare_exthost_packet_tcp;
		}
		size = 8;
	}

	table broadcast_mac_gtp {
		key = {
			eg_intr_md.egress_port : exact;
			//hdr.ethernet.etherType : exact;
			hdr.outer_ipv4.protocol : exact;
		}
		actions = {
			prepare_exthost_packet_udp;
			prepare_exthost_packet_tcp;
		}
		size = 8;
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
		//#ifdef GTP_ENCAP
		//if(hdr.outer_ipv4.isValid()&&hdr.ipv4.isValid()){
		//#else
		if(hdr.ipv4.isValid()){
		//#endif

			if(hdr.gtpu.isValid()&&hdr.tcp.isValid()&&hdr.ext_host_stats.isValid()){ //indicates TCP encapsulated in GTP-U and to ext host
				// not possible in action prepare_exthost_packet_udp as we dont know which L4 is encapsulated in GTP-U
				hdr.ipv4.paketlen = hdr.ipv4.paketlen - 20; // -20 byte tcp header, if UDP header is present no sub. required as replaced by exthost_udp header
			}

			//broadcast_mac table prepares duplicated packets for external host
			broadcast_mac.apply();
			broadcast_mac_gtp.apply();

			#ifdef GTP_ENCAP
			if(hdr.outer_ipv4.isValid()){
				if(hdr.outer_udp.isValid()){
					hdr.outer_udp.checksum = 0;
				}
			}
			#endif
			
			

			if (hdr.ext_host_stats.isValid()){

				hdr.exthost_udp.len = hdr.ipv4.paketlen - 20; // we assume 20 byte IPv4 header instead of using ihl to save ressources
				
				// update statistics length field here and not in action due to compiler bug breaking packets after stamping tstamp2, even to loadgen
				// we want to tell ext host the original paket size as it is received by loadgens
				if(hdr.vlan.isValid()){
						if(hdr.pppoe.isValid()){
							hdr.ext_host_stats.paket_len = meta.l4_metadata.ipv4_paketlen_temp + 26; // + 14 byte ethernet() and + 8 byte PPPoE() + 4 byte VLAN()
						} else {
							// using ifdef here ensures that p4 still works for PPPoE *and* GTP traffic when both GTP_ENCAP and PPPOE_ENCAP flags are set simultaniously
							#ifdef GTP_ENCAP
							hdr.ext_host_stats.paket_len = meta.l4_metadata.outer_ipv4_paketlen_temp + 18; // + 14 byte ethernet() + 4 byte VLAN()
							#else
							hdr.ext_host_stats.paket_len = meta.l4_metadata.ipv4_paketlen_temp + 18; // + 14 byte ethernet() + 4 byte VLAN()
							#endif
						}
				} else {
						if(hdr.pppoe.isValid()){
							hdr.ext_host_stats.paket_len = meta.l4_metadata.ipv4_paketlen_temp + 22; // + 14 byte ethernet() and + 8 byte PPPoE()
						} else {
							#ifdef GTP_ENCAP
							if(meta.l4_metadata.outer_ipv4_paketlen_temp > 0){
								hdr.ext_host_stats.paket_len = meta.l4_metadata.outer_ipv4_paketlen_temp + 14; // + 14 byte ethernet()
							} else {
								// Case: IP packet without encap (e.g. after egressing UPF upstream)
								hdr.ext_host_stats.paket_len = meta.l4_metadata.ipv4_paketlen_temp + 14; // + 14 byte ethernet()
							}
							#else
							hdr.ext_host_stats.paket_len = meta.l4_metadata.ipv4_paketlen_temp + 14; // + 14 byte ethernet()
							#endif
						}
				}
				// TODO: qinq vlan ext_host_stats.paket_len
				hdr.pppoe.setInvalid();
				hdr.vlan.setInvalid();
				hdr.vlan_qinq.setInvalid();
				
			}
		}

		if(hdr.ipv4.isValid()) {

			// maybe TODO: remove timestamp header after icmp header again so e.g. linux ping works
			// Problem: restore original checksum, resource heavy solveable
			// For now only supported for integrated generation
			// 0x0f10 indicates the packet already passed through the DUT
			// if(hdr.tcp_options_128bit_custom.myType == 16w0x0f11){
			// 	if (hdr.icmp.isValid()) {
			// 		hdr.tcp_options_128bit_custom.setInvalid()
			// 	}
			// }


			// 0x0f11 indicates that timestamp header was added in ingress pipeline, change to correct type
			if(hdr.tcp_options_128bit_custom.isValid() && hdr.tcp_options_128bit_custom.myType == 16w0x0f11){
				hdr.tcp_options_128bit_custom.myType = 16w0x0f10;
		 		if(hdr.tcp.isValid()) {
		 			add_timestamp1_tcp();
		 		} else if (hdr.udp.isValid()) {
		 			add_timestamp1_udp();
		 		} else if (hdr.icmp.isValid()) {
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
	Checksum() icmp_checksum;
	Checksum() ipv4_checksum;

	apply {
		if(meta.l4_metadata.updateEgressIPChecksum == 1w0x1){
			// we want ipv4 header for both cases (with or without GTP-U)
			// as only used for packets to ext host egress where outer ipv4 is truncated
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
		}

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
				hdr.tcp_options_128bit_custom
				#endif
			});

		 	hdr.udp.checksum = udp_checksum.update(data = {
		 		#ifdef MAC_STAMPING
				hdr.tcp_options_128bit_custom_without,
				#else
				hdr.tcp_options_128bit_custom,
				#endif
		 		meta.l4_metadata.checksum_l4_tmp
		 	}, zeros_as_ones = true);

		 	hdr.icmp.checksum = icmp_checksum.update(data = {
		 		#ifdef MAC_STAMPING
				hdr.tcp_options_128bit_custom_without,
				#else
				hdr.tcp_options_128bit_custom,
				#endif
		 		meta.l4_metadata.checksum_l4_tmp
		 	}, zeros_as_ones = true);
		
		}

		#ifdef MAC_STAMPING
			packet.emit(hdr.ptp);
			packet.emit(hdr.ethernet);

			#ifdef GTP_ENCAP
			//GTP-U case (only if valid)
			packet.emit(hdr.outer_ipv4);
			packet.emit(hdr.outer_udp);
			packet.emit(hdr.gtpu);
			packet.emit(hdr.advance);
			packet.emit(hdr.extension);
			packet.emit(hdr.last_extension);
			#endif

			#ifdef PPPOE_ENCAP
			//PPPoE case (only if valid)
			packet.emit(hdr.pppoe);
			#endif

			//VLAN case (only if valid)
			packet.emit(hdr.vlan);
			packet.emit(hdr.vlan_qinq);

			packet.emit(hdr.ipv4);

			//for external host capsulation (only if valid)
			packet.emit(hdr.exthost_udp);
			packet.emit(hdr.ext_host_stats);

			packet.emit(hdr.tcp);
			packet.emit(hdr.udp);
			packet.emit(hdr.icmp);
			packet.emit(hdr.tcp_options_128bit_custom_without); // when packet passes the first time through the switch custom_without is valid and custom is invalid
			packet.emit(hdr.tcp_options_128bit_custom); // when packet passes the second time through the switch custom is valid and custom_without is invalid
		#else
			// with exthost_udp and NO mac stamping maybe explicit ordering required as it is not parsed (only added for packets egressing to ext host)
			packet.emit(hdr.ethernet);

			#ifdef GTP_ENCAP
			//GTP-U case (only if valid)
			packet.emit(hdr.outer_ipv4);
			packet.emit(hdr.outer_udp);
			packet.emit(hdr.gtpu);
			packet.emit(hdr.advance);
			packet.emit(hdr.extension);
			packet.emit(hdr.last_extension);
			#endif

			#ifdef PPPOE_ENCAP
			//PPPoE case (only if valid)
			packet.emit(hdr.pppoe);
			#endif

			//VLAN case (only if valid)
			packet.emit(hdr.vlan);
			packet.emit(hdr.vlan_qinq);

			packet.emit(hdr.ipv4);

			//for external host capsulation (only if valid)
			packet.emit(hdr.exthost_udp);
			packet.emit(hdr.ext_host_stats);

			packet.emit(hdr.tcp);
			packet.emit(hdr.udp);
			packet.emit(hdr.icmp);
			packet.emit(hdr.tcp_options_128bit_custom);
			
		
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

