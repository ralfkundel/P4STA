
In order to recompile the protobuf python stubs (i.e. after an SDE update or python dependencies up-/downgrade):

1. update proto/bfruntime.proto
2. do in the directory of this readme:
```
source ../../../pastaenv/bin/activate;
python3 -m grpc_tools.protoc -I ./proto --python_out=. --grpc_python_out=. ./proto/bfruntime.proto; 
deactivate
```
