#!/usr/bin/env python

# Copyright Rene Rivera 2016
#
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at
# http://www.boost.org/LICENSE_1_0.txt)

import os.path
import time
import shutil

from ci_boost_common import main, utils, script_common, parallel_call

class script(script_common):
    '''
    Main script to build/test Boost C++ Libraries continuous releases. This base
    is not usable by itself, as it needs some setup for the particular CI
    environment before execution.
    '''

    def __init__(self, ci_klass, **kargs):
        script_common.__init__(self, ci_klass, **kargs)
        
    def init(self, opt, kargs):
        kargs = super(script,self).init(opt,kargs)
        opt.add_option( '--eol',
            help='type of EOLs to check out files as for packaging (LF or CRLF)')
        self.eol=os.getenv('EOL', os.getenv('RELEASE_BUILD', 'LF'))
        return kargs
        
    def start(self):
        super(script,self).start()
        # The basename we will use for the release archive.
        self.boost_release_name = 'boost_'+self.boost_version.replace('.','_')

    # Common test commands in the order they should be executed..
    
    def command_info(self):
        super(script,self).command_info()
        utils.check_call('xsltproc','--version')
    
    def command_install(self):
        super(script,self).command_install()
        self.command_install_rapidxml()
        self.command_install_docutils()
        self.command_install_docbook()
    
    def command_install_rapidxml(self):
        os.chdir(self.build_dir)
        # We use RapidXML for some doc building tools.
        if not os.path.exists(os.path.join(self.build_dir,'rapidxml.zip')):
            utils.check_call("wget","-O","rapidxml.zip","http://sourceforge.net/projects/rapidxml/files/latest/download")
            utils.check_call("unzip","-n","-d","rapidxml","rapidxml.zip")
    
    def command_install_docutils(self):
        os.chdir(self.build_dir)
        # Need docutils for building some docs.
        utils.check_call("sudo","pip","install","docutils")
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
        utils.check_call("./bootstrap.sh")
        shutil.copy2("b2", os.path.join(self.build_dir,"dist","bin","b2"))
        utils.check_call("git","clean","-dfqx")
        
        # Generate include dir structure.
        os.chdir(self.root_dir)
        self.b2("-q","-d0","headers")
        
        # Build doxygen_xml2qbk for building Boost Geometry docs.
        os.chdir(os.path.join(self.root_dir,"libs","geometry","doc","src","docutils","tools","doxygen_xml2qbk"))
        self.b2('-q','-d0','--build-dir=%s'%(self.build_dir),'--distdir=%s'%(os.path.join(self.build_dir,'dist')))
        os.chdir(os.path.join(self.root_dir,"libs","geometry"))
        utils.check_call("git","clean","-dfqx")
        
        # Build Quickbook documentation tool.
        os.chdir(os.path.join(self.root_dir,"tools","quickbook"))
        self.b2('-q','-d0','--build-dir=%s'%(self.build_dir),'--distdir=%s'%(os.path.join(self.build_dir,'dist')))
        utils.check_call("git","clean","-dfqx")
        
        # Build auto-index documentation tool.
        os.chdir(os.path.join(self.root_dir,"tools","auto_index","build"))
        self.b2('-q','-d0','--build-dir=%s'%(self.build_dir),'--distdir=%s'%(os.path.join(self.build_dir,'dist')))
        os.chdir(os.path.join(self.root_dir,"tools","auto_index"))
        utils.check_call("git","clean","-dfqx")
        
        # Set up build config.
        utils.make_file(os.path.join(self.build_dir,'site-config.jam'),
            'using quickbook : "%s" ;'%(os.path.join(self.build_dir,'dist','bin','quickbook')),
            'using auto-index : "%s" ;'%(os.path.join(self.build_dir,'dist','bin','auto_index')),
            'using docutils ;',
            'using doxygen ;',
            'using boostbook : "%s" : "%s" ;'%(
                os.path.join(self.build_dir,'docbook-xsl','docbook-xsl-1.79.1'),
                os.path.join(self.build_dir,'docbook-xml')))
        
        # Pre-build Boost Geometry docs.
        os.chdir(os.path.join(self.root_dir,"libs","geometry","doc"))
        utils.check_call('python','make_qbk.py','--release-build')
        
        # Build the full docs, and all the submodule docs.
        os.chdir(os.path.join(self.root_dir,"doc"))
        doc_build = self.b2('-q','-d0',
            '--build-dir=%s'%(self.build_dir),
            '--distdir=%s'%(os.path.join(self.build_dir,'dist')),
            '--release-build','--enable-index',
            parallel=True)
        while doc_build.is_alive():
            time.sleep(3*60)
            print("--- Building ---")
            utils.mem_info()
        doc_build.join()

        # Download the library list.
        os.chdir(self.root_dir)
        utils.check_call('wget', '-O', 'libs/libraries.htm', 'http://www.boost.org/doc/generate.php?page=libs/libraries.htm&version=%s'%(self.branch));

        # Make the real distribution tree from the base tree.
        os.chdir(os.path.join(self.build_dir))
        utils.check_call('wget','https://raw.githubusercontent.com/boostorg/release-tools/develop/MakeBoostDistro.py')
        utils.check_call('chmod','+x','MakeBoostDistro.py')
        os.chdir(os.path.dirname(self.root_dir))
        utils.check_call('python',os.path.join(self.build_dir,'MakeBoostDistro.py'),
            self.root_dir,self.boost_release_name)
        
        packages = []
        
        # Create packages for LF style content.
        if self.eol == 'LF':
            os.chdir(os.path.dirname(self.root_dir))
            packages.append(parallel_call('tar','-zcf','%s.tar.gz'%(self.boost_release_name),self.boost_release_name))
            packages.append(parallel_call('tar','-cjf','%s.tar.bz2'%(self.boost_release_name),self.boost_release_name))
        
        # Create packages for CRLF style content.
        if self.eol == 'CRLF':
            os.chdir(os.path.dirname(self.root_dir))
            packages.append(parallel_call('zip','-qr','%s.zip'%(self.boost_release_name),self.boost_release_name))
            with open('/dev/null') as dev_null:
                utils.check_call('7z','a','-bd','-m0=lzma','-mx=9','-mfb=64','-md=32m','-ms=on',
                    '%s.7z'%(self.boost_release_name),self.boost_release_name, stdout=dev_null)
        
        for package in packages:
            package.join()
        
        # List the results for debugging.
        utils.check_call('ls','-la')
    
    def upload_archives(self, *filenames):
        if not self.sf_releases_key and not self.bintray_key:
            return
        curl_cfg_data = []
        curl_cfg = os.path.join(self.build_dir,'curl.cfg')
        if self.sf_releases_key:
            curl_cfg_data += [
                'data = "api_key=%s"'%(self.sf_releases_key),
                ]
        if self.bintray_key:
            curl_cfg_data += [
                'user = "%s:%s"'%('grafikrobot',self.bintray_key),
                ]
        utils.make_file(curl_cfg,*curl_cfg_data)
        # Create version ahead of uploading to avoid invalid version errors.
        if self.bintray_key:
            utils.make_file(
                os.path.join(self.build_dir,'bintray_release.json'),
                '{ "name" : "%s", "desc" : "" }'%(self.commit))
            utils.check_call('curl',
                '-K',curl_cfg,
                '-T',os.path.join(self.build_dir,'bintray_release.json'),
                'https://api.bintray.com/packages/boostorg/%s/snapshot/versions'%(
                    # repo
                    self.branch))
        # Setup before we can upload to the release services.
        for filename in filenames:
            if self.sf_releases_key:
                pass
            if self.bintray_key:
                # You'd think that we would need to specify api.bintray.com/content/boostorg/*/snapshot/
                # as the root path to delete the existing archive. But Bintray has an API
                # (where A == asymetric), and hence nothing is intuitive.
                utils.check_call('curl',
                    '-K',curl_cfg,
                    '-X','DELETE',
                    'https://api.bintray.com/content/boostorg/%s/%s'%(
                        # repo, file
                        self.branch,filename))
                utils.check_call('curl',
                    '-K',curl_cfg,
                    '-X','DELETE',
                    'https://api.bintray.com/content/boostorg/%s/%s.asc'%(
                        # repo, file
                        self.branch,filename))
        # The uploads to the release services happen in parallel to minimize clock time.
        uploads = []
        for filename in filenames:
            if self.sf_releases_key:
                uploads.append(parallel_call(
                    'sshpass','-e',
                    'rsync','-e','ssh',
                    '-v','-v','-v','-v',
                    filename,
                    '${SSHUSER}@frs.sourceforge.net:/home/frs/project/boost/snapshots/%s/'%(self.branch)))
            if self.bintray_key:
                # You'd think that we would need to specify api.bintray.com/content/boostorg/*/snapshot/
                # as the root path to delete the existing archive. But Bintray has an API
                # (where A == asymetric), and hence nothing is intuitive.
                uploads.append(parallel_call('curl',
                    '-K',curl_cfg,
                    '-T',filename,
                    'https://api.bintray.com/content/boostorg/%s/snapshot/%s/%s?publish=1&override=1'%(
                        # repo, version, file
                        self.branch,self.commit,filename)))
        for upload in uploads:
            upload.join()
        # Configuration after uploads, like setting uploaded file properties.
        for filename in filenames:
            if self.sf_releases_key:
                pass
            if self.bintray_key:
                pass

    def command_after_success(self):
        super(script,self).command_after_success()
        # Publish created packages depending on the EOL style and branch.
        # We post archives to distribution services.
        if self.branch not in ['master', 'develop']:
            return
        
        if self.eol == 'LF':
            os.chdir(os.path.dirname(self.root_dir))
            self.upload_archives(
                '%s.tar.gz'%(self.boost_release_name),
                '%s.tar.bz2'%(self.boost_release_name))
        if self.eol == 'CRLF':
            os.chdir(os.path.dirname(self.root_dir))
            self.upload_archives(
                '%s.zip'%(self.boost_release_name),
                '%s.7z'%(self.boost_release_name))

main(script)
