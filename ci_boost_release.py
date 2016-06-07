#!/usr/bin/env python

# Copyright Rene Rivera 2016
#
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at
# http://www.boost.org/LICENSE_1_0.txt)
import sys
del sys.path[0]

import inspect
import optparse
import os.path
import string
import time
import subprocess
import codecs
import shutil
import threading

class SystemCallError(Exception):
    def __init__(self, command, result):
        self.command = command
        self.result = result
    def __str__(self, *args, **kwargs):
        return "'%s' ==> %s"%("' '".join(self.command), self.result)

class utils:
    
    @staticmethod
    def call(*command, **kargs):
        utils.log( "%s> '%s'"%(os.getcwd(), "' '".join(command)) )
        t = time.time()
        result = subprocess.call(command, **kargs)
        t = time.time()-t
        if result != 0:
            print "Failed: '%s' ERROR = %s"%("' '".join(command), result)
        utils.log( "%s> '%s' execution time %s seconds"%(os.getcwd(), "' '".join(command), t) )
        return result
    
    @staticmethod
    def check_call(*command, **kargs):
        cwd = os.getcwd()
        result = utils.call(*command, **kargs)
        if result != 0:
            raise(SystemCallError([cwd]+command, result))
    
    @staticmethod
    def makedirs( path ):
        if not os.path.exists( path ):
            os.makedirs( path )
    
    @staticmethod
    def log_level():
       frames = inspect.stack()
       level = 0
       for i in frames[ 3: ]:
           if i[0].f_locals.has_key( '__log__' ):
               level = level + i[0].f_locals[ '__log__' ]
       return level
    
    @staticmethod
    def log( message ):
        sys.stdout.flush()
        sys.stderr.flush()
        sys.stderr.write( '# ' + '    ' * utils.log_level() +  message + '\n' )
        sys.stderr.flush()

    @staticmethod
    def rmtree(path):
        if os.path.exists( path ):
            #~ shutil.rmtree( unicode( path ) )
            if sys.platform == 'win32':
                os.system( 'del /f /s /q "%s" >nul 2>&1' % path )
                shutil.rmtree( unicode( path ) )
            else:
                os.system( 'rm -f -r "%s"' % path )

    @staticmethod
    def retry( f, max_attempts=5, sleep_secs=10 ):
        for attempts in range( max_attempts, -1, -1 ):
            try:
                return f()
            except Exception, msg:
                utils.log( '%s failed with message "%s"' % ( f.__name__, msg ) )
                if attempts == 0:
                    utils.log( 'Giving up.' )
                    raise

                utils.log( 'Retrying (%d more attempts).' % attempts )
                time.sleep( sleep_secs )

    @staticmethod
    def web_get( source_url, destination_file, proxy = None ):
        import urllib

        proxies = None
        if proxy is not None:
            proxies = {
                'https' : proxy,
                'http' : proxy
                }

        src = urllib.urlopen( source_url, proxies = proxies )

        f = open( destination_file, 'wb' )
        while True:
            data = src.read( 16*1024 )
            if len( data ) == 0: break
            f.write( data )

        f.close()
        src.close()

    @staticmethod
    def unpack_archive( archive_path ):
        utils.log( 'Unpacking archive ("%s")...' % archive_path )

        archive_name = os.path.basename( archive_path )
        extension = archive_name[ archive_name.find( '.' ) : ]

        if extension in ( ".tar.gz", ".tar.bz2" ):
            import tarfile
            import stat

            mode = os.path.splitext( extension )[1][1:]
            tar = tarfile.open( archive_path, 'r:%s' % mode )
            for tarinfo in tar:
                tar.extract( tarinfo )
                if sys.platform == 'win32' and not tarinfo.isdir():
                    # workaround what appears to be a Win32-specific bug in 'tarfile'
                    # (modification times for extracted files are not set properly)
                    f = os.path.join( os.curdir, tarinfo.name )
                    os.chmod( f, stat.S_IWRITE )
                    os.utime( f, ( tarinfo.mtime, tarinfo.mtime ) )
            tar.close()
        elif extension in ( ".zip" ):
            import zipfile

            z = zipfile.ZipFile( archive_path, 'r', zipfile.ZIP_DEFLATED )
            for f in z.infolist():
                destination_file_path = os.path.join( os.curdir, f.filename )
                if destination_file_path[-1] == "/": # directory
                    if not os.path.exists( destination_file_path  ):
                        os.makedirs( destination_file_path  )
                else: # file
                    result = open( destination_file_path, 'wb' )
                    result.write( z.read( f.filename ) )
                    result.close()
            z.close()
        else:
            raise 'Do not know how to unpack archives with extension \"%s\"' % extension
    
    @staticmethod
    def make_file(filename, *text):
        f = codecs.open( filename, 'w', 'utf-8' )
        f.write( string.join( text, '\n' ) )
        f.close()

