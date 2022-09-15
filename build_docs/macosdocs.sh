#!/bin/bash

# Copyright 2022 Sam Darwin
#
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at http://boost.org/LICENSE_1_0.txt)

set -e

scriptname="macosdocs.sh"

# set defaults:
boostrelease=""

# git and getopt are required. If they are not installed, moving that part of the installation process
# to an earlier part of the script:
if ! command -v brew &> /dev/null
then
    echo "Installing brew. Check the instructions that are shown."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

if ! command -v git &> /dev/null
then
    echo "Installing git"
    brew install git
fi

# check apple silicon.
if ! command -v /usr/local/opt/gnu-getopt/bin/getopt &> /dev/null
then
    echo "Installing gnu-getopt"
    brew install gnu-getopt
fi
export PATH="/usr/local/opt/gnu-getopt/bin:$PATH"

# READ IN COMMAND-LINE OPTIONS

TEMP=`/usr/local/opt/gnu-getopt/bin/getopt -o t:,h::,q:: --long type:,help::,skip-boost::,skip-packages::,quick::,boostrelease:: -- "$@"`
eval set -- "$TEMP"

# extract options and their arguments into variables.
while true ; do
    case "$1" in
        -h|--help)
            helpmessage="""
usage: $scriptname [-h] [--type TYPE] [path_to_library]

Builds library documentation.

optional arguments:
  -h, --help            Show this help message and exit
  -t, --type TYPE       The \"type\" of build. Defaults to \"main\" which installs all standard boost prerequisites.
                        Another option is \"cppal\" which installs the prerequisites used by boostorg/json and a few other similar libraries.
                        More \"types\" can be added in the future if your library needs a specific set of packages installed.
                        The type is usually auto-detected and doesn't need to be specified.
  --skip-boost          Skip downloading boostorg/boost and building b2 if you are certain those steps have already been done.
  --skip-packages       Skip installing all packages (pip, gem, apt, etc.) if you are certain that has already been done.
  -q, --quick           Equivalent to setting both --skip-boost and --skip-packages. If not sure, then don't skip these steps.
  --boostrelease        Add the target //boostrelease to the doc build. This target is used when building production releases.
standard arguments:
  path_to_library       Where the library is located. Defaults to current working directory.
"""

            echo ""
            echo "$helpmessage" ;
            echo ""
            exit 0
            ;;
        -t|--type)
            case "$2" in
                "") typeoption="" ; shift 2 ;;
                 *) typeoption=$2 ; shift 2 ;;
            esac ;;
        --skip-boost)
            skipboostoption="yes" ; shift 2 ;;
        --skip-packages)
            skippackagesoption="yes" ; shift 2 ;;
        -q|--quick)
            skipboostoption="yes" ; skippackagesoption="yes" ; shift 2 ;;
        --boostrelease)
            boostrelease="//boostrelease" ; shift 2 ;;
        --) shift ; break ;;
        *) echo "Internal error!" ; exit 1 ;;
    esac
done

# git and getopt are required. In the unlikely case it's not yet installed, moving that part of the package install process
# here to an earlier part of the script:

if [ -n "$1" ]; then
    echo "Library path set to $1. Changing to that directory."
    cd $1
else
    workingdir=$(pwd)
    echo "Using current working directory ${workingdir}."
fi

# DETERMINE REPOSITORY

export REPONAME=$(basename -s .git `git config --get remote.origin.url` 2> /dev/null || echo "empty")
export BOOST_SRC_FOLDER=$(git rev-parse --show-toplevel 2> /dev/null || echo "nofolder")

if [ "${REPONAME}" = "empty" -o "${REPONAME}" = "release-tools" ]; then
    echo -e "\nSet the path_to_library as the first command-line argument:\n\n$scriptname _path_to_library_\n\nOr change the working directory to that first.\n"
    exit 1
else
    echo "Reponame is ${REPONAME}."
fi

# CHECK IF RUNNING IN BOOST-ROOT

# this case applies to boostorg/more
PARENTNAME=$(basename -s .git `git --git-dir ${BOOST_SRC_FOLDER}/../.git config --get remote.origin.url` 2> /dev/null || echo "not_found")
if [ -n "${PARENTNAME}" -a "${PARENTNAME}" = "boost" ]; then
    echo "Starting out inside boost-root."
    BOOSTROOTLIBRARY="yes"
    BOOSTROOTRELPATH=".."
