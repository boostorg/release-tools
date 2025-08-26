#!/bin/bash

# update the image name as necessary.
imagename="cppalliance/boost_superproject_build:24.04-v4"
# docker build --progress=plain -t $imagename . 2>&1 | tee /tmp/output.txt
docker build -t $imagename . 2>&1 | tee /tmp/output2.txt
