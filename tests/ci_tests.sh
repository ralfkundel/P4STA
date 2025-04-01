 
#!/bin/sh

DOCKER_FLAGS=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

function job_prepare() {
    set -e
    ALL_CONTAINERS=$(sudo docker ps -a -q --filter "ancestor=management" && sudo docker ps -a -q --filter "ancestor=mininet_bmv2" && sudo docker ps -a -q --filter "ancestor=bf_sde:9.13.0")    
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

    dockerid_p4sta_core=$(sudo docker run $DOCKER_FLAGS -dti -p 9997:9997 -v $PWD:/opt/p4-timestamping-middlebox/ --cap-add=NET_ADMIN management bash)
    mkdir -p bash_vars
    echo "$dockerid_p4sta_core" > bash_vars/dockerid_p4sta_core
    sudo docker exec -t $dockerid_p4sta_core bash -c "echo '%sudo ALL=(ALL) NOPASSWD:ALL' | sudo EDITOR='tee -a' visudo"
    printf "${GREEN} \xE2\x9C\x94 successfully started p4sta-core docker container\n${NC}"


    dockerid_mininet_py=$(sudo docker run $DOCKER_FLAGS -dti -p 22223:22223 --privileged -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix -v /lib/modules:/lib/modules -v $PWD:/opt/p4-timestamping-middlebox mininet_bmv2 bash)
    echo "$dockerid_mininet_py" > bash_vars/dockerid_mininet_py
    sudo docker exec -t $dockerid_mininet_py sudo /etc/init.d/ssh start
    printf "${GREEN} \xE2\x9C\x94 successfully started mininet-bmv2 docker container\n${NC}"

    dockerid_tofino=$(sudo docker run $DOCKER_FLAGS -dti -p 50052:50052 -v /mnt/huge:/mnt/huge -v $PWD:/opt/p4-timestamping-middlebox -v /usr/src:/usr/src -v /lib/modules:/lib/modules --cap-add=NET_ADMIN --cap-add SYS_ADMIN --privileged bf_sde:9.13.0 bash)
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
    # for mininet use old PTF version as ubuntu18.04 => fixed
    # removed from mininet exec: apt install python3-scapy python3-setuptools python3-pip; pip3 install thrift
    echo "Installing Mininet container ..."
    # sudo docker exec -t $dockerid_mininet_py bash -c 'apt update; apt -y install python3.8 python3.8-dev python3-distutils nano htop wget; wget https://bootstrap.pypa.io/get-pip.py; python3.8 get-pip.py; echo "INSTALLED pip for Python3.8"; python3.8 -m pip install setuptools scapy thrift cffi; git clone https://github.com/fridolinsiegmund/ptf.git; cd ptf; git checkout 1b0e3e2946ef158954e2ddd527463ba2e47feec4; python3.8 setup.py install' #removed git checkout
    sudo docker exec -t $dockerid_mininet_py bash -c 'apt update; apt -y install python3 python3-dev python3-distutils nano htop wget; wget https://bootstrap.pypa.io/get-pip.py; python3 get-pip.py; echo "INSTALLED pip for Python3"; python3 -m pip install setuptools scapy thrift cffi colorlog; git clone https://github.com/fridolinsiegmund/ptf.git; cd ptf; git checkout aac32a84b8944eaa7d46078bcbea7bc733c1e151; python3 -m pip install .' #removed git checkout
    echo "Installing Mininet container FINISHED"
    echo "Installing Tofino container ..."
    sudo docker exec -t $dockerid_tofino bash -c 'apt update; DEBIAN_FRONTEND=noninteractive apt -y install nano htop python3-setuptools python3-pip openssh-server iputils-ping psmisc; sudo /etc/init.d/ssh start; python3 -m pip install --upgrade pip; python3 -m pip install grpcio protobuf thrift google-api-core google-api-python-client scapy tabulate colorlog; git clone https://github.com/fridolinsiegmund/ptf.git; cd ptf; git checkout aac32a84b8944eaa7d46078bcbea7bc733c1e151; python3 -m pip install .'
    echo "Installing Tofino container FINISHED"
    mkdir -p log

    # install p4sta core/webserver
    sudo docker exec -t $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; USER=$(whoami); BATCH_MODE=YES; P4STA_VIRTUALENV="pastaenv_core_docker"; . install.sh; sudo /etc/init.d/ssh start'

    # copy core ssh key to mininet/tofino docker
    pubkey_core=$(sudo docker exec -t $dockerid_p4sta_core cat /root/.ssh/id_rsa.pub)
    sudo docker exec -t -e PUB="$pubkey_core" $dockerid_mininet_py bash -c '[ ! -d \"/root/.ssh\" ] && mkdir -p /root/.ssh; cd /root/.ssh; touch authorized_keys; echo $PUB>>authorized_keys'
    sudo docker exec -t -e PUB="$pubkey_core" $dockerid_tofino bash -c '[ ! -d \"/root/.ssh\" ] && mkdir -p /root/.ssh; cd /root/.ssh; touch authorized_keys; echo $PUB>>authorized_keys'
    nohup sudo docker exec -d -t $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; export P4STA_VIRTUALENV="pastaenv_core_docker"; (printf "2\n" | ./run.sh) > log/p4sta.out 2> log/p4sta.err < /dev/null '
    sleep 5

    # start installation script for loadgens & external host
    ssh_ip_mininet=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_mininet_py)
    ssh_ip_management=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_p4sta_core)
    ssh_ip_bf_sde=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_tofino)
    
    echo "Starting test_setup_device for target bmv2"
    sudo docker exec -t -e ssh_ip_mininet="$ssh_ip_mininet" -e ssh_ip_management="$ssh_ip_management" -e ssh_ip_bf_sde="$ssh_ip_bf_sde" $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; source pastaenv_core_docker/bin/activate; 
 python3 -b tests/test_setup_device.py --ip_mininet $ssh_ip_mininet --ip_management $ssh_ip_management --ip_bf_sde $ssh_ip_bf_sde --target bmv2 -v ; deactivate'
    sudo docker exec -t -e IP_DST="$ssh_ip_mininet" $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; ./autogen_scripts/install_server.sh'
    sudo docker exec -t $dockerid_p4sta_core bash -c 'python3 -B /opt/p4-timestamping-middlebox/tests/test_install.py -v || exit 1'
    printf "${GREEN} [INSTALL] job install bmv2 finished \n${NC}"

    echo "Starting test_setup_device for target intel tofino"
    sudo docker exec -t -e ssh_ip_mininet="$ssh_ip_mininet" -e ssh_ip_management="$ssh_ip_management" -e ssh_ip_bf_sde="$ssh_ip_bf_sde" $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; source pastaenv_core_docker/bin/activate; 
