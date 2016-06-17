#!/usr/bin/env python

# Copyright Rene Rivera 2016
#
# Distributed under the Boost Software License, Version 1.0.
# (See accompanying file LICENSE_1_0.txt or copy at
# http://www.boost.org/LICENSE_1_0.txt)

import os.path

from ci_boost_common import main, utils, script_common

class script(script_common):

    def __init__(self, ci_klass, **kargs):
        script_common.__init__(self, ci_klass, **kargs)

    def command_build(self):
        super(script,self).command_build()
        # Simple integrated status tests check. Currently this only
        # veryfies that we will not get build system errors from things
        # like missing test files.
        os.chdir(self.root_dir)
        utils.check_call("./bootstrap.sh")
        utils.check_call("./b2","-n")
        os.chdir(os.path.join(self.root_dir,"status"))
        utils.check_call("../b2","-n","-d0")

main(script)
