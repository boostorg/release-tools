#!/usr/bin/env python

# Copyright Rene Rivera 2016
#
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at
# http://www.boost.org/LICENSE_1_0.txt)

import sys
import os.path

from ci_boost_common import main, utils, script_common

# Check python version
if sys.version_info[0] == 2 :
    pythonversion="2"
    pythonbinary="python2"
else:
    pythonversion="3"
    pythonbinary="python3"

class script(script_common):

    def __init__(self, ci_klass, **kargs):
        script_common.__init__(self, ci_klass, **kargs)

    def init(self, opt, kargs):
        kargs = super(script,self).init(opt,kargs)

        opt.add_option( '--target', help='test target (none, quick, minimal)' )
        self.target = os.getenv( 'TARGET', 'none' )

        opt.add_option( '--toolset' )
        self.toolset = os.getenv( 'TOOLSET', None )

        opt.add_option( '--cxxstd' )
        self.cxxstd = os.getenv( 'CXXSTD', None )

        opt.add_option( '--release' )
        self.release = os.getenv( 'RELEASE', None )

        return kargs

    def command_build(self):
        super(script,self).command_build()

        # if --release, switch to release layout

        if self.release:

            os.chdir(self.build_dir)
            utils.check_call('wget','https://raw.githubusercontent.com/boostorg/release-tools/develop/MakeBoostDistro.py')
            utils.check_call('chmod','+x','MakeBoostDistro.py')

            os.chdir(self.root_dir)
            utils.check_call(pythonbinary,os.path.join(self.build_dir,'MakeBoostDistro.py'),
                self.root_dir, 'release')

            self.root_dir = os.path.join( self.root_dir, 'release' )

        # Build b2

        os.chdir(self.root_dir)
        if sys.platform == "win32":
            utils.check_call('cmd.exe', '/C', os.path.join(self.root_dir, "bootstrap.bat"))
        else:
            utils.check_call("./bootstrap.sh")
        os.environ['PATH'] = os.pathsep.join([self.root_dir,os.environ['PATH']])

        if self.target == 'none':

            # Simple integrated status tests check. Only verifies that
            # we will not get build system errors from things like missing
            # test files.

            utils.check_call("b2","headers")
            os.chdir(os.path.join(self.root_dir,"status"))
            utils.check_call("b2","-n","-d0")

        else:

            # Build specified target in status/Jamfile

            os.chdir(os.path.join(self.root_dir,"status"))

            cmd = [ 'b2', '-j%s' % (self.jobs), self.target ]

            if self.toolset:
                cmd.append( 'toolset=' + self.toolset )

            if self.cxxstd:
                cmd.append( 'cxxstd=' + self.cxxstd )

            utils.check_call( *cmd )

main(script)