class parallel_call(threading.Thread):
    
    def __init__(self, *command, **kargs):
        super(parallel_call,self).__init__()
        self.command = command
        self.command_kargs = kargs
        self.start()
    
    def run(self):
        self.result = utils.call(*self.command, **self.command_kargs)
    
    def join(self):
        super(parallel_call,self).join()
        if self.result != 0:
            raise(SystemCallError(self.command, self.result))

class script:
    '''
    Main script to build Boost C++ Libraries continuous releases. This base
    is not usable by itself, as it needs some setup for the particular CI
    environment before execution.
    '''

    def __init__(self, root_dir = None, branch = None, commit = None, actions = None):
        commands = [];
        for method in inspect.getmembers(self, predicate=inspect.ismethod):
            if method[0].startswith('command_'):
                commands.append(method[0][8:].replace('_','-'))
        commands = "commands: %s" % ', '.join(commands)

        opt = optparse.OptionParser(
            usage="%prog [options] [commands]",
            description=commands)

        #~ Debug Options:
        opt.add_option( '--debug-level',
            help="debugging level; controls the amount of debugging output printed",
            type='int' )
        
        opt.add_option( '-j',
            help="maximum number of parallel jobs to use for building with b2",
            type='int', dest='jobs')
        
        opt.add_option( '--eol',
            help='type of EOLs to check out files as for packaging (LF or CRLF)')
        
        opt.add_option('--branch')
        opt.add_option('--commit')

        #~ Defaults
        self.debug_level=0
        self.eol=os.getenv('RELEASE_BUILD', 'LF')
        self.jobs=3
        self.branch = branch
        self.commit = commit
        ( _opt_, self.actions ) = opt.parse_args(None,self)
        if not self.actions or self.actions == []:
            if actions:
                self.actions = actions
            else:
                self.actions = [ 'info' ]
        if not root_dir:
            self.root_dir = os.getcwd()
        else:
            self.root_dir = root_dir
        self.build_dir = os.path.join(os.path.dirname(self.root_dir), "build")
        self.home_dir = os.path.expanduser('~')
        
        #~ Read in the Boost version from the repo we are in.
        self.boost_version = branch
        if os.path.exists(os.path.join(self.root_dir,'Jamroot')):
            with codecs.open(os.path.join(self.root_dir,'Jamroot'), 'r', 'utf-8') as f:
                for line in f.readlines():
                    parts = line.split()
                    if len(parts) >= 5 and parts[1] == 'BOOST_VERSION':
                        self.boost_version = parts[3]
                        break
        if not self.boost_version:
            self.boost_version = 'default'
        
        # The basename we will use for the release archive.
        self.boost_release_name = 'boost_'+self.boost_version.replace('.','_')
        
        # API keys.
        self.bintray_key = os.getenv('BINTRAY_KEY')
        self.sf_releases_key = os.getenv('SF_RELEASES_KEY')

        self.main()

    # Common test commands in the order they should be executed..
    
    def command_base_info(self):
        pass
    
    def command_base_install(self):
        utils.makedirs(self.build_dir)
        os.chdir(self.build_dir)
        self.command_base_install_rapidxml()
        self.command_base_install_docutils()
        self.command_base_install_docbook()
    
    def command_base_install_rapidxml(self):
        os.chdir(self.build_dir)
        # We use RapidXML for some doc building tools.
        if not os.path.exists(os.path.join(self.build_dir,'rapidxml.zip')):
            utils.check_call("wget","-O","rapidxml.zip","http://sourceforge.net/projects/rapidxml/files/latest/download")
            utils.check_call("unzip","-n","-d","rapidxml","rapidxml.zip")
    
    def command_base_install_docutils(self):
        os.chdir(self.build_dir)
        # Need docutils for building some docs.
        utils.check_call("sudo","pip","install","docutils")
        os.chdir(self.root_dir)
    
    def command_base_install_docbook(self):
        os.chdir(self.build_dir)
        # Local DocBook schema and stylesheets.
        if not os.path.exists(os.path.join(self.build_dir,'docbook-xml.zip')):
            utils.check_call("wget","-O","docbook-xml.zip","http://www.docbook.org/xml/4.5/docbook-xml-4.5.zip")
            utils.check_call("unzip","-n","-d","docbook-xml","docbook-xml.zip")
        os.environ['DOCBOOK_DTD_DIR'] = os.path.join(self.build_dir,'docbook-xml')
        if not os.path.exists(os.path.join(self.build_dir,'docbook-xsl.zip')):
            utils.check_call("wget","-O","docbook-xsl.zip","https://sourceforge.net/projects/docbook/files/docbook-xsl/1.79.1/docbook-xsl-1.79.1.zip/download")
            utils.check_call("unzip","-n","-d","docbook-xsl","docbook-xsl.zip")
        os.environ['DOCBOOK_XSL_DIR'] = os.path.join(self.build_dir,'docbook-xsl','docbook-xsl-1.79.1')
    
    def command_base_before_build(self):
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

    def command_base_build(self):
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
            'using boostbook : "%s" : "%s" ;'%(os.environ['DOCBOOK_XSL_DIR'],os.environ['DOCBOOK_DTD_DIR']))
        
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
            print("Building.")
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
        curl_cfg = os.path.join(self.build_dir,'curl.cfg')
        if self.sf_releases_key:
            utils.make_file(curl_cfg,
                'data = "api_key=%s"'%(self.sf_releases_key))
        elif self.bintray_key:
            utils.make_file(curl_cfg,
                'user = "%s:%s"'%('grafikrobot',self.bintray_key))
        else:
            return
        uploads = []
        for filename in filenames:
            if self.sf_releases_key:
                uploads.append(parallel_call('curl',
                    '-K',curl_cfg,
                    '-H','Accept: application/json',
                    '-X','PUT',
                    '-d','default=windows&default=mac&default=linux&default=bsd&default=solaris&default=others',
                    '-T',filename,
                    'https://sourceforge.net/projects/boost/files/snapshots/%s/%s/%s'%(
                        self.branch,self.commit,filename)))
            else:
                # You'd think that we would need to specify api.bintray.com/content/boostorg/*/snapshot/
                # as the root path to delete the existing archive. But Bintray has an API
                # (where A == asymetric), and hence nothing is intuitive.
                utils.check_call('curl',
                    '-K',curl_cfg,
                    '-X','DELETE',
                    'https://api.bintray.com/content/boostorg/%s/%s'%(
                        # repo, file
                        self.branch,filename))
                uploads.append(parallel_call('curl',
                    '-K',curl_cfg,
                    '-T',filename,
                    'https://api.bintray.com/content/boostorg/%s/snapshot/%s/%s?publish=1&override=1'%(
                        # repo, version, file
                        self.branch,self.commit,filename)))
        for upload in uploads:
            upload.join()

    def command_base_publish(self):
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

    #~ Utilities...

    def main(self):
        for action in self.actions:
            action_m = "command_"+action.replace('-','_')
            if hasattr(self,action_m):
                utils.log( "### %s.."%(action) )
                if os.path.exists(self.root_dir):
                    os.chdir(self.root_dir)
                getattr(self,action_m)()
    
    def b2( self, *args, **kargs ):
        cmd = ['b2','--debug-configuration', '-j%s'%(self.jobs)]
        cmd.extend(args)

        if 'toolset' in kargs:
            cmd.append('toolset=' + kargs['toolset'])

        if 'parallel' in kargs:
            return parallel_call(*cmd)
        else:
            return utils.check_call(*cmd)

