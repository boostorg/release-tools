
# Copyright 2022 Sam Darwin
#
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at http://boost.org/LICENSE_1_0.txt)

param (
   [Parameter(Mandatory=$false)][alias("path")][string]$pathoption = "",
   [Parameter(Mandatory=$false)][alias("type")][string]$typeoption = "",
   [switch]$help = $false,
   [switch]${skip-boost} = $false,
   [switch]${skip-packages} = $false,
   [switch]$quick = $false,
   [switch]$boostrelease = $false
)

$scriptname="windowsdocs.ps1"

# Set-PSDebug -Trace 1

if ($help) {

$helpmessage="
usage: $scriptname [-help] [-type TYPE] [-skip-boost] [-skip-packages] [-quick] [-boostrelease] [path_to_library]

Builds library documentation.

optional arguments:
  -help                 Show this help message and exit
  -type TYPE            The `"type`" of build. Defaults to `"main`" which installs all standard boost prerequisites.
                        Another option is `"cppal`" which installs the prerequisites used by boostorg/json and a few other similar libraries.
                        More `"types`" can be added in the future if your library needs a specific set of packages installed.
                        The type is usually auto-detected and doesn't need to be specified.
  -skip-boost           Skip downloading boostorg/boost and building b2 if you are certain those steps have already been done.
  -skip-packages        Skip installing all packages (pip, gem, apt, etc.) if you are certain that has already been done.
  -quick                Equivalent to setting both -skip-boost and -skip-packages. If not sure, then don't skip these steps.
  -boostrelease         Add the target //boostrelease to the doc build. This target is used when building production releases.


standard arguments:
  path_to_library       Where the library is located. Defaults to current working directory.
"

echo $helpmessage
exit 0
}
if ($quick) { ${skip-boost} = $true ; ${skip-packages} = $true ; }
if ($boostrelease) {
    ${boostreleasetarget} = "//boostrelease"
 }
else {
    ${boostreleasetarget} = ""
}

pushd

# git is required. In the unlikely case it's not yet installed, moving that part of the package install process
# here to an earlier part of the script:

if ( -Not ${skip-packages} ) {
    if ( -Not (Get-Command choco -errorAction SilentlyContinue) ) {
        echo "Install chocolatey"
        iex ((new-object net.webclient).DownloadString('https://chocolatey.org/install.ps1'))
    }

    if ( -Not (Get-Command git -errorAction SilentlyContinue) ) {
        echo "Install git"
        choco install -y --no-progress git
    }

    # Make `refreshenv` available right away, by defining the $env:ChocolateyInstall
    # variable and importing the Chocolatey profile module.
    # Note: Using `. $PROFILE` instead *may* work, but isn't guaranteed to.
    $env:ChocolateyInstall = Convert-Path "$((Get-Command choco).Path)\..\.."
    Import-Module "$env:ChocolateyInstall\helpers\chocolateyProfile.psm1"
    refreshenv
}

if ($pathoption) {
    echo "Library path set to $pathoption. Changing to that directory."
    cd $pathoption
}
else
{
    $workingdir = pwd
    echo "Using current working directory $workingdir."
}

# DETERMINE REPOSITORY

$originurl=git config --get remote.origin.url
if ($LASTEXITCODE -eq 0)  {
    $REPONAME=[io.path]::GetFileNameWithoutExtension($originurl)
}
else {
    $REPONAME="empty"
}

if (($REPONAME -eq "empty") -or ($REPONAME -eq "release-tools")) {
    echo ""
    echo "Set the path_to_library as the first command-line argument:"
    echo ""
    echo "$scriptname _path_to_library_"
    echo ""
    echo "Or change the working directory to that first."
    exit 1
}
else {
    echo "REPONAME is $REPONAME"
}

