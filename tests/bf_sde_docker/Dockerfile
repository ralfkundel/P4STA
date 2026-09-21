FROM ubuntu:22.04

USER root
WORKDIR /root

#Volume untested
VOLUME /mnt/huge:/mnt/huge
VOLUME /lib/modules:/lib/modules
VOLUME /usr/src:/usr/src

# COPY bf-sde-9.13.4.tar.xz /opt/bf-sde-9.13.4.tar.xz
COPY p4sta_cfg.yaml /opt/p4sta_cfg.yaml
COPY compile.sh /opt/compile.sh

RUN chmod +x /opt/compile.sh

RUN ls /opt -lha

RUN apt update && apt install -y --no-install-recommends \
    xz-utils \
    tar \
    git \
    ca-certificates \
    linux-headers-$(uname -r)

RUN update-ca-certificates


# modified tofino-model version with 16 to 32 bit cast fix
# https://github.com/fridolinsiegmund/open-p4studio.git
# For now: we changed the P4 to circumvent the tofino-model bug and can use the official repo again
RUN cd /opt && git clone https://github.com/p4lang/open-p4studio.git && mv open-p4studio bf-sde-9.13.4


# RUN tar -xf /opt/bf-sde-9.13.4.tar.xz -C /opt

#RUN apt update && apt install -y --no-install-recommends linux-headers-$(uname -r) python python3 python3-pip python-setuptools python3-setuptools sudo inetutils-ping openssh-server psmisc lsb-release git nano tar kmod htop python3-dev build-essential python-yaml

#RUN python3 -m pip install --upgrade pip

RUN cd /opt/bf-sde-9.13.4/p4studio/ && ./install-p4studio-dependencies.sh
RUN cd /opt/bf-sde-9.13.4/p4studio/ && ./p4studio profile apply /opt/p4sta_cfg.yaml

ENV SDE=/opt/bf-sde-9.13.4
ENV SDE_INSTALL=${SDE}/install

# dummy manifest file for compatibility
RUN touch /opt/bf-sde-9.13.4/bf-sde-9.13.4.manifest

RUN test -x "$SDE_INSTALL/bin/p4c" && \
    ln -sfn "$SDE_INSTALL/bin/p4c" "$SDE_INSTALL/bin/bf-p4c" && \
    ln -sfn "$SDE_INSTALL/bin/p4c" "$SDE_INSTALL/bin/bf_p4c"
