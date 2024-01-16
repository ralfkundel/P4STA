import argparse
import logging
import requests
import time
import unittest


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
    parser.add_argument("--ip_management", dest="ip_management", required=True)
    parser.add_argument("--ip_bf_sde", dest="ip_bf_sde", required=True)
    parser.add_argument("--target", dest="target", required=True)
    ns, args = parser.parse_known_args(namespace=unittest)
    return ns, sys.argv[:1] + args


set_cfg = {}
if __name__ == '__main__':
    import sys

    args, argv = parse_args()
    ip_mininet = args.ip_mininet
    ip_management = args.ip_management
    ip_bf_sde = args.ip_bf_sde
    target = args.target


def http_post(page="", send_json={}):
    client = None
    try:
        if ip_mininet != "" and ip_management != "" and ip_bf_sde != "":
            URL = "http://" + str(ip_management) + ":9997/"
            client = requests.session()
            client.get(URL)
            if "csrftoken" in client.cookies:
                csrftoken = client.cookies["csrftoken"]
                send_json["csrfmiddlewaretoken"] = [csrftoken]
            r = client.post(URL + page, send_json)
            client.close()
            return r
        else:
            raise Exception(
                "No IP found for eth0 at docker mininet bmv2 container")
    except Exception:
        if type(client) == requests.sessions.Session:
            client.close()
        raise Exception("Connection to " + str(ip_management) + " failed")


def get_page(page, ajax=False):
    client = None
    try:
        if ip_mininet != "" and ip_management != "" and ip_bf_sde != "":
            URL = "http://" + str(ip_management) + ":9997/" + page
            client = requests.session()
            if ajax:
                r = client.get(
                    URL, headers={'X-Requested-With': 'XMLHttpRequest'})
            else:
                r = client.get(URL)
            client.close()
            return r
        else:
            raise Exception(
                "No IP found for eth0 at docker mininet bmv2 container")
    except Exception:
        if type(client) == requests.sessions.Session:
            client.close()
        raise Exception("Connection to " + str(ip_management) + " failed")


BMV2_DIR = "/root/behavioral-model"
SSH_USER = "root"


