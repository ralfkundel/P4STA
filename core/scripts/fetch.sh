#!/bin/bash
ssh -o ConnectTimeout=1 -o StrictHostKeyChecking=no $1@$2 "ifconfig $3"
