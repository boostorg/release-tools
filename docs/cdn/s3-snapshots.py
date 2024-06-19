#!/bin/bash

set -xe

export AWS_PROFILE=production; rclone -v sync --transfers 16 --checksum remote1:boost-archives/develop /drive2/boostorg/develop/ 2>&1 | tee /tmp/s3-snapshots-develop.log
export AWS_PROFILE=production; rclone -v sync --transfers 16 --checksum remote1:boost-archives/master /drive2/boostorg/master/ 2>&1 | tee /tmp/s3-snapshots-master.log


