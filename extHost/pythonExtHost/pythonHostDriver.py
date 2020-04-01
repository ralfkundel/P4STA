
import time
import subprocess
import P4STA_utils


from abstract_extHost import AbstractExtHost


class ExtHostImpl(AbstractExtHost):
    def __init__(self, host_cfg):
        super().__init__(host_cfg)
        print("init ext Host")

    def start_external(self, file_id, multi=1, tsmax=(2^32-1)):
        self.cfg = P4STA_utils.read_current_cfg()

        ext_py_dir = self.host_cfg["real_path"]
        errors = ()

        # check pip3 modules
        answer = P4STA_utils.execute_ssh(self.cfg["ext_host_user"], self.cfg["ext_host_ssh"], "python3 -c 'import pkgutil; print(1 if pkgutil.find_loader(\"setproctitle\") else 0)'")
        if answer[0] == "0":
            errors = errors + ("Python Module 'setproctitle' not found at external host -> 'pip3 install setproctitle'",)
            return errors

        answer = P4STA_utils.execute_ssh(self.cfg["ext_host_user"], self.cfg["ext_host_ssh"], "mkdir p4sta; cd p4sta; mkdir receiver; sudo killall external_host_python_receiver")

        input = ["scp", ext_py_dir+"/pythonRawSocketExtHost.py", self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] + "/p4sta/receiver"] 
        res = subprocess.run(input, stdout=subprocess.PIPE, timeout=3).stdout
        #print(res)

        input = ["scp", ext_py_dir+"/check_extH_status.sh", self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] + "/p4sta/receiver"]
        res = subprocess.run(input, stdout=subprocess.PIPE, timeout=3).stdout
        #print(res)
        
        input = ["ssh", self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"], ("cd p4sta; cd receiver; chmod +x pythonRawSocketExtHost.py; chmod +x check_extH_status.sh; rm pythonRawSocketExtHost.log; sudo ./pythonRawSocketExtHost.py --name "+ file_id +" --interface "+ self.cfg["ext_host_if"] +" --multi "+ str(multi) + " --tsmax "+ str(tsmax) + "")]
        res = subprocess.Popen(input).stdout
        #print(res)

        time.sleep(2) # wait for the ext-host to succeed/fail
        # check if interface is not found or other crash
        input = ["ssh", self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"], "cd p4sta/receiver; cat pythonRawSocketExtHost.log; exit"]
        res = subprocess.run(input, stdout=subprocess.PIPE, timeout=3).stdout
        result = res.decode("utf-8")

        if result.find("Errno 19") > -1:
            errors = errors + ("Interface " + str(cfg["ext_host_if"]) + " not found at external host: " + result,)
        elif result.find("Exception") > -1:
            errors = errors + ("An exception occurred: " + result,)
        elif result.find("Started") == -1:
            errors = errors + ("Ext host not started properly",)

        return errors



    def stop_external(self, file_id):
        self.cfg = P4STA_utils.read_current_cfg()
        P4STA_utils.execute_ssh(self.cfg["ext_host_user"], self.cfg["ext_host_ssh"], "sudo killall external_host_python_receiver")
        input = ["ssh", "-o ConnectTimeout=5", self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"], "cd p4sta/receiver; ./check_extH_status.sh; exit"]
        time.sleep(0.2)
        c = 0
        while True: #wait until exthost stopped
            time.sleep(0.3)
            c = c + 1
            res = subprocess.Popen(input, stdout=subprocess.PIPE).stdout
            result = res.read().decode()
            if result.find("1") > -1 or c > 59:
                # if 1 is found by check_extH_status.sh at external host, receiver has finished saving csv files
                break
        #out = subprocess.run([project_path + "/scripts/retrieve_external_results.sh", str(file_id), self.cfg["ext_host_ssh"], self.cfg["ext_host_user"], P4STA_utils.get_results_path(file_id)])
        subprocess.run( ["scp", self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] + "/p4sta/receiver/raw_packet_counter_"+file_id+".csv", P4STA_utils.get_results_path(file_id) ] )
        subprocess.run( ["scp", self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] + "/p4sta/receiver/total_throughput_"+file_id+".csv", P4STA_utils.get_results_path(file_id) ] )
        subprocess.run( ["scp", self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] + "/p4sta/receiver/throughput_at_time_"+file_id+".csv", P4STA_utils.get_results_path(file_id) ] )
        subprocess.run( ["scp", self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] + "/p4sta/receiver/timestamp1_list_"+file_id+".csv", P4STA_utils.get_results_path(file_id) ] )
        subprocess.run( ["scp", self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] + "/p4sta/receiver/timestamp2_list_"+file_id+".csv", P4STA_utils.get_results_path(file_id) ] )
        #time.sleep(0.2)
        P4STA_utils.execute_ssh(self.cfg["ext_host_user"], self.cfg["ext_host_ssh"], "cd p4sta; cd receiver; rm *.csv")
        return True



