#!/bin/bash
ssh -tt -o StrictHostKeyChecking=no $1@$2 "sudo reboot"