$BOOST_SRC_FOLDER=git rev-parse --show-toplevel
if ( ! $LASTEXITCODE -eq 0)  {
    $BOOST_SRC_FOLDER="nofolder"
}
else {
    echo "BOOST_SRC_FOLDER is $BOOST_SRC_FOLDER"
}

$PARENTNAME=[io.path]::GetFileNameWithoutExtension($(git --git-dir $BOOST_SRC_FOLDER/../.git config --get remote.origin.url))
if ( $PARENTNAME -eq "boost" ) {
    echo "Starting out inside boost-root"
    $BOOSTROOTLIBRARY="yes"
    $BOOSTROOTRELPATH=".."
}
else {
    $PARENTNAME=[io.path]::GetFileNameWithoutExtension($(git --git-dir $BOOST_SRC_FOLDER/../../.git config --get remote.origin.url))
    if ( $PARENTNAME -eq "boost" ) {
        echo "Starting out inside boost-root"
        $BOOSTROOTLIBRARY="yes"
        $BOOSTROOTRELPATH="../.."
    }
    else {
        $PARENTNAME=[io.path]::GetFileNameWithoutExtension($(git --git-dir $BOOST_SRC_FOLDER/../../../.git config --get remote.origin.url))
        if ( $PARENTNAME -eq "boost" )
        {
            echo "Starting out inside boost-root"
            $BOOSTROOTLIBRARY="yes"
            $BOOSTROOTRELPATH="../../.."
        }
        else {
            echo "Not starting out inside boost-root"
            $BOOSTROOTLIBRARY="no"
            }
    }
}

# DECIDE THE TYPE

$alltypes="main cppal"
$cppaltypes="json beast url http_proto socks_proto zlib"

if (! $typeoption ) {
    if ($cppaltypes.contains($REPONAME)) {
        $typeoption="cppal"
    }
    else {
        $typeoption="main"
    }
}

echo "Build type is $typeoption"

if ( ! $alltypes.contains($typeoption)) {
    echo "Allowed types are currently 'main' and 'cppal'. Not $typeoption. Please choose a different option. Exiting."
    exit 1
}

$REPO_BRANCH=git rev-parse --abbrev-ref HEAD
echo "REPO_BRANCH is $REPO_BRANCH"

if ( $REPO_BRANCH -eq "master" )
{
    $BOOST_BRANCH="master"
}
else
{
    $BOOST_BRANCH="develop"
}

echo "BOOST_BRANCH is $BOOST_BRANCH"

echo '==================================> INSTALL'

# graphviz package added for historical reasons, might not be used.

