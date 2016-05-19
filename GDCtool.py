#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

GDCtool.py: this file is part of mdbtools.  See the <root>/COPYRIGHT
file for the SOFTWARE COPYRIGHT and WARRANTY NOTICE.

@author: Michael S. Noble
@date:  2016-03-04
'''

# }}}

import sys
import os
import traceback
from GDCcli import GDCcli
from GDCutils import *

class GDCtool(object):
    ''' Base class for each tool '''

    def __init__(self, version=None):

        self.cli = GDCcli(version=version)
        # Derived classes can/should add custom options/description/version &
        # behavior in their respective __init__()/execute() implementations

    def execute(self):
        self.options = self.cli.parse_args()

    def status(self):
        # Emit system info (as header comments suitable for TSV, etc) ...
        gprint('#')  # @UndefinedVariable
        gprint('# %-22s = %s' % (self.__class__.__name__ + ' version ',  # @UndefinedVariable
                                 self.cli.version))

if __name__ == "__main__":
    tool = GDCtool()
    tool.execute()
    tool.status()