python3 -b tests/test_setup_device.py --ip_mininet $ssh_ip_mininet --ip_management $ssh_ip_management --ip_bf_sde $ssh_ip_bf_sde --target tofino -v; deactivate'
    sudo docker exec -t $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; ./autogen_scripts/install_server.sh'
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
    sudo docker exec -d -t $dockerid_mininet_py bash -c 'simple_switch -i 0@veth0 -i 1@veth2 -i 2@veth4 -i 3@veth6 -i 4@veth8 -i 5@veth10 -i 6@veth12 --thrift-port 22223 /opt/p4-timestamping-middlebox/stamper_targets/bmv2/data/bmv2_stamper_v1_0_0.json' 
    sleep 2
    sudo docker exec -t $dockerid_mininet_py bash -c 'cd /opt/p4-timestamping-middlebox/; ptf --log-file log/ptf_bmv2.log --test-dir ./tests/ptf/bmv2 --pypath $PWD --interface 0@veth1 --interface 1@veth3 --interface 2@veth5 --interface 3@veth7 --interface 4@veth9 --interface 5@veth11 --interface 6@veth13'
    sudo docker exec -t $dockerid_mininet_py bash -c 'pkill simple_switch'
}


# attention! import tofino_stamper_vxxxx is hardcoded in e.g. tofino_xxx_ptf.py imports and cfg
version=1.3.0
p4_file_without_ending=tofino_stamper_v1_3_0
p4_file=$p4_file_without_ending.p4
p4_path=stamper_targets/Wedge100B65/p4_files/v$version/$p4_file
p4_header_path=stamper_targets/Wedge100B65/p4_files/v$version/header_$p4_file

