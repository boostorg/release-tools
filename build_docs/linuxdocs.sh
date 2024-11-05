#!/bin/bash

# Copyright 2022 Sam Darwin
#
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at http://boost.org/LICENSE_1_0.txt)

set -e
shopt -s extglob
shopt -s dotglob

scriptname="linuxdocs.sh"

# set defaults:
boostrelease=""
BOOSTROOTRELPATH=".."
pythonvirtenvpath="${HOME}/venvboostdocs"

# READ IN COMMAND-LINE OPTIONS

TEMP=`getopt -o t:,h::,q:: --long type:,help::,skip-boost::,skip-packages::,quick::,boostrelease::,boostrootsubdir::,debug:: -- "$@"`
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
                        Another option is \"cppalv1\" which had installed the prerequisites used by boostorg/json and a few other similar libraries.
                        More \"types\" can be added in the future if your library needs a specific set of packages installed.
                        The type is usually auto-detected and doesn't need to be specified.
  --skip-boost   	Skip downloading boostorg/boost and building b2 if you are certain those steps have already been done.
  --skip-packages	Skip installing all packages (pip, gem, apt, etc.) if you are certain that has already been done.
  -q, --quick		Equivalent to setting both --skip-boost and --skip-packages. If not sure, then don't skip these steps.
  --boostrelease	Add the target //boostrelease to the doc build. This target is used when building production releases.
  --boostrootsubdir	If creating a boost-root directory, instead of placing it in ../ use a subdirectory.
  --debug               Debugging.
standard arguments:
  path_to_library	Where the library is located. Defaults to current working directory.
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
	--debug)
	    debugoption="yes" ; set -x ; shift 2 ;;
	--skip-packages)
	    skippackagesoption="yes" ; shift 2 ;;
	-q|--quick)
	    skipboostoption="yes" ; skippackagesoption="yes" ; shift 2 ;;
	--boostrelease)
	    boostrelease="//boostrelease" ; shift 2 ;;
	--boostrootsubdir)
	    boostrootsubdiroption="yes" ; BOOSTROOTRELPATH="." ; shift 2 ;;
        --) shift ; break ;;
        *) echo "Internal error!" ; exit 1 ;;
    esac
done

# git is required. In the unlikely case it's not yet installed, moving that part of the package install process
# here to an earlier part of the script:

if [ "$skippackagesoption" != "yes" ]; then
    sudo apt-get update
    if ! command -v git &> /dev/null
    then
        sudo apt-get install -y git
    fi
fi

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

# The purpose of this is to allow nvm/npm/node to use a subdirectory of the library in CI, so the job is self-contained
# and doesn't use external directories.
if [ "${boostrootsubdiroption}" = "yes" ]; then
    mkdir -p "${BOOST_SRC_FOLDER}/tmp_home"
    export HOME=${BOOST_SRC_FOLDER}/tmp_home
fi

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

# Generally, boostorg/release-tools treats all libraries the same, meaning it installs one set of packages and executes b2.
# Therefore all libraries ought to build under 'main' and shouldn't need anything customized.

all_types="main antora cppalv1"
# cppalv1_types="json beast url http_proto socks_proto zlib"
cppalv1_types="not_currently_used skipping_this"

if [ -z "$typeoption" ]; then
    if [ -f "$BOOST_SRC_FOLDER/doc/build_antora.sh" ]; then
        typeoption="antora"
    elif [[ " $cppalv1_types " =~ .*\ $REPONAME\ .* ]]; then
        # not used currently, but an example
        typeoption="cppalv1"
    else
        typeoption="main"
    fi
fi

echo "Build type is ${typeoption}."

if [[ !  " $all_types " =~ .*\ $typeoption\ .* ]]; then
    echo "Allowed types are currently 'main', 'antora' and 'cppalv1'. Not $typeoption. Please choose a different option. Exiting."
    exit 1
fi

if git rev-parse --abbrev-ref HEAD | grep master ; then BOOST_BRANCH=master ; else BOOST_BRANCH=develop ; fi


echo '==================================> INSTALL'

# graphviz package added for historical reasons, might not be used.