if ( -Not ${skip-packages} ) {

    if ( -Not (Get-Command choco -errorAction SilentlyContinue) ) {
        echo "Install chocolatey"
        iex ((new-object net.webclient).DownloadString('https://chocolatey.org/install.ps1'))
    }
    choco install -y --no-progress rsync sed doxygen.install xsltproc docbook-bundle
    if ( -Not (Get-Command java -errorAction SilentlyContinue) )
    {
        choco install -y --no-progress openjdk --version=17.0.1
    }
    if ( -Not (Get-Command make -errorAction SilentlyContinue) )
    {
        choco install -y --no-progress make
    }
    if ( -Not (Get-Command python -errorAction SilentlyContinue) )
    {
        choco install -y --no-progress python3
    }
    if ( -Not (Get-Command git -errorAction SilentlyContinue) )
    {
        choco install -y --no-progress git
    }
    if ($typeoption -eq "main") {
    if ( -Not (Get-Command ruby -errorAction SilentlyContinue) )
    {
        choco install -y --no-progress ruby
    }
    if ( -Not (Get-Command wget -errorAction SilentlyContinue) )
    {
        choco install -y --no-progress wget
    }
    }
    # Make `refreshenv` available right away, by defining the $env:ChocolateyInstall
    # variable and importing the Chocolatey profile module.
    # Note: Using `. $PROFILE` instead *may* work, but isn't guaranteed to.
    $env:ChocolateyInstall = Convert-Path "$((Get-Command choco).Path)\..\.."
    Import-Module "$env:ChocolateyInstall\helpers\chocolateyProfile.psm1"

    refreshenv

    if ( -Not (Get-Command python3 -errorAction SilentlyContinue) )
    {
        # create a symbolic link since windows doesn't have python3
        $pythoncommandpath=(Get-Command python).Path
        $python3commandpath=(Get-Command python).Path -replace 'python.exe', 'python3.exe'
        New-Item -ItemType SymbolicLink -Path "$python3commandpath" -Target "$pythoncommandpath"
    }

    if ($typeoption -eq "main") {
        $ghostversion="9.56.1"
        choco install -y --no-progress ghostscript --version $ghostversion
        choco install -y --no-progress texlive
        choco install -y --no-progress graphviz
        gem install public_suffix --version 4.0.7
        gem install asciidoctor --version 2.0.16
        gem install asciidoctor-pdf
        pip3 install docutils
        wget -O rapidxml.zip http://sourceforge.net/projects/rapidxml/files/latest/download
        unzip -n -d rapidxml rapidxml.zip
        #
        # pip3 had been using --user. what will happen without.
        pip3 install https://github.com/bfgroup/jam_pygments/archive/master.zip
        pip3 install Jinja2==2.11.2
        pip3 install MarkupSafe==1.1.1
        gem install pygments.rb --version 2.1.0
        pip3 install Pygments==2.2.0
        gem install rouge --version 3.26.1
        echo "Sphinx==1.5.6" > constraints.txt
        pip3 install Sphinx==1.5.6
        pip3 install sphinx-boost==0.0.3
        pip3 install -c constraints.txt git+https://github.com/rtfd/recommonmark@50be4978d7d91d0b8a69643c63450c8cd92d1212

        refreshenv

	# ghostscript fixes
        $newpathitem="C:\Program Files\gs\gs$ghostversion\bin"
        if( (Test-Path -Path $newpathitem) -and -Not ( $env:Path -like "*$newpathitem*"))
        {
               $env:Path += ";$newpathitem"
        }
        New-Item -ItemType SymbolicLink -Path "C:\Program Files\gs\gs9.56.1\bin\gswin32c.exe" -Target "C:\Program Files\gs\gs9.56.1\bin\gswin64c.exe"

        # Locking the version numbers in place offers a better guarantee of a known, good build.
        # At the same time, it creates a perpetual outstanding task, to upgrade the gem and pip versions
        # because they are out-of-date. When upgrading everything check the Dockerfiles and the other build scripts.
    }

    # A bug fix, which may need to be developed further:
    # b2 reports that the "cp" command can't be found on Windows.
    # Let's add git's version of "cp" to the PATH.
    $newpathitem="C:\Program Files\Git\usr\bin"
    if( (Test-Path -Path $newpathitem) -and -Not ( $env:Path -like "*$newpathitem*"))
    {
           $env:Path += ";$newpathitem"
    }

    # Copy-Item "C:\Program Files\doxygen\bin\doxygen.exe" "C:\Windows\System32\doxygen.exe"

    cd $BOOST_SRC_FOLDER
    cd ..
    if ( -Not (Test-Path -Path "tmp") )
    {
        mkdir tmp
    }

    cd tmp

    # Install saxon
    if ( -Not (Test-Path -Path "C:\usr\share\java\Saxon-HE.jar") )
    {
        $source = 'https://sourceforge.net/projects/saxon/files/Saxon-HE/9.9/SaxonHE9-9-1-4J.zip/download'
        $destination = 'saxonhe.zip'
        if ( Test-Path -Path $destination)
        {
            rm $destination
        }
        if ( Test-Path -Path "saxonhe")
        {
            rm Remove-Item saxonhe -Recurse -Force
        }
        Start-BitsTransfer -Source $source -Destination $destination
        Expand-Archive .\saxonhe.zip
        cd saxonhe
        if ( -Not (Test-Path -Path "C:\usr\share\java") )
        {
            mkdir "C:\usr\share\java"
        }
        cp saxon9he.jar Saxon-HE.jar
        cp Saxon-HE.jar "C:\usr\share\java\"
    }

}

