#!/usr/bin/env python

# Copyright Rene Rivera 2016
# Copyright Peter Dimov 2017
#
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at
# http://www.boost.org/LICENSE_1_0.txt)

import sys
import os.path

from ci_boost_common import main, utils, script_common

class script(script_common):

    def __init__(self, ci_klass, **kargs):
        script_common.__init__(self, ci_klass, **kargs)

    def init(self, opt, kargs):
        kargs = super(script,self).init(opt,kargs)

        opt.add_option( '--toolset' )
        self.toolset = os.getenv( 'TOOLSET', None )

        opt.add_option( '--cxxstd' )
        self.cxxstd = os.getenv( 'CXXSTD', None )

        return kargs

    def command_build(self):
        super(script,self).command_build()

        # Build b2

        os.chdir(self.root_dir)

        if sys.platform == "win32":
            utils.check_call('cmd.exe', '/C', os.path.join(self.root_dir, "bootstrap.bat"))
        else:
            utils.check_call("./bootstrap.sh")

        # Build Boost

        cmd = [ './b2', '-j%s' % (self.jobs) ]

        if self.toolset:
            cmd.append( 'toolset=' + self.toolset )

        if self.cxxstd:
            cmd.append( 'cxxstd=' + self.cxxstd )

        utils.check_call( *cmd )

main(script)
