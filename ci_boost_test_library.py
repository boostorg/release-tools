#!/usr/bin/env python

# Copyright Rene Rivera 2016
# Copyright Peter Dimov 2017
#
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at
# http://www.boost.org/LICENSE_1_0.txt)

import sys
import os.path
import re

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

        super( script, self ).command_build()

        os.chdir( self.root_dir )

        if self.commit_message:

            m = re.match( r'Update (\w+) from', self.commit_message )

            if m:

                target = 'libs/' + m.group(1) + '/test'

                if os.path.exists( target ):

                    # Build b2

                    if sys.platform == 'win32':

                        utils.check_call('cmd.exe', '/C', os.path.join(self.root_dir, "bootstrap.bat"))

                    else:

                        utils.check_call("./bootstrap.sh")

                    os.environ['PATH'] = os.pathsep.join([self.root_dir,os.environ['PATH']])

                    # Headers
                    utils.check_call( 'b2', '-q', 'headers' )

                    # Test updated library

                    cmd = [ 'b2', '-j%s' % (self.jobs), target ]

                    if self.toolset:
                        cmd.append( 'toolset=' + self.toolset )

                    if self.cxxstd:
                        cmd.append( 'cxxstd=' + self.cxxstd )

                    utils.check_call( *cmd )

main(script)
