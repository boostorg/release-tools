#!/bin/bash

set -xe

cd /drive2/boostorg && /usr/bin/jfrog rt download --url=https://boostorg.jfrog.io/artifactory/ --user=samdarwin --password= --detailed-summary --flat=false --recursive=true  main/ "./" > /tmp/jfrog-all.log 2>&1

