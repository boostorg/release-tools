
Dockerfiles to generate the boost_superproject_build images.  

While there should preferably be only one official docker image to build the boost superproject, that image is currently in transition, going from python2 to python3. And, as time passes, the best choice of a base docker image also changes. Therefore, let's keep a few copies of the Dockerfile available. After things stabilize, older copies can be removed.  

| file | description | hub.docker.com image | comments |
| ---- | ----------- | -------------------- | -------- |
| docker/python2/xenial/Dockerfile | Python2 on Xenial | cppalliance/boost_superproject_build:build-deps-5 | minor asciidoctor syntax problems, attributed to ruby version. Don't use Xenial. |
| docker/python2/bionic/Dockerfile | Python2 on Bionic | cppalliance/boost_superproject_build:build-deps-4 | 2021-10-20 in production |
| docker/python3/bionic/Dockerfile | Python3 on Bionic | cppalliance/boost_superproject_build:python3-build2 | 2021-10-20 planning to use this Dockerfile in production soon. |
