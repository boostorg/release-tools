#!/usr/bin/env -S python3 -u
#
# Downloads snapshots from artifactory, renames them, confirms the sha hash,
# and then uploads the files back to artifactory.
#
#
# Instructions
#
# - Install jfrog cli https://jfrog.com/getcli/
#
# - Run jfrog config add, to configure credentials. Example:
#
# jfrog config add
# Server ID: server1
# JFrog platform URL: https://boostorg.jfrog.io
# Access token (Leave blank for username and password/API key):
# User: _your_username_
# Password/API key: _your_password_
# Is the Artifactory reverse proxy configured to accept a client certificate? (y/n) [n]? n
# [Info] Encrypting password...
#
# GitHub Releases
#
# Set the following environment vars:
# GH_USER: name of account on github
# GH_TOKEN: auth token for github
#
# - Run the script. For example, to publish boost_1_76_0
#
# ./publish_release.py 1_76_0
#
# If you want to publish a beta, use the '-b' flag to specify which beta.
# If you want to publish a release candidate, use the '-r' flag to specify which RC.
#
# ./publish_release.py 1_76_0 -r 1       # publishes 1_76_0_rc1
# ./publish_release.py 1_76_0 -b 2       # publishes 1_76_0_b2
# ./publish_release.py 1_76_0 -b 4 -r 2  # publishes 1_76_0_b4_rc2

from optparse import OptionParser
import requests
import shutil
import urllib
import hashlib
import re, os, sys
import json
from pathlib import Path
import subprocess
import datetime

jfrogURL = "https://boostorg.jfrog.io/artifactory/"
boostRepository = "git@github.com:boostorg/boost.git"
boostRepositoryCacheDir = str(Path.home()) + "/.github/boostorg"
workspacedir = os.getcwd()


