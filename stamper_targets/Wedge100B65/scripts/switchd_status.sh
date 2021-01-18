#!/bin/bash
ssh $1@$2 "pid=\$(pidof bf_switchd); if [[ \$pid = *[!\ ]* ]]; then echo \$pid; ps -p \$pid -o cmd; fi"
