#!/usr/bin/env -S python3 -u

# Copy files from jfrog to the local machine on frequent cron schedule.
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
# Create a .env file in the same directory. Example:
# JFROG_URL="https://boostorg.jfrog.io/artifactory/"
# JFROG_USERNAME="_"
# JFROG_PASSWORD="_"
#
# Add a per-minute cron task:
#
# * * * * * ${HOME}/scripts/jfrog-file-sync.py > /tmp/jfrog-file-sync-output.txt 2>&1
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
jfrog_executable = "/usr/bin/jfrog"

JFROG_URL = os.getenv("JFROG_URL")
JFROG_USERNAME = os.getenv("JFROG_USERNAME")
JFROG_PASSWORD = os.getenv("JFROG_PASSWORD")

os.chdir(local_copy_of_archives)

# check hostname
result = subprocess.run(["hostname", "-f"], check=True, capture_output=True, text=True)
hostname = result.stdout.strip()

for source_file_list in source_file_lists:
    if not os.path.isfile(jfrog_executable):
        if debug > 0:
            print("The jfrog executable is missing in jfrog-file-sync.py. Exiting.")
        exit(1)
    
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
                and not re.match(r"\.\.", file)
                and not re.match("^/", file)
            ):
                # Example download:
                # cd /drive2/boostorg && /usr/bin/jfrog rt download --url=https://boostorg.jfrog.io/artifactory/ --user= --password= --detailed-summary --flat=false --recursive=true  main/ "./" > /tmp/jfrog-all.log 2>&1
                result = subprocess.run(
                    [
                        jfrog_executable,
                        "rt",
                        "download",
                        f"--url={JFROG_URL}",
                        f"--user={JFROG_USERNAME}",
                        f"--password={JFROG_PASSWORD}",
                        "--detailed-summary",
                        "--flat=false",
                        "--recursive=true",
                        file,
                        "./",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                if debug > 0:
                    print(result)
    
                if upload_to_s3 and hostname == "brorigin1.cpp.al":
                    archivePathLocal = re.sub("^main/", "", file)
                    archivePathRemote = (
                        "remote1:" + s3_archives_bucket + "/" + archivePathLocal
                    )
                    result = subprocess.run(
                        "export AWS_PROFILE=%s;rclone -v --s3-no-check-bucket copyto --checksum %s %s"
                        % ("production", archivePathLocal, archivePathRemote),
                        check=True,
                        shell=True,
                        text=True,
                    )
    
                    if debug > 0:
                        print(result)

