# adjusted from https://github.com/fstab/docker-ubuntu
FROM ubuntu:18.04

RUN apt update && \
    apt upgrade -y
    
RUN apt install -y \
    apt-utils \
    locales \
    tzdata

RUN echo "Europe/Berlin" | tee /etc/timezone && \
    ln -fs /usr/share/zoneinfo/Europe/Berlin /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata
    
RUN echo en_US.UTF-8 UTF-8 >> /etc/locale.gen && \
    locale-gen && \
    update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
#ENV LC_ALL en_US.UTF-8

RUN apt install -y python3 sudo inetutils-ping net-tools openssh-server psmisc tcpdump nano iproute2 htop

RUN echo 'defshell -bash' >> /root/.screenrc
RUN echo 'if [ -f /etc/bash_completion ] && ! shopt -oq posix; then' >> /root/.bashrc && \
    echo '    . /etc/bash_completion' >> /root/.bashrc && \
    echo 'fi' >> /root/.bashrc