def fileHash(fileName):
    sha256_hash = hashlib.sha256()
    with open(fileName, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def genJSON(snapshotJSON, fileName, incomingSHA):
    with open(snapshotJSON, "r") as f:
        snap = json.load(f)
    newJSON = {}
    newJSON["commit"] = snap["commit"]
    newJSON["file"] = fileName
    if "created" in snap:
        newJSON["created"] = snap["created"]
    newJSON["sha256"] = incomingSHA
    if snap["sha256"] != incomingSHA:
        print("ERROR: Checksum failure for '%s'" % fileName)
        print("Recorded:	%s" % snap["sha256"])
        print("Calculated: %s" % incomingSHA)

    return newJSON


def debug_output(result):
    if result.stdout != "" and result.stdout != None:
        print(result.stdout.strip())
    if result.stderr != "" and result.stdout != None:
        print(result.stderr.strip())


# Copied from https://stackoverflow.com/questions/16694907/download-large-file-in-python-with-requests
def downloadAFile(url, destFile):
    with requests.get(url, stream=True) as r:
        with open(destFile, "wb") as f:
            shutil.copyfileobj(r.raw, f)


def downloadJFROGFiles(sourceRepo, sourceFileName, destFileName, suffix):
    # 	Download two files here:
    # 		boost_X_YY_ZZ-snapshot.Q      -> boost_X_YY_ZZ.Q
    # 		boost_X_YY_ZZ-snapshot.Q.json -> boost_X_YY_ZZ-snapshot.Q.json

    sourceFile = "%s%s" % (sourceFileName, suffix)
    destFile = "%s%s" % (destFileName, suffix)
    jsonFile = "%s.json" % sourceFile
    print("Downloading: %s to %s" % (sourceFile, destFile))
    print("Downloading: %s to %s" % (jsonFile, jsonFile))
    downloadAFile(jfrogURL + sourceRepo + sourceFile, destFile)
    downloadAFile(jfrogURL + sourceRepo + jsonFile, jsonFile)


def copyJFROGFile(sourceRepo, sourceFileName, destRepo, destFileName, suffix):
    # 	Copy a file from one place to another on JFROG, renaming it along the way
    print("Copying: %s%s to %s%s" % (sourceFileName, suffix, destFileName, suffix))
    # os.system(
    #     "jfrog rt cp --flat=true %s%s%s %s%s%s"
    #     % (sourceRepo, sourceFileName, suffix, destRepo, destFileName, suffix)
    # )
    result = subprocess.run(
        "jfrog rt cp --flat=true %s%s%s %s%s%s"
        % (sourceRepo, sourceFileName, suffix, destRepo, destFileName, suffix),
        check=True,
        shell=True,
        text=True,
    )
    if options.debug:
        debug_output(result)


def uploadJFROGFile(sourceFileName, destRepo):
    # 	Upload a file to JFROG
    print("Uploading: %s" % (sourceFileName))
    # os.system("jfrog rt upload %s %s" % (sourceFileName, destRepo))
    result = subprocess.run(
        "jfrog rt upload %s %s" % (sourceFileName, destRepo),
        check=True,
        shell=True,
        text=True,
    )
    if options.debug:
        debug_output(result)


def checkGithubPrerequisites():
    """Determine if the necessary github software is in place."""
    if not options.dryrun_github:
        global gh_token
        global gh_user
        gh_token = os.getenv("GH_TOKEN", None)
        gh_user = os.getenv("GH_USER", None)
        general_response_message = "Or if you're not planning to upload github releases, set the --dry-run-github flag."
        if not shutil.which("git"):
            print("Please install git before proceeding. %s" % general_response_message)
            print("Cannot continue. Exiting.")
            exit(1)
        if not shutil.which("gh"):
            print(
                "gh is not installed. Download it from their releases page https://github.com/cli/cli/releases. %s"
                % general_response_message
            )
            print("Cannot continue. Exiting.")
            exit(1)
        if not gh_token or not gh_user:
            print(
                "Please set the environment variables GH_TOKEN and GH_USER. %s"
                % general_response_message
            )
            print("Cannot continue. Exiting.")
            exit(1)


def updateBoostRepository():
    """Check out boostorg/boost. This function should be idempotent, either cloning or updating the local repository"""
    tmpOrigDir = os.getcwd()
    Path(boostRepositoryCacheDir).mkdir(parents=True, exist_ok=True)
    os.chdir(boostRepositoryCacheDir)
    if Path("boost").is_dir():
        os.chdir("boost")
        if options.progress:
            print("git", "checkout", "master")
        result = subprocess.run(
            ["git", "checkout", "master"], check=True, capture_output=True, text=True
        )
        if options.debug:
            debug_output(result)
        if options.progress:
            print("git", "pull")
        result = subprocess.run(
            ["git", "pull"], check=True, capture_output=True, text=True
        )
        if options.debug:
            debug_output(result)
    else:
        if options.progress:
            print("git", "clone", boostRepository)
        try:
            result = subprocess.run(
                ["git", "clone", boostRepository],
                check=True,
                capture_output=True,
                text=True,
            )
            if options.debug:
                debug_output(result)
        except:
            print("Notes: failed to clone git repo.")
            print("Using the SSH method git@github.com:owner/reponame.git")
            print(
                "Set up an SSH key in Github, and locally in ~/.ssh/id_rsa or run ssh-agent."
            )
            exit(1)
        os.chdir("boost")

    if options.progress:
        print("git", "submodule", "update", "--init", "--recursive")
    result = subprocess.run(
        ["git", "submodule", "update", "--init", "--recursive"],
        check=True,
        capture_output=True,
        text=True,
    )
    if options.debug:
        debug_output(result)

    # gh has a concept of a "default remote repository". Setting that.
    result = subprocess.run(
        ["git", "config", "--local", "remote.origin.gh-resolved", "base"],
        check=True,
        text=True,
    )
    if options.debug:
        debug_output(result)

    # done with function, return to original dir
    os.chdir(tmpOrigDir)


def gitTags():
    """Create and push git tags, necessary for github releases"""
    tmpOrigDir = os.getcwd()
    os.chdir(boostRepositoryCacheDir + "/boost")
    global github_release_tag

    if options.beta and options.rc:
        github_release_tag = "boost-%s.beta%d.rc%d" % (
            dottedVersion,
            options.beta,
            options.rc,
        )
    elif options.rc:
        github_release_tag = "boost-%s.rc%d" % (dottedVersion, options.rc)
    elif options.beta:
        github_release_tag = "boost-%s.beta%d" % (dottedVersion, options.beta)
    else:
        github_release_tag = "boost-%s" % (dottedVersion)

    # Since an updated boost repository is always required by gitTag(), running updateBoostRepository() again.
    updateBoostRepository()

    result = subprocess.check_output(
        ["git", "tag", "-l", github_release_tag], text=True
    )
    if result.strip() == github_release_tag:
        if options.progress:
            print("The tag already exists. In that case, not modifying any tags.")
    else:
        if options.no_tags:
            print(
                "The git tags are missing, however you have selected the option to skip tagging."
            )
            print("Please manually tag the repos before uploading github releases.")
            print("Cannot proceed. Exiting.")
            exit(1)
        else:
            # The main path - create tags and upload them
            if options.progress:
                print("Tagging main repo")
                print(datetime.datetime.now())
            result = subprocess.run(
                ["git", "tag", github_release_tag],
                check=True,
                capture_output=True,
                text=True,
            )
            if options.debug:
                debug_output(result)
            if options.progress:
                print("Tagging all submodules")
                print(datetime.datetime.now())
            subcommand = "git tag %s" % github_release_tag
            result = subprocess.run(
                ["git", "submodule", "foreach", subcommand],
                check=True,
                capture_output=True,
                text=True,
            )
            if options.debug:
                debug_output(result)
            if options.progress:
                print("Uploading tag to main repo")
                print(datetime.datetime.now())
            result = subprocess.run(
                ["git", "push", "origin", github_release_tag],
                check=True,
                capture_output=True,
                text=True,
            )
            if options.debug:
                debug_output(result)
            if options.progress:
                print(datetime.datetime.now())
                print("Uploading tag to all submodules.")
            subcommand = "git push origin %s" % github_release_tag
            # subprocess.run(
            #     ["git", "submodule", "foreach", subcommand],
            #     check=True,
            #     capture_output=True,
            #     text=True,
            # )

            # Faster parallel loop:
            result = subprocess.run(
                "for DIR in $(git submodule foreach -q sh -c pwd); do cd $DIR && %s & done"
                % subcommand,
                check=True,
                text=True,
                shell=True,
                capture_output=True,
            )
            if options.debug:
                debug_output(result)
            if options.progress:
                print(datetime.datetime.now())

    # done with function, return to original dir
    os.chdir(tmpOrigDir)


def createGithubRelease():
    """Create a github release"""
    tmpOrigDir = os.getcwd()
    os.chdir(boostRepositoryCacheDir + "/boost")

    list_of_releases = subprocess.check_output(["gh", "release", "list"], text=True)
    # print(list_of_releases)

    if not re.search(r"\s+" + re.escape(github_release_tag) + r"\s+", list_of_releases):
        if options.progress:
            print("Creating github release")
        result = subprocess.run(
            [
                "gh",
                "release",
                "create",
                "%s" % (github_release_tag),
                "-t",
                "%s" % (github_release_title),
                "-n",
                "%s" % (github_release_notes),
            ],
            check=True,
            text=True,
        )
        if options.debug:
            debug_output(result)
    else:
        if options.progress:
            print("Release already exists. Continuing.")

    # done with function, return to original dir
    os.chdir(tmpOrigDir)


def uploadGithubReleaseFiles():
    """Upload files to a github release"""
    tmpOrigDir = os.getcwd()
    os.chdir(boostRepositoryCacheDir + "/boost")
    if options.progress:
        print("Uploading files to GitHub Release")
    filenames = [(actualName + s) for s in suffixes]
    jsonfilenames = [(actualName + s + ".json") for s in suffixes]
    filenames = filenames + jsonfilenames
    for filename in filenames:
        if options.progress:
            print("Uploading %s" % filename)
        result = subprocess.run(
            [
                "gh",
                "release",
                "upload",
                "%s" % (github_release_tag),
                "%s" % (os.path.join(workspacedir, filename)),
                "--clobber",
            ],
            check=True,
            text=True,
        )
        if options.debug:
            debug_output(result)

    # done with function, return to original dir
    os.chdir(tmpOrigDir)


###########################################################################################################

usage = "usage: %prog [options] boost_version     # Example: %prog 1_35_0"
parser = OptionParser(usage=usage)
parser.add_option(
    "-b", "--beta", default=None, type="int", help="build a beta release", dest="beta"
)
parser.add_option(
    "-r",
    "--release-candidate",
    default=None,
    type="int",
    help="build a release candidate",
    dest="rc",
)
parser.add_option(
    "-p",
    "--progress",
    default=True,
    action="store_true",
    help="print progress information",
    dest="progress",
)
parser.add_option(
    "-d",
    "--debug",
    default=False,
    action="store_true",
    help="print debug information",
    dest="debug",
)

parser.add_option(
    "-n",
    "--dry-run",
    default=False,
    action="store_true",
    help="download files only. No upload to jfrog.",
    dest="dryrun",
)

parser.add_option(
    "--dry-run-github",
    default=False,
    action="store_true",
    help="don't upload to github releases",
    dest="dryrun_github",
)

parser.add_option(
    "--no-tags",
    default=False,
    action="store_true",
    help="don't apply git tags (In this case, you should have already pushed new git tags)",
    dest="no_tags",
)

parser.add_option(
    "--no-downloads",
    default=False,
    action="store_true",
    help="don't download files (You should have already downloaded files to the current directory. Mainly for testing.)",
    dest="no_downloads",
)

(options, args) = parser.parse_args()
if len(args) != 1:
    print("Too Many arguments")
    parser.print_help()
    exit(1)

# Run this early to catch any problems:
if not options.dryrun_github:
    checkGithubPrerequisites()

boostVersion = args[0]
dottedVersion = boostVersion.replace("_", ".")

if options.beta and options.rc:
    github_release_tag = "boost-%s.beta%d.rc%d" % (
        dottedVersion,
        options.beta,
        options.rc,
    )
    github_release_title = "Boost %s beta %d rc %d" % (
        dottedVersion,
        options.beta,
        options.rc,
    )
    github_release_notes = "Boost Beta, Release Candidate"
elif options.rc:
    github_release_tag = "boost-%s.rc%d" % (dottedVersion, options.rc)
    github_release_title = "Boost %s release candidate %d" % (dottedVersion, options.rc)
    github_release_notes = "Boost Release Candidate"
elif options.beta:
    github_release_tag = "boost-%s.beta%d" % (dottedVersion, options.beta)
    github_release_title = "Boost %s beta %d" % (dottedVersion, options.beta)
    github_release_notes = "Boost Beta"
else:
    github_release_tag = "boost-%s" % (dottedVersion)
    github_release_title = "Boost %s" % (dottedVersion)
    github_release_notes = "Boost Release"

sourceRepo = "main/master/"
if options.beta == None:
    actualName = "boost_%s" % boostVersion
    hostedArchiveName = "boost_%s" % boostVersion
    unzippedArchiveName = "boost_%s" % boostVersion
    destRepo = "main/release/%s/source/" % dottedVersion
else:
    actualName = "boost_%s_b%d" % (boostVersion, options.beta)
    hostedArchiveName = "boost_%s_beta%d" % (boostVersion, options.beta)
    unzippedArchiveName = "boost_%s" % boostVersion
    destRepo = "main/beta/%s.beta%d/source/" % (dottedVersion, options.beta)

if options.rc != None:
    actualName += "_rc%d" % options.rc
    # hostedArchiveName
    # unzippedArchiveName

if options.progress:
    print("Creating release files named '%s'" % actualName)
    if options.dryrun:
        print("## Dry run; not uploading files to JFrog")

suffixes = [".7z", ".zip", ".tar.bz2", ".tar.gz"]
snapshotName = "boost_%s-snapshot" % boostVersion

# Download the files
if options.no_downloads:
    if options.progress:
        print("Downloads turned off. Continuing.")
else:
    if options.progress:
        print("Downloading from: %s" % sourceRepo)
    for s in suffixes:
        downloadJFROGFiles(sourceRepo, snapshotName, actualName, s)

# Create the JSON files
for s in suffixes:
    sourceFileName = actualName + s
    jsonFileName = sourceFileName + ".json"
    jsonSnapshotName = snapshotName + s + ".json"
    if options.progress:
        print("Writing JSON to: %s" % jsonFileName)
    jsonData = genJSON(jsonSnapshotName, sourceFileName, fileHash(sourceFileName))
    with open(jsonFileName, "w", encoding="utf-8") as f:
        json.dump(jsonData, f, ensure_ascii=False, indent=0)

# Unzip an archive locally in ~/archives/tmp/ and move it to ~/archives/
archiveDir = str(Path.home()) + "/archives"
archiveDirTmp = str(Path.home()) + "/archives/tmp"
archiveName = actualName + ".tar.gz"
Path(archiveDir).mkdir(parents=True, exist_ok=True)
if os.path.isdir(archiveDirTmp):
    shutil.rmtree(archiveDirTmp)
Path(archiveDirTmp).mkdir(parents=True, exist_ok=True)
shutil.copyfile(archiveName, archiveDirTmp + "/" + archiveName)
origDir = os.getcwd()
os.chdir(archiveDirTmp)
# os.system("tar -xvf %s" % (archiveName))
result = subprocess.run(
    "tar -xvf %s" % (archiveName),
    check=True,
    shell=True,
    capture_output=True,
    text=True,
)
if options.debug:
    debug_output(result)
os.chdir(archiveDir)
if os.path.isdir(hostedArchiveName):
    shutil.rmtree(hostedArchiveName)
shutil.move(archiveDirTmp + "/" + unzippedArchiveName, hostedArchiveName)
os.chdir(origDir)

#################################################################
#
# Upload the files to JFROG
#
#################################################################

if options.progress:
    print("Uploading to: %s" % destRepo)
if not options.dryrun:
    for s in suffixes:
        copyJFROGFile(sourceRepo, snapshotName, destRepo, actualName, s)
        uploadJFROGFile(actualName + s + ".json", destRepo)

##################################################################
#
# Upload the files to S3
#
##################################################################

aws_profiles = {
    "production": "boost.org.v2",
    "stage": "stage.boost.org.v2",
    "revsys": "boost.revsys.dev",
    "cppal-dev": "boost.org-cppal-dev-v2",
}
aws_region = "us-east-2"

# Create rclone config file
rclonefilecontents = """[remote1]
type = s3
provider = AWS
env_auth = true
region = us-east-2
"""

os.makedirs(str(Path.home()) + "/.config/rclone", exist_ok=True)
with open(str(Path.home()) + "/.config/rclone/rclone.conf", "w") as f:
    f.writelines(rclonefilecontents)

archivePathLocal = str(Path.home()) + "/archives/" + hostedArchiveName + "/"
if not shutil.which("rclone"):
    print("rclone is not installed. Instructions:")
    print(
        "wget https://downloads.rclone.org/v1.64.0/rclone-v1.64.0-linux-amd64.deb; dpkg -i rclone-v1.64.0-linux-amd64.deb"
    )
elif not Path(str(Path.home()) + "/.aws/credentials").is_file():
    print("AWS credentials are missing. Please add the file ~/.aws/credentials .")
else:
    if not options.dryrun:
        for profile, bucket in aws_profiles.items():
            # AWS cli method:
            # archivePathRemote="s3://" + bucket + "/archives/" + hostedArchiveName + "/"
            # os.system("aws s3 cp --recursive --region %s --profile %s %s %s" % (aws_region, profile, archivePathLocal, archivePathRemote))

            # Rclone method:
            archivePathRemote = (
                "remote1:" + bucket + "/archives/" + hostedArchiveName + "/"
            )
            # os.system(
            #     "export AWS_PROFILE=%s;rclone sync --transfers 16 --checksum %s %s"
            #     % (profile, archivePathLocal, archivePathRemote)
            # )
            result = subprocess.run(
                "export AWS_PROFILE=%s;rclone sync --transfers 16 --checksum %s %s"
                % (profile, archivePathLocal, archivePathRemote),
                check=True,
                shell=True,
                text=True,
            )
            if options.debug:
                debug_output(result)

############################################################################
#
# Upload the files to GitHub Releases
#
############################################################################

if not options.dryrun_github:
    if options.progress:
        print("Processing GitHub Releases")
    checkGithubPrerequisites()
    updateBoostRepository()
    gitTags()
    createGithubRelease()
    uploadGithubReleaseFiles()
