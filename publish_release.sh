#!/bin/bash
#
# publish_release.sh
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
# ./publish_release.sh 1_76_0
#
# Or a release candidate. Note the underscores.
#
# ./publish_release.sh 1_76_0 _rc1

VERSION=$1
VERSION_DOTTED=${VERSION//_/.}
RC=$2
SNAPSHOT="boost_${VERSION}-snapshot"
LOCAL="boost_${VERSION}${RC}"
REMOTE_SRC="main/master/${SNAPSHOT}"
REMOTE_DST="main/release/${VERSION_DOTTED}/source"
REMOTE_SRC_FULL="https://boostorg.jfrog.io/artifactory/${REMOTE_SRC}"

function dl_snapshot {
	echo "wget -q -O \"${LOCAL}.$1\" \"${REMOTE_SRC_FULL}.$1\""
	wget -q -O "${LOCAL}.$1" "${REMOTE_SRC_FULL}.$1"

	echo "wget -q -O \"${SNAPSHOT}.$1.json\" \"${REMOTE_SRC_FULL}.$1.json\""
	if wget -q -O "${SNAPSHOT}.$1.json" "${REMOTE_SRC_FULL}.$1.json";
	then
		SHA256=(`shasum -a 256 "${LOCAL}.$1"`)
		SHA256=${SHA256[0]}
		echo "{" > "${LOCAL}.$1.json"
		echo "\"sha256\":\"${SHA256}\"," >> "${LOCAL}.$1.json"
		echo "\"file\":\"${LOCAL}.$1\"," >> "${LOCAL}.$1.json"
		grep "commit" "${SNAPSHOT}.$1.json" >> "${LOCAL}.$1.json"
		echo -n "}" >> "${LOCAL}.$1.json"

		A=`grep sha256 "${SNAPSHOT}.$1.json"`
		B=`grep sha256 "${LOCAL}.$1.json"`
		echo "$A == $B"
		if [ "$A" != "$B" ] ; then
			echo "ERROR: Checksum failure for ${LOCAL}.$1.json"
			exit 1
		fi
	else
		echo "No json file for ${REMOTE_SRC_FULL}.$1"
	fi
}

function ul_snapshot {
	# "Upload snapshots"
	# To optimize bandwidth, copy them directly on artifactory rather than upload.
	echo "jfrog rt cp --flat=true ${REMOTE_SRC}.$1 ${REMOTE_DST}/${LOCAL}.$1"
	jfrog rt cp --flat=true ${REMOTE_SRC}.$1 ${REMOTE_DST}/${LOCAL}.$1

	# Upload the json files
	echo "jfrog rt upload ${LOCAL}.$1.json ${REMOTE_DST}/"
	jfrog rt upload ${LOCAL}.$1.json ${REMOTE_DST}/
}

rm ${LOCAL}*
dl_snapshot 7z
dl_snapshot zip
dl_snapshot tar.bz2
dl_snapshot tar.gz

ul_snapshot 7z
ul_snapshot zip
ul_snapshot tar.bz2
ul_snapshot tar.gz

