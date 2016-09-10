#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

GDCtool.py: this file is part of gdctools.  See the <root>/COPYRIGHT
file for the SOFTWARE COPYRIGHT and WARRANTY NOTICE.

@author: Michael S. Noble, Timothy DeFreitas, David I. Heiman
@date:  2016-05-20
'''

# }}}

import sys
import os
import traceback
import ConfigParser
import time
from GDCcli import GDCcli
from GDCcore import *

class GDCtool(object):
    ''' Base class for each tool in the GDCtools suite '''

    def __init__(self, version=None):

        self.cli = GDCcli(version=version)
        # Derived classes can/should add custom options/description/version &
        # behavior in their respective __init__()/execute() implementations

    def execute(self):
        self.options = self.cli.parse_args()
        self.parse_config()

    def parse_config(self):
        '''
        Read initial configuration state from one or more config files; store
        this state within .config member, a nested dict whose keys may also be
        referenced as attributes (safely, with a default value of None if unset)
        '''

        # FIXME: before pushing to main repo, ensure mirror/dice tools enforce
        # CONFIG_LISTS = [ 'mirror_programs', 'mirror_projects',
        #                   'dice_programs', 'dice_projects']

        self.config = attrdict(default=attrdict())      # initially empty
        if not self.options.config:                     # config file list
            return

        cfgparser = ConfigParser.SafeConfigParser()
        cfgparser.read( self.options.config )

        # [DEFAULT] defines vars for interpolation/substitution in other sections
        default_vars = [ item[0] for item in cfgparser.items('DEFAULT') ]

        config = self.config
        for section in cfgparser.sections():
            config[section] = attrdict()
            for option in cfgparser.options(section):
                # DEFAULT vars ALSO behave as though they were defined in every
                # section, but we purposely skip them here so that each section
                # reflects only the options explicitly defined in that section
                if option not in default_vars:
                    config[section][option] = cfgparser.get(section, option)

    def validate_config(self, vars_to_examine):
        '''
        Ensure that sufficient configuration state has been defined for tool to
        initiate its work; should only be called after CLI flags are parsed,
        because CLI has the highest precedence in setting configuration state
        '''
        for v in vars_to_examine:
            result = eval("self.config." + v)
            if result is None:
                gabort(100, "Required configuration variable is unset: %s" % v)

    def status(self):
        # Emit system info (as header comments suitable for TSV, etc) ...
        gprint('#')  # @UndefinedVariable
        gprint('# %-22s = %s' % (self.__class__.__name__ + ' version ',  # @UndefinedVariable
                                 self.cli.version))
        gprint('#')  # @UndefinedVariable

if __name__ == "__main__":
    tool = GDCtool()
    tool.execute()
    tool.status()

