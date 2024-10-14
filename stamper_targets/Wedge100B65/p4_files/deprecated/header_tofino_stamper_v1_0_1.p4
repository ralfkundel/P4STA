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
}
