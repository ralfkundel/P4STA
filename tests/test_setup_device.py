import argparse
import os
import requests
import unittest


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip_mininet", dest="ip_mininet")
    parser.add_argument("--ip_management", dest="ip_management")
    parser.add_argument("--ip_bf_sde", dest="ip_bf_sde")
    parser.add_argument("--target", dest="target")
    ns, args = parser.parse_known_args(namespace=unittest)
    return ns, sys.argv[:1] + args


def connect(args):
    ip_mininet = args.ip_mininet
    ip_management = args.ip_management
    ip_bf_sde = args.ip_bf_sde
    target = args.target

    print("ip_mininet: " + str(ip_mininet) + " | ip_management: " + str(
        ip_management) + " | ip_bf_sde: " + str(ip_bf_sde))
    client = None
    try:
        if ip_mininet != "" and ip_management != "":
            URL = "http://" + str(ip_management) + ":9997/setup_devices"
            client = requests.session()
            client.get(URL)
            csrftoken = client.cookies["csrftoken"]

            data = {}
            if target == "dpdk_host_only":
                data = {'enable_stamper': ['off'], 'ext_host_user': ['root'],
                        'selected_extHost': ['DpdkExtHost'],
                        'ext_host_ip': [ip_mininet], 'enable_ext_host': ['on'],
                        'selected_loadgen': ['iperf3'],
                        'csrfmiddlewaretoken': [csrftoken],
                        "create_setup_script_button": [""]}
            elif target == "bmv2":
                data = {'ext_host_user': ['root'], 'stamper_ip': [ip_mininet],
                        'loadgen_user_1': ['root'],
                        'selected_extHost': ['PythonExtHost'],
                        'enable_stamper': ['on'], 'selected_stamper': ['bmv2'],
                        'ext_host_ip': [ip_mininet],
                        'loadgen_ip_1': [ip_mininet],
                        'enable_ext_host': ['on'],
                        'selected_loadgen': ['iperf3'],
                        'csrfmiddlewaretoken': [csrftoken],
                        'stamper_user': ['root'],
                        "create_setup_script_button": [""]}
            elif target == "tofino":
                data = {'ext_host_user': ['root'], 'stamper_ip': [ip_bf_sde],
                        'loadgen_user_1': ['root'],
                        'selected_extHost': ['PythonExtHost'],
                        'enable_stamper': ['on'],
                        'selected_stamper': ['Stordis_BF6064XT'],
                        "sde": ["/opt/bf-sde-9.13.0"],
                        'ext_host_ip': [ip_bf_sde],
                        'loadgen_ip_1': [ip_bf_sde], 'enable_ext_host': ['on'],
                        'selected_loadgen': ['iperf3'],
                        'csrfmiddlewaretoken': [csrftoken],
                        'stamper_user': ['root'],
                        "create_setup_script_button": [""]}

            r = client.post(
                "http://" + str(ip_management) + ":9997/setup_devices/", data)
            client.close()

            return r

        else:
            raise Exception(
                "No IP found for eth0 at docker mininet bmv2 container")
    except Exception:
        if type(client) == requests.sessions.Session:
            client.close()
        raise Exception("Connection to " + str(ip_management) + " failed")


class TestP4staInstallServer(unittest.TestCase):
    def test_POST(self):
        self.assertEqual(r.status_code, 200)

    def test_script(self):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        project_path = dir_path[0:dir_path.find("/tests")]
        self.assertTrue("autogen_scripts/install_server.sh" in os.listdir(project_path))


if __name__ == '__main__':
    import sys

    args, argv = parse_args()  # run this first
    r = connect(args)
    sys.argv[:] = argv  # create cleans argv for main()
    unittest.main(exit=True)
