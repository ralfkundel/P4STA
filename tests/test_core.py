import argparse
import unittest
import os
import rpyc
import sys
import time

sys.path.append(os.path.dirname(os.path.realpath(__file__)).split("tests")[0])
try:
    from analytics import analytics
    from core import P4STA_utils
except Exception as e:
    print(e)


def make_orderer():
    order = {}

    def ordered(f):
        order[f.__name__] = len(order)
        return f

    def compare(a, b):
        return [1, -1][order[a] < order[b]]

    return ordered, compare


ordered, compare = make_orderer()
unittest.defaultTestLoader.sortTestMethodsUsing = compare


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip_mininet", dest="ip_mininet", required=True)
    ns, args = parser.parse_known_args(namespace=unittest)
    return ns, sys.argv[:1] + args


class TestP4staCore(unittest.TestCase):
    file_id = -1

    def __init__(self, *args, **kwargs):
        super(TestP4staCore, self).__init__(*args, **kwargs)

    @ordered
    def test_connect(self):
        try:
            core_conn = rpyc.connect('localhost', 6789)
            self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
            project_path = core_conn.root.get_project_path()
            self.assertEqual(type(project_path), str)
            self.assertTrue(len(project_path) > 1)
            core_conn.close()

            P4STA_utils.set_project_path(project_path)
            # insert bmv2 docker container IP
            cfg = P4STA_utils.read_current_cfg()
            print("BMV2 MININET IP: " + str(mininet_ip))
            cfg["stamper_ssh"] = mininet_ip
            P4STA_utils.write_config(cfg)

        finally:  # otherwise gitlab runner will never stop
            del core_conn

    @ordered
    def test_check_first_run(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
        self.assertFalse(core_conn.root.check_first_run(), False)
        core_conn.close()

    # core methods tested in test_install.py
    # def first_run_finished(self):
    # def write_install_script(self, first_time_cfg):
    @ordered
    def test_target_obj(self):
        core_conn = rpyc.connect('localhost', 6789)
        all_targets = P4STA_utils.flt(core_conn.root.get_all_targets())
        self.assertTrue(type(all_targets) == list)
        for target in all_targets:
            target_obj = P4STA_utils.flt(
                core_conn.root.get_stamper_target_obj(target))
            self.assertTrue(hasattr(target_obj, "target_cfg"))
            self.assertTrue(len(target_obj.target_cfg["target_driver"]) > 0)
            self.assertTrue(hasattr(target_obj, "realPath"))
            self.assertTrue(len(target_obj.realPath) > 0)
        core_conn.close()

    @ordered
    def test_get_extHost_obj(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
        current_ext_host = core_conn.root.get_current_extHost_obj()
        self.assertTrue(hasattr(current_ext_host, "host_cfg"))
        self.assertNotEqual(len(current_ext_host.host_cfg["name"]), 0)
        all_ext_host = P4STA_utils.flt(core_conn.root.get_all_extHost())
        self.assertTrue(type(all_ext_host) == list)
        for ext_host in all_ext_host:
            ext_host_obj = core_conn.root.get_extHost_obj(ext_host)
            self.assertTrue(hasattr(ext_host_obj, "host_cfg"))
            self.assertTrue(len(ext_host_obj.host_cfg["driver"]) > 0)
            self.assertTrue(hasattr(ext_host_obj, "realPath"))
            self.assertTrue(len(ext_host_obj.realPath) > 0)
        core_conn.close()

    @ordered
    def test_get_loadgen_obj(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
        all_loadgens = P4STA_utils.flt(core_conn.root.get_all_loadGenerators())
        self.assertTrue(type(all_loadgens) == list)
        for loadgen in all_loadgens:
            loadgen_obj = core_conn.root.get_loadgen_obj(loadgen)
            self.assertTrue(hasattr(loadgen_obj, "loadgen_cfg"))
            self.assertTrue(len(loadgen_obj.loadgen_cfg["driver"]) > 0)
            self.assertTrue(hasattr(loadgen_obj, "realPath"))
            self.assertTrue(len(loadgen_obj.realPath) > 0)

        core_conn.close()

    @ordered
    def test_get_target_cfg(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
        target_cfg = core_conn.root.get_target_cfg()
        self.assertTrue(len(target_cfg) > 0)
        self.assertEqual(target_cfg["target"], "bmv2")
        core_conn.close()

    @ordered
    def test_write_open_delete_config(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)

        P4STA_utils.write_config(
            {"write": "works"}, file_name="write_test.json")

        write_test_json = P4STA_utils.flt(
            core_conn.root.open_cfg_file("data/write_test.json"))
        self.assertDictEqual(write_test_json, {"write": "works"})

        cfg_files = core_conn.root.get_available_cfg_files()
        self.assertTrue(len(cfg_files) >= 0)
        # config.json not included and write_test.json should be in /data now
        # BUT is excluded because no timestring in name

        core_conn.close()

    @ordered
    def test_get_template_cfg_path(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)

        path = core_conn.root.get_template_cfg_path("bmv2")
        self.assertTrue(len(path) > 5)

        core_conn.close()

    @ordered
    def test_start_stamper_software(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
        core_conn.root.start_stamper_software()
        # no return value, nothing to assert
        core_conn.close()

    @ordered
    def test_stamper_status_started(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
        cfg, lines_pm, running, dev_status = core_conn.root.stamper_status()
        lines_pm = P4STA_utils.flt(lines_pm)
        self.assertTrue(type(lines_pm) == list)
        self.assertTrue(running)
        self.assertTrue(len(dev_status) > 5)
        core_conn.close()

    @ordered
    def test_get_stamper_startup_log(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
        log = P4STA_utils.flt(core_conn.root.get_stamper_startup_log())
        self.assertTrue(type(log) == list)
        core_conn.close()

    @ordered
    def test_deploy(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
        error = core_conn.root.deploy()
        self.assertEqual(error, "")
        core_conn.close()

    @ordered
    def test_ping(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
        output = core_conn.root.ping()
        worked = False
        for line in output:
            if line.find("icmp_seq=1") > -1:
                worked = True
        self.assertTrue(worked)

        core_conn.close()

    @ordered
    def test_status_overview(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
        cfg = core_conn.root.status_overview()
        self.assertEqual(cfg["ext_host_up_state"], "up")
        print("Needed to add: " + str(cfg["stamper_needed_sudos_to_add"]))
        self.assertEqual(len(cfg["stamper_needed_sudos_to_add"]), 0)
        for loadgen_grp in cfg["loadgen_groups"]:
            for host in loadgen_grp["loadgens"]:
                self.assertEqual(host["up_state"], "up")
                for check in host["custom_checks"]:
                    self.assertTrue(check[0])
        core_conn.close()

    @ordered
    def test_reset(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
        ret_val = core_conn.root.reset()
        self.assertEqual(ret_val, "")
        core_conn.close()

    @ordered
    def test_start_external(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
        TestP4staCore.file_id = core_conn.root.set_new_measurement_id()
        self.assertTrue(int(TestP4staCore.file_id) > 0)
        result_path = core_conn.root.get_current_results_path()
        self.assertTrue(result_path.find(
            "results/" + str(TestP4staCore.file_id)) > -1)
        running, errors = core_conn.root.start_external()
        self.assertTrue(running)
        self.assertEqual(len(errors), 0)
        core_conn.close()

    @ordered
    def test_start_loadgens(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
        start_loadgens = rpyc.timed(core_conn.root.start_loadgens, 60)
        file_id = start_loadgens(duration=10)
        file_id.wait()
        file_id_val = file_id.value
        self.assertEqual(file_id_val, TestP4staCore.file_id)
        core_conn.close()

    @ordered
    def test_stop_external(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
        stoppable = core_conn.root.stop_external()
        self.assertTrue(stoppable)
        core_conn.close()

    @ordered
    def test_stamper_results(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
        sw = P4STA_utils.flt(
            core_conn.root.stamper_results(TestP4staCore.file_id))
        # all stamped are > 0 because test uses config.json where
        # dut_1/2_outgoing_stamp = checked
        self.assertTrue(sw["average"][0][0] > 0)
        for dut in sw["dut_ports"]:
            if dut["use_port"] == "checked":
                self.assertTrue(dut["num_ingress_bytes"] > 0)
                self.assertTrue(dut["num_egress_bytes"] > 0)
                self.assertTrue(dut["num_ingress_stamped_bytes"] > 0)
                self.assertTrue(dut["num_egress_stamped_bytes"] > 0)

        for loadgen_grp in sw["loadgen_groups"]:
            for host in loadgen_grp["loadgens"]:
                for key, value in host.items():
                    # all values > 0 (except gbyte keys because bmv2 produces
                    # less than 0.1 gbyte throughput)
                    if (type(value) == float or type(value) == int) \
                            and key.find("gbyte") == -1:
                        self.assertTrue(value > 0)
        core_conn.close()

    @ordered
    def test_external_results(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
        cfg = P4STA_utils.read_result_cfg(TestP4staCore.file_id)
        extH_results = analytics.main(
            str(TestP4staCore.file_id), cfg["multicast"],
            P4STA_utils.get_results_path(TestP4staCore.file_id))
        self.assertTrue(
            extH_results["max_latency"] >= extH_results["min_latency"])
        self.assertTrue(extH_results["max_pdv"] >= extH_results["min_pdv"])
        self.assertTrue(extH_results["max_ipdv"] >= extH_results["min_ipdv"])
        self.assertTrue(
            extH_results["num_raw_packets"] >=
            extH_results["num_processed_packets"])
        core_conn.close()

    @ordered
    def test_getAllMeasurements(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
        found = core_conn.root.getAllMeasurements()
        last = core_conn.root.getLatestMeasurementId()
        self.assertGreaterEqual(len(found), 1)
        self.assertEqual(last, TestP4staCore.file_id)
        core_conn.close()

    @ordered
    def test_process_loadgens(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
        output, total_bits, error, total_retransmits, total_byte, custom_attr,\
            to_plot = core_conn.root.process_loadgens(TestP4staCore.file_id)
        output = P4STA_utils.flt(output)
        to_plot = P4STA_utils.flt(to_plot)
        self.assertEqual(len(output[0]), 0)
        self.assertTrue(total_bits > 1000)
        self.assertFalse(error)
        self.assertTrue(total_byte > 1000)
        self.assertTrue(len(to_plot) >= 3)
        core_conn.close()

    @ordered
    def test_fetch_interface(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
        cfg = P4STA_utils.read_result_cfg(TestP4staCore.file_id)
        for loadgen_grp in cfg["loadgen_groups"]:
            for host in loadgen_grp["loadgens"]:
                ns_string = core_conn.root.check_ns(host)
                if "namespace_id" in host:
                    ipv4, mac, prefix, up_state, iface_found = \
                        core_conn.root.fetch_interface(
                            host["ssh_user"], host["ssh_ip"],
                            host["loadgen_iface"], host["namespace_id"])
                    mtu = core_conn.root.fetch_mtu(
                        host["ssh_user"], host["ssh_ip"],
                        host["loadgen_iface"], host["namespace_id"])
                    self.assertTrue(ns_string.find("sudo ip netns exec") > -1)
                else:
                    ipv4, mac, prefix, up_state, iface_found = \
                        core_conn.root.fetch_interface(
                            host["ssh_user"], host["ssh_ip"],
                            host["loadgen_iface"])
                    mtu = core_conn.root.fetch_mtu(
                        host["ssh_user"], host["ssh_ip"],
                        host["loadgen_iface"])
                    self.assertEqual(len(ns_string), 0)
                self.assertEqual(ipv4, host["loadgen_ip"])
                self.assertEqual(mac, host["loadgen_mac"])
                self.assertEqual(prefix, "/24")
                self.assertEqual(up_state, "up")
                self.assertTrue(iface_found)
                self.assertTrue(int(mtu) > 0)
        core_conn.close()

    @ordered
    def test_stamper_status_stopped(self):
        core_conn = rpyc.connect('localhost', 6789)
        self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
        core_conn.root.stop_stamper_software()
        time.sleep(10)
        cfg, lines_pm, running, dev_status = core_conn.root.stamper_status()
        lines_pm = P4STA_utils.flt(lines_pm)
        self.assertTrue(type(lines_pm) == list)
        self.assertFalse(running)
        self.assertEqual("not running", dev_status)
        core_conn.close()

    # template
    # @ordered
    # def test_XXX(self):
    #     core_conn = rpyc.connect('localhost', 6789)
    #     self.assertEqual(type(core_conn), rpyc.core.protocol.Connection)
    #     #xxx = core_conn.root.xxx()
    #     # insert test
    #     core_conn.close()

# not tested:
# 253 def delete_by_id(self, file_id):
# 633 def reboot(self):
# 638 def refresh_links(self):
# 735 def set_interface(self, ssh_user, ssh_ip, iface, iface_ip, namespace=""):
# 786 def delete_namespace(self, ns, user, ssh_ip):


if __name__ == '__main__':
    import sys
    args, argv = parse_args()   # run this first
    mininet_ip = args.ip_mininet
    sys.argv[:] = argv       # create cleans argv for main()
    unittest.main(exit=True)
