#!/usr/bin/env python

# Copyright Sam Darwin 2021
#
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at
# http://www.boost.org/LICENSE_1_0.txt)


# Upload new official releases to github.
# The functionality should be merged with any existing official releases scripts.
#
# Use ci_boost_release.py instead for development snapshots.
#
# INSTRUCTIONS:
#
# Set values in Config section below.
#
# Set the following environment vars:
# GH_USER: name of account on github
# GH_TOKEN: auth token for github
#
# The directory structure will be as follows:
#
# ls -al
# .
# ..
# ghreleases/
# project/
# github_releases.py
# boost_1_76_0.tar.gz
# boost_1_76_0.tar.gz.json
# boost_1_76_0.tar.bz2
# boost_1_76_0.tar.gz.json
# boost_1_76_0.zip
# boost_1_76_0.zip.json
# boost_1_76_0.7z
# boost_1_76_0.7z.json
#
# The script assumes the release files such as boost_1_76_0.tar.gz have already been generated
# and are available in the current working directory.
# If publishing releases to boostorg/boost, the project/ directory should be a checked out copy of that repository.
# If publishing releases to boostorg/boost-releases, the ghreleases/ directory will be used to check out that repo.

import sys
import os
import subprocess
from ci_boost_common import utils

# Config

github_release_name="boost-1.76.0"
github_release_title="Boost 1.76.0"
github_release_notes="description here"
boost_package_name="boost_1_76_0-snapshot"

# The variable "github_releases_main_repo" determines if github releases will be hosted on the boost repository itself.
# It is assumed the main repo has been very recently checked out, and is located in github_releases_main_repo_local_directory.
github_releases_main_repo=False
github_releases_main_repo_local_directory="project"

# The next two variables are only used if github_releases_main_repo==False
github_releases_target_org="boostorg"
github_releases_target_repo="boost-releases"

# Running the script from the "basedir", where the packages are.
basedir = os.getcwd()

file_extensions=[".tar.gz",".tar.gz.json",".tar.bz2",".tar.bz2.json",".zip",".zip.json",".7z",".7z.json"]
filenames=[ boost_package_name+name for name in file_extensions ]

if github_releases_main_repo:
    github_releases_folder=os.path.join(basedir, github_releases_main_repo_local_directory)
else:
    github_releases_folder=os.path.join(basedir, "ghreleases")

gh_token = os.getenv('GH_TOKEN')
gh_user = os.getenv('GH_USER')

if not gh_token or not gh_user:
   print("Please set the environment variables GH_TOKEN and GH_USER.")
   sys.exit()

# Check out github releases target repo, if necessary
if not github_releases_main_repo:
    if os.path.isdir(github_releases_folder):
        os.chdir(github_releases_folder)
        utils.check_call('git', 'pull', 'https://github.com/%s/%s'%(github_releases_target_org, github_releases_target_repo))
        utils.check_call('git', 'checkout', 'master')
    else:
        utils.check_call('git',
            'clone', 'https://github.com/%s/%s'%(github_releases_target_org, github_releases_target_repo),
            '%s'%(github_releases_folder)
            )
        os.chdir(github_releases_folder)
        utils.check_call('git', 'pull', 'https://github.com/%s/%s'%(github_releases_target_org, github_releases_target_repo))
        utils.check_call('git', 'checkout', 'master')
elif github_releases_main_repo:
        os.chdir(github_releases_folder)
        # Error checking
        checkbranch=subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip()
        if checkbranch not in "master":
           print("An official release is usually done from the master branch. However, the branch is " + checkbranch)
           print("Please review this. Exiting.")
           sys.exit()

# gh has a concept called "base" repo. Pointing it to "origin".
utils.check_call('git', 'config', '--local', 'remote.origin.gh-resolved', 'base')

# allow git credentials to be read from $GH_USER and $GH_TOKEN env variables
credentialhelperscript='!f() { sleep 1; echo "username=${GH_USER}"; echo "password=${GH_TOKEN}"; }; f'
utils.check_call('git', 'config', 'credential.helper', '%s'%(credentialhelperscript))

# Create a release, if one is not present
list_of_releases=subprocess.check_output(['gh', 'release', 'list'])

if github_release_name not in list_of_releases:
    utils.check_call('gh',
                    'release',
                    'create',
                    '%s'%(github_release_name),
                    '-t',
                    '%s'%(github_release_title),
                    '-n',
                    '%s'%(github_release_notes))

# Update the tag
# When github_releases_main_repo is False, this may not be too important.
# If github_releases_main_repo is True, the git tag should match the release.
os.chdir(github_releases_folder)
utils.check_call('git',
        'tag',
        '-f',
        '%s'%(github_release_name))
utils.check_call('git',
        'push',
        '-f',
        'origin',
        '%s'%(github_release_name))

# upload the boost releases
for filename in filenames:
    utils.check_call('gh',
        'release',
        'upload',
        '%s'%(github_release_name),
        '%s'%(os.path.join(basedir,filename)),
        '--clobber')
