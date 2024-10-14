header ethernet_t {
	bit<48> dstAddr;
	bit<48> srcAddr;
	bit<16> etherType;
}


header vlan_tag_t {
        bit<3> pcp;
        bit<1> cfi;
        bit<12> vid;
        bit<16> etherType;
}

header pppoe_t {
	bit<4>  version; //=1 always
	bit<4>  typeID;  //=1 always
	bit<8>  code;
	bit<16>  sessionID;
	bit<16>  totalLength;
	bit<16>  protocol;
}


/// GTP-U: different than PPPoE (header after ethernet header) GTP-U is encapsualted in eth/outer_ip/outer_udp/gtp-u_header(s)/ip/udp or tcp...
//derived from https://github.com/801room/upf_p4_poc/blob/main/src/datapath/upf.p4
#define UDP_PORT_GTPU 2152
#define GTP_GPDU 0xff

header gtpu_t {
    bit<3>  version;    /* version */
    bit<1>  pt;         /* protocol type */
    bit<1>  spare;      /* reserved */
    bit<1>  ex_flag;    /* next extension hdr present? */
    bit<1>  seq_flag;   /* sequence no. */
    bit<1>  npdu_flag;  /* n-pdn number present ? */
    bit<8>  msgtype;    /* message type */
    bit<16> msglen;     /* message length */
    bit<32> teid;       /* tunnel endpoint id */
}

header gtp_advance_t {
	bit <24> foo;
}

header gtp_extension_pdu_session_container_t { //in total 4 byte
	bit <8> extension_type;
	bit <8> extension_length;
	bit <4> pdu_type;
	bit <4> spare; //unused
	bit <2> flags; //unused
	bit <6> qfi; //qos flow identifier
}

header gtp_last_extension_header_t {
	bit <8> extension_type;
}
//TODO: add gtp sequence number here as well
// GTP-U END


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

// GTP-U: required for lookahead in parser because lookahead ipv4 and then udp is not working but we need to check if udp is port 2152. Only one lookahead works => merge IP and UDP header
header ipv4_udp_t {
	// here starts IPv4
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
	// here starts UDP
	bit<16> srcPort;
	bit<16> dstPort;
	bit<16> len;
	bit<16> checksum;
}


// tofino inserts (not updates!) mac timestamp at given offset -> only space for timestamp2 is needed
header tcp_options_128bit_custom_without_t {
	bit<16> myType;
	bit<48> timestamp2;
}

header tcp_options_128bit_custom_t {
	bit<16> myType;
	bit<48> timestamp1;
	bit<16> empty;
	bit<48> timestamp2;
}

header ptp_mac_hdr_t {
	bit<8> udp_cksum_byte_offset;
	bit<8> cf_byte_offset;
	bit<48> updated_cf;
}

struct l4_metadata_t {
	bit<16> tcpLen;
	bit<1> updateChecksum;
	bit<16> threshold_multicast;
	bit<1> do_multicast;
	bit<1> timestamp2;
	bit<1> added_empty_header;
	bit<8> udp_length_cutted;
	bit<16> checksum_l4_tmp;
	bit<4> new_offset;
}

struct timestamp_metadata_t {
	bit<32> delta_sum_low;
	bit<32> delta;			// stores calculatet latency for packet
}

struct headers_t {
	ptp_mac_hdr_t ptp;
	ethernet_t ethernet;
	vlan_tag_t vlan;
	pppoe_t pppoe;

	//GTP-U related headers
	ipv4_udp_t ipv4_udp; //just needed for lookahead in parser
	ipv4_t outer_ipv4;
	udp_t outer_udp;
	gtpu_t gtpu;
	gtp_advance_t advance;
	gtp_extension_pdu_session_container_t extension;
	gtp_last_extension_header_t last_extension;

	ipv4_t ipv4;
	tcp_t tcp;
	udp_t udp;
	tcp_options_128bit_custom_t tcp_options_128bit_custom;
	#ifdef MAC_STAMPING
	tcp_options_128bit_custom_without_t tcp_options_128bit_custom_without; //egress only
	#endif
}

struct my_metadata_t {
	l4_metadata_t l4_metadata;
	timestamp_metadata_t timestamp_metadata;
	bit<8> header_offset; //variable which describes additional offset to minimal packet, e.g. a VLAN header or IPv6 instead of IPv4
}
