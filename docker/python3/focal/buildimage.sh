#!/bin/bash

# update the image name as necessary.
imagename="cppalliance/boost_superproject_build:20.04-v3"
docker build -t $imagename .
