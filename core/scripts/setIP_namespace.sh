#!/bin/bash

# if ssh -o ConnectTimeout=1 -o StrictHostKeyChecking=no $1@$2 "t=\$(ip netns list); arr=( \$t ); for i in \"\${arr[@]}\"; do found=\$(sudo ip netns exec \$i ifconfig | grep $3); if [ -n \"\$found\" ]; then echo deleting ns \$i; sudo ip netns del \$i; fi; done; sudo ip netns add $5; sudo ip link set $3 netns $5; sudo ip netns exec $5 bash -c \"if ifconfig $3 $4; then echo ifconfig_success; fi\""; [ $? -eq 255 ]
# then 
#   echo "failed"
# else
#   echo "worked"
# fi


ssh -o ConnectTimeout=1 -o StrictHostKeyChecking=no "$1@$2" 'bash -s' -- "$3" "$4" "$5" <<'REMOTE'
iface="$1"
addr="$2"
ns="$3"

for i in $(sudo ip netns list | awk '{print $1}'); do
  if sudo ip netns exec "$i" ip link show "$iface" >/dev/null 2>&1; then
    echo "deleting ns $i"
    sudo ip netns del "$i"
  fi
done

sudo ip netns add "$ns"
sudo ip link set "$iface" netns "$ns"

sudo ip netns exec "$ns" ip addr flush dev $iface

if sudo ip netns exec "$ns" ip addr replace "$addr" dev "$iface" && \
   sudo ip netns exec "$ns" ip link set "$iface" up; then
  echo ip_success
fi
REMOTE

if [ $? -eq 255 ]; then
  echo "failed"
else
  echo "worked"
fi