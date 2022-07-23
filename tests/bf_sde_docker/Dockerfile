# bf-sde-9.7.2.tar must be in same directory as THIS file!
FROM ubuntu:18.04

USER root
WORKDIR /root

#Volume untested
VOLUME /mnt/huge:/mnt/huge
VOLUME /lib/modules:/lib/modules
VOLUME /usr/src:/usr/src

COPY bf-sde-9.7.2.tgz /opt/bf-sde-9.7.2.tgz
COPY p4sta_cfg.yaml /opt/p4sta_cfg.yaml

RUN tar -zxvf /opt/bf-sde-9.7.2.tgz -C /opt

#RUN apt update && apt install -y --no-install-recommends linux-headers-$(uname -r) python python3 python3-pip python-setuptools python3-setuptools sudo inetutils-ping openssh-server psmisc lsb-release git nano tar kmod htop python3-dev build-essential python-yaml

#RUN python3 -m pip install --upgrade pip

RUN cd /opt/bf-sde-9.7.2/p4studio/ && ./install-p4studio-dependencies.sh
RUN cd /opt/bf-sde-9.7.2/p4studio/ && ./p4studio profile apply /opt/p4sta_cfg.yaml
