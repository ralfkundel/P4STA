 
#!/bin/sh

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

function job_prepare() {
    set -e
    ALL_CONTAINERS=$(sudo docker ps -a -q --filter "ancestor=management" && sudo docker ps -a -q --filter "ancestor=mininet_bmv2" && sudo docker ps -a -q --filter "ancestor=bf_sde")    
    [[ -z "$ALL_CONTAINERS" ]] && echo \"No containers to stop\" || sudo docker stop $ALL_CONTAINERS
    [[ -z "$ALL_CONTAINERS" ]] && echo \"No containers to remove\" || sudo docker rm $ALL_CONTAINERS
    printf "${GREEN} [PREPARE] successfully stopped old containers iff running \n${NC}"

    echo "working in directory: $PWD"
    mkdir -p data
    if [ -f "data/config.json" ]
    then
        mv data/config.json data/backup_config.json
        printf "${YELLOW}[PREPARE] backup the existing config file to data/backup_config.json \n${NC}"
    fi

    dockerid_p4sta_core=$(sudo docker run -dti -p 9997:9997 -v $PWD:/opt/p4-timestamping-middlebox/ --cap-add=NET_ADMIN management bash)
    mkdir -p bash_vars
    echo "$dockerid_p4sta_core" > bash_vars/dockerid_p4sta_core
    sudo docker exec -t $dockerid_p4sta_core bash -c "echo '%sudo ALL=(ALL) NOPASSWD:ALL' | sudo EDITOR='tee -a' visudo"
    printf "${GREEN} \xE2\x9C\x94 successfully started p4sta-core docker container\n${NC}"


    dockerid_mininet_py=$(sudo docker run -dti -p 22223:22223 --privileged -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix -v /lib/modules:/lib/modules -v $PWD:/opt/p4-timestamping-middlebox mininet_bmv2 bash)
    echo "$dockerid_mininet_py" > bash_vars/dockerid_mininet_py
    sudo docker exec -t $dockerid_mininet_py sudo /etc/init.d/ssh start
    printf "${GREEN} \xE2\x9C\x94 successfully started mininet-bmv2 docker container\n${NC}"

    dockerid_tofino=$(sudo docker run -dti -p 50052:50052 -v /mnt/huge:/mnt/huge -v $PWD:/opt/p4-timestamping-middlebox -v /usr/src:/usr/src -v /lib/modules:/lib/modules --cap-add=NET_ADMIN --cap-add SYS_ADMIN --privileged bf_sde:9.7.2 bash)
    echo "$dockerid_tofino" > bash_vars/dockerid_tofino
    printf "${GREEN} \xE2\x9C\x94 successfully started bf_sde docker container\n${NC}"
    printf "${GREEN} [PREPARE] Finished Prepare Job \n${NC}"
}