if [ "$skippackagesoption" != "yes" ]; then

    # already done:
    # sudo apt-get update

    sudo apt-get install -y build-essential cmake curl default-jre-headless python3 python3-venv rsync unzip wget

    if [ "$typeoption" = "antora" ]; then

        mkdir -p ~/.nvm_${REPONAME}_antora
        export NODE_VERSION=18.18.1
        # The container has a pre-installed nodejs. Overwrite those again.
        export NVM_BIN="$HOME/.nvm_${REPONAME}_antora/versions/node/v${NODE_VERSION}/bin"
        export NVM_DIR=$HOME/.nvm_${REPONAME}_antora
        export NVM_INC=$HOME/.nvm_${REPONAME}_antora/versions/node/v${NODE_VERSION}/include/node
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
        export NVM_DIR=$HOME/.nvm_${REPONAME}_antora
        . "$NVM_DIR/nvm.sh" && nvm install ${NODE_VERSION}
        . "$NVM_DIR/nvm.sh" && nvm use v${NODE_VERSION}
        . "$NVM_DIR/nvm.sh" && nvm alias default v${NODE_VERSION}
        export PATH="$HOME/.nvm_${REPONAME}_antora/versions/node/v${NODE_VERSION}/bin/:${PATH}"
        node --version
        npm --version
        npm install gulp-cli@2.3.0
        npm install @mermaid-js/mermaid-cli@10.5.1


    fi
    if [ "$typeoption" = "cppalv1" ]; then
        sudo apt-get install -y bison docbook docbook-xml docbook-xsl flex libfl-dev libsaxonhe-java xsltproc
    fi
    if [ "$typeoption" = "main" ]; then
        sudo apt-get install -y python3-pip ruby ruby-dev
        sudo apt-get install -y bison docbook docbook-xml docbook-xsl docutils-doc docutils-common flex ghostscript graphviz libfl-dev libsaxonhe-java texlive texlive-latex-extra xsltproc

        if [ ! -f ${pythonvirtenvpath}/bin/activate ]; then
            python3 -m venv ${pythonvirtenvpath}
        fi
        source ${pythonvirtenvpath}/bin/activate

        # the next two gems are for asciidoctor-pdf
        sudo gem install public_suffix --version 4.0.7		# 4.0.7 from 2022 still supports ruby 2.5. Continue to use until ~2024.
        sudo gem install css_parser --version 1.12.0		# 1.12.0 from 2022 still supports ruby 2.5. Continue to use until ~2024.
        sudo gem install asciidoctor --version 2.0.17
        sudo gem install asciidoctor-pdf --version 2.3.4
        sudo gem install asciidoctor-diagram --version 2.2.14
        sudo gem install asciidoctor-multipage --version 0.0.18
        pip3 install setuptools
        pip3 install docutils
        # which library is using rapidxml
        # wget -O rapidxml.zip http://sourceforge.net/projects/rapidxml/files/latest/download
        # unzip -n -d rapidxml rapidxml.zip
        pip3 install https://github.com/bfgroup/jam_pygments/archive/master.zip
        pip3 install Jinja2==3.1.2
        pip3 install MarkupSafe==2.1.1
        sudo gem install pygments.rb --version 2.3.0
        pip3 install Pygments==2.13.0
        sudo gem install rouge --version 4.0.0
        pip3 install Sphinx==5.2.1
        pip3 install git+https://github.com/pfultz2/sphinx-boost@8ad7d424c6b613864976546d801439c34a27e3f6
        # from dockerfile:
        pip3 install myst-parser==0.18.1
        pip3 install future==0.18.2
        pip3 install six==1.14.0

        # Locking the version numbers in place offers a better guarantee of a known, good build.
	# At the same time, it creates a perpetual outstanding task, to upgrade the gem and pip versions
        # because they are out-of-date. When upgrading everything check the Dockerfiles and the other build scripts.
    fi

    if [ "$typeoption" = "cppalv1" ] || [ "$typeoption" = "main" ]; then

        # Installing doxygen and saxonhe

        cd $BOOST_SRC_FOLDER
        cd $BOOSTROOTRELPATH
        mkdir -p tmp && cd tmp

        if which doxygen; then
            echo "doxygen found"
        else
            echo "building doxygen"
            if [ ! -d doxygen ]; then git clone -b 'Release_1_9_5' --depth 1 https://github.com/doxygen/doxygen.git && echo "not-cached" ; else echo "cached" ; fi
            cd doxygen
            cmake -H. -Bbuild -DCMAKE_BUILD_TYPE=Release
            cd build
            sudo make install
            cd ../..
        fi

        if [ ! -f saxonhe.zip ]; then curl -s -S --retry 10 -L -o saxonhe.zip https://sourceforge.net/projects/saxon/files/Saxon-HE/9.9/SaxonHE9-9-1-4J.zip/download && echo "not-cached" ; else echo "cached" ; fi
        unzip -d saxonhe -o saxonhe.zip
        cd saxonhe
        sudo rm /usr/share/java/Saxon-HE.jar || true
        sudo cp saxon9he.jar /usr/share/java/Saxon-HE.jar
    fi
