# Intel/Barefoot Tofino stamper

## Required SDE
For this version of P4STA please install the SDE in version 9.3.0 on your Tofino.
Please include the grpc and thrift APIs while building the SDE.
Assuming the SDE is already extracted in the /opt directory:
```
cd /opt/bf-sde-9.3.0/p4studio_build/
./p4studio_build.py --use-profile all_profile
```

## Compiling the P4-file with Tofino SDE
copy the following p4-files from this repository on your tofino:
```
~/P4STA/stamper_targets/Wedge100B65/PLEASE_COPY/header_tofino_stamper_v1_0_1.p4
~/P4STA/stamper_targets/Wedge100B65/PLEASE_COPY/tofino_stamper_v1_0_1.p4
```
and build them with the build script of the SDE:
```
./p4_build.sh ~/tofino_stamper_v1_0_1.p4
```

## install P4STA driver for tofino
Follow the installation process starting from step 3.1 in the main readme of this repository.
** Imortant: ** after the first installation p4sta must be stopped and restarted in the CLI in order to load the compiled grpc files.