function job_install() {
    set -e
    dockerid_p4sta_core=$(cat bash_vars/dockerid_p4sta_core)
    dockerid_mininet_py=$(cat bash_vars/dockerid_mininet_py)
    dockerid_tofino=$(cat bash_vars/dockerid_tofino)
    sudo docker exec -t $dockerid_p4sta_core bash -c "pkill python3" || true
    sudo docker cp tests/config_pythExtHost.json $dockerid_mininet_py:/opt/p4-timestamping-middlebox/data/config.json 
    sleep 1

    # prepare PTF tests and debug tools
    sudo docker exec -t $dockerid_mininet_py bash -c 'apt update; apt -y install nano htop python3-scapy python3-setuptools python3-pip; pip3 install thrift; git clone https://github.com/fridolinsiegmund/ptf.git; cd ptf; python3 setup.py install'
    sudo docker exec -t $dockerid_tofino bash -c 'apt update; apt -y install nano htop python3-scapy python3-setuptools python3-pip openssh-server iputils-ping psmisc; sudo /etc/init.d/ssh start; python3 -m pip install --upgrade pip; pip3 install grpcio protobuf thrift google-api-core google-api-python-client scapy tabulate; git clone https://github.com/fridolinsiegmund/ptf.git; cd ptf; python3 setup.py install'
    mkdir -p log

    # install p4sta core/webserver
    sudo docker exec -t $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; USER=$(whoami); BATCH_MODE=YES; P4STA_VIRTUALENV="pastaenv_core_docker"; . install.sh; sudo /etc/init.d/ssh start'

    # copy core ssh key to mininet/tofino docker
    pubkey_core=$(sudo docker exec -t $dockerid_p4sta_core cat /root/.ssh/id_rsa.pub)
    sudo docker exec -t -e PUB="$pubkey_core" $dockerid_mininet_py bash -c '[ ! -d \"/root/.ssh\" ] && mkdir /root/.ssh; cd /root/.ssh; touch authorized_keys; echo $PUB>>authorized_keys'
    sudo docker exec -t -e PUB="$pubkey_core" $dockerid_tofino bash -c '[ ! -d \"/root/.ssh\" ] && mkdir /root/.ssh; cd /root/.ssh; touch authorized_keys; echo $PUB>>authorized_keys'
    nohup sudo docker exec -t $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; export P4STA_VIRTUALENV="pastaenv_core_docker"; printf "2\n" | ./run.sh' > log/p4sta.out 2> log/p4sta.err < /dev/null &
    sleep 5

    # start installation script for loadgens & external host
    ssh_ip_mininet=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_mininet_py)
    ssh_ip_management=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_p4sta_core)
    ssh_ip_bf_sde=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_tofino)
    
    echo "Starting test_setup_device for target bmv2"
    sudo docker exec -t -e ssh_ip_mininet="$ssh_ip_mininet" -e ssh_ip_management="$ssh_ip_management" -e ssh_ip_bf_sde="$ssh_ip_bf_sde" $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; source pastaenv_core_docker/bin/activate; 
 python3 -b tests/test_setup_device.py --ip_mininet $ssh_ip_mininet --ip_management $ssh_ip_management --ip_bf_sde $ssh_ip_bf_sde --target bmv2 -v ; deactivate'
    sudo docker exec -t -e IP_DST="$ssh_ip_mininet" $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; ./install_server.sh'
    sudo docker exec -t $dockerid_p4sta_core bash -c 'python3 -B /opt/p4-timestamping-middlebox/tests/test_install.py -v || exit 1'
    printf "${GREEN} [INSTALL] job install bmv2 finished \n${NC}"

    echo "Starting test_setup_device for target intel tofino"
    sudo docker exec -t -e ssh_ip_mininet="$ssh_ip_mininet" -e ssh_ip_management="$ssh_ip_management" -e ssh_ip_bf_sde="$ssh_ip_bf_sde" $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; source pastaenv_core_docker/bin/activate; 
python3 -b tests/test_setup_device.py --ip_mininet $ssh_ip_mininet --ip_management $ssh_ip_management --ip_bf_sde $ssh_ip_bf_sde --target tofino -v; deactivate'
    sudo docker exec -t $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; ./install_server.sh'
    printf "${GREEN} [INSTALL] job install tofino finished \n${NC}"
}

function job_code_quality(){
    set -e
    mkdir -p log
    set -o pipefail
    [ -e log/pycodestyle_result.txt ] && rm log/pycodestyle_result.txt
    dockerid_p4sta_core=$(cat bash_vars/dockerid_p4sta_core)
    sudo docker exec -t $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; source pastaenv_core_docker/bin/activate; pycodestyle --max-line-length=180 --statistics --exclude builds,pastaenv,pastaenv_core_docker,./stamper_targets/netronome/sdk6_rte,./stamper_targets/bmv2/thrift/SimplePreLAG.py,./stamper_targets/bmv2/thrift/ttypes.py,./stamper_targets/bmv2/thrift/Standard.py,./stamper_targets/Wedge100B65/pd_fixed,./stamper_targets/Wedge100B65/bfrt_grpc/bfruntime_pb2.py,./stamper_targets/Wedge100B65/bfrt_grpc/bfruntime_pb2_grpc.py . --count | tee log/pycodestyle_result.txt; deactivate; chmod 666 log/pycodestyle_result.txt'
}

function job_ptf_bmv2(){
    dockerid_mininet_py=$(cat bash_vars/dockerid_mininet_py)
    sudo docker exec -t $dockerid_mininet_py bash -c 'cd /opt/p4-timestamping-middlebox/tests/ptf; chmod +x veth_setup.sh; ./veth_setup.sh'
    sudo docker exec -t $dockerid_mininet_py bash -c 'simple_switch -i 0@veth0 -i 1@veth2 -i 2@veth4 -i 3@veth6 -i 4@veth8 -i 5@veth10 -i 6@veth12 --thrift-port 22223 /opt/p4-timestamping-middlebox/stamper_targets/bmv2/data/bmv2_stamper_v1_0_0.json' &
    sleep 2
    sudo docker exec -t $dockerid_mininet_py bash -c 'cd /opt/p4-timestamping-middlebox/; ptf --log-file log/ptf_bmv2.log --test-dir ./tests/ptf/bmv2 --pypath $PWD --interface 0@veth1 --interface 1@veth3 --interface 2@veth5 --interface 3@veth7 --interface 4@veth9 --interface 5@veth11 --interface 6@veth13'
    sudo docker exec -t $dockerid_mininet_py bash -c 'pkill simple_switch'
}

