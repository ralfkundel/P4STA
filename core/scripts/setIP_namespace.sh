#!/bin/bash
if ssh -o ConnectTimeout=1 -o StrictHostKeyChecking=no $1@$2 "t=\$(ip netns list); arr=( \$t ); for i in \"\${arr[@]}\"; do found=\$(sudo ip netns exec \$i ifconfig | grep $3); if [ -n \"\$found\" ]; then echo deleting ns \$i; sudo ip netns del \$i; fi; done; sudo ip netns add $5; sudo ip link set $3 netns $5; sudo ip netns exec $5 bash -c \"if ifconfig $3 $4; then echo ifconfig_success; fi\""; [ $? -eq 255 ]
then 
  echo "failed"
else
  echo "worked"
fi