else
    # most libraries
    PARENTNAME=$(basename -s .git `git --git-dir ${BOOST_SRC_FOLDER}/../../.git config --get remote.origin.url` 2> /dev/null || echo "not_found")
    if [ -n "${PARENTNAME}" -a "${PARENTNAME}" = "boost" ]; then
        echo "Starting out inside boost-root."
        BOOSTROOTLIBRARY="yes"
        BOOSTROOTRELPATH="../.."
    else
        # numerics
        PARENTNAME=$(basename -s .git `git --git-dir ${BOOST_SRC_FOLDER}/../../../.git config --get remote.origin.url` 2> /dev/null || echo "not_found")
        if [ -n "${PARENTNAME}" -a "${PARENTNAME}" = "boost" ]; then
            echo "Starting out inside boost-root."
            BOOSTROOTLIBRARY="yes"
            BOOSTROOTRELPATH="../../.."
        else
            echo "Not starting out inside boost-root."
            BOOSTROOTLIBRARY="no"
        fi
    fi
fi

# DECIDE THE TYPE

alltypes="main cppal"
cppaltypes="json beast url http_proto socks_proto zlib"

if [ -z "$typeoption" ]; then
    if [[ " $cppaltypes " =~ .*\ $REPONAME\ .* ]]; then
        typeoption="cppal"
    else
        typeoption="main"
    fi
fi

echo "Build type is ${typeoption}."

if [[ !  " $alltypes " =~ .*\ $typeoption\ .* ]]; then
    echo "Allowed types are currently 'main' and 'cppal'. Not $typeoption. Please choose a different option. Exiting."
    exit 1
fi

if git rev-parse --abbrev-ref HEAD | grep master ; then BOOST_BRANCH=master ; else BOOST_BRANCH=develop ; fi

echo '==================================> INSTALL'

# graphviz package added for historical reasons, might not be used.

if [ "$skippackagesoption" != "yes" ]; then

    brew install doxygen
    brew install wget
    brew tap adoptopenjdk/openjdk
    brew install --cask adoptopenjdk11
    brew install gnu-sed
    brew install docbook
    brew install docbook-xsl

    if [ "$typeoption" = "main" ]; then
	brew install ghostscript
	brew install texlive
        brew install graphviz
	sudo gem install public_suffix --version 4.0.7
        sudo gem install asciidoctor --version 2.0.16
        sudo gem install asciidoctor-pdf
        pip3 install docutils --user
        # which library is using rapidxml
        # wget -O rapidxml.zip http://sourceforge.net/projects/rapidxml/files/latest/download
        # unzip -n -d rapidxml rapidxml.zip
        pip3 install --user https://github.com/bfgroup/jam_pygments/archive/master.zip
        pip3 install --user Jinja2==2.11.2
        pip3 install --user MarkupSafe==1.1.1
        sudo gem install pygments.rb --version 2.1.0
        pip3 install --user Pygments==2.2.0
        sudo gem install rouge --version 3.26.1
        echo "Sphinx==1.5.6" > constraints.txt
        pip3 install --user Sphinx==1.5.6
        pip3 install --user sphinx-boost==0.0.3
        pip3 install --user -c constraints.txt git+https://github.com/rtfd/recommonmark@50be4978d7d91d0b8a69643c63450c8cd92d1212

        # Locking the version numbers in place offers a better guarantee of a known, good build.
        # At the same time, it creates a perpetual outstanding task, to upgrade the gem and pip versions
        # because they are out-of-date. When upgrading everything check the Dockerfiles and the other build scripts.
    fi

    # an alternate set of packages from https://www.boost.org/doc/libs/develop/doc/html/quickbook/install.html
    # sudo port install libxslt docbook-xsl docbook-xml-4.2

    cd $BOOST_SRC_FOLDER
    cd ..
    mkdir -p tmp && cd tmp
    if [ ! -f saxonhe.zip ]; then wget -O saxonhe.zip https://sourceforge.net/projects/saxon/files/Saxon-HE/9.9/SaxonHE9-9-1-4J.zip/download; fi
    unzip -d saxonhe -o saxonhe.zip
    cd saxonhe

    sudo rm /Library/Java/Extensions/Saxon-HE.jar || true
    sudo cp saxon9he.jar /Library/Java/Extensions/Saxon-HE.jar
    sudo chmod 755 /Library/Java/Extensions/Saxon-HE.jar

