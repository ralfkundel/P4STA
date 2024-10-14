FROM ubuntu:22.04

USER root
WORKDIR /root

COPY ENTRYPOINT.sh /

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    curl \
    iproute2 \
    iputils-ping \
    mininet \
    net-tools \
    openvswitch-switch \
    openvswitch-testcontroller \
    tcpdump \
    vim \
    x11-xserver-utils \
    xterm \
    ethtool \
    htop \
 && rm -rf /var/lib/apt/lists/* \
 && chmod +x /ENTRYPOINT.sh

RUN apt-get update && apt-get install -y python3 sudo inetutils-ping openssh-server psmisc lsb-release git

RUN git clone https://github.com/p4lang/behavioral-model.git; ls; echo $PWD

RUN cd behavioral-model && ./install_deps_ubuntu_22.04.sh && ./autogen.sh && ./configure --disable-logging-macros && make -j`nproc` && make install

EXPOSE 6633 6653 6640

ENTRYPOINT ["/ENTRYPOINT.sh"]
