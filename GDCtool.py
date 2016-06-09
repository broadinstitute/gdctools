#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

GDCtool.py: this file is part of gdctools.  See the <root>/COPYRIGHT
file for the SOFTWARE COPYRIGHT and WARRANTY NOTICE.

@author: Michael S. Noble
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
    ''' Base class for each tool '''

    def __init__(self, version=None):

        self.cli = GDCcli(version=version)
        # Derived classes can/should add custom options/description/version &
        # behavior in their respective __init__()/execute() implementations

    def execute(self):
        self.options = self.cli.parse_args()
        self.parse_config()

    def __configure(self, option, cfg_parser, multi=False):
        '''Gets the value of "option" from the cfg_parser or it's default
        If multi is True, the option is split by ',' and returned as list
        '''
        today = time.strftime('%Y_%m_%d')
        CONFIG_DEFAULTS = {
            'mirror' : {
                'root_dir': 'gdc_mirror__' + today,
                'log_dir' : 'gdc_mirror_log__' + today,
                'programs': ['TCGA'],
                'projects': None
            },
            'dice' : {
                'root_dir': 'gdc_mirror__' + today,
                'log_dir' : 'gdc_mirror_log__' + today,
                'programs': 'TCGA',
                'projects': None
            }
        }
        # All options are namespaced
        sect, opt = option.split('_', 1)
        value = CONFIG_DEFAULTS[sect].get(opt, None)
        if cfg_parser is not None and cfg_parser.has_option(sect, opt):
            value = cfg_parser.get(sect, opt)
            if multi: value = value.strip().split(',')

        # If value was set by cli flag, overwrite it
        value = getattr(self.options, option, value)
        # Store the option in self
        setattr(self, option, value)
        return value


    def parse_config(self):
        """Read options from config, and optionally override them with args"""
        config_file = self.options.config
        cfg = None
        if config_file is not None:
            cfg = ConfigParser.ConfigParser()
            cfg.read(config_file)

        CONFIG_ITEMS = [ 'mirror_root_dir', 'mirror_log_dir',
                          'dice_root_dir', 'dice_log_dir']
        CONFIG_LISTS = [ 'mirror_programs', 'mirror_projects',
                         'dice_programs', 'dice_projects']

        for conf in CONFIG_ITEMS:
            self.__configure(conf, cfg)

        for conf in CONFIG_LISTS:
            self.__configure(conf, cfg, True)

    def status(self):
        # Emit system info (as header comments suitable for TSV, etc) ...
        gprint('#')  # @UndefinedVariable
        gprint('# %-22s = %s' % (self.__class__.__name__ + ' version ',  # @UndefinedVariable
                                 self.cli.version))

if __name__ == "__main__":
    tool = GDCtool()
    tool.execute()
    tool.status()