function job_ptf_tofino(){
    dockerid_tofino=$(cat bash_vars/dockerid_tofino) 
    sudo docker exec -t $dockerid_tofino bash -c 'pkill bf_switchd; pkill tofino-model' || true
    sleep 2

    #Copy/Update newest P4, ext host and PTF Code files (for debugging/development) in container
    sudo docker cp $p4_path $dockerid_tofino:/home/root/p4sta/stamper/tofino1/$p4_file
    sudo docker cp $p4_header_path $dockerid_tofino:/home/root/p4sta/stamper/tofino1/header_$p4_file
    #sudo docker cp extHost/pythonExtHost/pythonRawSocketExtHost.py $dockerid_tofino:/home/root/p4sta/externalHost/python/pythonRawSocketExtHost.py
    sudo docker cp extHost/goExtHostUdp/goUdpSocketExtHost.go $dockerid_tofino:/home/root/p4sta/externalHost/go/goUdpSocketExtHost.go
    sudo docker cp extHost/goExtHostUdp/extHostHTTPServer.go $dockerid_tofino:/home/root/p4sta/externalHost/go/extHostHTTPServer.go 
    sudo docker cp tests/ptf/. $dockerid_tofino:/opt/p4-timestamping-middlebox/tests/ptf/

    #DIRTY HACK
    sudo docker exec -t -e P4_FILE="$p4_file" $dockerid_tofino bash -c 'cd /home/root/p4sta/stamper/tofino1; sed -i -e "s/^#define MAC_STAMPING/\\/\\/#define MAC_STAMPING/g" $P4_FILE'

    sudo docker exec -t -e P4_FILE="$p4_file" $dockerid_tofino bash -c 'export SDE_INSTALL=/opt/bf-sde-9.13.0/install; cd /home/root/p4sta/stamper/tofino1; mkdir -p compile; $SDE_INSTALL/bin/bf-p4c -v -o $PWD/compile/ $P4_FILE'

    # to get the tofino-model log, use the following line instead of the one two below
    #sudo docker exec -d -t $dockerid_tofino bash -c 'export SDE=/opt/bf-sde-9.13.0 export SDE_INSTALL=/opt/bf-sde-9.13.0/install export PATH=$PATH:$SDE_INSTALL/bin; $SDE_INSTALL/bin/veth_setup.sh; /opt/bf-sde-9.13.0/run_tofino_model.sh -c /home/root/p4sta/stamper/tofino1/compile/tofino_stamper_v1_2_1.conf -p tofino_stamper_v1_2_1 > /opt/p4-timestamping-middlebox/log/tof_model.log 2>&1' #-q
    # alternative to line above:
    sudo docker exec -d -t -e P4_FILE_N="$p4_file_without_ending" $dockerid_tofino bash -c 'export SDE=/opt/bf-sde-9.13.0 export SDE_INSTALL=/opt/bf-sde-9.13.0/install export PATH=$PATH:$SDE_INSTALL/bin; $SDE_INSTALL/bin/veth_setup.sh; /opt/bf-sde-9.13.0/run_tofino_model.sh -c /home/root/p4sta/stamper/tofino1/compile/$P4_FILE_N.conf -p $P4_FILE_N -q'
    echo "started tofino_model, wait 30 seconds ..."
    sleep 30
    sudo docker exec -d -t -e P4_FILE_N="$p4_file_without_ending" $dockerid_tofino bash -c 'export SDE=/opt/bf-sde-9.13.0 export SDE_INSTALL=/opt/bf-sde-9.13.0/install export PATH=$PATH:$SDE_INSTALL/bin; /opt/bf-sde-9.13.0/run_switchd.sh -c /home/root/p4sta/stamper/tofino1/compile/$P4_FILE_N.conf > /opt/p4-timestamping-middlebox/log/tof_startup.log 2>&1 '
    sleep 30
    echo "started run_switchd, wait 30 seconds ..."
    sudo docker exec -t $dockerid_tofino bash -c 'cd /opt/p4-timestamping-middlebox/; ptf --log-file log/ptf_tofino.log --test-dir ./tests/ptf/tofino --pypath $PWD --interface 0@veth1 --interface 1@veth3 --interface 2@veth5 --interface 3@veth7 --interface 4@veth9 --interface 5@veth11 --interface 6@veth13'
    
    sudo docker exec -t $dockerid_tofino bash -c 'pkill bf_switchd; pkill tofino-model'
}

