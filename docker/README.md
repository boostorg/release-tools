
Dockerfiles to generate the boost_superproject_build images.  

| file | description | hub.docker.com image | comments |
| ---- | ----------- | -------------------- | -------- |
| docker/python2/xenial/Dockerfile | Python2 on Xenial | cppalliance/boost_superproject_build:build-deps-5 | minor asciidoctor syntax problems, attributed to ruby version. Don't use Xenial. |
| docker/python2/bionic/Dockerfile | Python2 on Bionic | cppalliance/boost_superproject_build:build-deps-4 | 2021-10-20 was used |
| docker/python3/bionic/Dockerfile | Python3 on Bionic | cppalliance/boost_superproject_build:python3-build2 | late 2021 through most of 2022 this was in production |
| docker/python3/focal/Dockerfile | Python3 on Focal | cppalliance/boost_superproject_build:20.04-v1 | 2023-01 Updates most gem and pip packages |
| docker/python3/focal/Dockerfile | Python3 on Focal | cppalliance/boost_superproject_build:20.04-v2 | 2023-09 Install rclone and aws cli |
| docker/python3/focal/Dockerfile | Python3 on Focal | cppalliance/boost_superproject_build:20.04-v3 | 2023-10 installs nodejs, npm for antora builds |
| docker/python3/focal/Dockerfile | Python3 on Focal | cppalliance/boost_superproject_build:20.04-v4 | 2023-10 asciidoctor-diagram, asciidoctor-multipage, @mermaid-js/mermaid-cli |
| docker/python3/jammy/Dockerfile | Python3 on Jammy | cppalliance/boost_superproject_build:22.04-v1 | 2024-05, with autocancel workflows |
| docker/python3/noble/Dockerfile | Python3 on Noble | cppalliance/boost_superproject_build:24.04-v1 | 2024-10 |
| docker/python3/noble/Dockerfile | Python3 on Noble | cppalliance/boost_superproject_build:24.04-v2 | 2024-11 Include few more package updates. used in Jenkins |
| docker/python3/noble/Dockerfile | Python3 on Noble | cppalliance/boost_superproject_build:24.04-v3 | 2024-12 Update many pip/gem packages |

See [technical-notes.md](technical-notes.md) for development details.  
