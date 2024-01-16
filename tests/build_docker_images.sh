sudo apt install docker.io



RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

SDE_FILE=bf_sde_docker/bf-sde-9.13.0.tgz
if test -f "$SDE_FILE"; then
    echo "$SDE_FILE exists."
    sudo docker build -t bf_sde:9.13.0 bf_sde_docker
    printf "${GREEN} \xE2\x9C\x94 successfully created tofino docker image\n${NC}"

else
    printf "${RED} $SDE_FILE does not exists. Please download the SDE from intel and copy it into this directory${NC}"
fi


sudo docker build -t management core_docker

if [ $? -ne 0 ]; then
    printf "${RED} [Docker Build] Error while building the core docker container${NC}"
else
    printf "${GREEN} \xE2\x9C\x94 successfully created p4sta-core docker image\n${NC}"
fi

sudo docker build -t mininet_bmv2 bmv2_mn_docker
if [ $? -ne 0 ]; then
    printf "${RED} [Docker Build] Error while building the bmv2 mininet docker container${NC}"
else
    printf "${GREEN} \xE2\x9C\x94 successfully created bmv2 docker image\n${NC}"
fi
