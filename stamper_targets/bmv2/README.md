# BMV2 stamper target
The BMV2 P4 software switch can be executed within Mininet for trying out P4STA.
However, the BMV2 provides NO time accuracy in any measurement.

##  requirements
The following dependencies are _not_ automatically installed with ./install.sh:
* Mininet >= 2.3.0d5. see: http://mininet.org/download/ Please use Option 2: Native Installation from Source
* bmv2 P4-behavioral model. see: https://github.com/p4lang/behavioral-model

## Running
If P4STA is installed and bmv2 is selected as stamper target, the mininet environment including the bmv2 switch can be started from the Deploy page in P4STA.

