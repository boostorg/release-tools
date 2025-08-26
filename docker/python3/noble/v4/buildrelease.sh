#!/bin/bash

# Run this inside the container

set -ex

cd $HOME

boostbranch=develop
if [ ! -d project ]; then
    git clone https://github.com/boostorg/boost project
    cd project
    # "git checkout" can also checkout commits
    git checkout $boostbranch
    cd ..
fi

export CIRCLECI=true
export CIRCLE_BRANCH=develop
export CIRCLE_WORKING_DIRECTORY=~/project

wget "https://raw.githubusercontent.com/boostorg/release-tools/master/ci_boost_common.py" -P ${HOME}
wget "https://raw.githubusercontent.com/boostorg/release-tools/master/ci_boost_release.py" -P ${HOME}

python3 ${HOME}/ci_boost_release.py checkout_post
EOL=LF python3 ${HOME}/ci_boost_release.py test_override