fi

# In the above 'packages' section a python virtenv was created. Activate it, if that has not been done already.
if [ -f ${pythonvirtenvpath}/bin/activate ]; then
    source ${pythonvirtenvpath}/bin/activate
fi

# In the above 'packages' section npm was installed. Activate it, if that has not been done already.
if [ -d $HOME/.nvm_${REPONAME}_antora ]; then
        export NODE_VERSION=18.18.1
        # The container has a pre-installed nodejs. Overwrite those again.
        export NVM_BIN="$HOME/.nvm_${REPONAME}_antora/versions/node/v${NODE_VERSION}/bin"
        export NVM_DIR=$HOME/.nvm_${REPONAME}_antora
        export NVM_INC=$HOME/.nvm_${REPONAME}_antora/versions/node/v${NODE_VERSION}/include/node
        . "$NVM_DIR/nvm.sh" && nvm use v${NODE_VERSION}
        export PATH="$HOME/.nvm_${REPONAME}_antora/versions/node/v${NODE_VERSION}/bin/:${PATH}"
        node --version
        npm --version
fi

cd $BOOST_SRC_FOLDER

getlibrarypath () {
    localreponame=$1
    locallibrarypath=$(git config --file .gitmodules --get submodule.$localreponame.path) || locallibrarypath="libs/$localreponame"
    echo "$locallibrarypath"
    }

if [ "$skipboostoption" = "yes" ] ; then
    # skip-boost was set. A reduced set of actions.
    if [ "${BOOSTROOTLIBRARY}" = "yes" ]; then
        cd $BOOSTROOTRELPATH
        export BOOST_ROOT=$(pwd)
        librarypath=$(getlibrarypath $REPONAME)
    else
        cd $BOOSTROOTRELPATH
        if [ ! -d boost-root ]; then
	    echo "boost-root missing. Rerun this script without --skip-boost or --quick option."
	    exit 1
        else
            cd boost-root
            export BOOST_ROOT=$(pwd)
            librarypath=$(getlibrarypath $REPONAME)
            mkdir -p $librarypath
            # running cp multiple times will fail to overwrite certain .git files
            # cp -r ${BOOST_SRC_FOLDER}/!(boost-root) ${librarypath} || true
            rsync -av --exclude 'boost-root' $BOOST_SRC_FOLDER/ $librarypath
        fi
    fi
else
    # skip-boost was not set. The standard flow.
    if [ "${BOOSTROOTLIBRARY}" = "yes" ]; then
        cd $BOOSTROOTRELPATH
        git checkout $BOOST_BRANCH
        git pull
        export BOOST_ROOT=$(pwd)
        librarypath=$(getlibrarypath $REPONAME)
    else
        cd $BOOSTROOTRELPATH
        if [ ! -d boost-root ]; then
            git clone -b $BOOST_BRANCH https://github.com/boostorg/boost.git boost-root --depth 1
            cd boost-root
	else
	    cd boost-root
            git checkout $BOOST_BRANCH
            git pull
	fi
        export BOOST_ROOT=$(pwd)
        librarypath=$(getlibrarypath $REPONAME)
        mkdir -p $librarypath
        # running cp multiple times will fail to overwrite certain .git files
        # cp -r ${BOOST_SRC_FOLDER}/!(boost-root) ${librarypath} || true
        rsync -av --exclude 'boost-root' $BOOST_SRC_FOLDER/ $librarypath
    fi
fi

# for Alan's antora scripts:
if [ "$EXPORT_BOOST_SRC_DIR" = "yes" ]; then
    export BOOST_SRC_DIR=${BOOST_ROOT}
fi

if [ "$skippackagesoption" != "yes" ] ; then
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

if [ "$skipboostoption" != "yes" ] && [ "$typeoption" != "antora" ] ; then

    git submodule update --init libs/context
    git submodule update --init tools/boostbook
    git submodule update --init tools/boostdep
    git submodule update --init tools/docca
    git submodule update --init tools/quickbook
    git submodule update --init tools/boostlook

    if [ "$typeoption" = "main" ]; then
        git submodule update --init tools/auto_index
        python3 tools/boostdep/depinst/depinst.py ../tools/auto_index

        # recopy the library if it was overwritten.
        if [ ! "${BOOSTROOTLIBRARY}" = "yes" ]; then
            # cp -rf ${BOOST_SRC_FOLDER}/!(boost-root) ${librarypath}
            rsync -av --exclude 'boost-root' --delete $BOOST_SRC_FOLDER/ $librarypath
        fi
    fi

    python3 tools/boostdep/depinst/depinst.py ../tools/quickbook
    ./bootstrap.sh
    ./b2 headers

