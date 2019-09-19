#!/bin/bash
ssh -tt $1@$2 "sudo ethtool -r $3"