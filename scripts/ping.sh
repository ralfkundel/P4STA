#!/bin/bash
ssh -o StrictHostKeyChecking=no $3@$1 "$4 timeout 1 ping $2 -i 0.2 -c 3"
