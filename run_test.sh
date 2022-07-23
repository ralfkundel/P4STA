AVAILABLE_TESTS="install|test_code_quality|test_ptf_bmv2|test_ptf_tofino|test_core|test_ui|test_ui_tofino|dpdk_install|test_core_dpdk|cleanup|all"
if [[ ! "$1" =~ $AVAILABLE_TESTS ]]
then
    echo "Usage: $0 [ ${AVAILABLE_TESTS//|/ | } ]"
    exit 1
fi

source tests/ci_tests.sh



if [[ "$1" == "install" ]]
then
    set -e
    job_prepare
    job_install
    printf "${GREEN} [SUCCESS] Succeeded installing p4sta ci test environment \n${NC}"
    exit 0
fi

if [[ "$1" == "test_code_quality" ]]
then
    set -e
    job_code_quality
    printf "${GREEN} [SUCCESS] Succeeded test_code_quality \n${NC}"
    exit 0
fi


if [[ "$1" == "test_ptf_bmv2" ]]
then
    set -e
    job_ptf_bmv2
    printf "${GREEN} [SUCCESS] Succeeded test_ptf_bmv2 \n${NC}"
    exit 0
fi

if [[ "$1" == "test_ptf_tofino" ]]
then
    set -e
    job_ptf_tofino
    printf "${GREEN} [SUCCESS] Succeeded test_ptf_tofino \n${NC}"
    exit 0
fi

if [[ "$1" == "test_core" ]]
then
    set -e
    job_test_core
    printf "${GREEN} [SUCCESS] Succeeded test_core \n${NC}"
    exit 0
fi

if [[ "$1" == "test_ui" ]]
then
    set -e
    job_test_django_bmv2
    printf "${GREEN} [SUCCESS] Succeeded test_ui \n${NC}"
    exit 0
fi

if [[ "$1" == "test_ui_tofino" ]]
then
    set -e
    job_test_django_tofino
    printf "${GREEN} [SUCCESS] Succeeded test_ui_tofino \n${NC}"
    exit 0
fi

if [[ "$1" == "dpdk_install" ]]
then
    set -e
    job_dpdk_install
    printf "${GREEN} [SUCCESS] Succeeded dpdk_install \n${NC}"
    exit 0
fi

if [[ "$1" == "test_core_dpdk" ]]
then
    set -e
    job_test_core_dpdk
    printf "${GREEN} [SUCCESS] Succeeded test_core_dpdk \n${NC}"
    exit 0
fi

if [[ "$1" == "cleanup" ]]
then
    set -e
    job_cleanup
    printf "${GREEN} [SUCCESS] Succeeded job_cleanup \n${NC}"
    exit 0
fi

if [[ "$1" == "all" ]]
then
    set -e
    job_prepare
    job_install
    printf "${GREEN} [SUCCESS] Succeeded installing p4sta ci test environment \n${NC}"
    job_code_quality
    printf "${GREEN} [SUCCESS] Succeeded test_code_quality \n${NC}"
    job_ptf_bmv2
    printf "${GREEN} [SUCCESS] Succeeded test_ptf_bmv2 \n${NC}"
    job_ptf_tofino
    printf "${GREEN} [SUCCESS] Succeeded test_ptf_tofino \n${NC}"
    job_test_core
    printf "${GREEN} [SUCCESS] Succeeded test_core \n${NC}"
    job_test_django_bmv2
    printf "${GREEN} [SUCCESS] Succeeded test_ui \n${NC}"
    job_test_django_tofino
    printf "${GREEN} [SUCCESS] Succeeded test_ui_tofino \n${NC}"
    job_dpdk_install
    printf "${GREEN} [SUCCESS] Succeeded dpdk_install \n${NC}"
    job_test_core_dpdk
    printf "${GREEN} [SUCCESS] Succeeded test_core_dpdk \n${NC}"    
    job_cleanup
    printf "${GREEN} [SUCCESS] Succeeded in all Test Jobs \n${NC}"
    exit 0
fi

