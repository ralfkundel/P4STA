#!/bin/bash
ssh -tt $2@$1 "ethtool $3"