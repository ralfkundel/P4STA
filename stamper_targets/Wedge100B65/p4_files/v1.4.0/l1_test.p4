#include <core.p4>

#if __TARGET_TOFINO__ == 2
#include <t2na.p4>
#else
#include <tna.p4>
#endif

#include "header_tofino_stamper_v1_4_0.p4"

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
        transition accept;
    }
}

parser SwitchIngressParser(packet_in packet, out headers_t hdr, out my_metadata_t meta, out ingress_intrinsic_metadata_t ig_intr_md) {

	TofinoIngressParser() tofino_parser;

	state start {
		tofino_parser.apply(packet, ig_intr_md);

                transition select(ig_intr_md.ingress_port) {
                     68:	parse_pktgen;
                    196: 	parse_pktgen;
                	324: 	parse_pktgen;
                	452: 	parse_pktgen;
                        default: parse_ethernet;
                }
	}

	state parse_pktgen{
                packet.extract(hdr.pkg_gen_timer);
                transition parse_ethernet;
        }

	state parse_ethernet {
        	transition accept;
        }


}

////////////////// PARSER END ///////////////////////////


////////////////// INGRESS START ////////////////////////
control SwitchIngress(
		inout headers_t hdr,
		inout my_metadata_t meta,
		in ingress_intrinsic_metadata_t ig_intr_md,
		in ingress_intrinsic_metadata_from_parser_t ig_intr_parser_md,
		inout ingress_intrinsic_metadata_for_deparser_t ig_intr_md_for_dprsr,
		inout ingress_intrinsic_metadata_for_tm_t ig_intr_tm_md) {


	action send(bit<9> egress_port) {
		ig_intr_tm_md.ucast_egress_port = egress_port;
	}

	action no_op() {
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


	apply {
	    t_l1_forwarding.apply();
        // if(ig_intr_md.ingress_port == 4){
        //     send(432);
        // }
        // if(ig_intr_md.ingress_port == 432){
        //     send(4);
        // }
		hdr.pkg_gen_timer.setInvalid();
	}
}


control SwitchIngressDeparser(packet_out packet, inout headers_t hdr, in my_metadata_t meta, in ingress_intrinsic_metadata_for_deparser_t ig_dprsr_md) {
	Checksum() ipv4_checksum;
	apply {
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

	state start {
		tofino_parser.apply(packet, eg_intr_md);
		transition parse_ethernet;
	}

	state parse_ethernet {
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

	apply {
	}
}

////////////////// EGRESS END ////////////////////////

control SwitchEgressDeparser(packet_out packet, inout headers_t hdr, in my_metadata_t meta, in egress_intrinsic_metadata_for_deparser_t eg_dprsr_md) {
	Checksum() ipv4_checksum;

	apply {
		packet.emit(hdr);
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