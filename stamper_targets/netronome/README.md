# Netronome NFP stamper
Tested hardware: NFP-4000 series with 2x10G and 1x40G.
NFP-6000 series is currently untested.


## installation:
Before installing the P4STA-stamper (as described in the main readme) it is required to install the Netronome driver in the version 6.1.0.
To do so:
```
tar -xf nfp-sdk-p4-rte-6.1.0.1-preview-3214.ubuntu.x86_64.tgz
sudo apt-get install realpath libftdi1 libjansson4 build-essential linux-headers-`uname -r` dkms
sudo ./sdk6_rte_install.sh install

```

In order to change the mode of a 40G NFP-card to 4x10G, insert the following command on the server of the Netronome SmartNIC:
```
sudo ./nfp-media phy0=4x10G
```