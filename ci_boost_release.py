#!/usr/bin/env python

# Copyright Rene Rivera 2016
#
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at
# http://www.boost.org/LICENSE_1_0.txt)

from __future__ import print_function

import os.path
import sys
import time
import shutil
import site
import hashlib
import subprocess
import os
import glob
from jinja2 import Environment, BaseLoader
import json
import pprint
from collections import defaultdict
import re

from ci_boost_common import main, utils, script_common, parallel_call

# Check python version
if sys.version_info[0] == 2:
    pythonversion = "2"
    pythonbinary = "python2"
else:
    pythonversion = "3"
    pythonbinary = "python3"


def generatehtmlpages(source_dir, build_dir):
    #
    # Versions of ci_boost_release.py from 2016-2021 were calling http://www.boost.org/doc/generate.php
    # to download and update index.html and libs/libraries.htm in the archive bundles.
    # If the boost website is being redesigned, generate.php will eventually be deprecated and removed.
    # It will be convenient to have a self-sufficient release-tool that doesn't depend on the website.
    #
    # This function creates the index.html and libs/libraries.htm files.
    #

    boostlibrarycategories = defaultdict(dict)
    boostlibrarycategories["Algorithms"]["title"] = "Algorithms"
    boostlibrarycategories["Workarounds"]["title"] = "Broken compiler workarounds"
    boostlibrarycategories["Concurrent"]["title"] = "Concurrent Programming"
    boostlibrarycategories["Containers"]["title"] = "Containers"
    boostlibrarycategories["Correctness"]["title"] = "Correctness and testing"
    boostlibrarycategories["Data"]["title"] = "Data structures"
    boostlibrarycategories["Domain"]["title"] = "Domain Specific"
    boostlibrarycategories["Error-handling"]["title"] = "Error handling and recovery"
    boostlibrarycategories["Function-objects"][
        "title"
    ] = "Function objects and higher-order programming"
    boostlibrarycategories["Generic"]["title"] = "Generic Programming"
    boostlibrarycategories["Image-processing"]["title"] = "Image processing"
    boostlibrarycategories["IO"]["title"] = "Input/Output"
    boostlibrarycategories["Inter-language"]["title"] = "Inter-language support"
    boostlibrarycategories["Iterators"]["title"] = "Iterators"
    boostlibrarycategories["Emulation"]["title"] = "Language Features Emulation"
    boostlibrarycategories["Math"]["title"] = "Math and numerics"
    boostlibrarycategories["Memory"]["title"] = "Memory"
    boostlibrarycategories["Parsing"]["title"] = "Parsing"
    boostlibrarycategories["Patterns"]["title"] = "Patterns and Idioms"
    boostlibrarycategories["Preprocessor"]["title"] = "Preprocessor Metaprogramming"
    boostlibrarycategories["Programming"]["title"] = "Programming Interfaces"
    boostlibrarycategories["State"]["title"] = "State Machines"
    boostlibrarycategories["String"]["title"] = "String and text processing"
    boostlibrarycategories["System"]["title"] = "System"
    boostlibrarycategories["Metaprogramming"]["title"] = "Template Metaprogramming"
    boostlibrarycategories["Miscellaneous"]["title"] = "Miscellaneous"

    for category in boostlibrarycategories:
        boostlibrarycategories[category]["libraries"] = []
    # libraries in libs/* we should skip
    boostlibrariestoskip = ["libs/detail", "libs/numeric", "libs/winapi"]
    # libraries not in libs/* we should add
    boostlibrariestoadd = [
        "libs/numeric/conversion",
        "libs/numeric/interval",
        "libs/numeric/odeint",
        "libs/numeric/ublas",
        "libs/spirit/classic",
        "libs/spirit/repository",
    ]

    def names_to_string(names):
        if isinstance(names, list):
            last_name = names.pop()
            if len(names) > 1:
                return ", ".join(names) + ", and " + last_name
            elif len(names) == 1:
                return names[0] + " and " + last_name
            else:
                return last_name
        else:
            return names

    # Discover boost version
    with open("Jamroot", "r", encoding="utf-8") as file:
        file_contents = file.read()
        m = re.search("constant BOOST_VERSION : (.*) ;", file_contents)
        source_version = m.group(1)
        source_version_underscores = source_version.replace(".", "_")
    release_notes_url = (
        "https://www.boost.org/users/history/version_"
        + source_version_underscores
        + ".html"
    )
    # Ingest all boost library metadata:
    allmetadata = {}
    all_libraries = []
    all_libraries.extend(boostlibrariestoadd)

    # add all libraries in libs/*
    for directoryname in glob.iglob("libs/*", recursive=False):
        if (
            os.path.isdir(directoryname)
            and (directoryname not in boostlibrariestoskip)
            and os.path.isfile(directoryname + "/meta/libraries.json")
        ):  # filter dirs
            all_libraries.append(directoryname)
    # get meta data from each library
    for directoryname in all_libraries:
        librarypath = re.sub(r"^libs/", "", directoryname)
        with open(
            directoryname + "/meta/libraries.json", "r", encoding="utf-8"
        ) as file:
            file_contents = file.read()
            data = json.loads(file_contents)
            if type(data) is dict:
                key = data["key"]
                allmetadata[key] = data
                allmetadata[key]["librarypath"] = librarypath
            if type(data) is list:
                for item in data:
                    key = item["key"]
                    allmetadata[key] = item
                    allmetadata[key]["librarypath"] = librarypath
    # pprint.pprint(allmetadata)
    # quit()

    # Identify documentation paths and generate author strings
    for key, value in allmetadata.items():
        # fix documentation
        # if not "documentation" in value:
        #     allmetadata[key]["documentation"]=value["librarypath"] + "/index.html"
        if not "documentation" in value:
            allmetadata[key]["documentation_modified"] = (
                value["librarypath"] + "/index.html"
            )
        else:
            allmetadata[key]["documentation_modified"] = (
                value["librarypath"] + "/" + allmetadata[key]["documentation"]
            )
            if allmetadata[key]["documentation_modified"].endswith("/"):
                allmetadata[key]["documentation_modified"] += "index.html"
        # removes any trailing whitespace and period from the description
        allmetadata[key]["description_modified"] = re.sub(
            r"\s*\.\s*$", "", allmetadata[key]["description"]
        )
        # create string with authors name
        allmetadata[key]["authors_modified"] = names_to_string(
            allmetadata[key]["authors"]
        )

    # Specific fixes which should be propagated upstream:

    # allmetadata['histogram']['name']="Histogram"            # sent pr. done.
    # allmetadata['parameter_python']['name']="Parameter Python Bindings"  # sent pr. done.
    # allmetadata["process"]["name"] = "Process"  # sent pr. done.
    # allmetadata['stl_interfaces']['name']="Stl_interfaces"  # sent pr. done.
    # allmetadata["utility/string_ref"]["name"] = "String_ref"  # sent pr
    # allmetadata["compatibility"]["category"] = ["Workarounds"]  # sent pr. done.
    # allmetadata['config']['category']=["Workarounds"]       # sent pr. done.
    # allmetadata['leaf']['category']=["Miscellaneous"]       # sent pr. done. obsolete.
    allmetadata["logic/tribool"]["documentation_modified"] = "../doc/html/tribool.html"

    # determine libraries per category
    for category in boostlibrarycategories:
        for library in allmetadata:
            if category in allmetadata[library]["category"]:
                boostlibrarycategories[category]["libraries"].append(library)
            # sort libraries in this category by name
            boostlibrarycategories[category]["libraries"].sort(
                key=lambda x: allmetadata[x]["name"].lower()
            )

    # sort allmetadata by name
    sorted_tuples = sorted(allmetadata.items(), key=lambda x: x[1]["name"].lower())
    allmetadata = {k: v for k, v in sorted_tuples}

    # generate index files
    for sourcefilename in ["index.html", "libs/libraries.htm"]:
        sourcefile = os.path.join(source_dir, sourcefilename)
        with open(sourcefile, "r", encoding="utf-8") as file:
            file_contents = file.read()
        if sourcefilename == "libs/libraries.htm":
            file_contents = file_contents.replace("charset=iso-8859-1", "charset=utf-8")
            file_contents = file_contents.replace(
                "{{#categorized}}\n",
                '{% for key, value in boostlibrarycategories.items() %}{% set category = key %}{% set name = key %}{% set title = value["title"] %}',
            )
            file_contents = file_contents.replace("{{/categorized}}\n", "{% endfor %}")
            file_contents = file_contents.replace(
                "{{#alphabetic}}\n",
                '{% for key, value in allmetadata.items() %}{% set name = value["name"] %}{% set authors = value["authors_modified"] %}{% set link = value["documentation_modified"] %}{% set description = value["description_modified"] %}',
            )
            file_contents = file_contents.replace("{{/alphabetic}}\n", "{% endfor %}")
            file_contents = file_contents.replace(
                "{{#libraries}}\n",
                '{% for library in boostlibrarycategories[category]["libraries"] %}{% set name = allmetadata[library]["name"] %}{% set authors = allmetadata[library]["authors_modified"] %}{% set link = allmetadata[library]["documentation_modified"] %}{% set description = allmetadata[library]["description_modified"] %}',
            )
            file_contents = file_contents.replace("{{/libraries}}\n", "{% endfor %}")
            file_contents = file_contents.replace("{{#authors}}", "")
            file_contents = file_contents.replace("{{/authors}}", "")
            string = """{{! This is a template for the library list. See the generated file at:
    http://www.boost.org/doc/libs/develop/libs/libraries.htm
}}
"""
            file_contents = file_contents.replace(string, "")
        elif sourcefilename == "index.html":
            string = """      {{#is_develop}}Development Snapshot{{/is_develop}}
"""
            file_contents = file_contents.replace(string, "")
            string = """
  {{#unreleased_lib_count}}
  <p>
  {{#is_develop}}This development snapshot{{/is_develop}}
  {{^is_develop}}Boost {{minor_release}}{{/is_develop}}
  includes {{unreleased_lib_count}} new
  {{#unreleased_library_plural}}libraries{{/unreleased_library_plural}}
  {{^unreleased_library_plural}}library{{/unreleased_library_plural}}
  ({{#unreleased_libs}}{{#index}}, {{/index}}<a href="{{link}}">{{name}}</a>{{/unreleased_libs}})
  as well as updates to many existing libraries.
  {{/unreleased_lib_count}}
  {{^unreleased_lib_count}}"""
            file_contents = file_contents.replace(string, "")
            string = """  {{/unreleased_lib_count}}
"""
            file_contents = file_contents.replace(string, "")
            file_contents = file_contents.replace("{{^is_develop}}", "")
            file_contents = file_contents.replace("{{/is_develop}}", "")
        # print(file_contents)
        # quit()
        rtemplate = Environment(loader=BaseLoader, autoescape=True).from_string(
            file_contents
        )
        data = rtemplate.render(
            release_notes_url=release_notes_url,
            version=source_version,
            allmetadata=allmetadata,
            boostlibrarycategories=boostlibrarycategories,
        )

        # Post processing
        data = data.replace(
            "Determines the type of a function call expression, from ",
            "Determines the type of a function call expression",
        )
        data = data.replace(
            "idiosyncrasies; not intended for library users, from ",
            "idiosyncrasies; not intended for library users",
        )
        data = data.replace(
            "makes the standard integer types safely available in namespace boost without placing any names in namespace std, from ",
            "makes the standard integer types safely available in namespace boost without placing any names in namespace std",
        )
        # print(data)
        destfile = os.path.join(build_dir, sourcefilename)
        utils.makedirs(os.path.dirname(destfile))
        with open(destfile, "w", encoding="utf-8") as f:
            print(data, file=f)