function job_ptf_tofino_encap(){
    dockerid_tofino=$(cat bash_vars/dockerid_tofino) 
    sudo docker exec -t $dockerid_tofino bash -c 'pkill bf_switchd; pkill tofino-model' || true
    sleep 2

    #Copy/Update newest P4, ext host and PTF Code files (for debugging/development) in container
    sudo docker cp $p4_path $dockerid_tofino:/home/root/p4sta/stamper/tofino1/$p4_file
    sudo docker cp $p4_header_path $dockerid_tofino:/home/root/p4sta/stamper/tofino1/header_$p4_file
    #sudo docker cp extHost/pythonExtHost/pythonRawSocketExtHost.py $dockerid_tofino:/home/root/p4sta/externalHost/python/pythonRawSocketExtHost.py
    sudo docker cp extHost/goExtHostUdp/goUdpSocketExtHost.go $dockerid_tofino:/home/root/p4sta/externalHost/go/goUdpSocketExtHost.go
    sudo docker cp extHost/goExtHostUdp/extHostHTTPServer.go $dockerid_tofino:/home/root/p4sta/externalHost/go/extHostHTTPServer.go

    # sudo docker exec -t $dockerid_tofino bash -c '/home/root/p4sta/externalHost/go/check_install_go.sh' => should be already installed


    sudo docker cp tests/ptf/. $dockerid_tofino:/opt/p4-timestamping-middlebox/tests/ptf/

    #DIRTY HACK
    sudo docker exec -t -e P4_FILE="$p4_file" $dockerid_tofino bash -c 'cd /home/root/p4sta/stamper/tofino1; sed -i -e "s/^#define MAC_STAMPING/\\/\\/#define MAC_STAMPING/g" $P4_FILE'

    sudo docker exec -t -e P4_FILE="$p4_file" $dockerid_tofino bash -c 'export SDE_INSTALL=/opt/bf-sde-9.13.0/install; cd /home/root/p4sta/stamper/tofino1; mkdir -p compile; $SDE_INSTALL/bin/bf-p4c -v -o $PWD/compile/ $P4_FILE -D PPPOE_ENCAP'

    # to get the tofino-model log, use the following line instead of the one two below
    #sudo docker exec -d -t $dockerid_tofino bash -c 'export SDE=/opt/bf-sde-9.13.0 export SDE_INSTALL=/opt/bf-sde-9.13.0/install export PATH=$PATH:$SDE_INSTALL/bin; $SDE_INSTALL/bin/veth_setup.sh; /opt/bf-sde-9.13.0/run_tofino_model.sh -c /home/root/p4sta/stamper/tofino1/compile/tofino_stamper_v1_2_1.conf -p tofino_stamper_v1_2_1 > /opt/p4-timestamping-middlebox/log/tof_model.log 2>&1' #-q
    # alternative to line above:
    sudo docker exec -d -t -e P4_FILE_N="$p4_file_without_ending" $dockerid_tofino bash -c 'export SDE=/opt/bf-sde-9.13.0 export SDE_INSTALL=/opt/bf-sde-9.13.0/install export PATH=$PATH:$SDE_INSTALL/bin; $SDE_INSTALL/bin/veth_setup.sh; /opt/bf-sde-9.13.0/run_tofino_model.sh -c /home/root/p4sta/stamper/tofino1/compile/$P4_FILE_N.conf -p $P4_FILE_N -q'
    echo "started tofino_model, wait 30 seconds ..."
    sleep 30
    sudo docker exec -d -t -e P4_FILE_N="$p4_file_without_ending" $dockerid_tofino bash -c 'export SDE=/opt/bf-sde-9.13.0 export SDE_INSTALL=/opt/bf-sde-9.13.0/install export PATH=$PATH:$SDE_INSTALL/bin; /opt/bf-sde-9.13.0/run_switchd.sh -c /home/root/p4sta/stamper/tofino1/compile/$P4_FILE_N.conf > /opt/p4-timestamping-middlebox/log/tof_startup.log 2>&1 '
    echo "started run_switchd, wait 30 seconds ..."
    sleep 30
    # PPPoE run first
    sudo docker exec -t $dockerid_tofino bash -c 'cd /opt/p4-timestamping-middlebox/; ptf --test-params="pppoe=True;gtpu=False" --log-file log/ptf_tofino_pppoe_encap.log --test-dir ./tests/ptf/tofino_encap --pypath $PWD --interface 0@veth1 --interface 1@veth3 --interface 2@veth5 --interface 3@veth7 --interface 4@veth9 --interface 5@veth11 --interface 6@veth13'

    # reload P4 file and set GTP-U and recompile
    sudo docker exec -t $dockerid_tofino bash -c 'pkill bf_switchd; pkill tofino-model'
    sudo docker cp $p4_path $dockerid_tofino:/home/root/p4sta/stamper/tofino1/$p4_file
    sudo docker exec -t -e P4_FILE="$p4_file" $dockerid_tofino bash -c 'cd /home/root/p4sta/stamper/tofino1; sed -i -e "s/^#define MAC_STAMPING/\\/\\/#define MAC_STAMPING/g" $P4_FILE'
    sudo docker exec -t -e P4_FILE="$p4_file" $dockerid_tofino bash -c 'export SDE_INSTALL=/opt/bf-sde-9.13.0/install; cd /home/root/p4sta/stamper/tofino1; mkdir -p compile; $SDE_INSTALL/bin/bf-p4c -v -o $PWD/compile/ $P4_FILE -D GTP_ENCAP'
    sudo docker exec -d -t -e P4_FILE_N="$p4_file_without_ending" $dockerid_tofino bash -c 'export SDE=/opt/bf-sde-9.13.0 export SDE_INSTALL=/opt/bf-sde-9.13.0/install export PATH=$PATH:$SDE_INSTALL/bin; $SDE_INSTALL/bin/veth_setup.sh; /opt/bf-sde-9.13.0/run_tofino_model.sh -c /home/root/p4sta/stamper/tofino1/compile/$P4_FILE_N.conf -p P4_FILE_N -q'
    echo "started tofino-model, wait 30 seconds ..."
    sleep 30
    sudo docker exec -d -t -e P4_FILE_N="$p4_file_without_ending" $dockerid_tofino bash -c 'export SDE=/opt/bf-sde-9.13.0 export SDE_INSTALL=/opt/bf-sde-9.13.0/install export PATH=$PATH:$SDE_INSTALL/bin; /opt/bf-sde-9.13.0/run_switchd.sh -c /home/root/p4sta/stamper/tofino1/compile/$P4_FILE_N.conf > /opt/p4-timestamping-middlebox/log/tof_startup.log 2>&1 '
    echo "started run_switchd, wait 30 seconds ..."
    sleep 30

    sudo docker exec -t $dockerid_tofino bash -c 'cd /opt/p4-timestamping-middlebox/; ptf --test-params="pppoe=False;gtpu=True" --log-file log/ptf_tofino_gtpu_encap.log --test-dir ./tests/ptf/tofino_encap --pypath $PWD --interface 0@veth1 --interface 1@veth3 --interface 2@veth5 --interface 3@veth7 --interface 4@veth9 --interface 5@veth11 --interface 6@veth13'
    
    sudo docker exec -t $dockerid_tofino bash -c 'pkill bf_switchd; pkill tofino-model'
}

