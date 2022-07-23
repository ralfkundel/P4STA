
In order to recompile the protobuf python stubs (i.e. after an SDE update):
```
source ../../../pastaenv/bin/activate;
python3 -m grpc_tools.protoc -I ./proto --python_out=. --grpc_python_out=. ./proto/bfruntime.proto; 
deactivate
```
