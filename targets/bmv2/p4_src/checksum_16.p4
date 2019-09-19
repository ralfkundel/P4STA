control verifyChecksum(inout headers_t hdr, inout metadata_t meta) {
    apply {
    }
}

control computeChecksum(inout headers_t hdr, inout metadata_t meta) {
    apply {
        update_checksum(true, { hdr.ipv4.version, hdr.ipv4.ihl, hdr.ipv4.diffServ, 
            hdr.ipv4.paketlen, hdr.ipv4.id, hdr.ipv4.flags, hdr.ipv4.fragOffset, 
            hdr.ipv4.ttl, hdr.ipv4.protocol, hdr.ipv4.srcAddr, hdr.ipv4.dstAddr }, 
            hdr.ipv4.header_checksum, HashAlgorithm.csum16);

        update_checksum_with_payload(hdr.tcp.isValid(), { hdr.ipv4.srcAddr, hdr.ipv4.dstAddr, 
            8w0, hdr.ipv4.protocol, meta.l4_metadata.tcpLength, hdr.tcp.srcPort, hdr.tcp.dstPort, 
            hdr.tcp.seqNo, hdr.tcp.ackNo, hdr.tcp.dataOffset, hdr.tcp.res, hdr.tcp.flags, hdr.tcp.window, 
            hdr.tcp.urgentPtr, hdr.tcp_options_96bit, hdr.tcp_options_128bit_custom }, hdr.tcp.checksum, HashAlgorithm.csum16);

	update_checksum_with_payload(hdr.udp.isValid(), { hdr.ipv4.srcAddr, hdr.ipv4.dstAddr, 
            8w0, hdr.ipv4.protocol, hdr.udp.len, hdr.udp.srcPort, hdr.udp.dstPort, hdr.udp.len}, hdr.udp.checksum, HashAlgorithm.csum16);
    }
}
