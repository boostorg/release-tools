#!/usr/bin/env python3

# Copyright Sam Darwin 2021
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at
# http://www.boost.org/LICENSE_1_0.txt)

# One-time upload of historical releases to github.
#
# INSTRUCTIONS:
#
# Download the releases from dl.bintray.com
# wget -e robots=off  --recursive --page-requisites --adjust-extension --span-hosts --convert-links --domains dl.bintray.com --no-parent dl.bintray.com/boostorg/
#
# Set values in Config section below.
# - The location of a local updated copy of the boost repository, such as github_releases_folder="/opt/github/project"
# - The location of wherever the wget has downloaded the archives such as github_releases_local_archives="/drive2/boostorg"
#   Within this dir are the subdirectories "beta, develop, master, release"
#
# Set the following environment vars:
# GH_USER: name of account on github
# GH_TOKEN: auth token for github

import sys
import os
import subprocess
import glob
import re
from ci_boost_common import utils

# Config

boost_versions=[ "1.63.0", "1.64.0", "1.65.0", "1.65.1", "1.66.0", "1.67.0", "1.68.0", "1.69.0", "1.70.0", "1.71.0", "1.72.0", "1.73.0", "1.74.0",
        "1.75.0", "1.76.0", "1.77.0", "1.78.0", "1.79.0", "1.80.0", "1.81.0", "1.82.0", "1.83.0", "1.84.0" ]

# Or for testing:
# boost_versions=[ "1.74.0", "1.75.0" ]

# Full path to local copy of boost repo
github_releases_folder="/opt/github/project"
os.chdir(github_releases_folder)

# Full path to local mirror of bintray. Within this dir are "beta, develop, master, release"
github_releases_local_archives="/drive2/boostorg"

gh_token = os.getenv('GH_TOKEN')
gh_user = os.getenv('GH_USER')

if not gh_token or not gh_user:
   print("Please set the environment variables GH_TOKEN and GH_USER.")
   sys.exit()

# gh has a concept called "base" repo. Pointing it to "origin".
utils.check_call('git', 'config', '--local', 'remote.origin.gh-resolved', 'base')

# allow git credentials to be read from $GH_USER and $GH_TOKEN env variables
credentialhelperscript='!f() { sleep 1; echo "username=${GH_USER}"; echo "password=${GH_TOKEN}"; }; f'
utils.check_call('git', 'config', 'credential.helper', '%s'%(credentialhelperscript))

# Create a release, if one is not present
list_of_releases=subprocess.check_output(['gh', 'release', 'list'], text=True)

print("Previous releases list_of_releases:")
print(list_of_releases)

for version in boost_versions:
    github_release_name="boost-" + version
    github_release_title="Boost " + version
    github_release_notes="Boost release"

    if github_release_name not in list_of_releases:
        utils.check_call('gh',
                        'release',
                        'create',
                        '%s'%(github_release_name),
                        '-t',
                        '%s'%(github_release_title),
                        '-n',
                        '%s'%(github_release_notes))
    else:
        print("Release %s already exists" % github_release_name)

    print("Uploading all files for %s" % github_release_name)

    for subfolder in ["source", "binaries"]:
        file_location=github_releases_local_archives + "/release/" + version + "/" + subfolder + "/*"
        list_of_files=glob.glob(file_location)
        list_of_files.sort()
        # print("List of files is ")
        # print(list_of_files)
        # exit()

        # upload files
        for filename in list_of_files:
            if not re.search(".*(html)$", filename, flags=0):
                utils.check_call('gh',
                    'release',
                    'upload',
                    '%s'%(github_release_name),
                    '%s'%(os.path.join(file_location,filename)),
                    '--clobber')