fi

# check this on apple silicon:
export PATH="/usr/local/opt/gnu-sed/libexec/gnubin:$PATH"

cd $BOOST_SRC_FOLDER

if [ "$skipboostoption" = "yes" ] ; then
    # skip-boost was set. A reduced set of actions.
    if [ "${BOOSTROOTLIBRARY}" = "yes" ]; then
        cd $BOOSTROOTRELPATH
        export BOOST_ROOT=$(pwd)
        librarypath=$(git config --file .gitmodules --get submodule.$REPONAME.path)
    else
        cd ..
        if [ ! -d boost-root ]; then
            echo "boost-root missing. Rerun this script without --skip-boost or --quick option."
            exit 1
        else
            cd boost-root
            export BOOST_ROOT=$(pwd)
            librarypath=$(git config --file .gitmodules --get submodule.$REPONAME.path)
            rsync -av $BOOST_SRC_FOLDER/ $librarypath
        fi
    fi
else
    # skip-boost was not set. The standard flow.
    if [ "${BOOSTROOTLIBRARY}" = "yes" ]; then
        cd $BOOSTROOTRELPATH
        git checkout $BOOST_BRANCH
        git pull
        export BOOST_ROOT=$(pwd)
        librarypath=$(git config --file .gitmodules --get submodule.$REPONAME.path)
    else
        cd ..
        if [ ! -d boost-root ]; then
            git clone -b $BOOST_BRANCH https://github.com/boostorg/boost.git boost-root --depth 1
            cd boost-root
            export BOOST_ROOT=$(pwd)
            librarypath=$(git config --file .gitmodules --get submodule.$REPONAME.path)
            rsync -av $BOOST_SRC_FOLDER/ $librarypath
        else
            cd boost-root
            git checkout $BOOST_BRANCH
            git pull
            export BOOST_ROOT=$(pwd)
            librarypath=$(git config --file .gitmodules --get submodule.$REPONAME.path)
            rsync -av $BOOST_SRC_FOLDER/ $librarypath
        fi
    fi
fi

if [ "$skippackagesoption" != "yes" ]; then
    mkdir -p build && cd build
    if [ ! -f docbook-xsl.zip ]; then
        wget -O docbook-xsl.zip https://sourceforge.net/projects/docbook/files/docbook-xsl/1.79.1/docbook-xsl-1.79.1.zip/download
    fi
    if [ ! -f docbook-xsl ]; then
        unzip -n -d docbook-xsl docbook-xsl.zip
    fi
    if [ ! -f docbook-xml.zip ]; then
        wget -O docbook-xml.zip http://www.docbook.org/xml/4.5/docbook-xml-4.5.zip
    fi
    if [ ! -d docbook-xml ]; then
        unzip -n -d docbook-xml docbook-xml.zip
    fi
    cd ..
fi

if [ -d ${BOOST_ROOT}/build/docbook-xsl/docbook-xsl-1.79.1 ]; then
    export DOCBOOK_XSL_DIR=${BOOST_ROOT}/build/docbook-xsl/docbook-xsl-1.79.1
fi

if [ -d ${BOOST_ROOT}/build/docbook-xml ]; then
    export DOCBOOK_DTD_DIR=${BOOST_ROOT}/build/docbook-xml
fi

if [ "$skipboostoption" != "yes" ] ; then

    git submodule update --init libs/context
    git submodule update --init tools/boostbook
    git submodule update --init tools/boostdep
    git submodule update --init tools/docca
    git submodule update --init tools/quickbook
    git submodule update --init tools/build
    sed -i 's~GLOB "/usr/share/java/saxon/"~GLOB "/Library/Java/Extensions/" "/usr/share/java/saxon/"~' tools/build/src/tools/saxonhe.jam

    if [ "$typeoption" = "main" ]; then
        git submodule update --init tools/auto_index
        git submodule update --quiet --init --recursive

        # recopy the library as it might have been overwritten
        rsync -av --delete $BOOST_SRC_FOLDER/ $librarypath
    fi

    python3 tools/boostdep/depinst/depinst.py ../tools/quickbook
    ./bootstrap.sh
    ./b2 headers

