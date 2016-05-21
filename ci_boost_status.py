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

        #~ Defaults
        self.debug_level=0
        ( _opt_, self.actions ) = opt.parse_args(None,self)
        if not self.actions or self.actions == []:
            self.actions = [ 'info' ]
        if not root_dir:
            self.root_dir = os.getcwd()
        else:
            self.root_dir = root_dir
        self.build_dir = os.path.join(os.path.dirname(self.root_dir), "build")
        self.home_dir = os.path.expanduser('~')
        self.branch = branch
        self.commit = commit

        self.main()

    # Common test commands in the order they should be executed..
    
    def command_base_info(self):
        pass
    
    def command_base_before_build(self):
        # Fetch the rest of the Boost submodules in the appropriate
        # EOL style.
        utils.check_call("git","submodule","update","--init","--recursive")

    def command_base_build(self):
        # Simple integrated status tests check. Currently this only
        # veryfies that we will not get build system errors from things
        # like missing test files.
        os.chdir(self.root_dir)
        utils.check_call("./bootstrap.sh")
        utils.check_call("./b2","-n")
        os.chdir(os.path.join(self.root_dir,"status"))
        utils.check_call("../b2","-n","-d0")

    #~ Utilities...

    def main(self):
        for action in self.actions:
            action_m = "command_"+action.replace('-','_')
            if hasattr(self,action_m):
                getattr(self,action_m)()

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
        pass

    def command_before_script(self):
        self.command_base_before_build()

    def command_script(self):
        self.command_base_build()

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

class script_appveyor(script):
    
    def __init__(self):
        script.__init__(self,
            root_dir=os.getenv("APPVEYOR_BUILD_FOLDER"))
    
    # Appveyor commands in the order they are executed..
    
    def command_install(self):
        pass
    
    def command_before_build(self):
        self.command_base_before_build()
    
    def command_build_script(self):
        self.command_base_build()
    
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