class TestP4staDjango(unittest.TestCase):
    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_POST_and_GET_configuration(self):
        # first call of main page gets forwarded to /setup_devices
        # because global var "first_run" = True
        set_cfg = {"selected_extHost": "PythonExtHost",
                   "stamper_ssh_ip": "1.2.3.4",
                   "ext_host_user": "test2",
                   "loadgens": [
                       {"loadgen_user": "test3", "loadgen_ssh_ip": "1.1.1.1"}
                   ],
                   "stamper_user": "test1",
                   "selected_loadgen": "iperf3",
                   "selected_stamper": "bmv2",
                   "target_specific_dict": {},
                   "ext_host_ssh_ip": "4.3.2.1"}
        r = http_post(page="setup_devices/", send_json=set_cfg)
        self.assertEqual(
            r.status_code, 200, msg="Wrong status code: " + str(r.status_code))

        set_cfg = {"add_to_grp_1": ["0"], "add_to_grp_2": ["0"],
                   "bmv2_dir": [BMV2_DIR], "btn_submit": [""],
                   "s2_1_loadgen_iface": ["h20-eth1"],
                   "s2_1_loadgen_ip": ["10.0.2.2"],
                   "s2_1_loadgen_mac": ["22:22:22:22:02:01"],
                   "s2_1_real_port": ["2"], "s2_1_ssh_ip": ["10.99.66.4"],
                   "s2_1_ssh_user": [SSH_USER],
                   "s2_2_loadgen_iface": ["h21-eth1"],
                   "s2_2_loadgen_ip": ["10.0.2.3"],
                   "s2_2_loadgen_mac": ["22:22:22:22:02:02"],
                   "s2_2_real_port": ["6"], "s2_2_ssh_ip": ["10.99.66.5"],
                   "s2_2_ssh_user": [SSH_USER], "dut1_real": ["3"],
                   "dut2_real": ["4"],
                   "dut1_real_flow_dst": ["4"], "dut2_real_flow_dst": ["3"],
                   "dut_1_outgoing_stamp": ["checked"],
                   "dut_2_outgoing_stamp": ["checked"],
                   "dut_2_use_port": ["checked"], "ext_host_if": ["extH-eth1"],
                   "ext_host_real": ["5"],
                   "ext_host_ssh": ["10.99.66.99"],
                   "ext_host_user": [SSH_USER], "forwarding_mode": ["2"],
                   "multicast": ["1"], "num_loadgen_groups": ["2"],
                   "num_grp_1": ["1"], "num_grp_2": ["2"],
                   "stamper_ssh": [ip_mininet],
                   "stamper_user": [SSH_USER],
                   "program": ["bmv2_stamper_v1_0_0"],
                   "s1_1_loadgen_iface": ["h10-eth1"],
                   "s1_1_loadgen_ip": ["10.0.1.2"],
                   "s1_1_loadgen_mac": ["22:22:22:22:01:01"],
                   "s1_1_real_port": ["1"],
                   "s1_1_ssh_ip": ["10.99.66.3"], "s1_1_ssh_user": [SSH_USER],
                   "selected_loadgen": ["iperf3"],
                   "selected_extHost": ["PythonExtHost"],
                   "stamp_tcp": ["checked"], "stamp_udp": ["checked"],
                   "target": ["bmv2"]}

        r = http_post(send_json=set_cfg)
        self.assertEqual(r.status_code, 200,
                         msg="Wrong status code: " + str(r.status_code))
        r_without = get_page("")  # server:9997/
        r = get_page("configuration/")  # server:9997/configuration
        self.assertEqual(r_without.status_code, 200,
                         msg="Wrong status code: " + str(
                             r_without.status_code))
        self.assertEqual(r.status_code, 200,
                         msg="Wrong status code: " + str(r.status_code))
        # both have different csrftokens -> only check length
        self.assertEqual(len(r_without.content), len(r.content),
                         msg="Wrong len for r_without: " + str(len(
                             r_without.content)))
        # check if alle neccessary fields are filled
        self.assertEqual(r.text.find("PLEASE_SET"), -1,
                         msg="'PLEASE_SET' found")
        # check if previously added Server 2.2 is in config ...
        self.assertTrue(r.text.find("10.99.66.5") > -1,
                        msg="'10.99.66.5' found")
        self.assertTrue(r.text.find("h21-eth1") > -1, msg="'h21-eth1' found")
        self.assertTrue(r.text.find("22:22:22:22:02:02") > -1,
                        msg="'22:22:22:22:02:02' found")
        self.assertTrue(r.text.find("10.0.2.3") > -1, msg="'10.0.2.3' found")

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_deploy(self):
        r = get_page("deploy/")
        self.assertEqual(r.status_code, 200,
                         msg="Wrong status code: " + str(r.status_code))
        self.assertTrue(r.text.find("Stop Stamper") > -1,
                        msg="String 'Stop Stamper' not found.")

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_run(self):
        r = get_page("run/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.text.find("Start Ping") > -1)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_analyze(self):
        r = get_page("analyze/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.text.find("Display all results") > -1)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_status_overview_before_start(self):
        r = get_page("status_overview/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text.count("DOWN"), 4)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_stamper_status_before_start(self):
        r = get_page("subpage_deploy_stamper_status/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.text.find(
            'Stamper is running: </b><span style="color:red">') >= 0)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_start_stamper_software(self):
        r = get_page("subpage_deploy_start_stamper_software/", ajax=True)
        self.assertEqual(r.status_code, 200)
        if len(r.text) > 0:
            print("\n##############################")
            print("PRINTED BY test_GET_start_stamper_software")
            print("##############################")
            print(r.text)
            print("\n############# END PRINTED #################")
        self.assertEqual(len(r.text), 0)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_status_overview_after_start(self):
        r = get_page("status_overview/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text.count("DOWN"), 0)
        if r.text.count("DOWN") > 0:
            print("#####\n")
            print(r.text)
            print("#####\n")
        self.assertEqual(r.text.count("UP"), 4)
        count = r.text.count("You shoud add to visudo")
        self.assertEqual(count, 0)
        if count > 0:
            for ind in len(r.text):
                found = r.text[ind:].find("You shoud add to visudo")
                if found == 0:
                    print(r.text[ind:ind + 80])
        # one red dot for failed check if compiled
        self.assertTrue(r.text.count(
            '<span class="dot_red">') <= 1)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_stamper_status_after_start(self):
        r = get_page("subpage_deploy_stamper_status/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.text.find(
            'Stamper is running: </b><span style="color:green">') >= 0)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_deploy_device(self):
        r = get_page("subpage_deploy_deploy_device/", ajax=True)
        self.assertEqual(r.status_code, 200)
        if r.text.find("Table entries successfully deployed!") < 0:
            print(r.text)
        self.assertTrue(
            r.text.find("Table entries successfully deployed!") >= 0)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_show_ports(self):
        r = get_page("subpage_deploy_show_ports/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(
            r.text.find("Management network for SSH connections:") >= 0)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_host_iface_status(self):
        r = get_page("subpage_deploy_host_iface_status/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.text.count('<span style="color:green">') >= 3)
        self.assertTrue(r.text.count("up") >= 3)
        if r.text.count("up") < 3:
            print(r.text)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_ping(self):
        r = get_page("subpage_run_ping/", ajax=True)
        self.assertEqual(r.status_code, 200)
        print(r.text.count("icmp_seq"), end="")
        self.assertTrue(r.text.count("icmp_seq") >= 6)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_get_stamper_startup_log(self):
        r = get_page("subpage_deploy_get_stamper_startup_log/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(
            r.text.find("For this target is no log available.") >= 0)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_startExternal(self):
        r = get_page("subpage_run_start_external/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.text.find("External host started") >= 0)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_reset(self):
        r = get_page("subpage_run_reset/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(
            r.text.find('<span style="color:green"><p>Registers and '
                        'Counters resetted.</p>') >= 0)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_POST_run_loadgens(self):
        set_cfg = {"duration": "10", "l4_selected": "tcp",
                   "packet_size_mtu": "1460"}
        r = http_post(page="subpage_run_run_loadgens/", send_json=set_cfg)
        self.assertEqual(r.status_code, 200)
        speed_ind = r.text.find("Total measured speed:")
        # print(r.text)
        self.assertTrue(speed_ind >= 0, msg=r.text)
        print("run loadgens: " + r.text[speed_ind:speed_ind + 50])

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_stopExternal(self):
        r = get_page("subpage_run_stop_external/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.text.find(
            "External host stopped and results are ready under ") >= 0)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_stamper_results(self):
        r = get_page("subpage_analyze_stamper_results/", ajax=True)
        self.assertEqual(r.status_code, 200)
        check = r.text.count("packetloss") >= 2
        if not check:
            print(" | times word Packetloss found : " + str(
                r.text.count("Packetloss")))
        self.assertTrue(check)
        # Better parsing of html to check results?

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_externalResults(self):
        r = get_page("subpage_analyze_external_results/", ajax=True)
        self.assertEqual(r.status_code, 200)
        speed_ind = r.text.find("Total throughput: </b>")
        self.assertTrue(speed_ind >= 0)
        print("external host: " + r.text[speed_ind:speed_ind + 50])
        self.assertTrue(r.text.count(".svg?cachebuster=") >= 11)
        # Better parsing of html to check results?

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_loadgen_results(self):
        r = get_page("subpage_analyze_loadgen_results/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.text.count(".svg?cachebuster=") >= 3)
        speed_ind = r.text.find("Total measured speed: </b>")
        self.assertTrue(speed_ind >= 0)
        print("loadgen results TCP: " + r.text[speed_ind:speed_ind + 50])
        logging.getLogger("TestP4staDjango.test_GET_loadgen_results").debug(
            "loadgen results TCP: " + r.text[speed_ind:speed_ind + 50])

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_startExternal_UDP(self):
        r = get_page("subpage_run_start_external/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.text.find("External host started") >= 0)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_reset_UDP(self):
        r = get_page("subpage_run_reset/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(
            r.text.find('<span style="color:green"><p>Registers and '
                        'Counters resetted.</p>') >= 0)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_POST_run_loadgens_UDP(self):
        set_cfg = {"duration": "10", "l4_selected": "udp",
                   "packet_size_mtu": "1460"}
        r = http_post(page="subpage_run_run_loadgens/", send_json=set_cfg)
        self.assertEqual(r.status_code, 200)
        speed_ind = r.text.find("Total measured speed:")
        if speed_ind == 0:
            logging.getLogger(
                "TestP4staDjango.test_POST_run_loadgens_UDP").debug(
                "loadgen results UDP: " + r.text[speed_ind:speed_ind + 50])
        self.assertTrue(speed_ind >= 0)
        print("run loadgens UDP: " + r.text[speed_ind:speed_ind + 50])

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_stopExternal_UDP(self):
        r = get_page("subpage_run_stop_external/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.text.find(
            "External host stopped and results are ready under ") >= 0)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_stamper_results_UDP(self):
        r = get_page("subpage_analyze_stamper_results/", ajax=True)
        self.assertEqual(r.status_code, 200)
        check = r.text.count("packetloss") >= 2
        if not check:
            print(" | times word Packetloss found : " + str(
                r.text.count("packetloss")))
        self.assertTrue(check)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_externalResults_UDP(self):
        r = get_page("subpage_analyze_external_results/", ajax=True)
        self.assertEqual(r.status_code, 200)
        speed_ind = r.text.find("Total throughput: </b>")
        self.assertTrue(speed_ind >= 0)
        print("external host: " + r.text[speed_ind:speed_ind + 50])
        self.assertTrue(r.text.count(".svg?cachebuster=") >= 11)
        # Better parsing of html to check results?

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_loadgen_results_UDP(self):
        r = get_page("subpage_analyze_loadgen_results/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.text.count(".svg?cachebuster=") >= 3)
        logging.getLogger(
            "TestP4staDjango.test_GET_loadgen_results_UDP").debug(
            "Cachebuster count: " + str(r.text.count(".svg?cachebuster=")))
        speed_ind = r.text.find("Total measured speed: </b>")
        self.assertTrue(speed_ind >= 0)
        print("loadgen results: " + r.text[speed_ind:speed_ind + 50])

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_downloadSwitch(self):
        r = get_page("downloadStamperResults/", ajax=True)
        self.assertEqual(r.status_code, 200)
        file_size = 0
        for chunk in r.iter_content(chunk_size=1):
            file_size = file_size + 1
        self.assertTrue(file_size > 2000)  # bigger than 2 KBytes
        print("P4 Dev Results Zip: " + str(int(file_size / 1000)) + " KBytes")

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_downloadExtResults(self):
        r = get_page("downloadExtResults/", ajax=True)
        self.assertEqual(r.status_code, 200)
        file_size = 0
        for chunk in r.iter_content(chunk_size=1):
            file_size = file_size + 1
        self.assertTrue(file_size > 1000)  # bigger than 1 KByte
        print("Ext Results Zip: " + str(int(file_size / 1000)) + " KBytes")

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_downloadLoadgen(self):
        r = get_page("downloadLoadgenResults/", ajax=True)
        self.assertEqual(r.status_code, 200)
        file_size = 0
        for chunk in r.iter_content(chunk_size=1):
            file_size = file_size + 1
        self.assertTrue(file_size > 50000)  # bigger than 50 KBytes
        print("Loadgen Results Zip: " + str(int(file_size / 1000)) + " KBytes")

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_downloadAll(self):
        r = get_page("downloadAllResults/", ajax=True)
        self.assertEqual(r.status_code, 200)
        file_size = 0
        for chunk in r.iter_content(chunk_size=1):
            file_size = file_size + 1
        self.assertTrue(file_size > 50000)  # bigger than 50 KBytes
        print("All Results Zip: " + str(int(file_size / 1000)) + " KBytes")

    # now test again but with 2 hosts in server group and no other group
    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_POST_and_GET_second_configuration(self):
        set_cfg = {"add_to_grp_1": ["0"], "add_to_grp_2": ["0"],
                   "bmv2_dir": [BMV2_DIR], "btn_submit": [""],
                   "dut1_real": ["3"], "dut2_real": ["4"],
                   "dut1_real_flow_dst": ["3"],
                   "dut_1_outgoing_stamp": ["checked"],
                   "dut_2_outgoing_stamp": ["unchecked"],
                   "dut_2_use_port": ["unchecked"],
                   "ext_host_if": ["extH-eth1"], "ext_host_real": ["5"],
                   "ext_host_ssh": ["10.99.66.99"],
                   "ext_host_user": [SSH_USER], "forwarding_mode": ["2"],
                   "multicast": ["1"], "num_grp_2": ["0"], "num_grp_1": ["2"],
                   "stamper_ssh": [ip_mininet],
                   "stamper_user": [SSH_USER],
                   "program": ["bmv2_stamper_v1_0_0"],
                   "num_loadgen_groups": ["1"],
                   "s1_1_loadgen_iface": ["h10-eth1"],
                   "s1_1_loadgen_ip": ["10.0.1.2"],
                   "s1_1_loadgen_mac": ["22:22:22:22:01:01"],
                   "s1_1_real_port": ["1"], "s1_1_ssh_ip": ["10.99.66.3"],
                   "s1_1_ssh_user": [SSH_USER],
                   "s1_2_loadgen_iface": ["h12-eth1"],
                   "s1_2_loadgen_ip": ["10.0.1.3"],
                   "s1_2_loadgen_mac": ["22:22:22:22:01:02"],
                   "s1_2_real_port": ["2"], "s1_2_ssh_ip": ["10.99.66.4"],
                   "s1_2_ssh_user": [SSH_USER], "selected_loadgen": ["iperf3"],
                   "selected_extHost": ["PythonExtHost"],
                   "stamp_tcp": ["checked"], "stamp_udp": ["checked"],
                   "target": ["bmv2"]}

        r = http_post(send_json=set_cfg)
        self.assertEqual(r.status_code, 200)
        r_without = get_page("")  # server:9997/
        r = get_page("configuration/")  # server:9997/configuration
        self.assertEqual(r_without.status_code, 200)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r_without.content), len(
            r.content))  # both have different csrftokens -> only check length
        self.assertEqual(r.text.find("PLEASE_SET"),
                         -1)  # check if alle neccessary fields are filled
        # check if previously added Server 2.2 is NOT in config anymore
        self.assertEqual(r.text.find("10.99.66.5"),
                         -1)

    # unfortunately for bmv2 the stamper needs to stop because bmv2
    # initializes the virtual hosts from config.json
    # for other devices a simple (re)deploy should be sufficient
    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_restart_stamper_software(self):
        self.test_GET_stop_stamper_software()
        self.test_GET_start_stamper_software()

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_deploy_device_second(self):
        self.test_GET_deploy_device()
        time.sleep(5)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_ping_second(self):
        self.test_GET_ping()

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_startExternal_second(self):
        self.test_GET_startExternal()

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_reset_second(self):
        self.test_GET_reset()

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_POST_run_loadgens_second(self):
        self.test_POST_run_loadgens()

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_stopExternal_second(self):
        self.test_GET_stopExternal()

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_stamper_results_second(self):
        self.test_GET_stamper_results()

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_externalResults_second(self):
        self.test_GET_externalResults()

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_loadgen_results_second(self):
        self.test_GET_loadgen_results()

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_downloadSwitch_second(self):
        self.test_GET_downloadSwitch()

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_downloadExtResults_second(self):
        self.test_GET_downloadExtResults()

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_downloadLoadgen_second(self):
        self.test_GET_downloadLoadgen()

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_stop_stamper_software(self):
        r = get_page("subpage_deploy_stop_stamper_software/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.text), 0)

    @ordered
    @unittest.skipIf(target == "tofino", "Not necessary for target " + target)
    def test_GET_stamper_status_after_finish(self):
        r = get_page("subpage_deploy_stamper_status/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.text.find(
            'Stamper is running: </b><span style="color:red">') >= 0)

    # NOW TEST TOFINO (tofino model)
    @ordered
    @unittest.skipIf(target != "tofino", "Not necessary for target " + target)
    def test_POST_and_GET_configuration_tofino(self):

        # first call of main page gets forwarded to /setup_devices
        # because global var "first_run" = True
        set_setup_device_cfg = {'selected_extHost': 'PythonExtHost',
                                'stamper_ssh_ip': '1.2.3.4',
                                'ext_host_user': 'test2',
                                'loadgens': [{'loadgen_user': 'test3',
                                              'loadgen_ssh_ip': '1.1.1.1'}],
                                'stamper_user': 'test1',
                                'selected_loadgen': 'iperf3',
                                'selected_stamper': 'bmv2',
                                'target_specific_dict': {},
                                'ext_host_ssh_ip': '4.3.2.1'}
        r = http_post(page="setup_devices/", send_json=set_setup_device_cfg)
        self.assertEqual(r.status_code, 200,
                         msg="Wrong status code: " + str(r.status_code))

        set_cfg = {"add_to_grp_2": ["0"], "add_to_grp_1": ["0"],
                   "btn_submit": [""], "s2_1_an": ["default"],
                   "s2_1_fec": ["NONE"], "s2_1_loadgen_iface": ["veth5"],
                   "s2_1_loadgen_ip": ["10.0.2.4"],
                   "s2_1_loadgen_mac": ["22:22:22:33:33:33"],
                   "s2_1_namespace": ["nsveth5"], "s2_1_real_port": ["1/2"],
                   "s2_1_shape": [""], "s2_1_speed": ["10G"],
                   "s2_1_ssh_ip": [ip_bf_sde], "s2_1_ssh_user": [SSH_USER],
                   "dataplane_duplication": [""],
                   "dut1_real_flow_dst": ["2/0"],
                   "dut2_real_flow_dst": ["1/3"],
                   "dut1_an": ["default"], "dut1_fec": ["NONE"],
                   "dut1_real": ["1/3"], "dut1_shape": [""],
                   "dut1_speed": ["10G"], "dut2_an": ["default"],
                   "dut2_fec": ["NONE"], "dut2_real": ["2/0"],
                   "dut2_shape": [""], "dut2_speed": ["10G"],
                   "dut_1_outgoing_stamp": ["checked"],
                   "dut_2_outgoing_stamp": ["checked"],
                   "dut_2_use_port": ["checked"], "ext_host_an": ["default"],
                   "ext_host_fec": ["NONE"], "ext_host_if": ["veth11"],
                   "ext_host_real": ["2/1"], "ext_host_shape": [""],
                   "ext_host_speed": ["10G"], "ext_host_ssh": [ip_bf_sde],
                   "ext_host_user": [SSH_USER],
                   "forwarding_mode": ["2"], "multicast": ["1"],
                   "num_grp_2": ["1"], "num_grp_1": ["1"],
                   "num_loadgen_groups": ["2"],
                   "stamper_ssh": [ip_bf_sde], "stamper_user": [SSH_USER],
                   "program": ["tofino_stamper_v1_2_0"],
                   "s1_1_an": ["default"], "s1_1_fec": ["NONE"],
                   "s1_1_loadgen_iface": ["veth3"],
                   "s1_1_loadgen_ip": ["10.0.1.3"],
                   "s1_1_loadgen_mac": ["22:22:22:22:22:22"],
                   "s1_1_namespace": ["nsveth3"], "s1_1_real_port": ["1/1"],
                   "s1_1_shape": [""], "s1_1_speed": ["10G"],
                   "s1_1_ssh_ip": [ip_bf_sde], "s1_1_ssh_user": [SSH_USER],
                   "sde": ["/opt/bf-sde-9.13.0"],
                   "selected_loadgen": ["iperf3"],
                   "selected_extHost": ["PythonExtHost"],
                   "stamp_tcp": ["checked"], "stamp_udp": ["checked"],
                   "target": ["tofino_model"]}
        # then define all fields
        r = http_post(send_json=set_cfg)
        self.assertEqual(r.status_code, 200)

        r_without = get_page("")  # server:9997/
        r = get_page("configuration/")  # server:9997/configuration
        self.assertEqual(r_without.status_code, 200)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r_without.content), len(
            r.content))  # both have different csrftokens -> only check length
        self.assertEqual(r.text.find("PLEASE_SET"),
                         -1)  # check if alle neccessary fields are filled
        self.assertTrue(r.text.find("veth5") > -1)
        self.assertTrue(r.text.find("22:22:22:33:33:33") > -1)
        self.assertTrue(r.text.find("10.0.2.4") > -1)

    # not working because in each namespace a route must be set because a DUT
    # is simulated with ipv4 forwarding
    # @ordered
    # def test_POST_set_iface_tofino(self):
    #     r = http_post(page="set_iface/", send_json={"user": "root",
    #       "ssh_ip": ip_bf_sde, "iface": "veth5", "iface_ip": "10.0.2.4",
    #       "namespace": "nsveth5"})
    #     self.assertEqual(r.status_code, 200)
    #
    #     r = http_post(
    #     page="set_iface/", send_json={"user": "root", "ssh_ip": ip_bf_sde,
    #       "iface": "veth3", "iface_ip": "10.0.1.3", "namespace": "nsveth3"})
    #     self.assertEqual(r.status_code, 200)

    @ordered
    @unittest.skipIf(target != "tofino", "Not necessary for target " + target)
    def test_GET_start_stamper_software_tofino(self):
        r = get_page("subpage_deploy_start_stamper_software/", ajax=True)
        self.assertEqual(r.status_code, 200)
        if len(r.text) > 0:
            print("\n##############################")
            print("PRINTED BY test_GET_start_stamper_software_tofino")
            print("##############################")
            print(r.text)
            print("############# END PRINTED #################\n")
        self.assertEqual(len(r.text), 0)
        time.sleep(20)

    @ordered
    @unittest.skipIf(target != "tofino", "Not necessary for target " + target)
    def test_GET_deploy_device_tofino(self):
        r = get_page("subpage_deploy_deploy_device/", ajax=True)
        self.assertEqual(r.status_code, 200)
        if r.text.find("Table entries successfully deployed!") < 0:
            print("\n##############################")
            print("PRINTED BY test_GET_deploy_device_tofino")
            print("##############################")
            print(r.text)
        self.assertTrue(
            r.text.find("Table entries successfully deployed!") >= 0)
        time.sleep(2)

    @ordered
    @unittest.skipIf(target != "tofino", "Not necessary for target " + target)
    def test_GET_ping_tofino(self):
        r = get_page("subpage_run_ping/", ajax=True)
        self.assertEqual(r.status_code, 200)
        print(r.text.count("icmp_seq"), end="")
        self.assertTrue(r.text.count("icmp_seq") >= 3)

    @ordered
    @unittest.skipIf(target != "tofino", "Not necessary for target " + target)
    def test_GET_startExternal_tofino(self):
        r = get_page("subpage_run_start_external/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.text.find("External host started") >= 0)

    @ordered
    @unittest.skipIf(target != "tofino", "Not necessary for target " + target)
    def test_GET_reset_tofino(self):
        r = get_page("subpage_run_reset/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(
            r.text.find('<span style="color:green"><p>Registers and '
                        'Counters resetted.</p>') >= 0)

    @ordered
    @unittest.skipIf(target != "tofino", "Not necessary for target " + target)
    def test_POST_run_loadgens_tofino(self):
        set_cfg = {"duration": "10", "l4_selected": "tcp",
                   "packet_size_mtu": "1460"}
        r = http_post(page="subpage_run_run_loadgens/", send_json=set_cfg)
        self.assertEqual(r.status_code, 200)
        speed_ind = r.text.find("Total measured speed:")
        # print(r.text)
        self.assertTrue(speed_ind >= 0, msg=r.text)
        print("run loadgens: " + r.text[speed_ind:speed_ind + 50])

    @ordered
    @unittest.skipIf(target != "tofino", "Not necessary for target " + target)
    def test_GET_stopExternal_tofino(self):
        r = get_page("subpage_run_stop_external/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.text.find(
            "External host stopped and results are ready under ") >= 0)

    @ordered
    @unittest.skipIf(target != "tofino", "Not necessary for target " + target)
    def test_GET_stamper_results_tofino(self):
        r = get_page("subpage_analyze_stamper_results/", ajax=True)
        self.assertEqual(r.status_code, 200)
        check = r.text.count("packetloss") >= 2
        if not check:
            print(" | times word Packetloss found : " + str(
                r.text.count("Packetloss")))
        self.assertTrue(check)
        # Better parsing of html to check results?

    @ordered
    @unittest.skipIf(target != "tofino", "Not necessary for target " + target)
    def test_GET_externalResults_tofino(self):
        r = get_page("subpage_analyze_external_results/", ajax=True)
        self.assertEqual(r.status_code, 200)
        speed_ind = r.text.find("Total throughput: </b>")
        self.assertTrue(speed_ind >= 0)
        print("external host: " + r.text[speed_ind:speed_ind + 50])
        self.assertTrue(r.text.count(".svg?cachebuster=") >= 11)
        # Better parsing of html to check results?

    @ordered
    @unittest.skipIf(target != "tofino", "Not necessary for target " + target)
    def test_GET_loadgen_results_tofino(self):
        r = get_page("subpage_analyze_loadgen_results/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.text.count(".svg?cachebuster=") >= 3)
        speed_ind = r.text.find("Total measured speed: </b>")
        self.assertTrue(speed_ind >= 0)
        print("loadgen results TCP: " + r.text[speed_ind:speed_ind + 50])
        logging.getLogger("TestP4staDjango.test_GET_loadgen_results").debug(
            "loadgen results TCP: " + r.text[speed_ind:speed_ind + 50])

    @ordered
    @unittest.skipIf(target != "tofino", "Not necessary for target " + target)
    def test_GET_downloadSwitch_tofino(self):
        r = get_page("downloadStamperResults/", ajax=True)
        self.assertEqual(r.status_code, 200)
        file_size = 0
        for chunk in r.iter_content(chunk_size=1):
            file_size = file_size + 1
        self.assertTrue(file_size > 2000)  # bigger than 2 KBytes
        print("P4 Dev Results Zip: " + str(int(file_size / 1000)) + " KBytes")

    @ordered
    @unittest.skipIf(target != "tofino", "Not necessary for target " + target)
    def test_GET_downloadExtResults_tofino(self):
        r = get_page("downloadExtResults/", ajax=True)
        self.assertEqual(r.status_code, 200)
        file_size = 0
        for chunk in r.iter_content(chunk_size=1):
            file_size = file_size + 1
        self.assertTrue(file_size > 1000)  # bigger than 1 KByte
        print("Ext Results Zip: " + str(int(file_size / 1000)) + " KBytes")

    @ordered
    @unittest.skipIf(target != "tofino", "Not necessary for target " + target)
    def test_GET_downloadLoadgen_tofino(self):
        r = get_page("downloadLoadgenResults/", ajax=True)
        self.assertEqual(r.status_code, 200)
        file_size = 0
        for chunk in r.iter_content(chunk_size=1):
            file_size = file_size + 1
        self.assertTrue(file_size > 50000)  # bigger than 50 KBytes
        print("Loadgen Results Zip: " + str(int(file_size / 1000)) + " KBytes")

    @ordered
    @unittest.skipIf(target != "tofino", "Not necessary for target " + target)
    def test_GET_stop_stamper_software_tofino(self):
        r = get_page("subpage_deploy_stop_stamper_software/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.text), 0)

    @ordered
    @unittest.skipIf(target != "tofino", "Not necessary for target " + target)
    def test_GET_stamper_status_after_finish_tofino(self):
        time.sleep(3)
        r = get_page("subpage_deploy_stamper_status/", ajax=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.text.find(
            'Stamper is running: </b><span style="color:red">') >= 0)


# not tested:
#     path('reboot/', views.reboot)
#     path('refresh_links/', views.refresh_links),
#     path('createConfig/', views.create_new_cfg_from_template),
#     path('openConfig/', views.open_selected_config),
#     path('deleteConfig/', views.delete_selected_config),
#     path('saveConfig/', views.save_config_as_file),
#     path('deleteData/', views.delete_data), #delete measurement@analyze page
#     path('deleteNamespace/', views.delete_namespace),
#     path('fetch_iface/', views.fetch_iface),
#     path('set_iface/', views.set_iface),

if __name__ == '__main__':
    logging.basicConfig(stream=sys.stderr)

    # retrieve a list of all contained functions
    for func_name in dir(TestP4staDjango()):
        if func_name.find("test_") == 0:
            logging.getLogger("TestP4staDjango." + func_name).setLevel(
                logging.DEBUG)

    print("ip_mininet: " + str(ip_mininet) + " | ip_management: " + str(
        ip_management) + " | ip_bf_sde: " + str(ip_bf_sde))
    print("Testing Django for target: " + target)
    sys.argv[:] = argv  # create cleans argv for main()
    unittest.main(exit=True)