fi

# Update path

pythonbasicversion=$(python3 --version | cut -d" " -f2 | cut -d"." -f1-2)
newpathitem=~/Library/Python/$pythonbasicversion/bin
if [[ ! "$PATH" =~ $newpathitem ]]; then
    export PATH=$newpathitem:$PATH
fi

if [[ ! $PATH =~ dist/bin ]]; then
    export PATH=$BOOST_ROOT/dist/bin:$PATH
fi

echo '==================================> COMPILE'

# exceptions:

# toolslist="auto_index bcp boostbook boostdep boost_install build check_build cmake docca inspect litre quickbook"
toolslist=("auto_index" "bcp" "boostbook" "boostdep" "boost_install" "build" "check_build" "cmake" "docca" "inspect" "litre" "quickbook")

if [[ " ${toolslist[*]} " =~ " ${REPONAME} " ]] && [ "$boostrelease" = "//boostrelease" ]; then
    echo "The boost tools do not have a //boostrelease target in their Jamfile. Run the build without --boostrelease instead."
    exit 0
fi

if [[ "$librarypath" =~ numeric ]] && [ "$boostrelease" = "//boostrelease" ]; then
    echo "The //boostrelease version of the numeric libraries should be run from the top level. That is, in the numeric/ directory. For this script it is a special case. TODO."
    exit 0
fi

if [ ! -d $librarypath/doc ]; then
    echo "doc/ folder is missing for this library. No need to compile. Exiting."
    exit 0
fi

if [ -f $librarypath/doc/Jamfile ] || [ -f $librarypath/doc/jamfile ] || [ -f $librarypath/doc/Jamfile.v2 ] || [ -f $librarypath/doc/jamfile.v2 ] || [ -f $librarypath/doc/Jamfile.v3 ] || [ -f $librarypath/doc/jamfile.v3 ] || [ -f $librarypath/doc/Jamfile.jam ] || [ -f $librarypath/doc/jamfile.jam ] || [ -f $librarypath/doc/build.jam ] ; then
     : # ok
else
    echo "doc/Jamfile (or similar) is missing for this library. No need to compile. Exiting."
    exit 0
fi

if [ "$REPONAME" = "geometry" ]; then
    set -x
    echo "in the geometry exception. ./b2 $librarypath/doc/src/docutils/tools/doxygen_xml2qbk"
    ./b2 $librarypath/doc/src/docutils/tools/doxygen_xml2qbk
    echo "running pwd"
    pwd
    echo "Running find command"
    find . -name '*doxygen_xml2qbk*'
    set +x
    echo "Debugging gil. Running find sphinx-build"
    find ~ -name "*sphinx-build*"
    echo "Running pip3 list"
    pip3 list
fi

# -----------------------------------

# the main compilation:

if [ "$typeoption" = "main" ]; then
    ./b2 -q -d0 --build-dir=build --distdir=build/dist tools/quickbook tools/auto_index/build
    echo "using quickbook : build/dist/bin/quickbook ; using auto-index : build/dist/bin/auto_index ; using docutils ; using doxygen ; using boostbook ; using asciidoctor ; using saxonhe ;" > tools/build/src/user-config.jam
    ./b2 -j3 $librarypath/doc${boostrelease}

elif  [ "$typeoption" = "cppal" ]; then
    echo "using doxygen ; using boostbook ; using saxonhe ;" > tools/build/src/user-config.jam
    ./b2 $librarypath/doc${boostrelease}
fi

if [ "${BOOSTROOTLIBRARY}" = "yes" ]; then
    echo ""
    echo "Build completed. Check the doc/ directory."
    echo ""
else
    echo ""
    echo "Build completed. Check the results in $BOOST_SRC_FOLDER/../boost-root/$librarypath/doc"
    echo ""
fi
