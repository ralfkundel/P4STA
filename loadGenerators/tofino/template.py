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
udp_packet_headers = Ether()/IP()/UDP(dport=42424)
packets["udp_packet"] = add_payload_0(udp_packet_headers, 1500)

# TCP Packet
tcp_packet_headers = Ether()/IP()/TCP(dport=24242)
packets["tcp_packet"] = add_payload_0(tcp_packet_headers, 1500)

# ICMP Echo Request
ping_headers = Ether(src="6b:8c:9a:f8:54:35", dst="b4:96:91:b3:b0:51")/IP(dst="10.10.20.1", src="10.10.20.42", ttl=20)/ICMP(type=8)
packets["ping_packet"] = add_payload_0(ping_headers, 66)

# PPPoE Packet

# GTP-U Packet

# # #
# Now craft whatever custom packets you desire for load generation and after saving assign them to the generator ports. 
# But keep in mind: P4STA does only stamp TCP and UDP packets, including (QinQ) VLANs, PPPoE and GTP-U if the P4 is compiled accordingly, see settings on the top right.