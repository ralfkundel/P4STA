# BMV2 stamper target
The BMV2 P4 software switch can be executed within Mininet for trying out P4STA.
However, the BMV2 provides NO time accuracy in any measurement.

##  requirements
The following dependencies are _not_ automatically installed with ./install.sh - please consider using the Docker installation in the next step instead of manual installation:
* Mininet >= 2.3.0d5. see: http://mininet.org/download/ Please use Option 2: Native Installation from Source
* bmv2 P4-behavioral model. see: https://github.com/p4lang/behavioral-model

## Install with Docker
We recommend to use our Mininet/BMV2 Docker image which must be build by yourself (docker must be installed on your system!):
* ```cd ../bmv2_mn_docker```
* ```sudo docker build -t mininet_bmv2 .```

Now start a container from the image you just built, you need to be in /P4STA main directory:
* ```dockerid_mininet_py=$(sudo docker run -dti -p 22223:22223 --privileged -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix -v /lib/modules:/lib/modules -v $PWD:/opt/p4-timestamping-middlebox mininet_bmv2 bash)```

Now start the ssh server inside the running container you just created and insert pub key of current machine into running container:
* ```sudo docker exec -t $dockerid_mininet_py sudo /etc/init.d/ssh start```
* ```pubkey_host=$(cat ~/.ssh/id_rsa.pub)```
* ```sudo docker exec -t -e PUB="$pubkey_host" $dockerid_mininet_py bash -c '[ ! -d "/root/.ssh" ] && mkdir /root/.ssh; cd /root/.ssh; touch authorized_keys; echo $PUB>>authorized_keys'```

Finally you need to retrieve the IP of running container:
* ```sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_mininet_py```

With the found IP you can create and execute the setup script: Tool button on the upper-right corner or http://IP:9997/setup_devices/ where you use the IP and root as user. The check SSH button should show a working SSH connection to the running container. Use the same IP and Username for Stamper, External Host and Loadgen (it is sufficient to only install one loadgen). Don't forget to execute the script as guided. BMV2 and P4STA should run now.

You may need to edit your config on http://IP:9997/configuration/ (main page), if you select a new configuration for bmv2 the correct SSH IPs from 10.99.66.0/24 are prefilled, please always use this subnet for SSH IPs otherwise the automatic generation of routes from management server to running mininet hosts inside docker container won't work.
* Use the IP of running container retrieved the step before as SSH IP for Stamper
* Use 10.99.66.0/24 for all loadgens as SSH IP
* Use root as SSH Username for all hosts (loadgen, ext-host, stamper)
* Loadgen interfaces are named (as suggested in prefilled config): h10-eth1 for Host1.1, h11-eth1 for Host1.2, h20-eth1 for Host2.1 and so on...
* Loadgen MACs are 22:22:22:22:group:host, so 22:22:22:22:01:01 for Host1.1 and 22:22:22:22:02:03 for Host2.3
* Loadgen IPs are 10.0.group.host+1, so 10.0.1.2 for Host1.1 and 10.0.2.4 for Host2.3
* External host should use the interface name extH-eth1


## Running
If P4STA is installed and bmv2 is selected as stamper target, the mininet environment including the bmv2 switch can be started from the Deploy page in P4STA.