function job_ptf_tofino(){
    dockerid_tofino=$(cat bash_vars/dockerid_tofino) 
    sudo docker exec -t $dockerid_tofino bash -c 'pkill bf_switchd; pkill tofino-model' || true
    sleep 2
    
    #DIRTY HACK
    sudo docker exec -t $dockerid_tofino bash -c 'cd /home/root/p4sta/stamper/tofino1; sed -i -e "s/#define MAC_STAMPING/\\/\\/#define MAC_STAMPING/g" tofino_stamper_v1_0_1.p4'
    sudo docker exec -t $dockerid_tofino bash -c 'export SDE_INSTALL=/opt/bf-sde-9.7.2/install; cd /home/root/p4sta/stamper/tofino1; mkdir -p compile; $SDE_INSTALL/bin/bf-p4c -v -o $PWD/compile/ tofino_stamper_v1_0_1.p4'

    sudo docker exec -t $dockerid_tofino bash -c 'export SDE=/opt/bf-sde-9.7.2 export SDE_INSTALL=/opt/bf-sde-9.7.2/install export PATH=$PATH:$SDE_INSTALL/bin; $SDE_INSTALL/bin/veth_setup.sh; /opt/bf-sde-9.7.2/run_tofino_model.sh -c /home/root/p4sta/stamper/tofino1/compile/tofino_stamper_v1_0_1.conf -p tofino_stamper_v1_0_1 -q' &
    sleep 30
    sudo docker exec -t $dockerid_tofino bash -c 'export SDE=/opt/bf-sde-9.7.2 export SDE_INSTALL=/opt/bf-sde-9.7.2/install export PATH=$PATH:$SDE_INSTALL/bin; /opt/bf-sde-9.7.2/run_switchd.sh -c /home/root/p4sta/stamper/tofino1/compile/tofino_stamper_v1_0_1.conf > /opt/p4-timestamping-middlebox/log/tof_startup.log 2>&1 ' &
    sleep 30
    sudo docker exec -t $dockerid_tofino bash -c 'cd /opt/p4-timestamping-middlebox/; ptf --log-file log/ptf_tofino.log --test-dir ./tests/ptf/tofino --pypath $PWD --interface 0@veth1 --interface 1@veth3 --interface 2@veth5 --interface 3@veth7 --interface 4@veth9 --interface 5@veth11 --interface 6@veth13'
    sudo docker exec -t $dockerid_tofino bash -c 'pkill bf_switchd; pkill tofino-model'
}

function job_test_core(){
    dockerid_p4sta_core=$(cat bash_vars/dockerid_p4sta_core)
    dockerid_mininet_py=$(cat bash_vars/dockerid_mininet_py)
    sudo docker exec -t $dockerid_p4sta_core bash -c "pkill python3" || true
    sudo docker cp tests/config_pythExtHost.json $dockerid_mininet_py:/opt/p4-timestamping-middlebox/data/config.json 
    sleep 2

    nohup sudo docker exec -t $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; export P4STA_VIRTUALENV="pastaenv_core_docker"; printf "2\n" | ./run.sh' > log/p4sta.out 2> log/p4sta.err < /dev/null &
    sleep 5
    ssh_ip_mininet=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_mininet_py)
    ssh_ip_management=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_p4sta_core)
    sudo docker exec -t -e IP_DST="$ssh_ip_mininet" $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox/; source pastaenv_core_docker/bin/activate; python3 -B tests/test_core.py --ip_mininet $IP_DST -v || exit 1; deactivate'
}