class script_cli(script):
    '''
    This version of the script provides a way to do manual building. It sets up
    additional environment and adds fetching of the git repos that would
    normally be done by the CI system. But it still has some pre-setup
    requirements. In particular Doxygen, LaTeX, XSLT, and the various
    compression programs need to already be installed. For some platforms
    this tries to find the tools in common install locations. But if it
    doesn't find them it will assume they are already available in the path.
    
    The common way to use this variant is to invoke something like:
    
        mkdir boost-ci-release-build
        cd boost-ci-release-build
        python path-to/ci_boost_release.py --branch=develop
    
    Note: This variant does everything except upload the resulting archives.
    Status: In working order.
    '''
    
    def __init__(self):
        if sys.platform == 'darwin':
            # Requirements for running on OSX:
            # https://www.stack.nl/~dimitri/doxygen/download.html#srcbin
            # https://tug.org/mactex/morepackages.html
            doxygen_path = "/Applications/Doxygen.app/Contents/Resources"
            if os.path.isdir(doxygen_path):
                os.environ["PATH"] = doxygen_path+':'+os.environ['PATH']
        script.__init__(self)
        self.clone()
        self.actions = [
            'install',
            'before_build',
            'build',
            # 'publish',
            ]
        self.main()
    
    def clone(self):
        cwd = os.getcwd()
        self.root_dir = os.path.join(cwd,'boostorg','boost')
        self.build_dir = os.path.join(os.path.dirname(self.root_dir), "build")
        if not os.path.exists(os.path.join(self.root_dir,'.git')):
            utils.check_call("git","clone","--depth=50","--branch=%s"%(self.branch),"https://github.com/boostorg/boost.git","boostorg/boost")
            os.chdir(self.root_dir)
        else:
            os.chdir(self.root_dir)
            utils.check_call("git","pull","--quiet","--no-recurse-submodules","--depth=50")
        if self.commit:
            utils.check_call("git","checkout","-qf",self.commit)
        utils.check_call("git","submodule","update","--quiet","--init","--recursive")
    
    def command_base_install_docutils(self):
        pass
    
    def command_install(self):
        self.command_base_install()
    
    def command_before_build(self):
        self.command_base_before_build()
    
    def command_build(self):
        self.command_base_build()
    
    def command_publish(self):
        self.command_base_publish()

