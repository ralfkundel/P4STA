
import time
import subprocess
import P4STA_utils


from abstract_extHost import AbstractExtHost


class ExtHostImpl(AbstractExtHost):
    def __init__(self, host_cfg):
        super().__init__(host_cfg)
        print("init ext Host")

    def start_external(self, file_id):
        self.cfg = P4STA_utils.read_current_cfg()

        if self.cfg["selected_target"] != "bmv2":
            multi = 1 # 1 = nanoseconds
        else:
            multi = 1000 # 1000 = microseconds

        input = ["ssh", self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"], "cd p4sta/receiver/dpdkExtHost/;touch receiver_stop; sleep 0.5; rm receiver_stop; sudo build/receiver 0 -- --name "+file_id+" "]
        res = subprocess.Popen(input).stdout
        print("started external host")
        print(res)
        errors = ()
        return errors



    def stop_external(self, file_id):
        self.cfg = P4STA_utils.read_current_cfg()
        input = ["ssh", self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"], "cd p4sta/receiver/dpdkExtHost/; touch receiver_stop"]
        res = subprocess.Popen(input).stdout
        print(res)
        input = ["ssh", "-o ConnectTimeout=5", self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"], "cd p4sta/receiver/dpdkExtHost/; ./check_extH_status.sh; exit"]
        c = 0
        while True: #wait until exthost stopped
            time.sleep(1)
            c = c + 1
            res = subprocess.Popen(input, stdout=subprocess.PIPE).stdout
            result = res.read().decode()
            if result.find("1") > -1 or c > 59:
                # if 1 is found by check_extH_status.sh at external host, receiver has finished saving csv files
                break
        subprocess.run( ["scp", self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] + "/p4sta/receiver/dpdkExtHost/raw_packet_counter_"+file_id+".csv", P4STA_utils.get_results_path(file_id) ] )
        subprocess.run( ["scp", self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] + "/p4sta/receiver/dpdkExtHost/total_throughput_"+file_id+".csv", P4STA_utils.get_results_path(file_id) ] )
        subprocess.run( ["scp", self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] + "/p4sta/receiver/dpdkExtHost/throughput_at_time_"+file_id+".csv", P4STA_utils.get_results_path(file_id) ] )
        subprocess.run( ["scp", self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] + "/p4sta/receiver/dpdkExtHost/timestamp1_list_"+file_id+".csv", P4STA_utils.get_results_path(file_id) ] )
        subprocess.run( ["scp", self.cfg["ext_host_user"] + "@" + self.cfg["ext_host_ssh"] + ":/home/" + self.cfg["ext_host_user"] + "/p4sta/receiver/dpdkExtHost/timestamp2_list_"+file_id+".csv", P4STA_utils.get_results_path(file_id) ] )
        time.sleep(1)
        P4STA_utils.execute_ssh(self.cfg["ext_host_user"], self.cfg["ext_host_ssh"], "cd p4sta/receiver/dpdkExtHost/; rm *.csv")
        return True



