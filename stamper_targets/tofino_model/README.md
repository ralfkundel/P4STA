To use Tofino model as stamper, you need to prepare a setup, e.g. with a tofino model docker container as it is used in the P4STA tests.

Deploy with P4STA tests:
- Ensure that your installation has run ```./build_docker_images.sh``` and ```./run_tests.sh install``` to build the docker image(s). Backup your config files in /data before as they may be overwritten.
- Retrieve IP of tofino docker container: ```sudo docker exec -it $dockerid_tofino ifconfig -a``` (dockerid_tofino can be found in dir bash_vars) => set IP in P4STA GUI
- If you have trouble starting P4STA again: Stop the management_ui docker container which blocks port 9997, but not the Tofino container
- Add ssh-key to tofino container, set my_pubkey before (something like ```my_pubkey=$(cat .ssh/id_rsa.pub)```):
```
sudo docker exec -t -e PUB="$my_pubkey" $dockerid_tofino bash -c '[ ! -d \"/root/.ssh\" ] && mkdir -p /root/.ssh; cd /root/.ssh; touch authorized_keys; echo $PUB>>authorized_keys'
```
- SSH into the container for testing: "ssh root@IP_container" should work without password now
- Open the install menu in P4STA and install the stamper, user is root, sde path: /opt/bf-sde-9.13.0
- Run tofino model:
```
sudo docker exec -d -t -e P4_FILE_N="tofino_stamper_v1_3_0" $dockerid_tofino bash -c 'export SDE=/opt/bf-sde-9.13.0 export SDE_INSTALL=/opt/bf-sde-9.13.0/install export PATH=$PATH:$SDE_INSTALL/bin; $SDE_INSTALL/bin/veth_setup.sh; /opt/bf-sde-9.13.0/run_tofino_model.sh -c /home/root/p4sta/stamper/tofino1/compile/$P4_FILE_N.conf -p $P4_FILE_N -q'
```


