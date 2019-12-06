#!/bin/bash
ssh -o StrictHostKeyChecking=no $2@$1 "sudo pkill python"
