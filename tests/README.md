
## A. Running the CI scripts locally:
### 1. build the docker containers
within this test directory
```
./build_docker_images.sh
```

### 2. run test initialization
in the root directory of this repo:
```
./run_test.sh install
```


### 4. run any test
```
./run_test.sh {install|test_code_quality|test_ptf_bmv2|test_ptf_tofino|test_core|test_ui|test_ui_tofino|dpdk_install|test_core_dpdk|cleanup|all}
```


## B. Configure gitlab ci runner for gitlab:
### 1. dependency install on CI server:
```
sudo apt install docker docker.io gitlab-runner
```

If you want to use automatic execution (e.g. by git push) you need to register the runner, please chose "Shell" as executor and "p4sta" as tag. More information: https://docs.gitlab.com/runner/register/

Mounted files edited/created inside a container are owned by root afterwards, hence gitlab-runner is not able to delete those files. Please edit /etc/gitlab-runner/config.toml _AFTER_ setting up the gitlab-runner. 


```
pre_clone_script = "[ -d \"/home/gitlab-runner/builds/PLEASE_INSERT/0/gitlab/ralf.kundel/p4-timestamping-middlebox/\" ] && cd /home/gitlab-runner/builds/PLEASE_INSERT/0/gitlab/ralf.kundel/p4-timestamping-middlebox/ && sudo git clean -ffdx"
```
### 2. create docker images:
Note: you must copy the bf-sde-9.7.2.tgz file into bf_sde_docker before creating the container
```
./build_docker_images.sh
```

### 3. add docker to visudo:

For automatic exection (e.g. triggered by git push):
```
gitlab-runner ALL=(ALL:ALL) NOPASSWD: /usr/bin/docker
gitlab-runner ALL=(ALL:ALL) NOPASSWD: /usr/bin/find
gitlab-runner ALL=(ALL:ALL) NOPASSWD: /usr/bin/git
```


## general remarks:
* Gitlab runs the job on a dedicated CI VM. The docker images are static and not rebuild ever run.

