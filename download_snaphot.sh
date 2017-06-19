#!/bin/bash

VERSION=$1
RC=$2
SNAPSHOT="boost_${VERSION}-snapshot"
REMOTE="https://dl.bintray.com/boostorg/master/${SNAPSHOT}"
LOCAL="boost_${VERSION}${RC}"

function dl_snapshot {
	echo "wget -O \"${LOCAL}.$1\" \"${REMOTE}.$1\""
	wget -O "${LOCAL}.$1" "${REMOTE}.$1"

	echo "wget -O \"${SNAPSHOT}.$1.json\" \"${REMOTE}.$1.json\""
	wget -O "${SNAPSHOT}.$1.json" "${REMOTE}.$1.json"

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
}

rm ${LOCAL}*
dl_snapshot 7z
dl_snapshot zip
dl_snapshot tar.bz2
dl_snapshot tar.gz
