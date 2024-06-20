#!/usr/bin/env -S python3 -u

# Download files from s3 to the local machine on a frequent cron schedule.
#
# Instructions
#
# This scripts reads a file /tmp/boostarchivesinfo/filelist.txt
#
# Each line of filelist.txt should contain a path to an artifactory file in this format:
# main/release/1.84.0/source/boost_1_84_0.tar.bz2
# main/release/1.84.0/source/boost_1_84_0.tar.bz2.json
#
# install dotenv:
# pip3 install python-dotenv
#
# install rclone:
# wget https://downloads.rclone.org/v1.66.0/rclone-v1.66.0-linux-amd64.deb; dpkg -i rclone-v1.66.0-linux-amd64.deb
#
# create ${HOME}/.config/rclone/rclone.conf
# [remote1]
# type = s3
# provider = AWS
# env_auth = true
# region = us-east-2
#
# create ${HOME}/.aws/credentials and config, with production profile
#
# Add a per-minute cron task:
#
# * * * * * ${HOME}/scripts/s3-file-sync.py > /tmp/s3-file-sync-output.txt 2>&1
#
# Run either s3-file-sync.py or jfrog-file-sync.py, but not both
#

import os
import subprocess
import pathlib
import re
from dotenv import load_dotenv

load_dotenv()

upload_to_s3 = True
s3_archives_bucket = "boost-archives"
debug = 1
source_file_lists = ["/tmp/boostarchivesinfo/filelist.txt", "/tmp/boostarchivesinfo/vsbinaries_filelist.txt"]
local_copy_of_archives = "/drive2/boostorg"

os.chdir(local_copy_of_archives)

for source_file_list in source_file_lists:
    if not os.path.isdir(os.path.dirname(source_file_list)):
        if debug > 0:
            print(
                "The directory of source_file_list is missing. Perhaps there are no files to sync right now. Exiting."
            )
        continue
    
    if not os.path.isfile(source_file_list):
        if debug > 0:
            print(
                "The source_file_list is missing. Perhaps there are no files to sync right now. Exiting."
            )
        continue
    
    # Download files
    with open(source_file_list, "r") as f:
        # data = f.readlines()
        data = f.read().splitlines()
        # Remove/clean-up source_file_list so it won't be processed next time
        pathlib.Path(source_file_list).unlink()
        for file in data:
            file = file.strip()
            # Sanitize file. It exists, matches ordinary characters, doesn't contain two dots "..", doesn't start with absolute path "/"
            if (
                file
                and re.match("^[a-zA-Z0-9_/.-]+$", file)
                and not re.match("\.\.", file)
                and not re.match("^/", file)
            ):
    
                archivePathLocal = re.sub("^main/", "", file)
                archivePathRemote = "remote1:" + s3_archives_bucket + "/" + archivePathLocal
                result = subprocess.run(
                    "export AWS_PROFILE=%s;rclone -v --s3-no-check-bucket copyto --checksum %s %s"
                    % ("production", archivePathRemote, archivePathLocal),
                    check=True,
                    shell=True,
                    text=True,
                )
    
                if debug > 0:
                    print(result)
