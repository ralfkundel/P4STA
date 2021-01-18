#!/bin/bash
echo "###########################################################################"
echo "Welcome to P4STA! Please select the mode you want to start the environment."
echo "To stop P4STA you just need to enter ctrl + c"
echo "###########################################################################"
source pastaenv/bin/activate
select yn in "P4STA Core + HTML-GUI (recommended)" "P4STA Core(VERBOSE) + HTML-GUI" "P4STA Core + CLI" "Just P4STA Core (VERBOSE)"; do
    case $yn in
        "P4STA Core + HTML-GUI (recommended)" ) (python3 core/core.py>/dev/null&); sleep 2; python3 manage.py runserver 0.0.0.0:9997; break;;
		"P4STA Core(VERBOSE) + HTML-GUI" ) (python3 core/core.py&); sleep 2; python3 manage.py runserver 0.0.0.0:9997; break;;
        "P4STA Core + CLI" ) (python3 core/core.py>/dev/null&); sleep 2; python3 cli/cli.py; break;;
		"Just P4STA Core (VERBOSE)" ) echo "To start the GUI or CLI separately use ./gui.sh or ./cli.sh"; python3 core/core.py; break;;
    esac
done
pkill python3 #kills core.py instance at the end
deactivate

