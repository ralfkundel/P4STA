#!/bin/bash
ssh -tt -o StrictHostKeyChecking=no $2@$1 "$4 ethtool $3"
