#!/bin/bash

set -xe

cd /drive2/boostorg && /usr/bin/jfrog rt download --url=https://boostorg.jfrog.io/artifactory/ --user=samdarwin --password= --detailed-summary --flat=false --recursive=true  main/develop/ "./" > /tmp/jfrog-snapshots-develop.log 2>&1
cd /drive2/boostorg && /usr/bin/jfrog rt download --url=https://boostorg.jfrog.io/artifactory/ --user=samdarwin --password= --detailed-summary --flat=false --recursive=true  main/master/ "./" > /tmp/jfrog-snapshots-master.log 2>&1


