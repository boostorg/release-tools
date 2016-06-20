#!/usr/bin/env python

# Copyright Rene Rivera 2016
#
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at
# http://www.boost.org/LICENSE_1_0.txt)

import sys
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
    
    call_stats = []
    
    @staticmethod
    def call(*command, **kargs):
        utils.log( "%s> '%s'"%(os.getcwd(), "' '".join(command)) )
        t = time.time()
        result = subprocess.call(command, **kargs)
        t = time.time()-t
        if result != 0:
            print "Failed: '%s' ERROR = %s"%("' '".join(command), result)
        utils.call_stats.append((t,os.getcwd(),command,result))
        utils.log( "%s> '%s' execution time %s seconds"%(os.getcwd(), "' '".join(command), t) )
        return result
    
    @staticmethod
    def print_call_stats():
        utils.log("================================================================================")
        for j in sorted(utils.call_stats, reverse=True):
            utils.log("{:>12.4f}\t{}> {} ==> {}".format(*j))
        utils.log("================================================================================")
    
    @staticmethod
    def check_call(*command, **kargs):
        cwd = os.getcwd()
        result = utils.call(*command, **kargs)
        if result != 0:
            raise(SystemCallError([cwd].extend(command), result))
    
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
    
    @staticmethod
    def mem_info():
        if sys.platform == "darwin":
            utils.call("top","-l","1","-s","0","-n","0")
        elif sys.platform.startswith("linux"):
            utils.call("free","-m","-l")

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

class script_common(object):
    '''
    Main script to run Boost C++ Libraries continuous integration.
    '''

    def __init__(self, ci_klass, **kargs):
        self.ci = ci_klass(self)

        opt = optparse.OptionParser(
            usage="%prog [options] [commands]")

        #~ Debug Options:
        opt.add_option( '--debug-level',
            help="debugging level; controls the amount of debugging output printed",
            type='int' )
        opt.add_option( '-j',
            help="maximum number of parallel jobs to use for building with b2",
            type='int', dest='jobs')
        opt.add_option('--branch')
        opt.add_option('--commit')
        kargs = self.init(opt,kargs)
        kargs = self.ci.init(opt, kargs)
        branch = kargs.get('branch',None)
        commit = kargs.get('commit',None)
        actions = kargs.get('actions',None)
        root_dir = kargs.get('root_dir',None)

        #~ Defaults
        self.debug_level=0
        self.jobs=2
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
        
        # API keys.
        self.bintray_key = os.getenv('BINTRAY_KEY')
        self.sf_releases_key = os.getenv('SF_RELEASES_KEY')

        try:
            self.start()
            self.command_info()
            self.main()
            utils.print_call_stats()
        except:
            utils.print_call_stats()
            raise
    
    def init(self, opt, kargs):
        return kargs
    
    def start(self):
        pass

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
    
    def __getattr__(self, attr):
        '''
        Wraps attribute access to fabricate method calls that
        forward to the ci instance. This allows the ci to add and
        override script commands as needed.
        '''
        if attr.startswith('command_'):
            ci_command = getattr(self.ci, attr)
            if ci_command:
                def call(*args, **kwargs):
                    return ci_command(*args, **kwargs)
                return call
        return self.__dict__[attr]

    # Common test commands in the order they should be executed..
    
    def command_info(self):
        if self.ci and hasattr(self.ci,'command_info'):
            self.ci.command_info()
    
    def command_install(self):
        utils.makedirs(self.build_dir)
        os.chdir(self.build_dir)
        if self.ci and hasattr(self.ci,'command_install'):
            self.ci.command_install()
    
    def command_before_build(self):
        if self.ci and hasattr(self.ci,'command_before_build'):
            self.ci.command_before_build()

    def command_build(self):
        if self.ci and hasattr(self.ci,'command_build'):
            self.ci.command_build()

    def command_after_success(self):
        if self.ci and hasattr(self.ci,'command_after_success'):
            self.ci.command_after_success()

