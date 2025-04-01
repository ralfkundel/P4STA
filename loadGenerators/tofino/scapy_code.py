# Do not worry about scapy imports - P4STA handles them for you.
# You can add packet crafts, helper functions and more in Python 3 here.
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# IMPORTANT: Do not forget to push packet as __ "packet name": scapy_packet __ to packets={} after crafting!
# CAUTION: All code from this window is evaluated as Python code in the management server without any filtering!

packets = {}

# adds packet payload "0" after scapy headers until total packet length is reached
def add_payload_0(scapy_headers, total_paket_len):
	return scapy_headers/Raw(load="0" * (total_paket_len - len(scapy_headers)))


# UDP Packet
udp_packet_headers = Ether(src="22:E4:75:0D:2D:57")/IP(src="10.11.12.1")/UDP(dport=42424)
packets["udp_packet"] = add_payload_0(udp_packet_headers, 1500)

udp_packet_headers = Ether(src="39:e9:0b:f1:20:7d")/IP(src="10.11.12.1")/UDP(dport=42424)
packets["1024B_udp_packet"] = add_payload_0(udp_packet_headers, 1024)

route_me_headers = Ether(src="6b:8c:9a:f8:54:35", dst="b4:96:91:b3:b0:51")/IP(src="10.10.20.42", dst="10.10.10.42")/TCP(dport=12345)
packets["route_me"] = add_payload_0(route_me_headers, 1460)



switch_me_headers = Ether(src="39:e9:0b:f1:20:7d", dst="64:9d:99:ff:f7:04")/IP(src="10.22.22.55", dst="10.33.33.42")/UDP(dport=12345)
packets["switch_me"] = add_payload_0(switch_me_headers, 1400)

# TCP Packet
tcp_packet_headers = Ether()/IP()/TCP(dport=24242)
packets["tcp_packet"] = add_payload_0(tcp_packet_headers, 1500)


#ping
ping_headers = Ether(src="6b:8c:9a:f8:54:35", dst="b4:96:91:b3:b0:51")/IP(dst="10.10.20.1", src="10.10.20.42", ttl=20)/ICMP(type=8)
packets["ping_packet"] = add_payload_0(ping_headers, 66)

#ARP
# pdst = IP we want to know the corresponding MAC to
arp_headers = Ether(src="6b:8c:9a:f8:54:35", dst="ff:ff:ff:ff:ff:ff")/ARP(pdst="10.10.20.1", hwsrc="6b:8c:9a:f8:54:35", psrc="10.10.20.42")
packets["arp_packet"] = add_payload_0(arp_headers, 128)


# GTP-U Packet
udp_base = Ether(src="02:8c:9a:d8:24:35", dst="b4:96:91:b3:b0:51")/IP(src="10.99.99.199", dst="10.99.99.99")/UDP(sport=2152, dport=2152)
gtp_base = gtp.GTPHeader(gtp_type=255, teid=846, E=1, next_ex=0x85)/gtp.GTPPDUSessionContainer(ExtHdrLen=1, type=1, QFI=1)

gtp_tcp_headers = udp_base/gtp_base/IP(src="10.45.0.2", dst="10.88.88.42")/TCP(sport=4242, dport=4242, flags="PA")
packets["gtpu_tcp"] = add_payload_0(gtp_tcp_headers,1444)

gtp_udp_headers = udp_base/gtp_base/IP(src="10.45.0.2", dst="10.88.88.42")/UDP(sport=4242, dport=4242)
packets["gtpu_udp"] = add_payload_0(gtp_udp_headers, 1460)



# Now craft whatever custom packets you desire for load generation and after saving assign them to the generator ports. 
# But keep in mind: P4STA does only stamp TCP and UDP packets, including (QinQ) VLANs, PPPoE and GTP-U if the P4 is compiled accordingly, see settings on the top right.