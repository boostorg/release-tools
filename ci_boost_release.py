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

from ci_boost_common import main, utils, script_common, parallel_call

# Check python version
if sys.version_info[0] == 2 :
    pythonversion="2"
    pythonbinary="python2"
else:
    pythonversion="3"
    pythonbinary="python3"

class script(script_common):
    '''
    Main script to build/test Boost C++ Libraries continuous releases. This base
    is not usable by itself, as it needs some setup for the particular CI
    environment before execution.
    '''
    
    archive_tag = "-snapshot"

    def __init__(self, ci_klass, **kargs):
        os.environ["PATH"] += os.pathsep + os.path.join(site.getuserbase(), 'bin')
        utils.log("PATH = %s"%(os.environ["PATH"]))
        script_common.__init__(self, ci_klass, **kargs)
        
    def init(self, opt, kargs):
        kargs = super(script,self).init(opt,kargs)

        opt.add_option( '--eol',
            help='type of EOLs to check out files as for packaging (LF or CRLF)')
        self.eol=os.getenv('EOL', os.getenv('RELEASE_BUILD', 'LF'))

        opt.add_option( '--mode', help="mode ('build' or 'check', default 'build')" )
        self.mode = os.getenv( 'MODE', 'build' )

        return kargs
        
    def start(self):
        super(script,self).start()
        # The basename we will use for the release archive.
        self.boost_release_name = 'boost_'+self.boost_version.replace('.','_')

    # Common test commands in the order they should be executed..
    
    def command_info(self):
        super(script,self).command_info()
        utils.log( "ci_boost_release: eol='%s', mode='%s'" % (self.eol, self.mode) )
        utils.check_call('xsltproc','--version')
    
    def command_install(self):
        super(script,self).command_install()
        self.command_install_rapidxml()
        self.command_install_docutils()
        self.command_install_docbook()
        self.command_install_sphinx()
        self.command_install_asciidoctor()
    
    def command_install_rapidxml(self):
        os.chdir(self.build_dir)
        # We use RapidXML for some doc building tools.
        if not os.path.exists(os.path.join(self.build_dir,'rapidxml.zip')):
            utils.check_call("wget","-O","rapidxml.zip","http://sourceforge.net/projects/rapidxml/files/latest/download")
            utils.check_call("unzip","-n","-d","rapidxml","rapidxml.zip")
    
    def command_install_docutils(self):
        os.chdir(self.build_dir)
        # Need docutils for building some docs.
        utils.check_call("pip","install","--user","docutils==0.12")
        os.chdir(self.root_dir)
    
    def command_install_sphinx(self):
        os.chdir(self.build_dir)
        # Need Sphinx for building some docs (ie boost python).
        utils.make_file(os.path.join(self.build_dir,'constraints.txt'), 'Sphinx==1.5.6')
        utils.check_call("pip","install","--user","Sphinx==1.5.6")
        utils.check_call("pip","install","--user","sphinx-boost==0.0.3")
        utils.check_call("pip","install","--user","-c", os.path.join(self.build_dir,'constraints.txt'), "git+https://github.com/rtfd/recommonmark@50be4978d7d91d0b8a69643c63450c8cd92d1212")
        os.chdir(self.root_dir)
    
    def command_install_docbook(self):
        os.chdir(self.build_dir)
        # Local DocBook schema and stylesheets.
        if not os.path.exists(os.path.join(self.build_dir,'docbook-xml.zip')):
            utils.check_call("wget","-O","docbook-xml.zip","http://www.docbook.org/xml/4.5/docbook-xml-4.5.zip")
            utils.check_call("unzip","-n","-d","docbook-xml","docbook-xml.zip")
        if not os.path.exists(os.path.join(self.build_dir,'docbook-xsl.zip')):
            utils.check_call("wget","-O","docbook-xsl.zip","https://sourceforge.net/projects/docbook/files/docbook-xsl/1.79.1/docbook-xsl-1.79.1.zip/download")
            utils.check_call("unzip","-n","-d","docbook-xsl","docbook-xsl.zip")

    def command_install_asciidoctor(self):
        os.chdir(self.build_dir)
        utils.check_call("gem","install","asciidoctor", "--version", "1.5.8")
        utils.check_call("asciidoctor","--version")
        utils.check_call("gem","install","rouge")
        if pythonversion=="2":
            utils.check_call("gem","install","pygments.rb", "--version", "1.2.1")
        else: 
            utils.check_call("gem","install","pygments.rb", "--version", "2.1.0")
        utils.check_call("pip","install","--user","Pygments==2.1")
        utils.check_call("pip","install","--user","https://github.com/bfgroup/jam_pygments/archive/master.zip")
        os.chdir(self.root_dir)

    def command_before_build(self):
        super(script,self).command_before_build()
        # Fetch the rest of the Boost submodules in the appropriate
        # EOL style.
        if self.eol == 'LF':
            utils.check_call("git","config","--global","core.eol","lf")
            utils.check_call("git","config","--global","core.autocrlf","input")
        else:
            utils.check_call("git","config","--global","core.eol","crlf")
            utils.check_call("git","config","--global","core.autocrlf","true")
        utils.check_call("git","rm","--quiet","--cache","-r",".")
        utils.check_call("git","reset","--quiet","--hard","HEAD")
        utils.check_call("git","submodule","--quiet","foreach","--recursive","git","rm","--quiet","--cache","-r",".")
        utils.check_call("git","submodule","--quiet","foreach","--recursive","git","reset","--quiet","--hard","HEAD")

    def command_build(self):
        super(script,self).command_build()
        # Build a packaged release. This involves building a fresh set
        # of docs and selectively packging parts of the tree. We try and
        # avoid creating extra files in the base tree to avoid including
        # extra stuff in the archives. Which means that we reset the git
        # tree state to cleanup after building.
        
        # Set up where we will "install" built tools.
        utils.makedirs(os.path.join(self.build_dir,'dist','bin'))
        os.environ['PATH'] = os.path.join(self.build_dir,'dist','bin')+':'+os.environ['PATH']
        os.environ['BOOST_BUILD_PATH'] = self.build_dir
        
        # Bootstrap Boost Build engine.
        os.chdir(os.path.join(self.root_dir,"tools","build"))
        cxx_flags = (os.getenv('CXX', ""), os.getenv('CXXFLAGS', ""))
        os.environ['CXX'] = ""
        os.environ['CXXFLAGS'] = ""
        utils.check_call("./bootstrap.sh")
        shutil.copy2("b2", os.path.join(self.build_dir,"dist","bin","b2"))
        os.environ['CXX'] = cxx_flags[0]
        os.environ['CXXFLAGS'] = cxx_flags[1]
        utils.check_call("git","clean","-dfqx")
        
        # Generate include dir structure.
        os.chdir(self.root_dir)
        self.b2("-q","-d0","headers")
        
        # Determine if we generate index on the docs. Which we limit as they
        # horrendous amounts of time to generate.
        enable_auto_index = self.ci.time_limit > 60 and self.branch == "master" and self.mode == "build"

        # Build various tools:
        # * Quickbook documentation tool.
        # * auto-index documentation tool.
        self.b2('-q','-d0','--build-dir=%s'%(self.build_dir),'--distdir=%s'%(os.path.join(self.build_dir,'dist')),
            'tools/quickbook',
            'tools/auto_index/build' if enable_auto_index else '')
        
        # Clean up build byproducts.
        os.chdir(os.path.join(self.root_dir,"tools","quickbook"))
        utils.check_call("git","clean","-dfqx")
        os.chdir(os.path.join(self.root_dir,"tools","auto_index"))
        utils.check_call("git","clean","-dfqx")
        
        # Set up build config.
        utils.make_file(os.path.join(self.build_dir,'site-config.jam'),
            'using quickbook : "%s" ;'%(os.path.join(self.build_dir,'dist','bin','quickbook')),
            'using auto-index : "%s" ;'%(os.path.join(self.build_dir,'dist','bin','auto_index')) if enable_auto_index else '',
            'using docutils : /usr/share/docutils ;',
            'using doxygen ;',
            'using boostbook : "%s" : "%s" ;'%(
                os.path.join(self.build_dir,'docbook-xsl','docbook-xsl-1.79.1'),
                os.path.join(self.build_dir,'docbook-xml')),
            'using asciidoctor ;',
            'using saxonhe ;')
        
        # Build the full docs, and all the submodule docs.
        os.chdir(os.path.join(self.root_dir,"doc"))

        if self.mode == "check":
            self.b2('-q','-d0','-n',
                '--build-dir=%s'%(self.build_dir),
                '--distdir=%s'%(os.path.join(self.build_dir,'dist')),
                '--release-build',
                'auto-index=off')
            return

        doc_build = self.b2('-q', # '-d0',
            '--build-dir=%s'%(self.build_dir),
            '--distdir=%s'%(os.path.join(self.build_dir,'dist')),
            '--release-build',
            '--exclude-libraries=beast',
            'auto-index=on' if enable_auto_index else 'auto-index=off',
            '--enable-index' if enable_auto_index else '',
            parallel=True)
        while doc_build.is_alive():
            time.sleep(3*60)
            print("--- Building ---")
            utils.mem_info()
        doc_build.join()

        try:
            self.b2('-q', # '-d0',
            '--build-dir=%s'%(self.build_dir),
            '--distdir=%s'%(os.path.join(self.build_dir,'dist')),
            '../libs/beast/doc//boostrelease')
        except:
            pass

        # Download some generated files.
        os.chdir(self.root_dir)
        utils.check_call('wget', '-O', 'libs/libraries.htm', 'http://www.boost.org/doc/generate.php?page=libs/libraries.htm&version=%s'%(self.boost_version));
        utils.check_call('wget', '-O', 'index.html', 'http://www.boost.org/doc/generate.php?page=index.html&version=%s'%(self.boost_version));
        
        # Clean up some extra build files that creep in. These are
        # from stuff that doesn't obey the build-dir options.
        utils.rmtree(os.path.join(self.root_dir,"libs","config","checks","architecture","bin"))
        utils.check_call("git","submodule","--quiet","foreach","rm","-fr","doc/bin")

        # Make the real distribution tree from the base tree.
        os.chdir(os.path.join(self.build_dir))
        utils.check_call('wget','https://raw.githubusercontent.com/sdarwin/release-tools/python3/MakeBoostDistro.py','-O','MakeBoostDistro.py')
        utils.check_call('chmod','+x','MakeBoostDistro.py')
        os.chdir(os.path.dirname(self.root_dir))
        utils.check_call(pythonbinary,os.path.join(self.build_dir,'MakeBoostDistro.py'),
            self.root_dir,self.boost_release_name)
        
        packages = []
        archive_files = []
        
        # Create packages for LF style content.
        if self.eol == 'LF':
            os.chdir(os.path.dirname(self.root_dir))
            os.environ['GZIP'] = "-9";
            os.environ['BZIP2'] = "-9";
            archive_files.append(
                '%s%s.tar.gz'%(self.boost_release_name, self.archive_tag));
            packages.append(parallel_call(
                'tar','-zcf',
                '%s%s.tar.gz'%(self.boost_release_name, self.archive_tag),
                self.boost_release_name))
            archive_files.append(
                '%s%s.tar.bz2'%(self.boost_release_name, self.archive_tag));
            packages.append(parallel_call(
                'tar','-jcf',
                '%s%s.tar.bz2'%(self.boost_release_name, self.archive_tag),
                self.boost_release_name))
        
        # Create packages for CRLF style content.
        if self.eol == 'CRLF':
            os.chdir(os.path.dirname(self.root_dir))
            archive_files.append(
                '%s%s.zip'%(self.boost_release_name, self.archive_tag));
            packages.append(parallel_call(
                'zip','-qr','-9',
                '%s%s.zip'%(self.boost_release_name, self.archive_tag),
                self.boost_release_name))
            archive_files.append(
                '%s%s.7z'%(self.boost_release_name, self.archive_tag));
            with open('/dev/null') as dev_null:
                utils.check_call(
                    '7z','a','-bd','-mx=7','-ms=on',
                    '%s%s.7z'%(self.boost_release_name, self.archive_tag),
                    self.boost_release_name, stdout=dev_null)
        
        for package in packages:
            package.join()
        
        # Create archive info data files.
        for archive_file in archive_files:
            sha256_sum = hashlib.sha256(open(archive_file,"rb").read()).hexdigest()
            utils.make_file("%s.json"%(archive_file),
                "{",
                '"sha256":"%s",'%(sha256_sum),
                '"file":"%s",'%(archive_file),
                '"branch":"%s",'%(self.branch),
                '"commit":"%s"'%(self.commit),
                "}")
        
        # List the results for debugging.
        utils.check_call('ls','-la')
    
    def upload_archives(self, *filenames):

        self.artifactory_user="boostsys"
        self.artifactory_org="boostorg"
        self.artifactory_repo="main"

	# If GH_TOKEN is set, github releases will activate.
	# The variable "github_releases_main_repo" determines if github releases will be hosted on the boost repository itself.
	# If set to False, the github releases will be directed to a separate repo.
        github_releases_main_repo=True

        # The next two variables are only used if github_releases_main_repo==False
        github_releases_target_org="boostorg"
        github_releases_target_repo="boost-releases"

        if github_releases_main_repo:
            github_releases_folder=self.root_dir
        else:
            github_releases_folder=os.path.join(os.path.dirname(self.root_dir),"ghreleases")

        github_release_name=self.branch + "-snapshot"

        if not self.sf_releases_key and not self.gh_token and not self.artifactory_pass:
            utils.log( "ci_boost_release: upload_archives: no tokens or keys provided" )
            return
        curl_cfg_data = []
        curl_cfg = os.path.join(self.build_dir,'curl.cfg')
        if self.sf_releases_key:
            curl_cfg_data += [
                'data = "api_key=%s"'%(self.sf_releases_key),
                ]
        utils.make_file(curl_cfg,*curl_cfg_data)

        if self.artifactory_pass:
            curl_cfg_rt = os.path.join(self.build_dir,'curl_rt.cfg')
            curl_cfg_rt_data = [
                'user = "%s:%s"'%(self.artifactory_user,self.artifactory_pass),
                ]
            utils.make_file(curl_cfg_rt,*curl_cfg_rt_data)

        # # The uploads to the release services happen in parallel to minimize clock time.
        # uploads = []

        # Prepare gh uploads
        if self.gh_token:
            os.chdir(os.path.dirname(self.root_dir))

            # Check out github releases target repo, if necessary
            if not github_releases_main_repo:
                if os.path.isdir(github_releases_folder):
                    os.chdir(github_releases_folder)
                    utils.check_call('git',
                        'pull',
                        'https://github.com/%s/%s'%(github_releases_target_org,github_releases_target_repo))
                    utils.check_call('git',
                        'checkout',
                        '%s'%(self.branch))
                else:
                    utils.check_call('git',
                        'clone',
                        'https://github.com/%s/%s'%(github_releases_target_org,github_releases_target_repo),
                        '%s'%(github_releases_folder)
                        )
                    os.chdir(github_releases_folder)
                    utils.check_call('git',
                        'checkout',
                        '%s'%(self.branch))

            os.chdir(github_releases_folder)

            # gh has a concept called "base" repo. Pointing it to "origin".
            utils.check_call('git',
                    'config',
                    '--local',
                    'remote.origin.gh-resolved',
                    'base')

            # allow credentials to be read from $GH_USER and $GH_TOKEN env variables
            credentialhelperscript='!f() { sleep 1; echo "username=${GH_USER}"; echo "password=${GH_TOKEN}"; }; f'
            utils.check_call('git',
                    'config',
                    'credential.helper',
                    '%s'%(credentialhelperscript))

            # Create a release, if one is not present
            if pythonversion=="2":
                list_of_releases=subprocess.check_output(['gh', 'release', 'list'])
            else:
                list_of_releases=subprocess.check_output(['gh', 'release', 'list'], encoding='UTF-8' )

            if github_release_name not in list_of_releases:
                utils.check_call('gh',
                    'release',
                    'create',
                    '%s'%(github_release_name),
                    '-t',
                    '%s snapshot'%(self.branch),
                    '-n',
                    'Latest snapshot of %s branch'%(self.branch))

            # Update the tag
            # When github_releases_main_repo is False, this may not be too important.
            # If github_releases_main_repo is True, the git tag should match the release.
            os.chdir(github_releases_folder)
            utils.check_call('git',
                    'tag',
                    '-f',
                    '%s'%(github_release_name))
            utils.check_call('git',
                    'push',
                    '-f',
                    'origin',
                    '%s'%(github_release_name))

            # Finished with "prepare gh uploads". Set directory back to reasonable value.
            os.chdir(os.path.dirname(self.root_dir))

        for filename in filenames:
            if self.sf_releases_key:
                # uploads.append(parallel_call(
                utils.check_call('curl',
                    'sshpass','-e',
                    'rsync','-e','ssh',
                    filename,
                    '%s@frs.sourceforge.net:/home/frs/project/boost/boost/snapshots/%s/'%(
                        os.environ['SSHUSER'], self.branch))
            if self.artifactory_pass:
                utils.check_call('curl',
                    '-K',curl_cfg_rt,
                    '-T',filename,
                    'https://' + self.artifactory_org + '.jfrog.io/artifactory/' + self.artifactory_repo + '/%s/%s'%(
                        self.branch,filename))
            if self.gh_token:
                os.chdir(github_releases_folder)
                utils.check_call('gh',
                    'release',
                    'upload',
                    '%s'%(github_release_name),
                    '%s'%(os.path.join(os.path.dirname(self.root_dir),filename)),
                    '--clobber')
                os.chdir(os.path.dirname(self.root_dir))

        # for upload in uploads:
        #     upload.join()

        # Configuration after uploads, like setting uploaded file properties.
        for filename in filenames:
            if self.sf_releases_key:
                pass

    def command_after_success(self):
        super(script,self).command_after_success()
        # Publish created packages depending on the EOL style and branch.
        # We post archives to distribution services.
        if self.branch not in ['master', 'develop']:
            return

        if self.mode == "check":
            return

        if self.eol == 'LF':
            os.chdir(os.path.dirname(self.root_dir))
            self.upload_archives(
                '%s%s.tar.gz'%(self.boost_release_name, self.archive_tag),
                '%s%s.tar.gz.json'%(self.boost_release_name, self.archive_tag),
                '%s%s.tar.bz2'%(self.boost_release_name, self.archive_tag),
                '%s%s.tar.bz2.json'%(self.boost_release_name, self.archive_tag))
        if self.eol == 'CRLF':
            os.chdir(os.path.dirname(self.root_dir))
            self.upload_archives(
                '%s%s.zip'%(self.boost_release_name, self.archive_tag),
                '%s%s.zip.json'%(self.boost_release_name, self.archive_tag),
                '%s%s.7z'%(self.boost_release_name, self.archive_tag),
                '%s%s.7z.json'%(self.boost_release_name, self.archive_tag))

main(script)