# Sometimes this job doesn't like to be executed out of order and throws errors for stamper_results etc.
function job_test_core(){
    dockerid_p4sta_core=$(cat bash_vars/dockerid_p4sta_core)
    dockerid_mininet_py=$(cat bash_vars/dockerid_mininet_py)
    sudo docker exec -t $dockerid_p4sta_core bash -c "pkill python3" || true
    sudo docker cp tests/config_pythExtHost.json $dockerid_mininet_py:/opt/p4-timestamping-middlebox/data/config.json 
    sleep 2

    nohup sudo docker exec -d -t $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; export P4STA_VIRTUALENV="pastaenv_core_docker"; (printf "2\n" | ./run.sh) > log/p4sta.out 2> log/p4sta.err < /dev/null'
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
    nohup sudo docker exec -d -t $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; export P4STA_VIRTUALENV="pastaenv_core_docker"; (printf "2\n" | ./run.sh) > log/p4sta.out 2> log/p4sta.err < /dev/null'
    sleep 10
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
    nohup sudo docker exec -d -t $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; export P4STA_VIRTUALENV="pastaenv_core_docker"; (printf "2\n" | ./run.sh) > log/p4sta.out 2> log/p4sta.err < /dev/null'
    sleep 5
    ssh_ip_mininet=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_mininet_py)
    ssh_ip_management=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_p4sta_core)
    ssh_ip_bf_sde=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_tofino)
    # now prepare BF_SDE container by starting tofino model again, assigning namespaces to veths and create routes
    
    #HACK: Disable MAC Timestamping for CI, as the tofino model has no MACs
    sudo docker exec -t -e P4_FILE="$p4_file" $dockerid_tofino bash -c 'cd /home/root/p4sta/stamper/tofino1; sed -i -e "s/^#define MAC_STAMPING/\\/\\/#define MAC_STAMPING/g" $P4_FILE'
    
    sudo docker exec -t -e P4_FILE="$p4_file" $dockerid_tofino bash -c 'export SDE_INSTALL=/opt/bf-sde-9.13.0/install; cd /home/root/p4sta/stamper/tofino1; mkdir -p compile; $SDE_INSTALL/bin/bf-p4c -v -o $PWD/compile/ $P4_FILE'
    
    sudo docker exec -d -t -e P4_FILE_N="$p4_file_without_ending" $dockerid_tofino bash -c 'export SDE=/opt/bf-sde-9.13.0 export SDE_INSTALL=/opt/bf-sde-9.13.0/install; export PATH=$PATH:$SDE_INSTALL/bin; $SDE_INSTALL/bin/veth_setup.sh; /opt/bf-sde-9.13.0/run_tofino_model.sh -c /home/root/p4sta/stamper/tofino1/compile/$P4_FILE_N.conf -p $P4_FILE_N -q'
    sleep 2
    sudo docker exec -t $dockerid_tofino bash -c 'sysctl -w net.ipv4.ip_forward=1; ip netns add nsveth3; ip link set veth3 netns nsveth3; ip netns add nsveth5; ip link set veth5 netns nsveth5; ip netns add dut; ip link set veth7 netns dut; ip link set veth9 netns dut; ip netns exec dut ifconfig veth7 10.0.1.1/24; ip netns exec dut ifconfig veth7 up; ip netns exec dut ifconfig veth9 10.0.2.1/24; ip netns exec dut ifconfig veth9 up; ip netns exec nsveth3 ifconfig veth3 hw ether 22:22:22:22:22:22; ip netns exec nsveth3 ifconfig veth3 10.0.1.3/24; ip netns exec nsveth3 ifconfig veth3 up; ip netns exec nsveth3 ip route add 10.0.2.0/24 via 10.0.1.1 dev veth3; ip netns exec nsveth5 ifconfig veth5 hw ether 22:22:22:33:33:33; ip netns exec nsveth5 ifconfig veth5 10.0.2.4/24; ip netns exec nsveth5 ifconfig veth5 up; ip addr add 10.11.12.99/24 dev veth11; ip link set dev veth11 address e2:46:14:e3:0b:7c; ip netns exec nsveth5 ip route add 10.0.1.0/24 via 10.0.2.1 dev veth5; ip netns exec nsveth3 ethtool --offload veth3 rx off tx off; ip netns exec nsveth5 ethtool --offload veth5 rx off tx off; ip netns exec dut ethtool --offload veth7 rx off tx off; ip netns exec dut ethtool --offload veth9 rx off tx off '
    
    sudo docker exec -t -e ssh_ip_mininet="$ssh_ip_mininet" -e ssh_ip_management="$ssh_ip_management" -e ssh_ip_bf_sde="$ssh_ip_bf_sde"  $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; source pastaenv_core_docker/bin/activate; python3 -b tests/test_django.py --ip_mininet $ssh_ip_mininet --ip_management $ssh_ip_management --ip_bf_sde $ssh_ip_bf_sde --target tofino -v; deactivate;'
    sudo docker exec -t $dockerid_tofino bash -c 'pkill bf_switchd; pkill tofino-model'
}

