#!/bin/bash
echo "###########################################################################"
echo "Welcome to P4STA! Please select the mode you want to start the environment."
echo "To stop P4STA you just need to enter ctrl + c"
echo "###########################################################################"

if [ -z "$P4STA_VIRTUALENV" ]
then
    P4STA_VIRTUALENV="pastaenv"
    echo "[LOG][run.sh] P4STA_VIRTUALENV not specified. taking default path 'pastaenv'"
fi
source $P4STA_VIRTUALENV/bin/activate
select yn in "P4STA Core + HTML-GUI (Log=Info)" "P4STA Core + HTML-GUI (Log=Debug)" "P4STA Core + CLI (not all functions supported)" "Just P4STA Core (Log=Debug)"; do
    case $yn in
        "P4STA Core + HTML-GUI (Log=Info)" ) (export P4STA_LOG_LEVEL=INFO; python3 core/core.py&); sleep 2; export P4STA_LOG_LEVEL=INFO; python3 manage.py runserver 0.0.0.0:9997; break;;
		"P4STA Core + HTML-GUI (Log=Debug)" ) (export P4STA_LOG_LEVEL=DEBUG; python3 core/core.py&); sleep 2; export P4STA_LOG_LEVEL=DEBUG; python3 -Wa manage.py runserver 0.0.0.0:9997; break;;
        "P4STA Core + CLI (not all functions supported)" ) (python3 core/core.py>/dev/null&); sleep 2; python3 cli/cli.py; break;;
		"Just P4STA Core (Log=Debug)" ) echo "To start the GUI or CLI separately use ./gui.sh or ./cli.sh"; export P4STA_LOG_LEVEL=DEBUG; python3 core/core.py; break;;
    esac
done
pkill python3 #kills core.py instance at the end
deactivate