# re-adding the path fix from above, even if skip-packages was set.
$newpathitem="C:\Program Files\Git\usr\bin"
if( (Test-Path -Path $newpathitem) -and -Not ( $env:Path -like "*$newpathitem*"))
    {
     $env:Path += ";$newpathitem"
    }

cd $BOOST_SRC_FOLDER

if ( ${skip-boost} ) {
    # skip-boost was set. A reduced set of actions.
    if ( $BOOSTROOTLIBRARY -eq "yes" ) {
        cd $BOOSTROOTRELPATH
        $Env:BOOST_ROOT=Get-Location | Foreach-Object { $_.Path }
        echo "Env:BOOST_ROOT is $Env:BOOST_ROOT"
        $librarypath=git config --file .gitmodules --get submodule.$REPONAME.path
        if ( ! $LASTEXITCODE -eq 0) {
          exit 1
        }
    }

    else {
        cd ..
        if ( -Not (Test-Path -Path "boost-root") ) {
            echo "boost-root missing. Rerun this script without the -skip-boost or -quick option."
            exit 1
	    }
        else {
            cd boost-root
            $Env:BOOST_ROOT=Get-Location | Foreach-Object { $_.Path }
            echo "Env:BOOST_ROOT is $Env:BOOST_ROOT"
            $librarypath=git config --file .gitmodules --get submodule.$REPONAME.path
            if ( ! $LASTEXITCODE -eq 0) {
              exit 1
            }

            if (Test-Path -Path "$librarypath")
            {
                rmdir $librarypath -Force -Recurse
            }
            Copy-Item -Path $BOOST_SRC_FOLDER -Destination $librarypath -Recurse -Force
            }
        }
    }
else {
    # skip-boost was not set. The standard flow.
    #
    if ( $BOOSTROOTLIBRARY -eq "yes" ) {
        echo "updating boost-root"
        cd $BOOSTROOTRELPATH
        git checkout $BOOST_BRANCH
        git pull
        $Env:BOOST_ROOT=Get-Location | Foreach-Object { $_.Path }
        echo "Env:BOOST_ROOT is $Env:BOOST_ROOT"
        $librarypath=git config --file .gitmodules --get submodule.$REPONAME.path
        if ( ! $LASTEXITCODE -eq 0) {
          exit 1
        }

    }
    else {
        cd ..
        if ( -Not (Test-Path -Path "boost-root") ) {
            echo "cloning boost-root"
            git clone -b $BOOST_BRANCH https://github.com/boostorg/boost.git boost-root --depth 1
            cd boost-root
            $Env:BOOST_ROOT=Get-Location | Foreach-Object { $_.Path }
            echo "Env:BOOST_ROOT is $Env:BOOST_ROOT"
            $librarypath=git config --file .gitmodules --get submodule.$REPONAME.path
            if ( ! $LASTEXITCODE -eq 0) {
              exit 1
            }

            if (Test-Path -Path "$librarypath")
            {
                rmdir $librarypath -Force -Recurse
            }
            Copy-Item -Path $BOOST_SRC_FOLDER -Destination $librarypath -Recurse -Force
        }
        else {
            echo "updating boost-root"
            cd boost-root
            git checkout $BOOST_BRANCH
            git pull
            $Env:BOOST_ROOT=Get-Location | Foreach-Object { $_.Path }
            echo "Env:BOOST_ROOT is $Env:BOOST_ROOT"
            $librarypath=git config --file .gitmodules --get submodule.$REPONAME.path
            if ( ! $LASTEXITCODE -eq 0) {
              exit 1
            }

            if (Test-Path -Path "$librarypath")
            {
                rmdir $librarypath -Force -Recurse
            }
            Copy-Item -Path $BOOST_SRC_FOLDER -Destination $librarypath -Recurse -Force
        }
    }
}

