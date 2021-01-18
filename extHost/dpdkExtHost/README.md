# DPDK external host
The dpdk external host can be installed by P4STA server install script generator.
Currently tested NICs: Intel X710, 82599
However, the kernel module must be loaded manually and the NIC bound to it e.g.:

## general
P4STA external host uses always the dpdk device nr 0.

## Use of the vfio kernel module (recommended)
1. enable the iommu and hugepages on the external host server:
Add the following parameters to the /etc/default/grub file:
```
GRUB_CMDLINE_LINUX_DEFAULT="intel_iommu=on default_hugepagesz=1G hugepagesz=1G hugepages=8 hugepagesz=2M hugepages=1024"
```
and update grub + restart:
```
sudo update-grub
sudo reboot 0
```

2. create an install script with p4sta (wrench in the top right corner of the p4sta GUI).

3. execute the install script once.

4. every time you restart the server, the kernel module must be loaded manually:

```
sudo modprobe vfio-pci
cd p4sta/externalHost/dpdkExtHost/dpdk-19.11/usertools/
sudo ./dpdk-devbind.py -b vfio-pci 05:00.0
```

## alternative kernel module (only if no iommu is available):
```
sudo insmod build/kmod/igb_uio.ko
sudo usertools/dpdk-devbind.py -b igb_uio 0000:05:00.0
```
