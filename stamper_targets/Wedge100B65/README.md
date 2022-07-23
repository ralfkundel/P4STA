# Intel/Barefoot Tofino stamper

## Required SDE
For this version of P4STA please install the SDE in version 9.7.x on your Tofino and the according BSP.
Please include at least the grpc and thrift APIs while building the SDE.
Assuming the SDE is already extracted in the /opt directory:
```
cd /opt/bf-sde-9.7.2/p4studio/
./install-p4studio-dependencies.sh
./p4studio build
```

or alternatively use our yaml config file (located in tests/bf_sde_docker/p4sta_cfg.yaml):
```
cd /opt/bf-sde-9.7.2/p4studio/
./install-p4studio-dependencies.sh
./p4studio profile apply /opt/p4sta_cfg.yaml
```
Note: this yaml file does not contain the path to the BSP and must be added according to the Intel guidelines.

## Compiling the P4-file with Tofino SDE
The default P4 p4sta program is compiled by the install script.

IF you want to use a custom P4 program, copy the p4-files on your tofino and compile them manually:
```
cd /home/<YOUR_USER>/p4sta/stamper/tofino1
$SDE_INSTALL/bin/bf-p4c -v -o $PWD/compile/ your_p4_program.p4
```
and change the p4 program name accordingly on the configure page of p4sta.
Note: the compile output MUST be located in this directory (.../p4sta/stamper/tofino1/compile) to be found by the P4STA core.


## install P4STA driver for tofino
Follow the installation process starting from step 3.1 in the main readme of this repository.