if ( -Not ${skip-packages} ) {
    mkdir build
    cd build
    if ( -Not (Test-Path -Path docbook-xsl.zip) ) {
        Invoke-Webrequest -usebasicparsing -Outfile docbook-xsl.zip -uri https://github.com/docbook/xslt10-stylesheets/releases/download/release%2F1.79.2/docbook-xsl-1.79.2.zip
    }
    if ( -Not (Test-Path -Path docbook-xsl) ) {
        unzip -n -d docbook-xsl docbook-xsl.zip
    }
    if ( -Not (Test-Path -Path docbook-xml.zip) ) {
        wget -O docbook-xml.zip http://www.docbook.org/xml/4.5/docbook-xml-4.5.zip
    }
    if ( -Not (Test-Path -Path docbook-xml) ) {
        unzip -n -d docbook-xml docbook-xml.zip
    }
    cd ..
}

$Folder="$Env:BOOST_ROOT/build/docbook-xsl/docbook-xsl-1.79.2"
if (Test-Path -Path $Folder) {
    $Env:DOCBOOK_XSL_DIR="$Env:BOOST_ROOT/build/docbook-xsl/docbook-xsl-1.79.2"
}

$Folder="$Env:BOOST_ROOT/build/docbook-xml"
if (Test-Path -Path $Folder) {
    $Env:DOCBOOK_DTD_DIR="$Env:BOOST_ROOT/build/docbook-xml"
}

if ( -Not ${skip-boost} ) {
    git submodule update --init libs/context
    git submodule update --init tools/boostbook
    git submodule update --init tools/boostdep
    git submodule update --init tools/docca
    git submodule update --init tools/quickbook
    git submodule update --init tools/build

    if ($typeoption -eq "main") {
        git submodule update --init tools/auto_index
        git submodule update --quiet --init --recursive
    }

    # Recopy the library, as it might have been overwritten by the submodule updates that just occurred.
    if ( -Not ($BOOSTROOTLIBRARY -eq "yes") ) {
        if (Test-Path -Path "$librarypath")
        {
            rmdir $librarypath -Force -Recurse
        }
        Copy-Item -Path $BOOST_SRC_FOLDER -Destination $librarypath -Recurse -Force
    }

    $matcher='\.saxonhe_jar = \$(jar\[1\]) ;$'
    $replacer='.saxonhe_jar = $(jar[1]) ;  .saxonhe_jar = \"/usr/share/java/Saxon-HE.jar\" ;'
    sed -i "s~$matcher~$replacer~" tools/build/src/tools/saxonhe.jam

    python tools/boostdep/depinst/depinst.py ../tools/quickbook

    echo "Running bootstrap.bat"
    ./bootstrap.bat

    echo "Running ./b2 headers"
    ./b2 headers
}

# Adjust PATH

$newpathitem="$env:BOOST_ROOT\dist\bin"
if( -Not ( $env:Path -like "*$newpathitem*"))
    {
           $env:Path = "$newpathitem;" + $env:Path
    }

$newpathitem="C:\Program Files\doxygen\bin"
if( -Not ( $env:Path -like "*$newpathitem*"))
    {
           $env:Path = "$newpathitem;" + $env:Path
    }
echo "new env:Path is $env:Path"

echo '==================================> COMPILE'

# exceptions:

# $toolslist="auto_index bcp boostbook boostdep boost_install build check_build cmake docca inspect litre quickbook"
$toolslist = @("auto_index", "bcp", "boostbook", "boostdep", "boost_install", "build", "check_build", "cmake", "docca", "inspect", "litre", "quickbook")
if ( ($toolslist.contains($REPONAME)) -and ("$boostreleasetarget" -eq "//boostrelease" )) {
    echo "The boost tools do not have a //boostrelease target in their Jamfile. Run the build without -boostrelease instead."
    exit 0
}