function job_test_django_bmv2(){
    dockerid_p4sta_core=$(cat bash_vars/dockerid_p4sta_core)
    dockerid_mininet_py=$(cat bash_vars/dockerid_mininet_py)
    dockerid_tofino=$(cat bash_vars/dockerid_tofino)
    sudo docker exec -t $dockerid_p4sta_core bash -c "pkill python3" || true
    sudo docker cp tests/config_pythExtHost.json $dockerid_mininet_py:/opt/p4-timestamping-middlebox/data/config.json 
    sleep 1

    sudo docker exec -t $dockerid_p4sta_core rm -rf /opt/p4-timestamping-middlebox/data
    mkdir -p data
    nohup sudo docker exec -t $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; export P4STA_VIRTUALENV="pastaenv_core_docker"; printf "2\n" | ./run.sh' > log/p4sta.out 2> log/p4sta.err < /dev/null &
    sleep 5
    ssh_ip_mininet=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_mininet_py)
    ssh_ip_management=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_p4sta_core)
    ssh_ip_bf_sde=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_tofino)
    sudo docker exec -t -e ssh_ip_mininet="$ssh_ip_mininet" -e ssh_ip_management="$ssh_ip_management" -e ssh_ip_bf_sde="$ssh_ip_bf_sde" $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; source pastaenv_core_docker/bin/activate; python3 -b tests/test_django.py --ip_mininet $ssh_ip_mininet --ip_management $ssh_ip_management --ip_bf_sde $ssh_ip_bf_sde --target bmv2 -v; deactivate'
}

function job_test_django_tofino(){
    dockerid_p4sta_core=$(cat bash_vars/dockerid_p4sta_core)
    dockerid_mininet_py=$(cat bash_vars/dockerid_mininet_py)
    dockerid_tofino=$(cat bash_vars/dockerid_tofino)
    sudo docker exec -t $dockerid_tofino bash -c 'pkill bf_switchd; pkill tofino-model' || true
    sudo docker exec -t $dockerid_p4sta_core bash -c "pkill python3" || true
    sleep 2

    sudo docker exec -t $dockerid_p4sta_core rm -rf /opt/p4-timestamping-middlebox/data
    mkdir -p data
    nohup sudo docker exec -t $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; export P4STA_VIRTUALENV="pastaenv_core_docker"; printf "2\n" | ./run.sh' > log/p4sta.out 2> log/p4sta.err < /dev/null &
    sleep 5
    ssh_ip_mininet=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_mininet_py)
    ssh_ip_management=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_p4sta_core)
    ssh_ip_bf_sde=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_tofino)
    # now prepare BF_SDE container by starting tofino model again, assigning namespaces to veths and create routes
    
    #DIRTY HACK
    sudo docker exec -t $dockerid_tofino bash -c 'cd /home/root/p4sta/stamper/tofino1; sed -i -e "s/#define MAC_STAMPING/\\/\\/#define MAC_STAMPING/g" tofino_stamper_v1_0_1.p4'
    sudo docker exec -t $dockerid_tofino bash -c 'export SDE_INSTALL=/opt/bf-sde-9.7.2/install; cd /home/root/p4sta/stamper/tofino1; mkdir -p compile; $SDE_INSTALL/bin/bf-p4c -v -o $PWD/compile/ tofino_stamper_v1_0_1.p4'
    
    sudo docker exec -t $dockerid_tofino bash -c 'export SDE=/opt/bf-sde-9.7.2 export SDE_INSTALL=/opt/bf-sde-9.7.2/install; export PATH=$PATH:$SDE_INSTALL/bin; $SDE_INSTALL/bin/veth_setup.sh; /opt/bf-sde-9.7.2/run_tofino_model.sh -c /home/root/p4sta/stamper/tofino1/compile/tofino_stamper_v1_0_1.conf -p tofino_stamper_v1_0_1 -q'  &
    sleep 2
    sudo docker exec -t $dockerid_tofino bash -c 'sysctl -w net.ipv4.ip_forward=1; ip netns add nsveth3; ip link set veth3 netns nsveth3; ip netns add nsveth5; ip link set veth5 netns nsveth5; ip netns add dut; ip link set veth7 netns dut; ip link set veth9 netns dut; ip netns exec dut ifconfig veth7 10.0.1.1/24; ip netns exec dut ifconfig veth7 up; ip netns exec dut ifconfig veth9 10.0.2.1/24; ip netns exec dut ifconfig veth9 up; ip netns exec nsveth3 ifconfig veth3 hw ether 22:22:22:22:22:22; ip netns exec nsveth3 ifconfig veth3 10.0.1.3/24; ip netns exec nsveth3 ifconfig veth3 up; ip netns exec nsveth3 ip route add 10.0.2.0/24 via 10.0.1.1 dev veth3; ip netns exec nsveth5 ifconfig veth5 hw ether 22:22:22:33:33:33; ip netns exec nsveth5 ifconfig veth5 10.0.2.4/24; ip netns exec nsveth5 ifconfig veth5 up; ip netns exec nsveth5 ip route add 10.0.1.0/24 via 10.0.2.1 dev veth5; ip netns exec nsveth3 ethtool --offload veth3 rx off tx off; ip netns exec nsveth5 ethtool --offload veth5 rx off tx off; ip netns exec dut ethtool --offload veth7 rx off tx off; ip netns exec dut ethtool --offload veth9 rx off tx off '
    
    sudo docker exec -t -e ssh_ip_mininet="$ssh_ip_mininet" -e ssh_ip_management="$ssh_ip_management" -e ssh_ip_bf_sde="$ssh_ip_bf_sde"  $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; source pastaenv_core_docker/bin/activate; python3 -b tests/test_django.py --ip_mininet $ssh_ip_mininet --ip_management $ssh_ip_management --ip_bf_sde $ssh_ip_bf_sde --target tofino -v; deactivate;'
    sudo docker exec -t $dockerid_tofino bash -c 'pkill bf_switchd; pkill tofino-model'
}

