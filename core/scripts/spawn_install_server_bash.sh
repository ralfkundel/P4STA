#!/bin/bash
echo "printf '*********************************\nPLEASE ENTER: ./install_server.sh\n*********************************\n'; $PWD/install_server.sh " > initfile
bash --init-file initfile
