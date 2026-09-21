from scapy.all import Packet, ShortField, IntField

class Exthost(Packet):
    name = "ExthostPacket"
    fields_desc = [
        ShortField("len", 0),       # 2 bytes
        IntField("session_id", 0),  # 4 bytes
    ]