fi

# Update path

if [[ ! $PATH =~ \.local/bin ]]; then
    export PATH=~/.local/bin:$PATH
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

if [ -f $librarypath/doc/build_antora.sh ] ||  [ -f $librarypath/doc/Jamfile ] || [ -f $librarypath/doc/jamfile ] || [ -f $librarypath/doc/Jamfile.v2 ] || [ -f $librarypath/doc/jamfile.v2 ] || [ -f $librarypath/doc/Jamfile.v3 ] || [ -f $librarypath/doc/jamfile.v3 ] || [ -f $librarypath/doc/Jamfile.jam ] || [ -f $librarypath/doc/jamfile.jam ] || [ -f $librarypath/doc/build.jam ] ; then
     : # ok
else
    echo "doc/Jamfile or similar is missing for this library. No need to compile. Exiting."
    exit 0
fi

if [ "$REPONAME" = "geometry" ]; then
    ./b2 $librarypath/doc/src/docutils/tools/doxygen_xml2qbk/
    # adjusting PATH var instead
    # cp dist/bin/doxygen_xml2qbk /usr/local/bin/
    echo "Debugging for macos. which sphinx-build"
    which sphinx-build || true
    echo "Running ls dist/bin"
    ls -al dist/bin || true
fi

# -------------------------------

# the main compilation:

echo "DEBUGGING"
pwd
ls -al libs || true

if [ "$typeoption" = "main" ]; then
    ./b2 -q -d0 --build-dir=build --distdir=build/dist tools/quickbook tools/auto_index
    echo "using quickbook : build/dist/bin/quickbook ; using auto-index : build/dist/bin/auto_index ; using docutils : /usr/share/docutils ; using doxygen ; using boostbook ; using asciidoctor ; using saxonhe ;" > tools/build/src/user-config.jam
    ./b2 -j3 $librarypath/doc${boostrelease}

elif [ "$typeoption" = "antora" ]; then
    library_is_submodule=""
    timestamp=""
    if [ -f "${librarypath}/.git" ]; then
        library_is_submodule="true"
        timestamp=$(date +%s)
        echo "Antora will not run on a git module. Copying to /tmp"
        mkdir -p /tmp/builddocs-${timestamp}/${REPONAME}
        cp -rp ${librarypath}/* /tmp/builddocs-${timestamp}/${REPONAME}/
        cd /tmp/builddocs-${timestamp}/${REPONAME}/
        rm -f .git
        git init
        git config user.email "test@example.com"
        git config user.name "test"
        git add .
        git commit -m "initial commit"
        cd doc
    else 
        cd ${librarypath}/doc
    fi
    chmod 755 build_antora.sh
    ./build_antora.sh

    if [ ! -f build/site/index.html ]; then
        echo "build/site/index.html is missing. It is likely that antora did not complete successfully."
        exit 1
    fi
        
    if [ "$library_is_submodule" = "true" ]; then
        mkdir -p ${BOOST_ROOT}/${librarypath}/doc/build/
        cp -rp build/* ${BOOST_ROOT}/${librarypath}/doc/build/
    fi   

elif [ "$typeoption" = "cppalv1" ]; then
    echo "using doxygen ; using boostbook ; using saxonhe ;" > tools/build/src/user-config.jam
    ./b2 $librarypath/doc${boostrelease}
fi

if [ "$typeoption" = "antora" ]; then
    result_sub_path="doc/build/site/"
else
    result_sub_path="doc/html/"
fi

if [ "${BOOSTROOTLIBRARY}" = "yes" ]; then
    echo ""
    echo "Build completed. View the results in $librarypath/${result_sub_path}"
    echo ""
else
    if  [ "$BOOSTROOTRELPATH" = "." ]; then
        pathfiller="/"
    else
        pathfiller="/${BOOSTROOTRELPATH}/"
    fi
    echo ""
    echo "Build completed. View the results in ${BOOST_SRC_FOLDER}${pathfiller}boost-root/$librarypath/${result_sub_path}"
    echo ""
fi
