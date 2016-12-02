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

from lib import common

class GDCtool(object):
    ''' Base class for each tool in the GDCtools suite '''
    def __init__(self, version=None):

        self.cli = GDCcli(version=version)
        # Derived classes can/should add custom options/description/version &
        # behavior in their respective __init__()/execute() implementations

    def execute(self):
        self.options = self.cli.parse_args()
        self.parse_config()
        self.init_logging()

    def parse_config(self):
        '''
        Read initial configuration state from one or more config files; store
        this state within .config member, a nested dict whose keys may also be
        referenced as attributes (safely, with a default value of None if unset)
        '''

        self.config = attrdict(default=attrdict())      # initially empty
        if not self.options.config:                     # list of config files
            return

        cfgparser = ConfigParser.SafeConfigParser()
        # Since we use argparse to ensure filenames, but config parser expects
        # filenames, convert them here
        cfgparser.read([f.name for f in self.options.config])
        config = self.config

        # [DEFAULT] defines common variables for interpolation/substitution in
        # other sections, and are stored at the root level of the config object
        for keyval in cfgparser.items('DEFAULT'):
            config[keyval[0]] = keyval[1]

        for section in cfgparser.sections():
            config[section] = attrdict()
            for option in cfgparser.options(section):
                # DEFAULT vars ALSO behave as though they were defined in every
                # section, but we purposely skip them here so that each section
                # reflects only the options explicitly defined in that section
                if not config[option]:
                    config[section][option] = cfgparser.get(section, option)

        def get_config_values_as_list(values):
            if values:
                return [ v.strip() for v in values.split(',') ]
            else:
                return [ ]

        # Ensure programs,projects,cases config state are lists
        config.programs = get_config_values_as_list(config.programs)
        config.projects = get_config_values_as_list(config.projects)
        config.cases    = get_config_values_as_list(config.cases)

        # Ensure that aggregate cohort names (if present) are in uppercase
        # (necessary because ConfigParser returns option names in lowercase)
        # If no aggregates are defined, change None obj to empty dict, for
        # cleaner "if X in config.aggregates:" queries that will always work
        if config.aggregates:
            for key, val in config.aggregates.items():
                config.aggregates[key.upper()] = config.aggregates.pop(key)
        else:
            config.aggregates = {}

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

    def init_logging(self):
        # Get today's datestamp, the default value
        datestamp = time.strftime('%Y_%m_%d', time.localtime())

        if self.options.datestamp:
            # We are using an explicit datestamp, so it must match one from
            # the datestamps file, or be the string "latest"
            datestamp = self.options.datestamp
            datestamps_file = self.config.datestamps
            # Any error trying to read the existing datestamps is equally bad
            try:
                # Read existing stamps
                existing_stamps = sorted([d.strip() for d in open(datestamps_file)])

                if datestamp == "latest":
                    datestamp = existing_stamps[-1]
                elif datestamp not in existing_stamps:
                    # Timestamp not recognized, but print a combined message later
                    raise Exception
            except:
                raise ValueError("Given datestamp not present in "
                                 + datestamps_file
                                 + ". Mirror likely does not exist" )

        # At this point, datestamp must be a valid value, so initialize the
        # logging with that value
        self.datestamp = datestamp

        # Put the logs in the right place, with the right name
        log_dir = self.config.log_dir
        tool_name = self.__class__.__name__
        log_dir = os.path.join(log_dir, tool_name)

        #TODO: Move the rest of this function here
        common.init_logging(datestamp, log_dir, tool_name)



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