function job_dpdk_install(){
    dockerid_p4sta_core=$(cat bash_vars/dockerid_p4sta_core)
    dockerid_mininet_py=$(cat bash_vars/dockerid_mininet_py)
    sudo docker exec -t $dockerid_p4sta_core bash -c "pkill python3" || true
    sleep 1

    # start p4sta core before starting dpdk install
    nohup sudo docker exec -t $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; export P4STA_VIRTUALENV="pastaenv_core_docker"; printf "2\n" | ./run.sh' > log/p4sta.out 2> log/p4sta.err < /dev/null &
    sleep 5
    ssh_ip_mininet=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_mininet_py)
    ssh_ip_management=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_p4sta_core)
    sudo docker exec -t -e ssh_ip_mininet="$ssh_ip_mininet" -e ssh_ip_management="$ssh_ip_management" $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; source pastaenv_core_docker/bin/activate; 
python3 -b tests/test_setup_device.py --ip_mininet $ssh_ip_mininet --ip_management $ssh_ip_management --ip_bf_sde not-needed --target dpdk_host_only -v; deactivate'
    sudo docker exec -t -e IP_DST="$ssh_ip_mininet" $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; ./install_server.sh'
    sudo docker exec -t $dockerid_mininet_py bash -c 'cd /home/root/p4sta/externalHost/dpdkExtHost; test -f build/receiver'
}

function job_test_core_dpdk(){
    dockerid_p4sta_core=$(cat bash_vars/dockerid_p4sta_core)
    dockerid_mininet_py=$(cat bash_vars/dockerid_mininet_py)
    sudo docker exec -t $dockerid_p4sta_core bash -c "pkill python3" || true
    sudo docker cp tests/config_dpdk.json $dockerid_mininet_py:/opt/p4-timestamping-middlebox/data/config.json 
    sleep 2

    nohup sudo docker exec -t $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; export P4STA_VIRTUALENV="pastaenv_core_docker"; printf "2\n" | ./run.sh' > log/p4sta.out 2> log/p4sta.err < /dev/null &
    sleep 5
    ssh_ip_mininet=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_mininet_py)
    ssh_ip_management=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_p4sta_core)
    sudo docker exec -t -e IP_DST="$ssh_ip_mininet" $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox/; source pastaenv_core_docker/bin/activate; python3 -B tests/test_core.py --ip_mininet $IP_DST -v || exit 1; deactivate'


    sudo docker cp tests/config_pythExtHost.json $dockerid_mininet_py:/opt/p4-timestamping-middlebox/data/config.json 
}

function job_cleanup(){
    dockerid_p4sta_core=$(cat bash_vars/dockerid_p4sta_core)
    dockerid_mininet_py=$(cat bash_vars/dockerid_mininet_py)
    dockerid_tofino=$(cat bash_vars/dockerid_tofino)
    sudo docker exec -t $dockerid_p4sta_core sudo killall -q python3 || true
    if [ -f "data/backup_config.json" ]
    then
        mv data/backup_config.json data/config.json
        printf "${YELLOW}[CLEANUP] restore the backup data/backup_config.json into data/config.json \n${NC}"
    fi
    #sudo docker exec -t $dockerid_p4sta_core rm -rf /opt/p4-timestamping-middlebox/results
    sudo docker exec -t $dockerid_p4sta_core rm -rf /opt/p4-timestamping-middlebox/pastenv
    sudo docker stop $dockerid_p4sta_core
    sudo docker stop $dockerid_mininet_py
    sudo docker stop $dockerid_tofino
    sudo find . -regex '^.*\\(__pycache__\\|\\.py[co]\\)$' -delete
}
