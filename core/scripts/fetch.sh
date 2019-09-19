#!/bin/bash
ssh -o ConnectTimeout=1 $1@$2 "ifconfig $3"
