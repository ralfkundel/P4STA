FROM ubuntu:18.04

USER root
WORKDIR /root

COPY ENTRYPOINT.sh /

RUN apt-get update && apt-get install -y --no-install-recommends \
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
 && rm -rf /var/lib/apt/lists/* \
 && chmod +x /ENTRYPOINT.sh

RUN apt-get update && apt-get install -y python3 sudo inetutils-ping openssh-server psmisc lsb-release git

RUN git clone https://github.com/p4lang/behavioral-model.git; ls; echo $PWD

RUN cd behavioral-model && ./install_deps.sh && ./autogen.sh && ./configure --disable-logging-macros && make && make install

EXPOSE 6633 6653 6640

ENTRYPOINT ["/ENTRYPOINT.sh"]
