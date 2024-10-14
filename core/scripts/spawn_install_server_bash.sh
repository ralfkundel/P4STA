#!/bin/bash
echo "printf '*********************************\nPLEASE ENTER: ./autogen_scripts/nstall_server.sh\n*********************************\n'; $PWD/autogen_scripts/install_server.sh " > initfile
bash --init-file initfile
