#!/bin/bash
ssh $3@$1 "timeout 1 ping $2 -i 0.2 -c 3"