# install for bmv2 target, but dpdk ext host needs tofino in v1.2.1 => but still basic testing possible
function job_dpdk_install_bmv2(){
    dockerid_p4sta_core=$(cat bash_vars/dockerid_p4sta_core)
    dockerid_mininet_py=$(cat bash_vars/dockerid_mininet_py)
    sudo docker exec -t $dockerid_p4sta_core bash -c "pkill python3" || true
    sleep 1

    # start p4sta core before starting dpdk install
    nohup sudo docker exec -d -t $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; export P4STA_VIRTUALENV="pastaenv_core_docker"; (printf "2\n" | ./run.sh) > log/p4sta.out 2> log/p4sta.err < /dev/null'
    sleep 5
    ssh_ip_mininet=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_mininet_py)
    ssh_ip_management=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_p4sta_core)
    sudo docker exec -t -e ssh_ip_mininet="$ssh_ip_mininet" -e ssh_ip_management="$ssh_ip_management" $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; source pastaenv_core_docker/bin/activate; 
python3 -b tests/test_setup_device.py --ip_mininet $ssh_ip_mininet --ip_management $ssh_ip_management --ip_bf_sde not-needed --target dpdk_bmv2 -v; deactivate'
    sudo docker exec -t -e IP_DST="$ssh_ip_mininet" $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; ./autogen_scripts/install_server.sh'
    sudo docker exec -t $dockerid_mininet_py bash -c 'cd /home/root/p4sta/externalHost/dpdkExtHost; test -f build/receiver'
}