class ci_cli():
    '''
    This version of the script provides a way to do manual building. It sets up
    additional environment and adds fetching of the git repos that would
    normally be done by the CI system.
    
    The common way to use this variant is to invoke something like:
    
        mkdir boost-ci
        cd boost-ci
        python path-to/ci_boost_<script>.py --branch=develop
    
    Status: In working order.
    '''
    
    def __init__(self,script):
        if sys.platform == 'darwin':
            # Requirements for running on OSX:
            # https://www.stack.nl/~dimitri/doxygen/download.html#srcbin
            # https://tug.org/mactex/morepackages.html
            doxygen_path = "/Applications/Doxygen.app/Contents/Resources"
            if os.path.isdir(doxygen_path):
                os.environ["PATH"] = doxygen_path+':'+os.environ['PATH']
        self.script = script
    
    def init(self, opt, kargs):
        kargs['actions'] = [
            'clone',
            'install',
            'before_build',
            'build',
            ]
        return kargs
    
    def command_clone(self):
        '''
        This clone mimicks the way Travis-CI clones a project's repo. So far
        Travis-CI is the most limiting in the sense of only fetching partial
        history of the repo.
        '''
        cwd = os.getcwd()
        self.script.root_dir = os.path.join(cwd,'boostorg','boost')
        self.script.build_dir = os.path.join(os.path.dirname(self.script.root_dir), "build")
        if not os.path.exists(os.path.join(self.script.root_dir,'.git')):
            utils.check_call("git","clone","--depth=50","--branch=%s"%(self.script.branch),"https://github.com/boostorg/boost.git","boostorg/boost")
            os.chdir(self.script.root_dir)
        else:
            os.chdir(self.script.root_dir)
            utils.check_call("git","pull","--quiet","--no-recurse-submodules","--depth=50")
        if self.script.commit:
            utils.check_call("git","checkout","-qf",self.script.commit)
        utils.check_call("git","submodule","update","--quiet","--init","--recursive")

class ci_travis(object):
    '''
    This variant build releases in the context of the Travis-CI service.
    
    Status: In working order.
    '''
    
    def __init__(self,script):
        self.script = script
    
    def init(self, opt, kargs):
        kargs['root_dir'] = os.getenv("TRAVIS_BUILD_DIR")
        kargs['branch'] = os.getenv("TRAVIS_BRANCH")
        kargs['commit'] = os.getenv("TRAVIS_COMMIT")
        return kargs

    # Travis-CI commands in the order they are executed. We need
    # these to forward to our common commands, if they are different.
    
    def command_before_install(self):
        pass
    
    def command_install(self):
        pass

    def command_before_script(self):
        self.script.command_before_build()

    def command_script(self):
        self.script.command_build()

    def command_after_success(self):
        pass

    def command_after_failure(self):
        pass

    def command_before_deploy(self):
        pass

    def command_after_deploy(self):
        pass

    def command_after_script(self):
        pass

class ci_circleci(object):
    '''
    This variant build releases in the context of the CircleCI service.
    
    Status: Untested.
    '''
    
    def __init__(self,script):
        self.script = script
    
    def init(self, opt, kargs):
        kargs['root_dir'] = os.getenv("TRAVIS_BUILD_DIR")
        kargs['branch'] = os.getenv("CIRCLE_BRANCH")
        kargs['commit'] = os.getenv("CIRCLE_SHA1")
        return kargs

class ci_appveyor(object):
    
    def __init__(self,script):
        self.script = script
    
    def init(self, opt, kargs):
        kargs['root_dir'] = os.getenv("APPVEYOR_BUILD_FOLDER")
        kargs['branch'] = os.getenv("APPVEYOR_REPO_BRANCH")
        kargs['commit'] = os.getenv("APPVEYOR_REPO_COMMIT")
        return kargs
    
    # Appveyor commands in the order they are executed. We need
    # these to forward to our common commands, if they are different.
    
    def command_install(self):
        pass
    
    def command_before_build(self):
        os.chdir(self.script.root_dir)
        utils.check_call("git","submodule","update","--quiet","--init","--recursive")
    
    def command_build_script(self):
        self.script.command_build()
    
    def command_after_build(self):
        pass
    
    def command_before_test(self):
        pass
    
    def command_test_script(self):
        pass
    
    def command_after_test(self):
        pass
    
    def command_on_success(self):
        self.script.command_after_success()
    
    def command_on_failure(self):
        pass
    
    def command_on_finish(self):
        pass

def main(script_klass):
    if os.getenv('TRAVIS', False):
        script_klass(ci_travis)
    elif os.getenv('CIRCLECI', False):
        script_klass(ci_circleci)
    elif os.getenv('APPVEYOR', False):
        script_klass(ci_appveyor)
    else:
        script_klass(ci_cli)