if (($librarypath -match "numeric") -and ($boostreleasetarget -eq "//boostrelease")) {
    echo "The //boostrelease version of the numeric libraries should be run from the top level. That is, in the numeric/ directory. For this script it is a special case. TODO."
    exit 0
}

if ( -Not (Test-Path -Path $librarypath/doc/ )) {
    echo "doc/ folder is missing for this library. No need to compile. Exiting."
    exit 0
}

if ( (Test-Path -Path $librarypath/doc/Jamfile) -or (Test-Path -Path $librarypath/doc/Jamfile.v2) -or (Test-Path -Path $librarypath/doc/Jamfile.v3) -or (Test-Path -Path $librarypath/doc/Jamfile.jam) -or (Test-Path -Path $librarypath/doc/build.jam)) {
  }
else {
    echo "doc/Jamfile (or similar) is missing for this library. No need to compile. Exiting."
    exit 0
}

if ("$REPONAME" -eq "geometry") {
    echo "In geometry exception. running ./b2 $librarypath/doc/src/docutils/tools/doxygen_xml2qbk"
    ./b2 $librarypath/doc/src/docutils/tools/doxygen_xml2qbk
    echo "running pwd"
    pwd
    echo "running dir dist\bin"
    dir dist\bin
    echo "checking path"
    echo $env:Path
    # moving this to PATH var
    # echo "running cp dist/bin/doxygen_xml2qbk C:\windows\system32"
    # cp dist/bin/doxygen_xml2qbk.exe C:\windows\system32
    try { (Get-Command doxygen_xml2qbk.exe).Path }
    catch { echo "couldn't find doxygen_xml2qbk.exe" }
}

# the main compilation:

if ($typeoption -eq "main") {

    $asciidoctorpath=(Get-Command asciidoctor).Path -replace '\\', '/'
    $autoindexpath="$Env:BOOST_ROOT/build/dist/bin/auto_index.exe"
    $autoindexpath=$autoindexpath -replace '\\', '/'
    $quickbookpath="$Env:BOOST_ROOT/build/dist/bin/quickbook.exe"
    $quickbookpath=$quickbookpath -replace '\\', '/'

    ./b2 -q -d0 --build-dir=build --distdir=build/dist tools/quickbook tools/auto_index/build
    $content="using quickbook : `"$quickbookpath`" ; using auto-index : `"$autoindexpath`" ; using docutils ; using doxygen : `"/Program Files/doxygen/bin/doxygen.exe`" ; using boostbook ; using asciidoctor : `"$asciidoctorpath`" ; using saxonhe ;"
    $filename="$Env:BOOST_ROOT\tools\build\src\user-config.jam"
    [IO.File]::WriteAllLines($filename, $content)
    ./b2 -d 2 $librarypath/doc${boostreleasetarget}
     if ( ! $LASTEXITCODE -eq 0)  {
         echo "doc build failed. exiting."
         exit 1
     }
}
elseif ($typeoption -eq "cppal") {
    $content="using doxygen : `"/Program Files/doxygen/bin/doxygen.exe`" ; using boostbook ; using saxonhe ;"
    $filename="$Env:BOOST_ROOT\tools\build\src\user-config.jam"
    [IO.File]::WriteAllLines($filename, $content)
    ./b2 -d 2 $librarypath/doc${boostreleasetarget}
     if ( ! $LASTEXITCODE -eq 0)  {
         echo "doc build failed. exiting."
         exit 1
     }
}

if ($BOOSTROOTLIBRARY -eq "yes") {
    echo ""
    echo "Build completed. Check the doc/ directory."
    echo ""
}
else {
    echo ""
    echo "Build completed. Check the results in $BOOST_SRC_FOLDER/../boost-root/$librarypath/doc"
    echo ""
}

popd

