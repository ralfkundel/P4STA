#!/bin/bash

VERSION=1.22.3

install=false
if [ ! -d "$PWD/go/bin/" ]; then
    echo "$PWD/go/bin/ does not exist."
    install=true
else
    go_output_p4sta=$($PWD/go/bin/go version)
    if [[ "$go_output_p4sta" == *"$SUB"* ]]; then
        echo "Found golang executeable in p4sta folder."
        install=false
    else
        install=true
    fi
fi


if [ "$install" = true ] ; then
    echo "Golang not found in p4sta folder. Pulling v$VERSION from google server as binary and installing in /p4sta/externalHost/go/go/bin"
    wget https://go.dev/dl/go$VERSION.linux-amd64.tar.gz
    tar -xzf go$VERSION.linux-amd64.tar.gz

    # check if it works
    go_output2=$($PWD/go/bin/go version)
    echo "Installed Golang $VERSION"
    echo $go_output2

    rm go$VERSION.linux-amd64.tar.gz
fi

