#!/usr/bin/env python3
import time

import requests

session = requests.Session()
session.headers.update({"Content-Type": "application/json"})


# backup if no config is provided
config={
    "interfaces": {
        "access": [
            {
                "interface": "enp4s0f1",
                "type": "pppoe",
                "vlan-mode": "N:1",
                "qinq": True,
                "outer-vlan": 111,
                "inner-vlan": 7
            }
        ]
    },
    "pppoe": {
        "reconnect": True
    },
    "ppp": {
        "authentication": {
            "username": "user10@rtbrick.com",
            "password": "test",
            "protocol": "PAP"
        },
        "lcp": {
            "keepalive-interval": 10
        },
        "ipcp": {
            "enable": True
        },
        "ip6cp": {
            "enable": False
        }
    },
    "dhcpv6": {
        "enable": False
    }
}


class BlasterApiError(RuntimeError):
    """A controller failure with diagnostics suitable for displaying to users."""


class BlasterInstanceNotFound(BlasterApiError):
    """There is no test instance to query."""


class BlasterInstanceStopped(BlasterApiError):
    """The instance exists, but its process is stopped."""


class BlasterApiClient:
    def __init__(self, ip, instance, timeout=10, logger=None, run_id=None):
        self.instance = instance
        self.http_timeout = timeout
        self.run_id = run_id # TODO, not really used here - remove?
        self.logger = logger
        self.session = requests.Session()
        self.url =  "http://" + ip + ":8001/api/v1/instances/" + instance

    def _diagnostics(self):
        # Output files remain available after the process/control socket exits.
        diagnostics = []
        for filename in ("run.log", "run.stderr", "run.stdout"):
            try:
                response = self.session.get(
                    f"{self.url}/{filename}", timeout=self.http_timeout,
                    headers={"Range": "bytes=-8192"})
                if response.ok and response.text.strip():
                    excerpt = "\n".join(response.text.strip().splitlines()[-40:])[-8192:]
                    diagnostics.append(f"{filename}:\n{excerpt}")
            except requests.RequestException:
                # Missing logs or a failed download must not hide the error.
                continue
        return "\n\n".join(diagnostics) or "No BNG Blaster diagnostic output is available."

    def _check_response(self, response, operation, diagnostics=False,
                        expect_json=False):
        if diagnostics and response.status_code == 404:
            # A missing instance is normal before starting or after teardown.
            # A missing command endpoint on an existing instance is still an error.
            instance = self.session.get(self.url, timeout=self.http_timeout)
            if instance.status_code == 404:
                raise BlasterInstanceNotFound("No BNG Blaster instance exists.")
        error = None
        if not response.ok:
            error = response.text.strip() or response.reason
        elif expect_json:
            try:
                data = response.json()
            except ValueError:
                error = "Controller returned invalid JSON."
            else:
                if not isinstance(data, dict):
                    error = "Controller returned an invalid response."
                elif data.get("status") == "error" or data.get("error") or (
                        isinstance(data.get("code"), int) and data["code"] >= 400):
                    error = data.get("error") or data.get("message") or response.text
        if error is not None:
            message = (f"BNG Blaster {operation} failed (HTTP {response.status_code}): "
                       f"{str(error)[:2000]}")
            if diagnostics:
                message += "\n\n" + self._diagnostics()
                if response.status_code == 412:
                    try:
                        body = response.json()
                    except ValueError:
                        body = None
                    if isinstance(body, dict) and body.get("message") == "instance is not running":
                        raise BlasterInstanceStopped(message)
            raise BlasterApiError(message)

    def create_instance(self, config=config):
        self.logger.debug("create_instance config = " + str(config))
        r = self.session.put(self.url, json=config, timeout=self.http_timeout)
        self.logger.debug("code " + str(r.status_code) + ": " + str(r.text))
        self._check_response(r, "configuration")

        return r.status_code

    def establish_sessions(self, session_count=1, logging=True, logging_flags=["debug", "pppoe", "ip"], report=True):
        r = self.session.post(f"{self.url}/_start", json={
            "logging": logging,
            "logging_flags": logging_flags,
            "report": report,
            "session_count": session_count,
            # "pcap_capture": True # TODO: maybe add checkbox to GUI, download pcap in GUI
        }, timeout=self.http_timeout)
        self.logger.debug("code " + str(r.status_code) + ": " + str(r.text))
        self._check_response(r, "start")
        
        return r.status_code
    
    def _session_command(self, command):
        # _start can return before the process's control socket is ready.
        # Retry only this controller response; preserve diagnostics on failure.
        for attempt in range(11):
            r = self.session.post(
                f"{self.url}/_command", json=command, timeout=self.http_timeout)
            self.logger.debug("code " + str(r.status_code) + ": " + str(r.text))
            try:
                body = r.json()
            except ValueError:
                body = None
            not_ready = (r.status_code == 500 and isinstance(body, dict)
                         and body.get("message") == "not able to send command")
            if not_ready and attempt < 10:
                time.sleep(1)
                continue
            self._check_response(r, "session query", diagnostics=True, expect_json=True)
            return r.status_code, r.text

    def get_session_info(self, session_id=1):
        return self._session_command({
            "command": "session-info",
            "arguments": {
                "session-id": session_id
            }
        })
    
    def get_sessions_summary(self):
        return self._session_command({
            "command": "session-summary"
        })
    
    def teardown_sessions(self):
        r = self.session.post(f"{self.url}/_stop")
        self.logger.debug("code " + str(r.status_code) + ": " + str(r.text))
        return r.status_code, r.text
    
    def delete_instance(self):
        r = self.session.delete(self.url)
        self.logger.debug("code " + str(r.status_code) + ": " + str(r.text))
        return r.status_code, r.text