class script_travis(script):
    '''
    This variant build releases in the context of the Travis-CI service.
    
    Status: In working order.
    '''

    def __init__(self):
        script.__init__(self,
            root_dir=os.getenv("TRAVIS_BUILD_DIR"),
            branch=os.getenv("TRAVIS_BRANCH"),
            commit=os.getenv("TRAVIS_COMMIT"))

    # Travis-CI commands in the order they are executed..
    
    def command_before_install(self):
        pass
    
    def command_install(self):
        self.command_base_install()

    def command_before_script(self):
        self.command_base_before_build()

    def command_script(self):
        self.command_base_build()

    def command_after_success(self):
        self.command_base_publish()

    def command_after_failure(self):
        pass

    def command_before_deploy(self):
        pass

    def command_after_deploy(self):
        pass

    def command_after_script(self):
        pass

class script_circleci(script):
    '''
    This variant build releases in the context of the CircleCI service.
    
    Status: Untested.
    '''
    
    def __init(self):
        script.__init__(self,
            branch=os.getenv("CIRCLE_BRANCH"),
            commit=os.getenv("CIRCLE_SHA1"))

if os.getenv('TRAVIS', False):
    script_travis()
elif os.getenv('CIRCLECI', False):
    script_circleci()
else:
    script_cli()