# for tofino target
function job_dpdk_install_tofino(){
    dockerid_p4sta_core=$(cat bash_vars/dockerid_p4sta_core)
    dockerid_mininet_py=$(cat bash_vars/dockerid_mininet_py)
    dockerid_tofino=$(cat bash_vars/dockerid_tofino)
    sudo docker exec -t $dockerid_p4sta_core bash -c "pkill python3" || true
    sleep 1

    # start p4sta core before starting dpdk install
    nohup sudo docker exec -d -t $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; export P4STA_VIRTUALENV="pastaenv_core_docker"; (printf "2\n" | ./run.sh) > log/p4sta.out 2> log/p4sta.err < /dev/null'
    sleep 5
    ssh_ip_mininet=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_mininet_py) #not required, installs in tofino container
    ssh_ip_management=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_p4sta_core)
    ssh_ip_bf_sde=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_tofino)
    sudo docker exec -t -e ssh_ip_mininet="$ssh_ip_mininet" -e ssh_ip_management="$ssh_ip_management" -e ssh_ip_bf_sde="$ssh_ip_bf_sde" $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; source pastaenv_core_docker/bin/activate; 
python3 -b tests/test_setup_device.py --ip_mininet $ssh_ip_mininet --ip_management $ssh_ip_management --ip_bf_sde $ssh_ip_bf_sde --target dpdk_tofino -v; deactivate'
    sudo docker exec -t -e IP_DST="$ssh_ip_bf_sde" $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; ./autogen_scripts/install_server.sh'
    sudo docker exec -t $dockerid_tofino bash -c 'cd /home/root/p4sta/externalHost/dpdkExtHost; test -f build/receiver'
}

# test core with bmv2
function job_test_core_dpdk(){
    dockerid_p4sta_core=$(cat bash_vars/dockerid_p4sta_core)
    dockerid_mininet_py=$(cat bash_vars/dockerid_mininet_py)
    dockerid_tofino=$(cat bash_vars/dockerid_tofino)
    sudo docker exec -t $dockerid_p4sta_core bash -c "pkill python3" || true
    sudo docker cp tests/config_dpdk.json $dockerid_mininet_py:/opt/p4-timestamping-middlebox/data/config.json 

    sleep 2

    nohup sudo docker exec -d -t $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; export P4STA_VIRTUALENV="pastaenv_core_docker"; (printf "2\n" | ./run.sh) > log/p4sta.out 2> log/p4sta.err < /dev/null'
    sleep 5
    ssh_ip_mininet=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_mininet_py)
    ssh_ip_tofino=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_tofino)
    ssh_ip_management=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_p4sta_core)
    sudo docker exec -t -e IP_DST="$ssh_ip_mininet" $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox/; source pastaenv_core_docker/bin/activate; python3 -B tests/test_core.py --ip_mininet $IP_DST --dpdkisTrue -v || exit 1; deactivate'

    sudo docker cp tests/config_pythExtHost.json $dockerid_mininet_py:/opt/p4-timestamping-middlebox/data/config.json 
}

