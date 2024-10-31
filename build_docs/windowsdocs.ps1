# Copyright 2022 Sam Darwin
#
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at http://boost.org/LICENSE_1_0.txt)

[System.Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSAvoidUsingInvokeExpression', '')]

param (
   [Parameter(Mandatory=$false)][alias("path")][string]$pathoption = "",
   [Parameter(Mandatory=$false)][alias("type")][string]$typeoption = "",
   [switch]$help = $false,
   [switch]${skip-boost} = $false,
   [switch]${skip-packages} = $false,
   [switch]$quick = $false,
   [switch]$boostrelease = $false,
   [switch]$boostrootsubdir = $false
)

$scriptname="windowsdocs.ps1"
$pythonvirtenvpath="${HOME}\venvboostdocs"
$nvm_install_version="1.1.11"
$node_version="20.17.0"
$node_version_basic="20"

Set-PSDebug -Trace 1

if ($help) {

$helpmessage="
usage: $scriptname [-help] [-type TYPE] [-skip-boost] [-skip-packages] [-quick] [-boostrelease] [-boostrootsubdir] [path_to_library]

Builds library documentation.

optional arguments:
  -help                 Show this help message and exit
  -type TYPE            The `"type`" of build. Defaults to `"main`" which installs all standard boost prerequisites.
                        Another option is `"cppalv1`" which had installed the prerequisites used by boostorg/json and a few other similar libraries.
                        More `"types`" can be added in the future if your library needs a specific set of packages installed.
                        The type is usually auto-detected and doesn't need to be specified.
  -skip-boost           Skip downloading boostorg/boost and building b2 if you are certain those steps have already been done.
  -skip-packages        Skip installing all packages (pip, gem, apt, etc.) if you are certain that has already been done.
  -quick                Equivalent to setting both -skip-boost and -skip-packages. If not sure, then don't skip these steps.
  -boostrelease         Add the target //boostrelease to the doc build. This target is used when building production releases.
  -boostrootsubdir      If creating a boost-root directory, instead of placing it in ../ use a subdirectory.


standard arguments:
  path_to_library       Where the library is located. Defaults to current working directory.
"

Write-Output $helpmessage
exit 0
}
if ($quick) { ${skip-boost} = $true ; ${skip-packages} = $true ; }
if ($boostrelease) {
    ${boostreleasetarget} = "//boostrelease"
 }
else {
    ${boostreleasetarget} = ""
}

if ($boostrootsubdir) {
    ${BOOSTROOTRELPATH} = "."
    ${boostrootsubdiroption} = "yes"
  }
else {
    ${BOOSTROOTRELPATH} = ".."
}

Push-Location

function refenv {

    # Make `refreshenv` available right away, by defining the $env:ChocolateyInstall
    # variable and importing the Chocolatey profile module.
    # Note: Using `. $PROFILE` instead *may* work, but isn't guaranteed to.
    $env:ChocolateyInstall = Convert-Path "$((Get-Command choco).Path)\..\.."
    Import-Module "$env:ChocolateyInstall\helpers\chocolateyProfile.psm1"

    # refreshenv might delete path entries. Return those to the path.
    $originalpath=$env:PATH
    refreshenv
    $joinedpath="${originalpath};$env:PATH"
    $joinedpath=$joinedpath.replace(';;',';')
    $env:PATH = ($joinedpath -split ';' | Select-Object -Unique) -join ';'
    }

# git is required. In the unlikely case it's not yet installed, moving that part of the package install process
# here to an earlier part of the script:

if ( -Not ${skip-packages} ) {
    if ( -Not (Get-Command choco -errorAction SilentlyContinue) ) {
        Write-Output "Install chocolatey"
        Invoke-Expression ((new-object net.webclient).DownloadString('https://chocolatey.org/install.ps1'))
    }

    if ( -Not (Get-Command git -errorAction SilentlyContinue) ) {
        Write-Output "Install git"
        choco install -y --no-progress git
    }

    refenv
}

function DownloadWithRetry([string] $url, [string] $downloadLocation, [int] $retries)
{
    while($true)
    {
        try
        {
	    # Invoke-WebRequest $url -OutFile $downloadLocation
	    Start-BitsTransfer -Source $url -Destination $downloadLocation
            break
        }
        catch
        {
            $exceptionMessage = $_.Exception.Message
            Write-Output "Failed to download '$url': $exceptionMessage"
            if ($retries -gt 0) {
                $retries--
                Write-Output "Waiting 10 seconds before retrying. Retries left: $retries"
                Start-Sleep -Seconds 10

            }
            else
            {
                $exception = $_.Exception
                throw $exception
            }
        }
    }
}

if ($pathoption) {
    Write-Output "Library path set to $pathoption. Changing to that directory."
    Set-Location $pathoption
}
else
{
    $workingdir = Get-Location | Foreach-Object { $_.Path }
    Write-Output "Using current working directory $workingdir."
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
    Write-Output ""
    Write-Output "Set the path_to_library as the first command-line argument:"
    Write-Output ""
    Write-Output "$scriptname _path_to_library_"
    Write-Output ""
    Write-Output "Or change the working directory to that first."
    exit 1
}
else {
    Write-Output "REPONAME is $REPONAME"
}

$BOOST_SRC_FOLDER=git rev-parse --show-toplevel
if ( ! $LASTEXITCODE -eq 0)  {
    $BOOST_SRC_FOLDER="nofolder"
}
else {
    Write-Output "BOOST_SRC_FOLDER is $BOOST_SRC_FOLDER"
}

# The purpose of this is to allow nvm/npm/node to use a subdirectory of the library in CI, so the job is self-contained
# and doesn't use external directories.
# On WINDOWS, this has not yet been tested. It's not certain that it must be done, or if there are side-effects.
# Copying the logic from linuxdocs.sh. Since CI isn't usually done on Windows, it may not be important.
if ( ${boostrootsubdiroption} -eq "yes" ) {
    New-Item -Path "${BOOST_SRC_FOLDER}\"  -Name "tmp_home" -ItemType "directory"
    Set-Variable HOME "${BOOST_SRC_FOLDER}\tmp_home" -Force
}

$PARENTNAME=[io.path]::GetFileNameWithoutExtension($(git --git-dir $BOOST_SRC_FOLDER/../.git config --get remote.origin.url))
if ( $PARENTNAME -eq "boost" ) {
    Write-Output "Starting out inside boost-root"
    $BOOSTROOTLIBRARY="yes"
    $BOOSTROOTRELPATH=".."
}
else {
    $PARENTNAME=[io.path]::GetFileNameWithoutExtension($(git --git-dir $BOOST_SRC_FOLDER/../../.git config --get remote.origin.url))
    if ( $PARENTNAME -eq "boost" ) {
        Write-Output "Starting out inside boost-root"
        $BOOSTROOTLIBRARY="yes"
        $BOOSTROOTRELPATH="../.."
    }
    else {
        $PARENTNAME=[io.path]::GetFileNameWithoutExtension($(git --git-dir $BOOST_SRC_FOLDER/../../../.git config --get remote.origin.url))
        if ( $PARENTNAME -eq "boost" )
        {
            Write-Output "Starting out inside boost-root"
            $BOOSTROOTLIBRARY="yes"
            $BOOSTROOTRELPATH="../../.."
        }
        else {
            Write-Output "Not starting out inside boost-root"
            $BOOSTROOTLIBRARY="no"
            }
    }
}

# DECIDE THE TYPE

# Generally, boostorg/release-tools treats all libraries the same, meaning it installs one set of packages and executes b2.
# Therefore all libraries ought to build under 'main' and shouldn't need anything customized.

$all_types="main antora cppalv1"
# $cppalv1_types="json beast url http_proto socks_proto zlib"
$cppalv1_types="not_currently_used skipping_this"

if (! $typeoption ) {

    if (Test-Path "$BOOST_SRC_FOLDER\doc\build_antora.sh") {
        $typeoption="antora"
    }
    elseif ($cppalv1_types.contains($REPONAME)) {
        $typeoption="cppalv1"
    }
    else {
        $typeoption="main"
    }
}

Write-Output "Build type is $typeoption"

if ( ! $all_types.contains($typeoption)) {
    Write-Output "Allowed types are currently 'main', 'antora' and 'cppalv1'. Not $typeoption. Please choose a different option. Exiting."
    exit 1
}

$REPO_BRANCH=git rev-parse --abbrev-ref HEAD
Write-Output "REPO_BRANCH is $REPO_BRANCH"

if ( $REPO_BRANCH -eq "master" )
{
    $BOOST_BRANCH="master"
}
else
{
    $BOOST_BRANCH="develop"
}

Write-Output "BOOST_BRANCH is $BOOST_BRANCH"

Write-Output '==================================> INSTALL'

# graphviz package added for historical reasons, might not be used.

if ( -Not ${skip-packages} ) {

    if ( -Not (Get-Command choco -errorAction SilentlyContinue) ) {
        Write-Output "Install chocolatey"
        Invoke-Expression ((new-object net.webclient).DownloadString('https://chocolatey.org/install.ps1'))
    }
    choco install -y --no-progress rsync
    choco install -y --no-progress sed
    choco install -y --no-progress doxygen.install
    choco install -y --no-progress xsltproc
    choco install -y --no-progress docbook-bundle
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

    refenv

    if ($typeoption -eq "antora") {

        if ( -Not (Get-Command clang++ -errorAction SilentlyContinue) )
        {
            choco install -y --no-progress llvm
        }

        if ( -Not (Get-Command 7z -errorAction SilentlyContinue) )
        {
            choco install -y --no-progress 7zip.install
        }

        if ( -Not (Get-Command cmake -errorAction SilentlyContinue) )
        {
            choco install -y cmake --installargs 'ADD_CMAKE_TO_PATH=System' --apply-install-arguments-to-dependencies
        }

        if ( -Not (Get-Command ninja -errorAction SilentlyContinue) )
        {
            choco install -y ninja
            Expand-Archive -LiteralPath 'C:\ProgramData\chocolatey\lib\ninja\tools\ninja-win_x32.zip' -DestinationPath C:\windows\system32\
        }

        if ( -Not (Get-Command nvm -errorAction SilentlyContinue) )
          {
              # 1.1.12 doesn't allow reading stdout. Will be fixed in 1.1.13 supposedly.
              choco install -y --no-progress nvm.install --version ${nvm_install_version}
              Write-Output "NVM was just installed. Close this terminal window, and then restart the script."
              Write-Output "The process has not finished. Please open a new terminal window. And restart the script."
              exit 0
          }

        refenv

        if (nvm list | Select-String "${node_version}")
        {
            # Node already installed
            ForEach-Object 'foo'
        }
        else
        {
            nvm install $node_version
            nvm use $node_version_basic
        }

        npm install gulp-cli@2.3.0
        npm install @mermaid-js/mermaid-cli@10.5.1

    }

    if ($typeoption -eq "main") {
        $ghostversion="9.56.1"

        if (!(Test-Path "${pythonvirtenvpath}\Scripts\activate")) {
            python -m venv ${pythonvirtenvpath}
        }
        "${pythonvirtenvpath}\Scripts\activate"

        choco install -y --no-progress ghostscript --version $ghostversion
        choco install -y --no-progress texlive
        choco install -y --no-progress graphviz
        gem install public_suffix --version 4.0.7               # 4.0.7 from 2022 still supports ruby 2.5. Continue to use until ~2024.
        gem install css_parser --version 1.12.0                 # 1.12.0 from 2022 still supports ruby 2.5. Continue to use until ~2024.
        gem install asciidoctor --version 2.0.17
        gem install asciidoctor-pdf --version 2.3.4
        gem install asciidoctor-diagram --version 2.2.14
        gem install asciidoctor-multipage --version 0.0.18
        pip3 install docutils
        ## Invoke-WebRequest -O rapidxml.zip http://sourceforge.net/projects/rapidxml/files/latest/download
        # Invoke-WebRequest -O rapidxml.zip https://downloads.sourceforge.net/project/rapidxml/rapidxml/rapidxml%201.13/rapidxml-1.13.zip
        # unzip -n -d rapidxml rapidxml.zip
        #
        # pip3 had been using --user. what will happen without.
        pip3 install https://github.com/bfgroup/jam_pygments/archive/master.zip
        pip3 install Jinja2==3.1.2
        pip3 install MarkupSafe==2.1.1
        gem install pygments.rb --version 2.3.0
        pip3 install Pygments==2.13.0
        gem install rouge --version 4.0.0
        pip3 install Sphinx==5.2.1
        pip3 install --user git+https://github.com/pfultz2/sphinx-boost@8ad7d424c6b613864976546d801439c34a27e3f6
	# from dockerfile:
        pip3 install myst-parser==0.18.1
        pip3 install future==0.18.2
        pip3 install six==1.14.0

        refenv

	# ghostscript fixes
        $newpathitem="C:\Program Files\gs\gs$ghostversion\bin"
        if( (Test-Path -Path $newpathitem) -and -Not ( $env:Path -like "*$newpathitem*"))
        {
               $env:Path += ";$newpathitem"
        }

        $file1="C:\Program Files\gs\gs9.56.1\bin\gswin32c.exe"
        $file2="C:\Program Files\gs\gs9.56.1\bin\gswin64c.exe"
        if (-not(Test-Path -Path $file1 -PathType Leaf)) {
            New-Item -ItemType SymbolicLink -Path $file1 -Target $file2
        }

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
        $temp_path = $env:Path.Trim(";"," ")
        $env:Path = "${temp_path};${newpathitem}"
    }

    # Copy-Item "C:\Program Files\doxygen\bin\doxygen.exe" "C:\Windows\System32\doxygen.exe"

    if ( ( $typeoption -eq "cppalv1" ) -Or ($typeoption -eq "main" )) {

    Set-Location $BOOST_SRC_FOLDER
    Set-Location $BOOSTROOTRELPATH
    if ( -Not (Test-Path -Path "tmp") )
    {
        mkdir tmp
    }

    Set-Location tmp

    # Install saxon
    if ( -Not (Test-Path -Path "C:\usr\share\java\Saxon-HE.jar") )
    {
        $source = 'https://sourceforge.net/projects/saxon/files/Saxon-HE/9.9/SaxonHE9-9-1-4J.zip/download'
        $destination = 'saxonhe.zip'
        if ( Test-Path -Path $destination)
        {
            Remove-Item $destination
        }
        if ( Test-Path -Path "saxonhe")
        {
            Remove-Item saxonhe -Recurse -Force
        }

        # Start-BitsTransfer -Source $source -Destination $destination
	DownloadWithRetry -url $source -downloadLocation $destination -retries 6
        Expand-Archive .\saxonhe.zip
        Set-Location saxonhe
        if ( -Not (Test-Path -Path "C:\usr\share\java") )
        {
            mkdir "C:\usr\share\java"
        }
        Copy-Item saxon9he.jar Saxon-HE.jar
        Copy-Item Saxon-HE.jar "C:\usr\share\java\"
    }
}
}

# In the above 'packages' section a python virtenv was created. Activate it, if that has not been done already.

if ( Test-Path "${pythonvirtenvpath}\Scripts\activate" ) {
    "${pythonvirtenvpath}\Scripts\activate"
}

if ( $typeoption -eq "antora" ) {
    nvm use $node_version_basic
    }

# re-adding the path fix from above, even if skip-packages was set.
$newpathitem="C:\Program Files\Git\usr\bin"
if( (Test-Path -Path $newpathitem) -and -Not ( $env:Path -like "*$newpathitem*"))
    {
        $temp_path = $env:Path.Trim(";"," ")
        $env:Path = "${temp_path};${newpathitem}"

    }

Set-Location $BOOST_SRC_FOLDER

function getlibrarypath {
   param (
       $localreponame
       )
   $locallibrarypath=git config --file .gitmodules --get submodule.$localreponame.path
   if ($LASTEXITCODE -ne 0)  {
       $locallibrarypath="libs/$localreponame"
       $global:LASTEXITCODE=0
   }
   Write-Output "$locallibrarypath"
   }

if ( ${skip-boost} ) {
    # skip-boost was set. A reduced set of actions.
    if ( $BOOSTROOTLIBRARY -eq "yes" ) {
        Set-Location $BOOSTROOTRELPATH
        $Env:BOOST_ROOT=Get-Location | Foreach-Object { $_.Path }
        Write-Output "Env:BOOST_ROOT is $Env:BOOST_ROOT"
        $librarypath=getlibrarypath $REPONAME
    }

    else {
	Set-Location $BOOSTROOTRELPATH
        if ( -Not (Test-Path -Path "boost-root") ) {
            Write-Output "boost-root missing. Rerun this script without the -skip-boost or -quick option."
            exit 1
	    }
        else {
            Set-Location boost-root
            $Env:BOOST_ROOT=Get-Location | Foreach-Object { $_.Path }
            Write-Output "Env:BOOST_ROOT is $Env:BOOST_ROOT"
            $librarypath=getlibrarypath $REPONAME

            if (Test-Path -Path "$librarypath")
            {
                Remove-Item $librarypath -Force -Recurse
            }
            # Copy-Item -Exclude boost-root -Path $BOOST_SRC_FOLDER -Destination $librarypath -Recurse -Force
            robocopy $BOOST_SRC_FOLDER $librarypath /MIR /XD boost-root | Out-Null
            }
        }
    }
else {
    # skip-boost was not set. The standard flow.
    #
    if ( $BOOSTROOTLIBRARY -eq "yes" ) {
        Write-Output "updating boost-root"
        Set-Location $BOOSTROOTRELPATH
        git checkout $BOOST_BRANCH
        git pull
        $Env:BOOST_ROOT=Get-Location | Foreach-Object { $_.Path }
        Write-Output "Env:BOOST_ROOT is $Env:BOOST_ROOT"
        $librarypath=getlibrarypath $REPONAME
    }
    else {
	Set-Location $BOOSTROOTRELPATH
        if ( -Not (Test-Path -Path "boost-root") ) {
            Write-Output "cloning boost-root"
            git clone -b $BOOST_BRANCH https://github.com/boostorg/boost.git boost-root --depth 1
            Set-Location boost-root
        }
        else {
            Write-Output "updating boost-root"
            Set-Location boost-root
            git checkout $BOOST_BRANCH
            git pull
        }

        $Env:BOOST_ROOT=Get-Location | Foreach-Object { $_.Path }
        Write-Output "Env:BOOST_ROOT is $Env:BOOST_ROOT"
        $librarypath=getlibrarypath $REPONAME

        if (Test-Path -Path "$librarypath")
        {
            Remove-Item $librarypath -Force -Recurse
        }
        # Copy-Item -Exclude boost-root -Path $BOOST_SRC_FOLDER -Destination $librarypath -Recurse -Force
        robocopy $BOOST_SRC_FOLDER $librarypath /MIR /XD boost-root | Out-Null
    }
}

# for Alan's antora scripts:
$Env:BOOST_SRC_DIR=$Env:BOOST_ROOT

if ( -Not ${skip-packages} ) {
    mkdir build
    Set-Location build
    if ( -Not (Test-Path -Path docbook-xsl.zip) ) {
        Invoke-Webrequest -usebasicparsing -Outfile docbook-xsl.zip -uri https://github.com/docbook/xslt10-stylesheets/releases/download/release%2F1.79.2/docbook-xsl-1.79.2.zip
    }
    if ( -Not (Test-Path -Path docbook-xsl) ) {
        unzip -n -d docbook-xsl docbook-xsl.zip
    }
    if ( -Not (Test-Path -Path docbook-xml.zip) ) {
        Invoke-WebRequest -O docbook-xml.zip http://www.docbook.org/xml/4.5/docbook-xml-4.5.zip
    }
    if ( -Not (Test-Path -Path docbook-xml) ) {
        unzip -n -d docbook-xml docbook-xml.zip
    }
    Set-Location ..
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
  if ( -Not ( ${typeoption} -eq "antora" ) ) {
    git submodule update --init libs/context
    git submodule update --init tools/boostbook
    git submodule update --init tools/boostdep
    git submodule update --init tools/docca
    git submodule update --init tools/quickbook
    git submodule update --init tools/build
    git submodule update --init tools/boostlook

    if ($typeoption -eq "main") {
        git submodule update --init tools/auto_index
        python tools/boostdep/depinst/depinst.py ../tools/auto_index
    }

    # Recopy the library, if it was overwritten by the submodule updates that just occurred.
    if ( -Not ($BOOSTROOTLIBRARY -eq "yes") ) {
        if (Test-Path -Path "$librarypath")
        {
            Remove-Item $librarypath -Force -Recurse
        }
        # Copy-Item -Exclude boost-root -Path $BOOST_SRC_FOLDER -Destination $librarypath -Recurse -Force
        robocopy $BOOST_SRC_FOLDER $librarypath /MIR /XD boost-root | Out-Null
    }

    $matcher='\.saxonhe_jar = \$(jar\[1\]) ;$'
    $replacer='.saxonhe_jar = $(jar[1]) ;  .saxonhe_jar = \"/usr/share/java/Saxon-HE.jar\" ;'
    sed -i "s~$matcher~$replacer~" tools/build/src/tools/saxonhe.jam

    python tools/boostdep/depinst/depinst.py ../tools/quickbook

    Write-Output "Running bootstrap.bat"
    ./bootstrap.bat

    Write-Output "Running ./b2 headers"
    ./b2 headers
}}
else {
Write-Output "Skipping those submodules"
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
Write-Output "new env:Path is $env:Path"

Write-Output '==================================> COMPILE'

# exceptions:

# $toolslist="auto_index bcp boostbook boostdep boost_install build check_build cmake docca inspect litre quickbook"
$toolslist = @("auto_index", "bcp", "boostbook", "boostdep", "boost_install", "build", "check_build", "cmake", "docca", "inspect", "litre", "quickbook")
if ( ($toolslist.contains($REPONAME)) -and ("$boostreleasetarget" -eq "//boostrelease" )) {
    Write-Output "The boost tools do not have a //boostrelease target in their Jamfile. Run the build without -boostrelease instead."
    exit 0
}

if (($librarypath -match "numeric") -and ($boostreleasetarget -eq "//boostrelease")) {
    Write-Output "The //boostrelease version of the numeric libraries should be run from the top level. That is, in the numeric/ directory. For this script it is a special case. TODO."
    exit 0
}

if ( -Not (Test-Path -Path $librarypath/doc/ )) {
    Write-Output "doc/ folder is missing for this library. No need to compile. Exiting."
    exit 0
}

if ( (Test-Path -Path $librarypath/doc/build_antora.sh ) -or (Test-Path -Path $librarypath/doc/Jamfile) -or (Test-Path -Path $librarypath/doc/Jamfile.v2) -or (Test-Path -Path $librarypath/doc/Jamfile.v3) -or (Test-Path -Path $librarypath/doc/Jamfile.jam) -or (Test-Path -Path $librarypath/doc/build.jam)) {
  }
else {
    Write-Output "doc/Jamfile or similar is missing for this library. No need to compile. Exiting."
    exit 0
}

if ("$REPONAME" -eq "geometry") {
    Write-Output "In geometry exception. running ./b2 $librarypath/doc/src/docutils/tools/doxygen_xml2qbk"
    ./b2 $librarypath/doc/src/docutils/tools/doxygen_xml2qbk/
    Write-Output "running Get-Location"
    Get-Location
    Write-Output "running dir dist\bin"
    Get-ChildItem dist\bin
    Write-Output "checking path"
    Write-Output $env:Path
    # moving this to PATH var
    # Write-Output "running cp dist/bin/doxygen_xml2qbk C:\windows\system32"
    # cp dist/bin/doxygen_xml2qbk.exe C:\windows\system32
    try { (Get-Command doxygen_xml2qbk.exe).Path }
    catch { Write-Output "couldn't find doxygen_xml2qbk.exe" }
}

# the main compilation:

if ($typeoption -eq "antora") {
    $library_is_submodule=""
    $timestamp=""
    if ( Test-Path "${librarypath}\.git" -PathType Leaf ) {
        $library_is_submodule="true"
        $timestamp=[int](Get-Date -UFormat %s -Millisecond 0)
        Write-Output "Antora will not run on a git module. Copying to /tmp"
        New-Item -Path "c:\" -Name "tmp" -ItemType "directory"  -Force
        New-Item -Path "c:\tmp" -Name "builddocs-${timestamp}"  -ItemType "directory"  -Force
        New-Item -Path "c:\tmp\builddocs-${timestamp}" -Name "${REPONAME}" -ItemType "directory"  -Force
        robocopy "${librarypath}" "C:\tmp\builddocs-${timestamp}\${REPONAME}" /MIR /np /nfl
        Set-Location "C:\tmp\builddocs-${timestamp}\${REPONAME}"
        Get-ChildItem
        Remove-Item .git -Force
        git init
        git config user.email "test@example.com"
        git config user.name "test"
        git add .
        git commit -m "initial commit"
        Set-Location doc
    }
    else {
     Set-Location ${librarypath}/doc
      }
	dos2unix .\build_antora.sh
    & 'C:\Program Files\Git\bin\bash.exe' .\build_antora.sh
    if ( ! $LASTEXITCODE -eq 0)  {
         Write-Output "build_antora failed. exiting."
         exit 1
    }

    if ( -Not (Test-Path -Path "build\site\index.html") ) {
        Write-Output "build\site\index.html is missing. It is likely that antora did not complete successfully."
        exit 1
    }

    if ( $library_is_submodule -eq "true" ) {
        New-Item -Path "${BOOST_ROOT}\${librarypath}\doc\" -Name "build" -ItemType "directory"  -Force
        robocopy build "${BOOST_ROOT}\${librarypath}\doc\build" /MIR /np /nfl
		Write-Output "The exit code of robocopy was $LASTEXITCODE."
    }
}
elseif ($typeoption -eq "main") {

    $asciidoctorpath=(Get-Command asciidoctor).Path -replace '\\', '/'
    $autoindexpath="$Env:BOOST_ROOT/build/dist/bin/auto_index.exe"
    $autoindexpath=$autoindexpath -replace '\\', '/'
    $quickbookpath="$Env:BOOST_ROOT/build/dist/bin/quickbook.exe"
    $quickbookpath=$quickbookpath -replace '\\', '/'

    ./b2 -q -d0 --build-dir=build --distdir=build/dist tools/quickbook tools/auto_index
    $content="using quickbook : `"$quickbookpath`" ; using auto-index : `"$autoindexpath`" ; using docutils ; using doxygen : `"/Program Files/doxygen/bin/doxygen.exe`" ; using boostbook ; using asciidoctor : `"$asciidoctorpath`" ; using saxonhe ;"
    $filename="$Env:BOOST_ROOT\tools\build\src\user-config.jam"
    [IO.File]::WriteAllLines($filename, $content)
    ./b2 -d 2 $librarypath/doc${boostreleasetarget}
     if ( ! $LASTEXITCODE -eq 0)  {
         Write-Output "doc build failed. exiting."
         exit 1
     }
}
elseif ($typeoption -eq "cppalv1") {
    $content="using doxygen : `"/Program Files/doxygen/bin/doxygen.exe`" ; using boostbook ; using saxonhe ;"
    $filename="$Env:BOOST_ROOT\tools\build\src\user-config.jam"
    [IO.File]::WriteAllLines($filename, $content)
    ./b2 -d 2 $librarypath/doc${boostreleasetarget}
     if ( ! $LASTEXITCODE -eq 0)  {
         Write-Output "doc build failed. exiting."
         exit 1
     }
}

if ( $typeoption -eq "antora") {
    $result_sub_path="doc/build/site/"
   }
else {
    $result_sub_path="doc/html/"
}

if ($BOOSTROOTLIBRARY -eq "yes") {
    Write-Output ""
    Write-Output "Build completed. View the results in $librarypath/$result_sub_path"
    Write-Output ""
}
else {
    if ($BOOSTROOTRELPATH -eq ".") {
        $pathfiller="/"
    }
    else {
        $pathfiller="/${BOOSTROOTRELPATH}/"
    }
    Write-Output ""
    Write-Output "Build completed. View the results in ${BOOST_SRC_FOLDER}${pathfiller}boost-root/$librarypath/$result_sub_path"
    Write-Output ""
}

Pop-Location
echo "At the end of $scriptname"
exit 0
