#!/usr/bin/env -S python3 -u
#
# Downloads snapshots from artifactory, renames them, confirms the sha hash,
# and then uploads the files back to artifactory.
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
import pathlib
import time

# run: pip3 install python-dotenv
from dotenv import load_dotenv

jfrogURL = "https://boostorg.jfrog.io/artifactory/"
fastlyURL = "https://archives.boost.io/"
s3_archives_bucket = "boost-archives"
aws_profile = "production"
# git tag settings:
boost_repo_url = "git@github.com:boostorg/boost.git"
boost_branch = "master"

# webhook settings:
boost_websites = ["https://www.boost.org", "https://www.stage.boost.org"]

# defaults, used later
stagingPath2 = ""
checksum_succeeded = True


def fileHash(fileName):
    sha256_hash = hashlib.sha256()
    with open(fileName, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def genJSON(snapshotJSON, fileName, incomingSHA, nodocs=False):
    global checksum_succeeded
    with open(snapshotJSON, "r") as f:
        snap = json.load(f)
    newJSON = {}
    newJSON["commit"] = snap["commit"]
    newJSON["file"] = fileName
    if "created" in snap:
        newJSON["created"] = snap["created"]
    newJSON["sha256"] = incomingSHA
    if not nodocs and snap["sha256"] != incomingSHA:
        print("ERROR: Checksum failure for '%s'" % fileName)
        print("Recorded:	%s" % snap["sha256"])
        print("Calculated: %s" % incomingSHA)
        checksum_succeeded = False

    return newJSON


# Copied from https://stackoverflow.com/questions/16694907/download-large-file-in-python-with-requests
def downloadAFile(url, destFile):
    if os.path.exists(destFile) and options.skip_redownloading:
        print(f"{destFile} already present. Skipping the download.")
    else:
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


def downloadFASTLYFiles(sourceFileName, destFileName, suffix):
    #   Download two files here:
    #           boost_X_YY_ZZ-snapshot.Q      -> boost_X_YY_ZZ.Q
    #           boost_X_YY_ZZ-snapshot.Q.json -> boost_X_YY_ZZ-snapshot.Q.json

    sourceFile = "%s%s" % (sourceFileName, suffix)
    destFile = "%s%s" % (destFileName, suffix)
    jsonFile = "%s.json" % sourceFile
    print("Downloading: %s to %s" % (sourceFile, destFile))
    downloadAFile(fastlyURL + "master/" + sourceFile, destFile)
    print("Downloading: %s to %s" % (jsonFile, jsonFile))
    downloadAFile(fastlyURL + "master/" + jsonFile, jsonFile)


def copyJFROGFile(sourceRepo, sourceFileName, destRepo, destFileName, suffix):
    # 	Copy a file from one place to another on JFROG, renaming it along the way
    print("Copying: %s%s to %s%s" % (sourceFileName, suffix, destFileName, suffix))
    os.system(
        "jfrog rt cp --flat=true %s%s%s %s%s%s"
        % (sourceRepo, sourceFileName, suffix, destRepo, destFileName, suffix)
    )


def uploadJFROGFile(sourceFileName, destRepo):
    # 	Upload a file to JFROG
    print("Uploading: %s to JFROG" % (sourceFileName))
    os.system("jfrog rt upload %s %s" % (sourceFileName, destRepo))


def uploadS3File(sourceFileName, destRepo):
    # 	Upload an archive to S3
    print("Uploading: %s to S3" % (sourceFileName))
    archivePathLocal = sourceFileName
    archivePathRemote = re.sub("^main/", "", destRepo)
    archivePathRemote = "remote1:" + s3_archives_bucket + "/" + archivePathRemote
    result = subprocess.run(
        "export AWS_PROFILE=%s;rclone -v --s3-no-check-bucket copy --checksum %s %s"
        % (aws_profile, archivePathLocal, archivePathRemote),
        check=True,
        shell=True,
        text=True,
    )
    if options.progress:
        print(result)


def copyStagingS3():
    global stagingPath2
    if options.beta == None:
        stagingPath1 = "staging/%s/binaries/" % (dottedVersion)
        stagingPath2 = "release/%s/binaries/" % (dottedVersion)
    else:
        stagingPath1 = "staging/%s.beta%d/binaries/" % (dottedVersion, options.beta)
        stagingPath2 = "beta/%s.beta%d/binaries/" % (dottedVersion, options.beta)

    print("Staging copy: %s to %s" % (stagingPath1, stagingPath2))
    archivePath1 = "remote1:" + s3_archives_bucket + "/" + stagingPath1
    archivePath2 = "remote1:" + s3_archives_bucket + "/" + stagingPath2
    result = subprocess.run(
        "export AWS_PROFILE=%s;rclone -v --s3-no-check-bucket copy --checksum %s %s"
        % (aws_profile, archivePath1, archivePath2),
        check=True,
        shell=True,
        text=True,
    )
    if options.progress:
        print(result)


def git_tags():
    if options.rc != None or not git_tag:
        print("This is a release candidate. Not tagging.")
        # Is this right? There are currently no release candidate tags.
        return

    boost_repo_parent_dir = str(Path.home()) + "/github/release-tools-cache"
    Path(boost_repo_parent_dir).mkdir(parents=True, exist_ok=True)
    origDir = os.getcwd()
    os.chdir(boost_repo_parent_dir)

    if not os.path.isdir("boost"):
        result = subprocess.run(
            f"git clone -b {boost_branch} {boost_repo_url}",
            shell=True,
            text=True,
        )
        if result.returncode != 0:
            print("git checkout failed")
            print(result)
            exit(1)
    os.chdir("boost")
    print("checking branch")
    result = subprocess.run(
        f" git rev-parse --abbrev-ref HEAD", capture_output=True, shell=True, text=True
    )
    if not boost_branch in result.stdout:
        print("branch check failed")
        print(result)
        exit(1)
    print("checking remote")
    result = subprocess.run(
        f"git remote -v | grep origin", capture_output=True, shell=True, text=True
    )
    if not boost_repo_url in result.stdout:
        print("git remote check failed")
        print(result)
        exit(1)
    print("git pull")
    result = subprocess.run(f"git pull", shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print("git pull failed")
        print(result)
        exit(1)
    print("git submodule update --init --recursive  --checkout")
    result = subprocess.run(
        "git submodule update --init --recursive --checkout", shell=True, text=True
    )
    if result.returncode != 0:
        print("git submodule update failed")
        print(result)
        exit(1)
    print(f"git tag {git_tag}")
    result = subprocess.run(f"git tag {git_tag}", shell=True, text=True)
    if result.returncode != 0:
        print("git tag failed")
        print(result)
        exit(1)
    print(f"git submodule foreach 'git tag {git_tag}'")
    result = subprocess.run(
        f"git submodule foreach 'git tag {git_tag}'", shell=True, text=True
    )
    if result.returncode != 0:
        print("git tag submodules failed")
        print(result)
        exit(1)

    print(
        f"The git submodules have been tagged in {boost_repo_parent_dir}/boost. That should be fine, but you may review. The next step will be 'git push'."
    )
    answer = input("Do you want to continue: [y/n]")
    if not answer or answer[0].lower() != "y":
        print("Exiting.")
        exit(1)
    print(f"git push origin {git_tag}")
    result = subprocess.run(f"git push origin {git_tag}", shell=True, text=True)
    if result.returncode != 0:
        print("git push failed")
        print(result)
        exit(1)

    # Submodules in series. Slower.
    # print(f"git submodule foreach 'git push origin {git_tag}'")
    # result = subprocess.run(
    #     f"git submodule foreach 'git push origin {git_tag}'", shell=True, text=True
    # )

    # Submodules in a parallel loop. Faster.
    print(
        f"Running the equivalent of the following in a bash loop: git submodule foreach 'git push origin {git_tag}'"
    )
    subcommand = "git push origin %s" % git_tag
    result = subprocess.run(
        "for DIR in $(git submodule foreach -q sh -c pwd); do cd $DIR && %s & done"
        % subcommand,
        text=True,
        shell=True,
    )
    if result.returncode != 0:
        print("git push submodules failed")
        print(result)
        exit(1)

    # function complete
    os.chdir(origDir)


def preflight():
    load_dotenv()

    print(
        "Testing /etc/mime.types. The file should exist and contain hpp, but please ensure it's a full copy from Linux."
    )

    with open("/etc/mime.types") as myfile:
        if "hpp" in myfile.read():
            print("/etc/mime.types ok")
        else:
            print("/etc/mime.types check failed")
            exit(1)

    print("Searching for required executables.")
    required_executables = [
        "rclone",
        "curl",
        "7z",
        "zip",
        "gzip",
        "bzip2",
        "unzip",
        "tar",
        "pigz",
        "lbzip2",
        "time",
    ]
    for required_executable in required_executables:
        if not shutil.which(required_executable):
            print(f"{required_executable} is not installed. It may be needed later.")
            answer = input("Do you want to continue anyway: [y/n]")
            if not answer or answer[0].lower() != "y":
                print("Exiting.")
                exit(1)

    print("Test ssh to brorigin servers")

    SSH_USER = os.getenv("SSH_USER", "mclow")
    for origin in ["brorigin1.cpp.al", "brorigin2.cpp.al"]:
        result = subprocess.run(
            f'ssh {SSH_USER}@{origin} "echo test > test10.txt"',
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print("SSH FAILED")
            print(
                "Preflight verification of SSH to the CDN origin servers failed. Check your SSH keys, and set SSH_USER=_username_ in an .env file in the same directory as publish_release.py. The best way to debug is manually SSHing to brorigin1.cpp.al and brorigin2.cpp.al"
            )
            print(result)
            answer = input("Do you want to continue anyway: [y/n]")
            if not answer or answer[0].lower() != "y":
                print("Exiting.")
                exit(1)

    # github verification:
    print("Test github connection")

    result = subprocess.run(
        f"ssh -T git@github.com",
        shell=True,
        capture_output=True,
        text=True,
    )
    if not "successfully authenticated" in result.stderr:
        print("GITHUB TEST FAILED")
        print(
            "Preflight test of your connection to github failed. This command was run: 'ssh -T git@github.com' You should configure ~/.ssh/config with:\nHost github.com\n    User git\n    Hostname github.com\n    PreferredAuthentications publickey\n    IdentityFile /home/__path__to__file__"
        )
        print(result)
        answer = input("Do you want to continue anyway: [y/n]")
        if not answer or answer[0].lower() != "y":
            print("Exiting.")
            exit(1)

    # webhook verification:
    for boost_website in boost_websites:
        print(f"Checking admin login to {boost_website}")
        WEB_USER = os.getenv("WEB_USER", "marshall@idio.com")
        WEB_PASSWORD = os.getenv("WEB_PASSWORD", "qqq")
        WEBSITE_URL = boost_website
        BASE_ADMIN = f"{WEBSITE_URL}/admin/"
        LOGIN = f"{BASE_ADMIN}login/"

        session = requests.session()
        # do a request just to get a csrftoken
        response = session.get(LOGIN)
        response.raise_for_status()
        response = session.post(
            LOGIN,
            data={
                "csrfmiddlewaretoken": session.cookies["csrftoken"],
                "username": WEB_USER,
                "password": WEB_PASSWORD,
            },
        )
        response.raise_for_status()
        if "errornote" in response.text:
            print(
                f"An 'errornote' was found in the attempt to log into {boost_website} with your WEB_USER and WEB_PASSWORD. Review those values in the .env file, and try manually logging into the admin panel"
            )
            answer = input("Do you want to continue anyway: [y/n]")
            if not answer or answer[0].lower() != "y":
                print("Exiting.")
                exit(1)


def import_new_releases():
    print(
        "\nThe last step is to trigger a version import on boost.io. This can also be done by visiting https://www.boost.io/admin/versions/version/ and clicking 'Import New Releases' for betas, or 'Do It All' for a full release. publish_release.py will remotely contact that webpage with a GET request.\n"
    )
    print("Waiting 2 minutes for the CDN to update, before proceeding.\n")
    time.sleep(120)

    for s in suffixes:
        for appended in ["", ".json"]:
            archiveFilename = actualName + s + appended
            archivePathRemote = re.sub("^main/", "", destRepo)
            url = f"{fastlyURL}{archivePathRemote}{archiveFilename}"

            result = subprocess.run(
                f"curl --output /dev/null --silent --head --fail {url}",
                capture_output=True,
                shell=True,
                text=True,
            )

            if result.returncode != 0:
                print(
                    f"\n{archiveFilename} is not present on the CDN, when it was expected. Check all the release files are available for download, and then manually log into the website to import releases. Exiting.\n"
                )
                print(result)
                exit(1)
            else:
                print(
                    "Expected archive file is present. See debug output below. continuing."
                )
                print(result)

    for boost_website in boost_websites:
        WEB_USER = os.getenv("WEB_USER", "marshall@idio.com")
        WEB_PASSWORD = os.getenv("WEB_PASSWORD", "qqq")
        BASE_ADMIN = f"{boost_website}/admin/"
        LOGIN = f"{BASE_ADMIN}login/"
        if options.beta == None and options.rc == None:
            # Standard releases
            NEW_RELEASE = f"{BASE_ADMIN}versions/version/new_versions/"
            # "release_tasks" were more extensive. May be deprecated.
            # NEW_RELEASE = f"{BASE_ADMIN}versions/version/release_tasks/"
        elif options.rc == None:
            # Betas
            NEW_RELEASE = f"{BASE_ADMIN}versions/version/new_versions/"
        else:
            NEW_RELEASE = ""

        session = requests.session()
        # do a request just to get a csrftoken
        response = session.get(LOGIN)
        response.raise_for_status()
        response = session.post(
            LOGIN,
            data={
                "csrfmiddlewaretoken": session.cookies["csrftoken"],
                "username": WEB_USER,
                "password": WEB_PASSWORD,
            },
        )
        response.raise_for_status()
        if NEW_RELEASE != "":
            print(f"Contacting {NEW_RELEASE}")
            response = session.get(NEW_RELEASE)
            response.raise_for_status()
        else:
            print("Not contacting webhook")

    # End of function import_new_releases


#####
usage = "usage: %prog [options] boost_version     # Example: %prog 1_85_0"
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
    default=False,
    action="store_true",
    help="print progress information",
    dest="progress",
)

parser.add_option(
    "-g",
    "--git-tag",
    default=False,
    action="store_true",
    help="tag the release in git/github",
    dest="git_tagging",
)


# The main 'dryrun' setting now applies to the following topics:
# archive uploads to s3
# files uploads to s3 for the website
# informing the CDN servers about the uploads
# also, if set, it will prevent JFrog uploads
parser.add_option(
    "-n",
    "--dry-run",
    default=False,
    action="store_true",
    help="download files only",
    dest="dryrun",
)
# The more specific 'dryrun_jfrog' setting does not affect
# most of the above 'dryrun' topics, and only indicates if files
# will be uploaded to JFrog or not. Set this to default=True as soon as
# JFrog goes offline.
parser.add_option(
    "--dry-run-jfrog",
    default=True,
    action="store_true",
    help="don't upload release archives to JFrog",
    dest="dryrun_jfrog",
)

parser.add_option(
    "--skip-nodocs",
    default=False,
    action="store_true",
    help="skip nodocs archives",
    dest="skip_nodocs",
)

parser.add_option(
    "--skip-redownloading",
    default=False,
    action="store_true",
    help="skip redownloading archives during tests",
    dest="skip_redownloading",
)

# Usually staging/ will be published.
# This setting overrides a main 'dryrun'.
parser.add_option(
    "--force-staging",
    default=False,
    action="store_true",
    help="publish staging/ files",
    dest="force_staging",
)

# Dryrun setting specific to staging/
parser.add_option(
    "--dry-run-staging",
    default=False,
    action="store_true",
    help="do not publish staging/ files",
    dest="dryrun_staging",
)

(options, args) = parser.parse_args()
if len(args) != 1:
    print("Too Many arguments")
    parser.print_help()
    exit(1)

preflight()

boostVersion = args[0]
dottedVersion = boostVersion.replace("_", ".")
sourceRepo = "main/master/"
if options.beta == None:
    # Standard releases
    actualName = "boost_%s" % boostVersion
    hostedArchiveName = "boost_%s" % boostVersion
    unzippedArchiveName = "boost_%s" % boostVersion
    destRepo = "main/release/%s/source/" % dottedVersion
    destRepoNoDocs = "main/release/%s/source-nodocs/" % dottedVersion
    git_tag = f"boost-{dottedVersion}"
else:
    # Beta releases
    actualName = "boost_%s_b%d" % (boostVersion, options.beta)
    hostedArchiveName = "boost_%s_beta%d" % (boostVersion, options.beta)
    unzippedArchiveName = "boost_%s" % boostVersion
    destRepo = "main/beta/%s.beta%d/source/" % (dottedVersion, options.beta)
    destRepoNoDocs = "main/beta/%s.beta%d/source-nodocs/" % (
        dottedVersion,
        options.beta,
    )
    git_tag = f"boost-{dottedVersion}.beta{options.beta}"

if options.rc != None:
    actualName += "_rc%d" % options.rc
    # hostedArchiveName
    # unzippedArchiveName
    git_tag = f"{git_tag}.rc{options.rc}"
    # or, does an rc get tagged?
    git_tag = ""

if options.git_tagging:
    git_tags()
else:
    print(
        "You did not run this script with the --git-tag option. Please be sure you have already tagged the release. In the future publish-release.py should switch --git-tag to --skip-git-tag and enable tagging by default."
    )
    answer = input("Do you want to continue anyway: [y/n]")
    if not answer or answer[0].lower() != "y":
        print("Exiting.")
        exit(1)

if options.progress:
    print("Creating release files named '%s'" % actualName)
    if options.dryrun:
        print("## Dry run; not uploading files to s3://boost-archives/")

suffixes = [".7z", ".zip", ".tar.bz2", ".tar.gz"]
snapshotName = "boost_%s-snapshot" % boostVersion

# Download the files
if options.progress:
    print("Downloading from: %s" % sourceRepo)
for s in suffixes:
    # downloadJFROGFiles(sourceRepo, snapshotName, actualName, s)
    downloadFASTLYFiles(snapshotName, actualName, s)

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

if not checksum_succeeded:
    exit(1)

print("Extracting one archive locally in ~/archives/")
print("This is used for the web upload later.")
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
os.system("tar -xf %s" % (archiveName))
os.chdir(archiveDir)
if os.path.isdir(hostedArchiveName):
    shutil.rmtree(hostedArchiveName)
shutil.move(archiveDirTmp + "/" + unzippedArchiveName, hostedArchiveName)
os.chdir(origDir)

# Generate nodocs versions
if not options.skip_nodocs:
    print("Processing nodocs")
    origDir = os.getcwd()
    # [".7z", ".zip", ".tar.bz2", ".tar.gz"]
    unzip_method = {}
    unzip_method[".7z"] = "7z x"
    unzip_method[".zip"] = "unzip -q"
    unzip_method[".tar.bz2"] = "tar -xf"
    unzip_method[".tar.gz"] = "tar -xf"
    zip_method = {}
    zip_method[".7z"] = "7z a -bd -mx=7 -mmt8 -ms=on"
    zip_method[".zip"] = "zip -qr -9"
    # zip_method[".tar.bz2"] = "tar -jcf"
    zip_method[".tar.bz2"] = "tar -cf"
    # zip_method[".tar.gz"] = "tar -zcf"
    zip_method[".tar.gz"] = "tar -cf"
    zip_extra_flags = {}
    zip_extra_flags[".7z"] = ""
    zip_extra_flags[".zip"] = ""
    zip_extra_flags[".tar.bz2"] = "--use-compress-program=lbzip2"
    zip_extra_flags[".tar.gz"] = "--use-compress-program=pigz"

    for s in suffixes:
        os.chdir(origDir)
        archiveName = actualName + s
        archiveDirTmp = str(Path.home()) + f"/archives-nodocs/{s}"
        if os.path.isdir(archiveDirTmp):
            shutil.rmtree(archiveDirTmp)
        Path(archiveDirTmp).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(archiveName, archiveDirTmp + "/" + archiveName)
        os.chdir(archiveDirTmp)
        extraction_command = unzip_method[s]
        print(f"Extracting {archiveName}")
        # os.system(f"{extraction_command} {archiveName}")
        result = subprocess.run(
            f"time -p {extraction_command} {archiveName}",
            shell=True,
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        print(result.stderr)
        os.chdir(f"boost_{boostVersion}")
        print(f"Removing doc/ directories")
        os.system("rm -rf libs/*/doc libs/numeric/*/doc tools/*/doc doc/")
        os.chdir("../")
        if os.path.exists("../" + archiveName):
            print(f"Removing {archiveName}")
            os.remove("../" + archiveName)
        compression_method = zip_method[s]
        extra_flags = zip_extra_flags[s]
        print(f"Compressing {archiveName}")
        # os.system(f"{compression_method} ../{archiveName} boost_{boostVersion}")
        result = subprocess.run(
            f"time -p {compression_method} ../{archiveName} boost_{boostVersion} {extra_flags}",
            shell=True,
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        print(result.stderr)
        os.chdir("../")

        # Create the JSON files
        sourceFileName = actualName + s
        jsonFileName = sourceFileName + ".json"
        jsonSnapshotName = origDir + "/" + snapshotName + s + ".json"
        if options.progress:
            print("Writing JSON to: %s" % jsonFileName)
        jsonData = genJSON(
            jsonSnapshotName, sourceFileName, fileHash(sourceFileName), nodocs=True
        )
        with open(jsonFileName, "w", encoding="utf-8") as f:
            json.dump(jsonData, f, ensure_ascii=False, indent=0)

        os.chdir(origDir)


# Upload the files to JFROG
if options.progress:
    print("Uploading to: %s" % destRepo)
if not options.dryrun_jfrog and not options.dryrun:
    for s in suffixes:
        copyJFROGFile(sourceRepo, snapshotName, destRepo, actualName, s)
        uploadJFROGFile(actualName + s + ".json", destRepo)

##############################################################
#
# Upload extracted files to S3 for the website docs
#
##############################################################

aws_profiles = {
    "production": "boost.org.v2",
    "stage": "stage.boost.org.v2",
    "cppal-dev": "boost.org-cppal-dev-v2",
}
# before: "revsys": "boost.revsys.dev",

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
        "wget https://downloads.rclone.org/rclone-current-linux-amd64.deb; dpkg -i rclone-current-linux-amd64.deb"
    )
elif not Path(str(Path.home()) + "/.aws/credentials").is_file():
    print("AWS credentials are missing. Please add the file ~/.aws/credentials .")
else:
    if not options.dryrun and options.rc == None:
        for profile, bucket in aws_profiles.items():
            # AWS cli method:
            # archivePathRemote="s3://" + bucket + "/archives/" + hostedArchiveName + "/"
            # os.system("aws s3 cp --recursive --region %s --profile %s %s %s" % (aws_region, profile, archivePathLocal, archivePathRemote))

            # Rclone method:
            archivePathRemote = (
                "remote1:" + bucket + "/archives/" + hostedArchiveName + "/"
            )
            os.system(
                "export AWS_PROFILE=%s;rclone sync --transfers 16 --checksum %s %s"
                % (profile, archivePathLocal, archivePathRemote)
            )

# Upload archives to S3
if not options.dryrun:
    for s in suffixes:
        uploadS3File(actualName + s, destRepo)
        uploadS3File(actualName + s + ".json", destRepo)
    if not options.skip_nodocs:
        for s in suffixes:
            uploadS3File(
                str(Path.home()) + "/archives-nodocs/" + actualName + s, destRepoNoDocs
            )
            uploadS3File(
                str(Path.home()) + "/archives-nodocs/" + actualName + s + ".json",
                destRepoNoDocs,
            )

# Publish Windows .exe files from their location in staging/
if options.force_staging or (not options.dryrun and not options.dryrun_staging):
    copyStagingS3()

###############################################################################
#
# Inform CDN origins about uploaded files
#
###############################################################################

# The CDN origins are set to update on a slow schedule, once per day.
# To refresh them more quickly, upload a text file with information.
#

if not options.dryrun:
    load_dotenv()
    SSH_USER = os.getenv("SSH_USER", "mclow")

    list_of_uploaded_files = []
    for s in suffixes:
        list_of_uploaded_files.append(destRepo + actualName + s)
        list_of_uploaded_files.append(destRepo + actualName + s + ".json")

    if not options.skip_nodocs:
        for s in suffixes:
            list_of_uploaded_files.append(destRepoNoDocs + actualName + s)
            list_of_uploaded_files.append(destRepoNoDocs + actualName + s + ".json")

    if stagingPath2:
        list_of_uploaded_files.append(stagingPath2)

    source_file_list = "/tmp/boostarchivesinfo/filelist.txt"
    source_file_list_dir = os.path.dirname(source_file_list)

    # create dir
    Path(source_file_list_dir).mkdir(mode=0o777, parents=True, exist_ok=True)

    # if source_file_list existed previously, remove it
    if os.path.isfile(source_file_list):
        pathlib.Path(source_file_list).unlink()

    # populate source_file_list
    with open(source_file_list, "w") as f:
        for file in list_of_uploaded_files:
            f.write(file)
            f.write("\n")

    for origin in ["brorigin1.cpp.al", "brorigin2.cpp.al"]:
        result = subprocess.run(
            f'ssh {SSH_USER}@{origin} "mkdir -p {source_file_list_dir}; chmod 777 {source_file_list_dir} || true"',
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print("SSH FAILED")
            print(result)

        result = subprocess.run(
            f"scp -p {source_file_list} {SSH_USER}@{origin}:{source_file_list}",
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print("SSH FAILED")
            print(result)

if not options.dryrun:
    import_new_releases()
