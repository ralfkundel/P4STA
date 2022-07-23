#!/bin/bash
DIRECTORY="tests"
if [ -d "$DIRECTORY" ]; then
  echo "you need to be in /tests/ptf"
  cd tests/ptf
fi
echo "cd to: "
echo $PWD
simple_switch -i 0@veth0 -i 1@veth2 -i 2@veth4 -i 3@veth6 -i 4@veth8 -i 5@veth10 -i 6@veth12 -i 7@veth14 --thrift-port 22223 $PWD/../../stamper_targets/bmv2/data/bmv2_stamper_v1_0_0.json &
sudo ptf --test-dir ./bmv2 --pypath $PWD --interface 0@veth1 --interface 1@veth3 --interface 2@veth5 --interface 3@veth7 --interface 4@veth9 --interface 5@veth11 --interface 6@veth13
