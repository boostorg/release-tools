#!/bin/bash

# Create ~/.config/rclone/rclone.conf
# [remote1]
# type = s3
# provider = AWS
# env_auth = true
# region = us-east-2

# Create ~/.aws/credentials
# [production]
# aws_access_key_id =
# aws_secret_access_key =

set -xe

# time export AWS_PROFILE=production; rclone -v sync --transfers 16 --checksum remote1:boost-archives /drive2/boostorg/ 2>&1 | tee output.txt
time export AWS_PROFILE=production; rclone -v copy --transfers 16 --checksum remote1:boost-archives /drive2/boostorg/ 2>&1 | tee output.txt

