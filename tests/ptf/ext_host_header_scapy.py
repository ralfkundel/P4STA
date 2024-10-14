from scapy.all import ShortField, Packet

class Exthost(Packet):
    name = "ExthostPacket "
    fields_desc=[ ShortField("len", None) ]