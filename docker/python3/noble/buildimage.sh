#!/bin/bash

# update the image name as necessary.
imagename="cppalliance/boost_superproject_build:24.04-v2"
docker build --progress=plain -t $imagename . 2>&1 | tee /tmp/output.txt
