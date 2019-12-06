#!/bin/bash
ssh -o StrictHostKeyChecking=no $3@$2 "sudo killall external_host_python_receiver"

