#!/bin/bash

# Change to directory that contains nfp4build, rtecli and others
export P4C_BIN_DIR=/opt/netronome/p4/bin

# Change to correct platform
PLATFORM=lithium


mkdir -p build

"$P4C_BIN_DIR"/nfp4build --nfirc_mac_ingress_timestamp --no-debug-info --shared-codestore --nfp4c_p4_version 16 -p build/out/ -o build/firmware.nffw -l $PLATFORM -4 middlebox_v7.p4
