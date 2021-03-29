from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from thrift.protocol import TMultiplexedProtocol
from pd_fixed.tm import Client
import inspect
import traceback


class PDFixedConnect:
    # connects directly to tm_api_rpc
    def __init__(self, thrift_ip, port=9090):
        try:
            transport = TTransport.TBufferedTransport(
                TSocket.TSocket(thrift_ip, port))
            transport.open()
            bproto = TBinaryProtocol.TBinaryProtocol(transport)
            proto = TMultiplexedProtocol.TMultiplexedProtocol(bproto, "tm")
            thr = Client(proto)
            self.meth_dict = dict(inspect.getmembers(thr, inspect.ismethod))
            self.error = False
            self.error_message = ""
        except Exception:
            message = traceback.format_exc()
            print(message)
            self.error = True
            self.error_message = message

    def set_port_shaping_rate(self, port, rate):
        # rate limit over 100 Gbit/s is not possible
        if rate > 100000000:
            rate = 100000000
        cells = int(rate / 300)
        if cells > 250000:
            # more doesn't make sense
            cells = 250000
        elif cells < 300:
            cells = 300
        print("Set Tofino Shaping Rate: " + str(rate/1000) + "Mbit/s | Cells: "
              + str(cells) + " for port " + str(port))
        self.meth_dict["tm_set_port_shaping_rate"](0, port, False, 1600, rate)
        self.meth_dict["tm_set_ingress_port_drop_limit"](0, port, cells)

    def enable_port_shaping(self, port):
        self.meth_dict["tm_enable_port_shaping"](0, port)

    def disable_port_shaping(self, port):
        self.meth_dict["tm_disable_port_shaping"](0, port)