# test gui with tofino model
function job_test_django_tofino_dpdk(){
    dockerid_p4sta_core=$(cat bash_vars/dockerid_p4sta_core)
    dockerid_mininet_py=$(cat bash_vars/dockerid_mininet_py)
    dockerid_tofino=$(cat bash_vars/dockerid_tofino)
    sudo docker exec -t $dockerid_tofino bash -c 'pkill bf_switchd; pkill tofino-model' || true
    sudo docker exec -t $dockerid_p4sta_core bash -c "pkill python3" || true
    sleep 2

    sudo docker exec -t $dockerid_p4sta_core rm -rf /opt/p4-timestamping-middlebox/data
    mkdir -p data
    nohup sudo docker exec -d -t $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; export P4STA_VIRTUALENV="pastaenv_core_docker"; (printf "2\n" | ./run.sh) > log/p4sta.out 2> log/p4sta.err < /dev/null'
    sleep 5
    ssh_ip_mininet=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_mininet_py)
    ssh_ip_management=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_p4sta_core)
    ssh_ip_bf_sde=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_tofino)
    # now prepare BF_SDE container by starting tofino model again, assigning namespaces to veths and create routes
    
    #HACK: Disable MAC Timestamping for CI, as the tofino model has no MACs
    sudo docker exec -t -e P4_FILE="$p4_file" $dockerid_tofino bash -c 'cd /home/root/p4sta/stamper/tofino1; sed -i -e "s/^#define MAC_STAMPING/\\/\\/#define MAC_STAMPING/g" $P4_FILE'
    
    sudo docker exec -t -e P4_FILE="$p4_file" $dockerid_tofino bash -c 'export SDE_INSTALL=/opt/bf-sde-9.13.0/install; cd /home/root/p4sta/stamper/tofino1; mkdir -p compile; $SDE_INSTALL/bin/bf-p4c -v -o $PWD/compile/ $P4_FILE'
    
    sudo docker exec -d -e P4_FILE_N="$p4_file_without_ending" -t $dockerid_tofino bash -c 'export SDE=/opt/bf-sde-9.13.0 export SDE_INSTALL=/opt/bf-sde-9.13.0/install; export PATH=$PATH:$SDE_INSTALL/bin; $SDE_INSTALL/bin/veth_setup.sh; /opt/bf-sde-9.13.0/run_tofino_model.sh -c /home/root/p4sta/stamper/tofino1/compile/$P4_FILE_N.conf -p $P4_FILE_N -q'
    sleep 2
    sudo docker exec -t $dockerid_tofino bash -c 'sysctl -w net.ipv4.ip_forward=1; ip netns add nsveth3; ip link set veth3 netns nsveth3; ip netns add nsveth5; ip link set veth5 netns nsveth5; ip netns add dut; ip link set veth7 netns dut; ip link set veth9 netns dut; ip netns exec dut ifconfig veth7 10.0.1.1/24; ip netns exec dut ifconfig veth7 up; ip netns exec dut ifconfig veth9 10.0.2.1/24; ip netns exec dut ifconfig veth9 up; ip netns exec nsveth3 ifconfig veth3 hw ether 22:22:22:22:22:22; ip netns exec nsveth3 ifconfig veth3 10.0.1.3/24; ip netns exec nsveth3 ifconfig veth3 up; ip netns exec nsveth3 ip route add 10.0.2.0/24 via 10.0.1.1 dev veth3; ip netns exec nsveth5 ifconfig veth5 hw ether 22:22:22:33:33:33; ip netns exec nsveth5 ifconfig veth5 10.0.2.4/24; ip netns exec nsveth5 ifconfig veth5 up; ip addr add 10.11.12.99/24 dev veth11; ip link set dev veth11 address e2:46:14:e3:0b:7c; ip netns exec nsveth5 ip route add 10.0.1.0/24 via 10.0.2.1 dev veth5; ip netns exec nsveth3 ethtool --offload veth3 rx off tx off; ip netns exec nsveth5 ethtool --offload veth5 rx off tx off; ip netns exec dut ethtool --offload veth7 rx off tx off; ip netns exec dut ethtool --offload veth9 rx off tx off '
    
    sudo docker exec -t -e ssh_ip_mininet="$ssh_ip_mininet" -e ssh_ip_management="$ssh_ip_management" -e ssh_ip_bf_sde="$ssh_ip_bf_sde"  $dockerid_p4sta_core bash -c 'cd /opt/p4-timestamping-middlebox; source pastaenv_core_docker/bin/activate; python3 -b tests/test_django.py --ip_mininet $ssh_ip_mininet --ip_management $ssh_ip_management --ip_bf_sde $ssh_ip_bf_sde --target tofino --dpdkisTrue -v; deactivate;'
    sudo docker exec -t $dockerid_tofino bash -c 'pkill bf_switchd; pkill tofino-model'
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
    sudo docker exec -t $dockerid_p4sta_core rm -rf /opt/p4-timestamping-middlebox/pastenv || true
    sudo docker stop $dockerid_p4sta_core
    sudo docker stop $dockerid_mininet_py
    sudo docker stop $dockerid_tofino
    sudo find . -regex '^.*\\(__pycache__\\|\\.py[co]\\)$' -delete
}
