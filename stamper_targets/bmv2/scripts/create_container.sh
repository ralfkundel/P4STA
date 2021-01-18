#!/bin/bash
echo Starting mininet/bmv2 container from mininet_bmv2 image
dockerid_mininet=$(sudo docker run -dti -p 22223:22223 --privileged -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix -v /lib/modules:/lib/modules mininet_bmv2 bash) #-v $PWD:/opt/p4-timestamping-middlebox
sudo docker exec -t $dockerid_mininet bash -c "sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/g' /etc/ssh/sshd_config"
sudo docker exec -t $dockerid_mininet bash -c "service ssh restart"
sudo docker exec -t $dockerid_mininet bash -c "ldconfig; apt update; apt install lsof"
pubkey_management=$(cat ~/.ssh/id_rsa.pub)
sudo docker exec -t -e PUB="$pubkey_management" $dockerid_mininet bash -c '[ ! -d "/root/.ssh" ] && mkdir /root/.ssh; cd /root/.ssh; touch authorized_keys; echo $PUB>>authorized_keys'
ssh_ip_mininet=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $dockerid_mininet)
echo IP MININET CONTAINER:  $ssh_ip_mininet
echo finished
