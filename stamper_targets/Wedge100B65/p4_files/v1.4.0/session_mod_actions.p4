action mod_fields_ethernet(bit<48> eth_dstAddr, bit<48> eth_srcAddr) {
    hdr.ethernet.dstAddr = eth_dstAddr;
    hdr.ethernet.srcAddr = eth_srcAddr;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_field_vlan(bit<12> vlan_vid) {
    hdr.vlan.vid = vlan_vid;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_field_vlan_qinq(bit<12> vlan_qinq_vid) {
    hdr.vlan_qinq.vid = vlan_qinq_vid;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_field_pppoe(bit<16> pppoe_sessionID) {
    hdr.pppoe.sessionID = pppoe_sessionID;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_ipv4(bit<32> ipv4_srcAddr, bit<32> ipv4_dstAddr) {
    hdr.ipv4.srcAddr = ipv4_srcAddr;
    hdr.ipv4.dstAddr = ipv4_dstAddr;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_ethernet_vlan(bit<48> eth_dstAddr, bit<48> eth_srcAddr, bit<12> vlan_vid) {
    hdr.ethernet.dstAddr = eth_dstAddr;
    hdr.ethernet.srcAddr = eth_srcAddr;
    hdr.vlan.vid = vlan_vid;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_ethernet_vlan_qinq(bit<48> eth_dstAddr, bit<48> eth_srcAddr, bit<12> vlan_qinq_vid) {
    hdr.ethernet.dstAddr = eth_dstAddr;
    hdr.ethernet.srcAddr = eth_srcAddr;
    hdr.vlan_qinq.vid = vlan_qinq_vid;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_ethernet_pppoe(bit<48> eth_dstAddr, bit<48> eth_srcAddr, bit<16> pppoe_sessionID) {
    hdr.ethernet.dstAddr = eth_dstAddr;
    hdr.ethernet.srcAddr = eth_srcAddr;
    hdr.pppoe.sessionID = pppoe_sessionID;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_ethernet_ipv4(bit<48> eth_dstAddr, bit<48> eth_srcAddr, bit<32> ipv4_srcAddr, bit<32> ipv4_dstAddr) {
    hdr.ethernet.dstAddr = eth_dstAddr;
    hdr.ethernet.srcAddr = eth_srcAddr;
    hdr.ipv4.srcAddr = ipv4_srcAddr;
    hdr.ipv4.dstAddr = ipv4_dstAddr;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_vlan_vlan_qinq(bit<12> vlan_vid, bit<12> vlan_qinq_vid) {
    hdr.vlan.vid = vlan_vid;
    hdr.vlan_qinq.vid = vlan_qinq_vid;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_vlan_pppoe(bit<12> vlan_vid, bit<16> pppoe_sessionID) {
    hdr.vlan.vid = vlan_vid;
    hdr.pppoe.sessionID = pppoe_sessionID;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_vlan_ipv4(bit<12> vlan_vid, bit<32> ipv4_srcAddr, bit<32> ipv4_dstAddr) {
    hdr.vlan.vid = vlan_vid;
    hdr.ipv4.srcAddr = ipv4_srcAddr;
    hdr.ipv4.dstAddr = ipv4_dstAddr;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_vlan_qinq_pppoe(bit<12> vlan_qinq_vid, bit<16> pppoe_sessionID) {
    hdr.vlan_qinq.vid = vlan_qinq_vid;
    hdr.pppoe.sessionID = pppoe_sessionID;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_vlan_qinq_ipv4(bit<12> vlan_qinq_vid, bit<32> ipv4_srcAddr, bit<32> ipv4_dstAddr) {
    hdr.vlan_qinq.vid = vlan_qinq_vid;
    hdr.ipv4.srcAddr = ipv4_srcAddr;
    hdr.ipv4.dstAddr = ipv4_dstAddr;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_pppoe_ipv4(bit<16> pppoe_sessionID, bit<32> ipv4_srcAddr, bit<32> ipv4_dstAddr) {
    hdr.pppoe.sessionID = pppoe_sessionID;
    hdr.ipv4.srcAddr = ipv4_srcAddr;
    hdr.ipv4.dstAddr = ipv4_dstAddr;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_ethernet_vlan_vlan_qinq(bit<48> eth_dstAddr, bit<48> eth_srcAddr, bit<12> vlan_vid, bit<12> vlan_qinq_vid) {
    hdr.ethernet.dstAddr = eth_dstAddr;
    hdr.ethernet.srcAddr = eth_srcAddr;
    hdr.vlan.vid = vlan_vid;
    hdr.vlan_qinq.vid = vlan_qinq_vid;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_ethernet_vlan_pppoe(bit<48> eth_dstAddr, bit<48> eth_srcAddr, bit<12> vlan_vid, bit<16> pppoe_sessionID) {
    hdr.ethernet.dstAddr = eth_dstAddr;
    hdr.ethernet.srcAddr = eth_srcAddr;
    hdr.vlan.vid = vlan_vid;
    hdr.pppoe.sessionID = pppoe_sessionID;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_ethernet_vlan_ipv4(bit<48> eth_dstAddr, bit<48> eth_srcAddr, bit<12> vlan_vid, bit<32> ipv4_srcAddr, bit<32> ipv4_dstAddr) {
    hdr.ethernet.dstAddr = eth_dstAddr;
    hdr.ethernet.srcAddr = eth_srcAddr;
    hdr.vlan.vid = vlan_vid;
    hdr.ipv4.srcAddr = ipv4_srcAddr;
    hdr.ipv4.dstAddr = ipv4_dstAddr;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_ethernet_vlan_qinq_pppoe(bit<48> eth_dstAddr, bit<48> eth_srcAddr, bit<12> vlan_qinq_vid, bit<16> pppoe_sessionID) {
    hdr.ethernet.dstAddr = eth_dstAddr;
    hdr.ethernet.srcAddr = eth_srcAddr;
    hdr.vlan_qinq.vid = vlan_qinq_vid;
    hdr.pppoe.sessionID = pppoe_sessionID;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_ethernet_vlan_qinq_ipv4(bit<48> eth_dstAddr, bit<48> eth_srcAddr, bit<12> vlan_qinq_vid, bit<32> ipv4_srcAddr, bit<32> ipv4_dstAddr) {
    hdr.ethernet.dstAddr = eth_dstAddr;
    hdr.ethernet.srcAddr = eth_srcAddr;
    hdr.vlan_qinq.vid = vlan_qinq_vid;
    hdr.ipv4.srcAddr = ipv4_srcAddr;
    hdr.ipv4.dstAddr = ipv4_dstAddr;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_ethernet_pppoe_ipv4(bit<48> eth_dstAddr, bit<48> eth_srcAddr, bit<16> pppoe_sessionID, bit<32> ipv4_srcAddr, bit<32> ipv4_dstAddr) {
    hdr.ethernet.dstAddr = eth_dstAddr;
    hdr.ethernet.srcAddr = eth_srcAddr;
    hdr.pppoe.sessionID = pppoe_sessionID;
    hdr.ipv4.srcAddr = ipv4_srcAddr;
    hdr.ipv4.dstAddr = ipv4_dstAddr;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_vlan_vlan_qinq_pppoe(bit<12> vlan_vid, bit<12> vlan_qinq_vid, bit<16> pppoe_sessionID) {
    hdr.vlan.vid = vlan_vid;
    hdr.vlan_qinq.vid = vlan_qinq_vid;
    hdr.pppoe.sessionID = pppoe_sessionID;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_vlan_vlan_qinq_ipv4(bit<12> vlan_vid, bit<12> vlan_qinq_vid, bit<32> ipv4_srcAddr, bit<32> ipv4_dstAddr) {
    hdr.vlan.vid = vlan_vid;
    hdr.vlan_qinq.vid = vlan_qinq_vid;
    hdr.ipv4.srcAddr = ipv4_srcAddr;
    hdr.ipv4.dstAddr = ipv4_dstAddr;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_vlan_pppoe_ipv4(bit<12> vlan_vid, bit<16> pppoe_sessionID, bit<32> ipv4_srcAddr, bit<32> ipv4_dstAddr) {
    hdr.vlan.vid = vlan_vid;
    hdr.pppoe.sessionID = pppoe_sessionID;
    hdr.ipv4.srcAddr = ipv4_srcAddr;
    hdr.ipv4.dstAddr = ipv4_dstAddr;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_vlan_qinq_pppoe_ipv4(bit<12> vlan_qinq_vid, bit<16> pppoe_sessionID, bit<32> ipv4_srcAddr, bit<32> ipv4_dstAddr) {
    hdr.vlan_qinq.vid = vlan_qinq_vid;
    hdr.pppoe.sessionID = pppoe_sessionID;
    hdr.ipv4.srcAddr = ipv4_srcAddr;
    hdr.ipv4.dstAddr = ipv4_dstAddr;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_ethernet_vlan_vlan_qinq_pppoe(bit<48> eth_dstAddr, bit<48> eth_srcAddr, bit<12> vlan_vid, bit<12> vlan_qinq_vid, bit<16> pppoe_sessionID) {
    hdr.ethernet.dstAddr = eth_dstAddr;
    hdr.ethernet.srcAddr = eth_srcAddr;
    hdr.vlan.vid = vlan_vid;
    hdr.vlan_qinq.vid = vlan_qinq_vid;
    hdr.pppoe.sessionID = pppoe_sessionID;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_ethernet_vlan_vlan_qinq_ipv4(bit<48> eth_dstAddr, bit<48> eth_srcAddr, bit<12> vlan_vid, bit<12> vlan_qinq_vid, bit<32> ipv4_srcAddr, bit<32> ipv4_dstAddr) {
    hdr.ethernet.dstAddr = eth_dstAddr;
    hdr.ethernet.srcAddr = eth_srcAddr;
    hdr.vlan.vid = vlan_vid;
    hdr.vlan_qinq.vid = vlan_qinq_vid;
    hdr.ipv4.srcAddr = ipv4_srcAddr;
    hdr.ipv4.dstAddr = ipv4_dstAddr;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_ethernet_vlan_pppoe_ipv4(bit<48> eth_dstAddr, bit<48> eth_srcAddr, bit<12> vlan_vid, bit<16> pppoe_sessionID, bit<32> ipv4_srcAddr, bit<32> ipv4_dstAddr) {
    hdr.ethernet.dstAddr = eth_dstAddr;
    hdr.ethernet.srcAddr = eth_srcAddr;
    hdr.vlan.vid = vlan_vid;
    hdr.pppoe.sessionID = pppoe_sessionID;
    hdr.ipv4.srcAddr = ipv4_srcAddr;
    hdr.ipv4.dstAddr = ipv4_dstAddr;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_ethernet_vlan_qinq_pppoe_ipv4(bit<48> eth_dstAddr, bit<48> eth_srcAddr, bit<12> vlan_qinq_vid, bit<16> pppoe_sessionID, bit<32> ipv4_srcAddr, bit<32> ipv4_dstAddr) {
    hdr.ethernet.dstAddr = eth_dstAddr;
    hdr.ethernet.srcAddr = eth_srcAddr;
    hdr.vlan_qinq.vid = vlan_qinq_vid;
    hdr.pppoe.sessionID = pppoe_sessionID;
    hdr.ipv4.srcAddr = ipv4_srcAddr;
    hdr.ipv4.dstAddr = ipv4_dstAddr;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_vlan_vlan_qinq_pppoe_ipv4(bit<12> vlan_vid, bit<12> vlan_qinq_vid, bit<16> pppoe_sessionID, bit<32> ipv4_srcAddr, bit<32> ipv4_dstAddr) {
    hdr.vlan.vid = vlan_vid;
    hdr.vlan_qinq.vid = vlan_qinq_vid;
    hdr.pppoe.sessionID = pppoe_sessionID;
    hdr.ipv4.srcAddr = ipv4_srcAddr;
    hdr.ipv4.dstAddr = ipv4_dstAddr;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

action mod_fields_ethernet_vlan_vlan_qinq_pppoe_ipv4(bit<48> eth_dstAddr, bit<48> eth_srcAddr, bit<12> vlan_vid, bit<12> vlan_qinq_vid, bit<16> pppoe_sessionID, bit<32> ipv4_srcAddr, bit<32> ipv4_dstAddr) {
    hdr.ethernet.dstAddr = eth_dstAddr;
    hdr.ethernet.srcAddr = eth_srcAddr;
    hdr.vlan.vid = vlan_vid;
    hdr.vlan_qinq.vid = vlan_qinq_vid;
    hdr.pppoe.sessionID = pppoe_sessionID;
    hdr.ipv4.srcAddr = ipv4_srcAddr;
    hdr.ipv4.dstAddr = ipv4_dstAddr;
    meta.p4sta_metadata.updateChecksum = 1w0x1;
    meta.p4sta_metadata.updateEgressIPChecksum = 1w0x1;
    #ifdef DO_METER
    direct_shaper.execute();
    #endif
}

