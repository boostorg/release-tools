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
    def call(*command):
        utils.log( "%s> '%s'"%(os.getcwd(), "' '".join(command)) )
        result = subprocess.call(command)
        if result != 0:
            print "Failed: '%s' ERROR = %s"%("' '".join(command), result)
        return result
    
    @staticmethod
    def check_call(*command):
        result = utils.call(*command)
        if result != 0:
            raise(SystemCallError(command, result))
    
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
    
    def __init__(self, *command):
        super(parallel_call,self).__init__()
        self.command = command
        self.start()
    
    def run(self):
        self.result = utils.call(*self.command)
    
    def join(self):
        super(parallel_call,self).join()
        if self.result != 0:
            raise(SystemCallError(self.command, self.result))

class script:

    def __init__(self, root_dir = None, branch = None, commit = None, test_args = []):
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
        
        opt.add_option( '--eof',
            help='type of EOLs to check out files as for packaging (LF or CRLF)')
        
        opt.add_option('--branch')
        opt.add_option('--commit')

        #~ Defaults
        self.debug_level=0
        self.eof=os.getenv('RELEASE_BUILD', 'LF')
        self.jobs=3
        self.branch = branch
        self.commit = commit
        ( _opt_, self.actions ) = opt.parse_args(None,self)
        if not self.actions or self.actions == []:
            self.actions = [ 'info' ]
        if not root_dir:
            self.root_dir = os.getcwd()
        else:
            self.root_dir = root_dir
        self.build_dir = os.path.join(os.path.dirname(self.root_dir), "build")
        self.home_dir = os.path.expanduser('~')
        
        #~ Read in the Boost version from the repo we are in.
        self.boost_version = branch
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
        
        # Special Bintray key.
        self.bintray_key = os.getenv('BINTRAY')

        self.main()

    # Common test commands in the order they should be executed..
    
    def command_base_info(self):
        pass
    
    def command_base_install(self):
        utils.makedirs(self.build_dir)
        os.chdir(self.build_dir)
        # We use RapidXML for some doc building tools.
        utils.check_call("wget","-O","rapidxml.zip","http://sourceforge.net/projects/rapidxml/files/latest/download")
        utils.check_call("unzip","-n","-d","rapidxml","rapidxml.zip")
        # export RAPIDXML=`ls -1d ${PWD}/rapidxml/rapidxml-*`
        # Need docutils for building some docs.
        utils.check_call("sudo","pip","install","docutils")
        os.chdir(self.root_dir)
    
    def command_base_before_build(self):
        # Fetch the rest of the Boost submodules in the appropriate
        # EOL style.
        if self.eof == 'LF':
            utils.check_call("git","config","--global","core.eol","lf")
            utils.check_call("git","config","--global","core.autocrlf","input")
        else:
            utils.check_call("git","config","--global","core.eol","crlf")
            utils.check_call("git","config","--global","core.autocrlf","true")
        utils.check_call("git","rm","--cache","-r",".")
        utils.check_call("git","reset","--quiet","--hard","HEAD")
        utils.check_call("git","submodule","update","--init","--recursive")

    def command_base_build(self):
        # Build a packaged release. This involves building a fresh set
        # of docs and selectively packging parts of the tree. We try and
        # avoid creating extra files in the base tree to avoid including
        # extra stuff in the archives. Which means that we reset the git
        # tree state to cleanup after building.
        
        # Set up where we will "install" built tools.
        utils.makedirs(os.path.join(self.build_dir,'dist','bin'))
        os.environ['PATH'] = os.path.join(self.build_dir,'dist','bin')+':'+os.environ['PATH']
        
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
        utils.make_file(os.path.join(self.home_dir,'user-config.jam'),
            'using quickbook : "%s" ;'%(os.path.join(self.build_dir,'dist','bin','quickbook')),
            'using auto-index : "%s" ;'%(os.path.join(self.build_dir,'dist','bin','auto_index')),
            'using docutils ;',
            'using doxygen ;')
        
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
        
        # Make the real distribution tree from the base tree.
        os.chdir(os.path.join(self.build_dir))
        utils.check_call('wget','https://raw.githubusercontent.com/boostorg/release-tools/develop/MakeBoostDistro.py')
        utils.check_call('chmod','+x','MakeBoostDistro.py')
        os.chdir(os.path.dirname(self.root_dir))
        utils.check_call('python',os.path.join(self.build_dir,'MakeBoostDistro.py'),
            self.root_dir,self.boost_release_name)
        
        # Create packages for LF style content.
        if self.eof == 'LF':
            os.chdir(os.path.dirname(self.root_dir))
            utils.check_call('tar','-zcf','%s.tar.gz'%(self.boost_release_name),self.boost_release_name)
            utils.check_call('tar','-cjf','%s.tar.bz2'%(self.boost_release_name),self.boost_release_name)
        
        # Create packages for CRLF style content.
        if self.eof == 'CRLF':
            os.chdir(os.path.dirname(self.root_dir))
            utils.check_call('zip','-qr','%s.zip'%(self.boost_release_name),self.boost_release_name)
            utils.check_call('7z','-a','-r','%s.7z'%(self.boost_release_name),self.boost_release_name,'>/dev/null')
        
        # List the results for debugging.
        utils.check_call('ls','-la')
    
    def upload_archive(self, filename):
        utils.check_call('curl','-T',
            filename,
            '-ugrafikrobot:%s'%(self.bintray_key),
            'https://api.bintray.com/content/boostorg/snapshots/%s/%s/%s?publish=1&override=1'%(
                self.branch,self.commit,filename))

    def command_base_publish(self):
        # Publish created packages depending on the EOL style and branch.
        # We post archives to distribution services. But currently we only
        # post master packages as they happen less often. And we are
        # unlikely to ever want anything else as a package for the
        # releases.
        if self.branch != 'master':
            return
        
        if self.eol == 'LF':
            os.chdir(os.path.dirname(self.root_dir))
            self.upload_archive('%s.tar.gz'%(self.boost_release_name))
            self.upload_archive('%s.tar.bz2'%(self.boost_release_name))
        if self.eol == 'CRLF':
            os.chdir(os.path.dirname(self.root_dir))
            self.upload_archive('%s.zip'%(self.boost_release_name))
            self.upload_archive('%s.7z'%(self.boost_release_name))

    #~ Utilities...

    def main(self):
        for action in self.actions:
            action_m = "command_"+action.replace('-','_')
            if hasattr(self,action_m):
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

class script_travis(script):

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

class script_appveyor(script):
    
    def __init__(self):
        script.__init__(self,
            root_dir=os.getenv("APPVEYOR_BUILD_FOLDER"))
    
    # Appveyor commands in the order they are executed..
    
    def command_install(self):
        pass
    
    def command_before_build(self):
        pass
    
    def command_build_script(self):
        pass
    
    def command_after_build(self):
        pass
    
    def command_before_test(self):
        pass
    
    def command_test_script(self):
        pass
    
    def command_after_test(self):
        pass
    
    def command_on_success(self):
        pass
    
    def command_on_failure(self):
        pass
    
    def command_on_finish(self):
        pass

if os.getenv('APPVEYOR', False):
    script_appveyor()
elif os.getenv('TRAVIS', False):
    script_travis()
else:
    script()

