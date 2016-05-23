#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

gdc_mirror: this file is part of gdctools.  See the <root>/COPYRIGHT
file for the SOFTWARE COPYRIGHT and WARRANTY NOTICE.

@author: Michael S. Noble, Timothy DeFreitas
@date:  2016_05_18
'''

# }}}
from __future__ import print_function


import sys
import os
import logging
import time
import ConfigParser

from GDCtool import GDCtool

class gdc_mirror(GDCtool):

    def __init__(self):
        super(gdc_mirror, self).__init__(version="0.3.0")
        cli = self.cli

        desc =  'Create local mirror of the data from arbitrary programs '\
                'and projects warehoused at the Genomic Data Commons (GDC)\n'
        cli.description = desc

        #Optional overrides of config file
        #cli.add_argument('-l', '--log-directory', help='Folder to store logfiles')
        
        cli.add_argument('config', help='GDC mirror configuration file')

    def set_timestamp(self):
        '''Creates a timestamp for the current mirror'''
        self.timestamp = time.strftime('%Y_%m_%d__%H_%M_%S')
        return self.timestamp 

    def init_logging(self):
        logfile_name = ".".join(["gdcMirror", self.timestamp, "log"])
        if not os.path.isdir(self.log_dir):
            os.makedirs(self.log_dir)
        logfile_path = os.path.join(self.log_dir, logfile_name)
        logging.basicConfig(filename=logfile_path, 
                            format='%(asctime)s::%(levelname)s  %(message)s',
                            datefmt='%Y-%m-%d %I:%M:%S %p', 
                            level=logging.INFO)
        
        #Create a symlink indicating this is the latest log
        latest_path = os.path.join(self.log_dir, "gdcMirror.latest.log")
        try:
            os.unlink(latest_path)
        except OSError:
            #Symlink didn't exist, no problem
            pass
        os.symlink(os.path.abspath(logfile_path), latest_path)


    def parseConfig(self, config_file):
        """Read options from config, and optionally override them with args"""
        cfg = ConfigParser.ConfigParser()
        cfg.read(config_file)

        self.config = cfg
        cwd = os.getcwd()

        #Required configuration parameters
        self.gdc_api_root = cfg.get('general', 'GDC_API_ROOT')

        #Optional configuration parameters
        if cfg.has_option('general', 'LOG_DIRECTORY'):
            self.log_dir = cfg.get('general', 'LOG_DIRECTORY')
        else:
            self.log_dir = cwd
        
        if cfg.has_option('general', 'MIRROR_ROOT_DIR'):
            self.root_dir = cfg.get('general', 'MIRROR_ROOT_DIR')
        else:
            self.root_dir = os.path.join(cwd, "gdc_mirror_root")

    def mirror(self):
        logging.info("GDC Mirror Version: %s", self.cli.version)
        logging.info("Configuration File: %s", os.path.abspath(self.options.config))

        if not os.path.isdir(self.root_dir):
            os.makedirs(self.root_dir)


    def execute(self):
        super(gdc_mirror, self).execute()
        opts = self.options
        self.parseConfig(opts.config)
        self.set_timestamp()
        self.init_logging()
        self.mirror()

if __name__ == "__main__":
    gdc_mirror().execute()
