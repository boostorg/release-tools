## Building the documentation for specific boost libraries

Each boost libraries contains documentation in the doc/ folder. For example, https://github.com/boostorg/core has documentation in core/doc/. The format is generally [quickbook](https://www.boost.org/doc/libs/master/doc/html/quickbook.html) and needs to be compiled into html. The scripts here accomplish that.

There are different possible configurations when building the docs:

Option 1. Start out with one boost library, and nothing else.

A new boost-root directory will be generated for you, next to the current repo, (in the location ../boost-root)  and the docs will be output to ../boost-root/libs/_name-of-this-repo_/doc/html

or

Option 2. You have already set up boost-root.

The repo has already been placed in boost-root/libs/_name-of-this-repo_, and that's where you will run the build. In that case, the docs will be output in the current directory, such as _name-of-this-repo_/doc/html.  The existing boost-root will be used.

Either of the above choices are possible. The build scripts detect if they are being run from a boost-root or not.

That said, it is preferable to start outside of boost-root when testing modifications to core boost libraries in order to avoid complications with boostdep.

In either case, always start by checking out code from git. Begin the process with a `git clone` command. (Not by downloading a complete boost archive, which may already have compiled documentation included).     

In order to build the documentation, refer to the appropriate sections below.

One of the main actions of these scripts is to install _packages_. Depending on the operating system this may be using apt, brew, choco, pip, or a different package manager. Usually this is perfectly fine. However, If you are concerned about package conflicts on your local machine, run the installation in a docker container or a separate cloud server to isolate the build process. The script will not install a C++ compiler, since there are many choices in that realm, so make sure a compiler is available.

## Linux

There various ways to run the script. One method is to run the script from the current location, and tell it where the docs are:
```
./linuxdocs.sh _path_to_boost_library_
```
Another method which might be easier is to copy the script into location in $PATH, so it can be run anywhere. Then, switch to the library's directory.
```
cp linuxdocs.sh /usr/local/bin/
which linuxdocs.sh
cd _path_to_boost_library_
linuxdocs.sh
```

## MacOS

There various ways to run the script. One method is to run the script from the current location, and tell it where the docs are:
```
./macosdocs.sh _path_to_boost_library_
```
Another method which might be easier is to copy the script into location in $PATH, so it can be run anywhere. Then, switch to the library's directory.
```
cp macosdocs.sh /usr/local/bin/
which macosdocs.sh
cd _path_to_boost_library_
macosdocs.sh
```

## Windows

There various ways to run the script. One method is to run the script from the current location, and tell it where the docs are:
```
.\windowsdocs.ps1 _path_to_boost_library_
```
Another method which might be easier is to copy the script into location in $PATH, so it can be run anywhere. Then, switch to the library's directory.
```
cp windowsdocs.ps1 C:\windows\system32
where windowsdocs.ps1
cd _path_to_boost_library_
windowsdocs.ps1
```

windowsdocs.ps1 requires a version of Visual Studio C++ to be available. Optionally, see the scripts here in the [other/](other/) directory such as `windows-2022-clang.ps1` for a method to install that.  
&nbsp;  
&nbsp;  
Further discussion about a small number of issues affecting certain libraries is continued in [compatibility.md](compatibility.md)
