#!/bin/bash
ssh -tt -o StrictHostKeyChecking=no $2@$1 "ethtool $3"