class script(script_common):
    """
    Main script to build/test Boost C++ Libraries continuous releases. This base
    is not usable by itself, as it needs some setup for the particular CI
    environment before execution.
    """

    archive_tag = "-snapshot"

    def __init__(self, ci_klass, **kargs):
        os.environ["PATH"] += os.pathsep + os.path.join(site.getuserbase(), "bin")
        utils.log("PATH = %s" % (os.environ["PATH"]))
        script_common.__init__(self, ci_klass, **kargs)

    def init(self, opt, kargs):
        kargs = super(script, self).init(opt, kargs)

        opt.add_option(
            "--eol",
            help="type of EOLs to check out files as for packaging (LF or CRLF)",
        )
        self.eol = os.getenv("EOL", os.getenv("RELEASE_BUILD", "LF"))

        opt.add_option("--mode", help="mode ('build' or 'check', default 'build')")
        self.mode = os.getenv("MODE", "build")

        opt.add_option(
            "--build-dir",
            help="override the build dir (default ../build)",
            default=None,
        )
        self.build_dir = None

        opt.add_option(
            "--releases-dir", help="override the release dir (default ..)", default=None
        )
        self.releases_dir = None

        return kargs

    def start(self):
        super(script, self).start()
        # The basename we will use for the release archive.
        self.boost_release_name = "boost_" + self.boost_version.replace(".", "_")

    # Common test commands in the order they should be executed..

    def command_info(self):
        super(script, self).command_info()
        utils.log("ci_boost_release: eol='%s', mode='%s'" % (self.eol, self.mode))
        utils.check_call("xsltproc", "--version")

    def command_install(self):
        super(script, self).command_install()
        # These dependencies are installed in the build dir
        self.command_install_rapidxml()
        self.command_install_docbook()
        # Host dependencies
        self.command_install_docutils()
        self.command_install_sphinx()
        self.command_install_asciidoctor()

    def command_install_rapidxml(self):
        os.chdir(self.build_dir)
        # We use RapidXML for some doc building tools.
        if not os.path.exists(os.path.join(self.build_dir, "rapidxml.zip")):
            utils.check_call(
                "wget",
                "-O",
                "rapidxml.zip",
                "http://sourceforge.net/projects/rapidxml/files/latest/download",
            )
            utils.check_call("unzip", "-n", "-d", "rapidxml", "rapidxml.zip")

    def command_install_docutils(self):
        os.chdir(self.build_dir)
        # Need docutils for building some docs.
        utils.check_call("pip", "install", "--user", "docutils==0.12")
        os.chdir(self.root_dir)

    def command_install_sphinx(self):
        os.chdir(self.build_dir)
        # Need Sphinx for building some docs (ie boost python).
        utils.make_file(
            os.path.join(self.build_dir, "constraints.txt"), "Sphinx==1.5.6"
        )
        utils.check_call("pip", "install", "--user", "Sphinx==1.5.6")
        utils.check_call("pip", "install", "--user", "sphinx-boost==0.0.3")
        utils.check_call(
            "pip",
            "install",
            "--user",
            "-c",
            os.path.join(self.build_dir, "constraints.txt"),
            "git+https://github.com/rtfd/recommonmark@50be4978d7d91d0b8a69643c63450c8cd92d1212",
        )
        os.chdir(self.root_dir)

    def command_install_docbook(self):
        os.chdir(self.build_dir)
        # Local DocBook schema and stylesheets.
        if not os.path.exists(os.path.join(self.build_dir, "docbook-xml.zip")):
            utils.check_call(
                "wget",
                "-O",
                "docbook-xml.zip",
                "http://www.docbook.org/xml/4.5/docbook-xml-4.5.zip",
            )
            utils.check_call("unzip", "-n", "-d", "docbook-xml", "docbook-xml.zip")
        if not os.path.exists(os.path.join(self.build_dir, "docbook-xsl.zip")):
            utils.check_call(
                "wget",
                "-O",
                "docbook-xsl.zip",
                "https://sourceforge.net/projects/docbook/files/docbook-xsl/1.79.1/docbook-xsl-1.79.1.zip/download",
            )
            utils.check_call("unzip", "-n", "-d", "docbook-xsl", "docbook-xsl.zip")

    def command_install_asciidoctor(self):
        os.chdir(self.build_dir)
        if os.geteuid() != 0:
            os.environ["GEM_HOME"] = os.path.join(self.build_dir, ".gems")
            os.environ["PATH"] += os.pathsep + os.path.join(
                self.build_dir, ".gems", "bin"
            )
        utils.check_call("gem", "install", "asciidoctor", "--version", "1.5.8")
        utils.check_call("asciidoctor", "--version")
        utils.check_call("gem", "install", "rouge")
        if pythonversion == "2":
            utils.check_call("gem", "install", "pygments.rb", "--version", "1.2.1")
        else:
            utils.check_call("gem", "install", "pygments.rb", "--version", "2.1.0")
        utils.check_call("pip", "install", "--user", "Pygments==2.1")
        utils.check_call(
            "pip",
            "install",
            "--user",
            "https://github.com/bfgroup/jam_pygments/archive/master.zip",
        )
        os.chdir(self.root_dir)

    @staticmethod
    def parse_semver(s):
        parts = s.split(".")
        try:
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0
        except (ValueError, IndexError):
            return None
        return major, minor, patch

    @staticmethod
    def is_semver_compatible(a, b):
        if a is None:
            return b is None
        if type(a) is str:
            a = script.parse_semver(a)
        if type(b) is str:
            b = script.parse_semver(b)
        if a[0] > 0:
            return a[0] == b[0]
        elif a[1] > 0:
            return a[1] == b[1]
        else:
            return a[2] == b[2]

    def command_before_build(self):
        super(script, self).command_before_build()
        # Fetch the rest of the Boost submodules in the appropriate
        # EOL style.
        if self.eol == "LF":
            utils.check_call("git", "config", "--global", "core.eol", "lf")
            utils.check_call("git", "config", "--global", "core.autocrlf", "input")
        else:
            utils.check_call("git", "config", "--global", "core.eol", "crlf")
            utils.check_call("git", "config", "--global", "core.autocrlf", "true")
        utils.check_call("git", "rm", "--quiet", "--cache", "-r", ".")
        utils.check_call("git", "reset", "--quiet", "--hard", "HEAD")
        utils.check_call(
            "git",
            "submodule",
            "--quiet",
            "foreach",
            "--recursive",
            "git",
            "rm",
            "--quiet",
            "--cache",
            "-r",
            ".",
        )
        utils.check_call(
            "git",
            "submodule",
            "--quiet",
            "foreach",
            "--recursive",
            "git",
            "reset",
            "--quiet",
            "--hard",
            "HEAD",
        )

    def command_build(self):
        super(script, self).command_build()
        # Build a packaged release. This involves building a fresh set
        # of docs and selectively packging parts of the tree. We try and
        # avoid creating extra files in the base tree to avoid including
        # extra stuff in the archives. Which means that we reset the git
        # tree state to cleanup after building.

        # Set up where we will "install" built tools.
        utils.makedirs(os.path.join(self.build_dir, "dist", "bin"))
        os.environ["PATH"] = (
            os.path.join(self.build_dir, "dist", "bin") + ":" + os.environ["PATH"]
        )
        os.environ["BOOST_BUILD_PATH"] = self.build_dir

        # Bootstrap Boost Build engine.
        os.chdir(os.path.join(self.root_dir, "tools", "build"))
        cxx_flags = (os.getenv("CXX", ""), os.getenv("CXXFLAGS", ""))
        os.environ["CXX"] = ""
        os.environ["CXXFLAGS"] = ""
        utils.check_call("./bootstrap.sh")
        shutil.copy2("b2", os.path.join(self.build_dir, "dist", "bin", "b2"))
        os.environ["CXX"] = cxx_flags[0]
        os.environ["CXXFLAGS"] = cxx_flags[1]
        utils.check_call("git", "clean", "-dfqx")

        # Generate include dir structure.
        os.chdir(self.root_dir)
        self.b2("-q", "-d0", "headers")

        # Determine if we generate index on the docs. Which we limit as they
        # horrendous amounts of time to generate.
        enable_auto_index = (
            self.ci.time_limit > 60 and self.branch == "master" and self.mode == "build"
        )

        # Build various tools:
        # * Quickbook documentation tool.
        # * auto-index documentation tool.
        self.b2(
            "-q",
            "-d0",
            "--build-dir=%s" % (self.build_dir),
            "--distdir=%s" % (os.path.join(self.build_dir, "dist")),
            "tools/quickbook",
            "tools/auto_index/build" if enable_auto_index else "",
        )

        # Clean up build byproducts.
        os.chdir(os.path.join(self.root_dir, "tools", "quickbook"))
        utils.check_call("git", "clean", "-dfqx")
        os.chdir(os.path.join(self.root_dir, "tools", "auto_index"))
        utils.check_call("git", "clean", "-dfqx")

        # Set up build config.
        docutils_path = "/usr/share/docutils"
        utils.make_file(
            os.path.join(self.build_dir, "site-config.jam"),
            'using quickbook : "%s" ;'
            % (os.path.join(self.build_dir, "dist", "bin", "quickbook")),
            'using auto-index : "%s" ;'
            % (os.path.join(self.build_dir, "dist", "bin", "auto_index"))
            if enable_auto_index
            else "",
            "using docutils : %s ;" % docutils_path,
            "using doxygen ;",
            'using boostbook : "%s" : "%s" ;'
            % (
                os.path.join(self.build_dir, "docbook-xsl", "docbook-xsl-1.79.1"),
                os.path.join(self.build_dir, "docbook-xml"),
            ),
            "using asciidoctor ;",
            "using saxonhe ;",
        )

        # Build the full docs, and all the submodule docs.
        os.chdir(os.path.join(self.root_dir, "doc"))

        if self.mode == "check":
            self.b2(
                "-q",
                "-d0",
                "-n",
                "--build-dir=%s" % (self.build_dir),
                "--distdir=%s" % (os.path.join(self.build_dir, "dist")),
                "--release-build",
                "auto-index=off",
            )
            return

        exclude_libraries = {"beast"}
        doc_build = self.b2(
            "-q",  # '-d0',
            "--build-dir=%s" % (self.build_dir),
            "--distdir=%s" % (os.path.join(self.build_dir, "dist")),
            "--release-build",
            "--exclude-libraries=%s" % ",".join(exclude_libraries),
            "auto-index=on" if enable_auto_index else "auto-index=off",
            "--enable-index" if enable_auto_index else "",
            parallel=True,
        )
        while doc_build.is_alive():
            time.sleep(3 * 60)
            print("--- Building ---")
            utils.mem_info()
        doc_build.join()

        # Try to build beast docs separately to avoid breaking the build
        try:
            self.b2(
                "-q",  # '-d0',
                "--build-dir=%s" % (self.build_dir),
                "--distdir=%s" % (os.path.join(self.build_dir, "dist")),
                "../libs/beast/doc//boostrelease",
            )
        except:
            pass

        # Build antora docs
        ## Determine the boost branch for which the antora script should
        ## generate the documentation
        os.chdir(self.root_dir)
        if self.branch is None:
            self.branch = "develop"
            output = subprocess.check_output(["git", "branch"]).decode("utf-8")
            lines = output.split("\n")
            for line in lines:
                if line.startswith("*"):
                    current_branch = line[2:]
                    self.branch = current_branch
                    break

        ## Determine the branch of site-docs to use
        if self.branch == "master":
            checkout_branch = "master"
        else:
            checkout_branch = "develop"

        # Call antora project main script
        os.chdir(self.build_dir)
        antora_dir = os.path.join(self.build_dir, "antora")
        if not os.path.exists(antora_dir):
            utils.check_call(
                "git",
                "clone",
                "--depth=1",
                "--branch=%s" % checkout_branch,
                "https://github.com/cppalliance/site-docs.git",
                "antora",
            )
        os.chdir(antora_dir)
        if self.parse_semver(self.branch) is not None:
            libdoc_branch = self.boost_version
        else:
            libdoc_branch = self.branch
        utils.check_call(os.path.join(antora_dir, "libdoc.sh"), libdoc_branch)

        # Render the libs/libraries and index.html templates in-place
        os.chdir(self.root_dir)
        generatehtmlpages(self.root_dir, self.build_dir)

        # Clean up some extra build files that creep in. These are
        # from stuff that doesn't obey the build-dir options.
        utils.rmtree(
            os.path.join(
                self.root_dir, "libs", "config", "checks", "architecture", "bin"
            )
        )
        utils.check_call(
            "git", "submodule", "--quiet", "foreach", "rm", "-fr", "doc/bin"
        )

        # Make the real distribution tree from the base tree.
        # This will also copy the docs generated in-source
        if self.releases_dir is None:
            self.releases_dir = os.path.dirname(self.root_dir)
        elif not os.path.isabs(self.releases_dir):
            self.releases_dir = os.path.join(self.root_dir, self.releases_dir)
            utils.makedirs(self.releases_dir)
        if os.path.isfile("MakeBoostDistro.py"):
            import MakeBoostDistro

            os.chdir(self.releases_dir)
            MakeBoostDistro.main(self.root_dir, self.boost_release_name)
        else:
            os.chdir(os.path.join(self.build_dir))
            utils.check_call(
                "wget",
                "https://raw.githubusercontent.com/boostorg/release-tools/master/MakeBoostDistro.py",
                "-O",
                "MakeBoostDistro.py",
            )
            utils.check_call("chmod", "+x", "MakeBoostDistro.py")
            os.chdir(os.path.dirname(self.root_dir))
            utils.check_call(
                pythonbinary,
                os.path.join(self.build_dir, "MakeBoostDistro.py"),
                self.root_dir,
                self.boost_release_name,
            )

        # Patch release with the html generate in-place
        for sourcefilename in ["index.html", "libs/libraries.htm"]:
            shutil.copyfile(
                os.path.join(self.build_dir, sourcefilename),
                os.path.join(
                    self.releases_dir, self.boost_release_name, sourcefilename
                ),
            )

        # Patch release with antora docs
        antora_lib_docs = os.path.join(self.build_dir, "antora/build/lib/doc")
        release_lib_docs = os.path.join(
            self.releases_dir, self.boost_release_name, "libs"
        )
        shutil.copytree(
            antora_lib_docs, release_lib_docs, symlinks=False, dirs_exist_ok=True
        )

        packages = []
        archive_files = []

        # Create packages for LF style content.
        if self.eol == "LF":
            os.chdir(self.releases_dir)
            os.environ["GZIP"] = "-9"
            os.environ["BZIP2"] = "-9"
            archive_files.append(
                "%s%s.tar.gz" % (self.boost_release_name, self.archive_tag)
            )
            packages.append(
                parallel_call(
                    "tar",
                    "--exclude=ci_boost_common.py",
                    "--exclude=ci_boost_release.py",
                    "-zcf",
                    "%s%s.tar.gz" % (self.boost_release_name, self.archive_tag),
                    self.boost_release_name,
                )
            )
            archive_files.append(
                "%s%s.tar.bz2" % (self.boost_release_name, self.archive_tag)
            )
            packages.append(
                parallel_call(
                    "tar",
                    "--exclude=ci_boost_common.py",
                    "--exclude=ci_boost_release.py",
                    "-jcf",
                    "%s%s.tar.bz2" % (self.boost_release_name, self.archive_tag),
                    self.boost_release_name,
                )
            )

        # Create packages for CRLF style content.
        if self.eol == "CRLF":
            os.chdir(self.releases_dir)
            archive_files.append(
                "%s%s.zip" % (self.boost_release_name, self.archive_tag)
            )
            packages.append(
                parallel_call(
                    "zip",
                    "-qr",
                    "-9",
                    "%s%s.zip" % (self.boost_release_name, self.archive_tag),
                    self.boost_release_name,
                    "-x",
                    self.boost_release_name + "/ci_boost_common.py",
                    self.boost_release_name + "/ci_boost_release.py",
                )
            )
            archive_files.append(
                "%s%s.7z" % (self.boost_release_name, self.archive_tag)
            )
            with open("/dev/null") as dev_null:
                utils.check_call(
                    "7z",
                    "a",
                    "-bd",
                    "-mx=7",
                    "-ms=on",
                    "-x!" + self.boost_release_name + "/ci_boost_common.py",
                    "-x!" + self.boost_release_name + "/ci_boost_release.py",
                    "%s%s.7z" % (self.boost_release_name, self.archive_tag),
                    self.boost_release_name,
                    stdout=dev_null,
                )

        for package in packages:
            package.join()

        # Create archive info data files.
        for archive_file in archive_files:
            sha256_sum = hashlib.sha256(open(archive_file, "rb").read()).hexdigest()
            created_date = ""
            try:
                created_date = subprocess.check_output(
                    "set -e && set -o pipefail; TZ=UTC git -C "
                    + self.root_dir
                    + " show -s --date='format-local:%Y-%m-%dT%H:%M:%SZ' "
                    + self.commit
                    + " | grep Date: | tr -s ' ' | cut -d' ' -f 2 ",
                    universal_newlines=True,
                    shell=True,
                    executable="/bin/bash",
                )
                created_date = created_date.strip()
            except:
                print("Could not find the commit in the git log.")

            utils.make_file(
                "%s.json" % (archive_file),
                "{",
                '"sha256":"%s",' % (sha256_sum),
                '"file":"%s",' % (archive_file),
                '"branch":"%s",' % (self.branch),
                '"commit":"%s",' % (self.commit),
                '"created":"%s"' % (created_date),
                "}",
            )

        # List the results for debugging.
        utils.check_call("ls", "-la")

    def upload_archives(self, *filenames):
        self.artifactory_user = "boostsys"
        self.artifactory_org = "boostorg"
        self.artifactory_repo = "main"

        # If GH_TOKEN is set, github releases will activate.
        # The variable "github_releases_main_repo" determines if github releases will be hosted on the boost repository itself.
        # If set to False, the github releases will be directed to a separate repo.
        github_releases_main_repo = True

        # The next two variables are only used if github_releases_main_repo==False
        github_releases_target_org = "boostorg"
        github_releases_target_repo = "boost-releases"

        if github_releases_main_repo:
            github_releases_folder = self.root_dir
        else:
            github_releases_folder = os.path.join(
                os.path.dirname(self.root_dir), "ghreleases"
            )

        github_release_name = self.branch + "-snapshot"

        if not self.sf_releases_key and not self.gh_token and not self.artifactory_pass:
            utils.log("ci_boost_release: upload_archives: no tokens or keys provided")
            return
        curl_cfg_data = []
        curl_cfg = os.path.join(self.build_dir, "curl.cfg")
        if self.sf_releases_key:
            curl_cfg_data += [
                'data = "api_key=%s"' % (self.sf_releases_key),
            ]
        utils.make_file(curl_cfg, *curl_cfg_data)

        if self.artifactory_pass:
            curl_cfg_rt = os.path.join(self.build_dir, "curl_rt.cfg")
            curl_cfg_rt_data = [
                'user = "%s:%s"' % (self.artifactory_user, self.artifactory_pass),
            ]
            utils.make_file(curl_cfg_rt, *curl_cfg_rt_data)

        # # The uploads to the release services happen in parallel to minimize clock time.
        # uploads = []

        # Prepare gh uploads
        if self.gh_token:
            os.chdir(os.path.dirname(self.root_dir))

            # Check out github releases target repo, if necessary
            if not github_releases_main_repo:
                if os.path.isdir(github_releases_folder):
                    os.chdir(github_releases_folder)
                    utils.check_call(
                        "git",
                        "pull",
                        "https://github.com/%s/%s"
                        % (github_releases_target_org, github_releases_target_repo),
                    )
                    utils.check_call("git", "checkout", "%s" % (self.branch))
                else:
                    utils.check_call(
                        "git",
                        "clone",
                        "https://github.com/%s/%s"
                        % (github_releases_target_org, github_releases_target_repo),
                        "%s" % (github_releases_folder),
                    )
                    os.chdir(github_releases_folder)
                    utils.check_call("git", "checkout", "%s" % (self.branch))

            os.chdir(github_releases_folder)

            # gh has a concept called "base" repo. Pointing it to "origin".
            utils.check_call(
                "git", "config", "--local", "remote.origin.gh-resolved", "base"
            )

            # allow credentials to be read from $GH_USER and $GH_TOKEN env variables
            credentialhelperscript = '!f() { sleep 1; echo "username=${GH_USER}"; echo "password=${GH_TOKEN}"; }; f'
            utils.check_call(
                "git", "config", "credential.helper", "%s" % (credentialhelperscript)
            )

            # Create a release, if one is not present
            if pythonversion == "2":
                list_of_releases = subprocess.check_output(["gh", "release", "list"])
            else:
                list_of_releases = subprocess.check_output(
                    ["gh", "release", "list"], encoding="UTF-8"
                )

            if github_release_name not in list_of_releases:
                utils.check_call(
                    "gh",
                    "release",
                    "create",
                    "%s" % (github_release_name),
                    "-t",
                    "%s snapshot" % (self.branch),
                    "-n",
                    "Latest snapshot of %s branch" % (self.branch),
                )

            # Update the tag
            # When github_releases_main_repo is False, this may not be too important.
            # If github_releases_main_repo is True, the git tag should match the release.
            os.chdir(github_releases_folder)
            utils.check_call("git", "tag", "-f", "%s" % (github_release_name))
            utils.check_call(
                "git", "push", "-f", "origin", "%s" % (github_release_name)
            )

            # Finished with "prepare gh uploads". Set directory back to reasonable value.
            os.chdir(os.path.dirname(self.root_dir))

        for filename in filenames:
            if self.sf_releases_key:
                # uploads.append(parallel_call(
                utils.check_call(
                    "curl",
                    "sshpass",
                    "-e",
                    "rsync",
                    "-e",
                    "ssh",
                    filename,
                    "%s@frs.sourceforge.net:/home/frs/project/boost/boost/snapshots/%s/"
                    % (os.environ["SSHUSER"], self.branch),
                )
            if self.artifactory_pass:
                utils.check_call(
                    "curl",
                    "-K",
                    curl_cfg_rt,
                    "-T",
                    filename,
                    "https://"
                    + self.artifactory_org
                    + ".jfrog.io/artifactory/"
                    + self.artifactory_repo
                    + "/%s/%s" % (self.branch, filename),
                )
            if self.gh_token:
                os.chdir(github_releases_folder)
                utils.check_call(
                    "gh",
                    "release",
                    "upload",
                    "%s" % (github_release_name),
                    "%s" % (os.path.join(os.path.dirname(self.root_dir), filename)),
                    "--clobber",
                )
                os.chdir(os.path.dirname(self.root_dir))

        # for upload in uploads:
        #     upload.join()

        # Configuration after uploads, like setting uploaded file properties.
        for filename in filenames:
            if self.sf_releases_key:
                pass

    def upload_to_s3(self):
        """Upload the contents of the archive to S3 for website hosting."""

        os.chdir(os.path.dirname(self.root_dir))

        # if not shutil.which("aws"):
        #     print("aws cli is missing. Cannot proceed.")
        #     return

        if not shutil.which("rclone"):
            print("rclone is missing. Cannot proceed.")
            return

        web_environments = ["PRODUCTION", "REVSYS", "STAGE", "CPPAL_DEV"]
        for web_environment in web_environments:
            if not (web_environment + "_AWS_ACCESS_KEY_ID") in os.environ:
                print(web_environment + "_AWS_ACCESS_KEY_ID not set.")
            elif not (web_environment + "_AWS_SECRET_ACCESS_KEY") in os.environ:
                print(web_environment + "_AWS_SECRET_ACCESS_KEY not set.")
            elif not (web_environment + "_BUCKET") in os.environ:
                print(web_environment + "_BUCKET not set.")
            else:
                print("Uploading " + web_environment + " environment to S3.\n")
                os.environ["AWS_ACCESS_KEY_ID"] = os.environ[
                    web_environment + "_AWS_ACCESS_KEY_ID"
                ]
                os.environ["AWS_SECRET_ACCESS_KEY"] = os.environ[
                    web_environment + "_AWS_SECRET_ACCESS_KEY"
                ]
                os.environ["S3_BUCKET"] = os.environ[web_environment + "_BUCKET"]
                os.environ["AWS_DEFAULT_REGION"] = "us-east-2"

                # Functional 'aws s3 sync' example:
                # x = subprocess.run(['aws', 's3', 'sync', self.boost_release_name + '/', 's3://' + os.environ["S3_BUCKET"] + '/archives/' + self.branch + '/'], stderr=sys.stderr, stdout=sys.stdout, bufsize=1, text=True)

                #
                # Use rclone instead:
                #

                filecontents = """[remote1]
type = s3
provider = AWS
env_auth = true
region = us-east-2
"""

                os.makedirs("/root/.config/rclone", exist_ok=True)
                with open("/root/.config/rclone/rclone.conf", "w") as f:
                    f.writelines(filecontents)
                x = subprocess.run(
                    ["date"], stderr=sys.stderr, stdout=sys.stdout, bufsize=1, text=True
                )
                print(x)
                x = subprocess.run(
                    [
                        "rclone",
                        "sync",
                        "--checksum",
                        self.boost_release_name + "/",
                        "remote1:"
                        + os.environ["S3_BUCKET"]
                        + "/archives/"
                        + self.branch
                        + "/",
                    ],
                    stderr=sys.stderr,
                    stdout=sys.stdout,
                    bufsize=1,
                    text=True,
                )
                print(x)
                x = subprocess.run(
                    ["date"], stderr=sys.stderr, stdout=sys.stdout, bufsize=1, text=True
                )
                print(x)

    def command_after_success(self):
        super(script, self).command_after_success()
        # Publish created packages depending on the EOL style and branch.
        # We post archives to distribution services.
        if self.branch not in ["master", "develop"]:
            return

        if self.mode == "check":
            return

        if self.eol == "LF":
            os.chdir(os.path.dirname(self.root_dir))
            self.upload_archives(
                "%s%s.tar.gz" % (self.boost_release_name, self.archive_tag),
                "%s%s.tar.gz.json" % (self.boost_release_name, self.archive_tag),
                "%s%s.tar.bz2" % (self.boost_release_name, self.archive_tag),
                "%s%s.tar.bz2.json" % (self.boost_release_name, self.archive_tag),
            )
        if self.eol == "CRLF":
            os.chdir(os.path.dirname(self.root_dir))
            self.upload_archives(
                "%s%s.zip" % (self.boost_release_name, self.archive_tag),
                "%s%s.zip.json" % (self.boost_release_name, self.archive_tag),
                "%s%s.7z" % (self.boost_release_name, self.archive_tag),
                "%s%s.7z.json" % (self.boost_release_name, self.archive_tag),
            )

        self.upload_to_s3()


main(script)
