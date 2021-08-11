#!/usr/bin/env python3
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

jfrogURL = "https://boostorg.jfrog.io/artifactory/"

def fileHash(fileName):
	sha256_hash = hashlib.sha256()
	with open(fileName,"rb") as f:
	# Read and update hash string value in blocks of 4K
		for byte_block in iter(lambda: f.read(4096),b""):
			sha256_hash.update(byte_block)
	return sha256_hash.hexdigest()


def genJSON(snapshotJSON, fileName, incomingSHA):
	with open(snapshotJSON,"r") as f:
		snap = json.load(f)
	newJSON = {}
	newJSON ['commit'] = snap['commit']
	newJSON ['file']   = fileName
	if 'created' in snap:
		newJSON ['created'] = snap['created']
	newJSON ['sha256'] = incomingSHA
	if snap ['sha256'] != incomingSHA:
		print ("ERROR: Checksum failure for '%s'" % fileName)
		print ("Recorded:	%s" % snap['sha256'])
		print ("Calculated: %s" % incomingSHA)

	return newJSON


# Copied from https://stackoverflow.com/questions/16694907/download-large-file-in-python-with-requests
def downloadAFile(url, destFile):
	with requests.get(url, stream=True) as r:
		with open(destFile, 'wb') as f:
			shutil.copyfileobj(r.raw, f)

def downloadJFROGFiles(sourceRepo, sourceFileName, destFileName, suffix):
#	Download two files here:
#		boost_X_YY_ZZ-snapshot.Q      -> boost_X_YY_ZZ.Q
#		boost_X_YY_ZZ-snapshot.Q.json -> boost_X_YY_ZZ-snapshot.Q.json

	sourceFile = "%s%s" % (sourceFileName, suffix)
	destFile   = "%s%s" % (destFileName, suffix)
	jsonFile   = "%s.json" % sourceFile
	print ("Downloading: %s to %s" % (sourceFile, destFile))
	print ("Downloading: %s to %s" % (jsonFile, jsonFile))
	downloadAFile(jfrogURL + sourceRepo + sourceFile, destFile)
	downloadAFile(jfrogURL + sourceRepo + jsonFile,   jsonFile)
	

def copyJFROGFile(sourceRepo, sourceFileName, destRepo, destFileName, suffix):
#	Copy a file from one place to another on JFROG, renaming it along the way
	print ("Copying: %s%s to %s%s" % (sourceFileName, suffix, destFileName, suffix))
	os.system("jfrog rt cp --flat=true %s%s%s %s%s%s" % (sourceRepo, sourceFileName, suffix, destRepo, destFileName, suffix))

def uploadJFROGFile(sourceFileName, destRepo):
#	Upload a file to JFROG
	print ("Uploading: %s" % (sourceFileName))
	os.system("jfrog rt upload %s %s" % (sourceFileName, destRepo))


##### 
parser = OptionParser()
parser.add_option("-b", "--beta",              default=None, type="int",  help="build a beta release", dest="beta")
parser.add_option("-r", "--release-candidate", default=None, type="int",  help="build a release candidate", dest="rc")
parser.add_option("-p", "--progress",   default=False, action="store_true",  help="print progress information", dest="progress")
parser.add_option("-n", "--dry-run",    default=False, action="store_true",  help="download files only", dest="dryrun")

(options, args) = parser.parse_args()
if len(args) != 1:
	print ("Too Many arguments")
	parser.print_help ()
	exit (1)
	
boostVersion = args[0]
dottedVersion = boostVersion.replace('_', '.')
sourceRepo = "main/master/"
if options.beta == None:
	actualName = "boost_%s" % boostVersion
	destRepo   = "main/release/%s/source/" % dottedVersion
else:
	actualName = "boost_%s_b%d" % (boostVersion, options.beta)
	destRepo   = "main/beta/%s.beta%d/source/" % (dottedVersion, options.beta)

if options.rc != None:
	actualName += "_rc%d" % options.rc

if options.progress:
	print ("Creating release files named '%s'" % actualName)
	if options.dryrun:
		print ("## Dry run; not uploading files to JFrog")
		
suffixes = [ ".7z", ".zip", ".tar.bz2", ".tar.gz" ]
snapshotName = "boost_%s-snapshot" % boostVersion

# Download the files
if options.progress:
	print ("Downloading from: %s" % sourceRepo)
for s in suffixes:
	downloadJFROGFiles (sourceRepo, snapshotName, actualName, s)

# Create the JSON files
for s in suffixes:
	sourceFileName   = actualName + s
	jsonFileName     = sourceFileName + '.json'
	jsonSnapshotName = snapshotName + s + '.json'
	if options.progress:
		print ("Writing JSON to: %s" % jsonFileName)
	jsonData = genJSON(jsonSnapshotName, sourceFileName, fileHash(sourceFileName))
	with open(jsonFileName, 'w', encoding='utf-8') as f:
		json.dump(jsonData, f, ensure_ascii=False, indent=0)

# Upload the files
if options.progress:
	print ("Uploading to: %s" % destRepo)
if not options.dryrun:
	for s in suffixes:
		copyJFROGFile (sourceRepo, snapshotName, destRepo, actualName, s)
		uploadJFROGFile (actualName + s + '.json', destRepo)
