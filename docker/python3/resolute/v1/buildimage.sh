#!/bin/bash

# update the image name as necessary.
imagename="cppalliance/boost_superproject_build:26.04-v1"
# docker build --progress=plain -t $imagename . 2>&1 | tee /tmp/output.txt
time docker build -t $imagename . 2>&1 | tee /tmp/output2.txt
