#!/bin/bash
if [ -z "$4" ]; then
    ssh -o ConnectTimeout=1 -o StrictHostKeyChecking=no $1@$2 "ifconfig $3"
else
	ssh -o ConnectTimeout=1 -o StrictHostKeyChecking=no $1@$2 "sudo ip netns exec $4 ifconfig $3"
fi

