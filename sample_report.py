#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

sample_report: wrapper around SampleSummaryReport.R for GDC-derived data
See the <root>/COPYRIGHT file for the SOFTWARE COPYRIGHT and WARRANTY NOTICE.

@author: Timothy DeFreitas
@date:  2016_06_28
'''

# }}}

from __future__ import print_function
import logging
import os
import csv
import ConfigParser
from lib import common
from pkg_resources import resource_filename
import subprocess
from GDCtool import GDCtool


class sample_report(GDCtool):

    def __init__(self):
        super(sample_report, self).__init__(version="0.1.0")
        cli = self.cli

        desc =  'Create a Firehose loadfile from diced Genomic Data Commons (GDC) data'
        cli.description = desc
        cli.add_argument('timestamp',
                         help='Generate sample summary report for the given date.')

    def parse_args(self):
        opts = self.options

        # Parse custom [loadfiles] section from configuration file.
        # This logic is intentionally omitted from GDCtool:parse_config, since
        # loadfiles are only useful to FireHose, and this tool is not distributed

        if opts.config:
            cfg = ConfigParser.ConfigParser()
            cfg.read(opts.config)

            # FIXME: this implicitly uses default lowercase behavior of config
            #        parser ... which I believe we consider a bit more
            #        For case sensitivity we can use the str() function as in:
            #           cfg.optionxform = str

            #FIXME: Surround the required config options in try/catch

            #Filtered samples file, required
            filtered_samples_file = cfg.get('loadfiles', 'filtered_samples')
            #Where redactions are stored
            redactions_dir = cfg.get('loadfiles', 'redactions_dir')
            # Blacklisted samples or aliquots
            blacklist_file = cfg.get('loadfiles', 'blacklist')
            # Reference data
            reference_dir = cfg.get('loadfiles', 'ref_dir')

            #
            if cfg.has_option('loadfiles', 'load_dir'):
                self.load_dir = cfg.get('loadfiles', 'load_dir')
            if cfg.has_option('loadfiles', 'heatmaps_dir'):
                self.heatmaps_dir = cfg.get('loadfiles', 'heatmaps_dir')

            self.aggregates = dict()
            if cfg.has_section('aggregates'):
                for aggr in cfg.options('aggregates'):
                    aggr = aggr.upper()
                    self.aggregates[aggr] = cfg.get('aggregates', aggr)

        else:
            raise ValueError('Config file required for sample report generation')



        # Now infer certain values from the diced data directory
        sample_counts_file = get_counts_file()
        heatmaps_dir = get_heatmaps_dir()
        sample_loadfile = get_sample_loadfile()
        aggregates_file = get_aggregates_file()


        # Command line arguments for report generation
        self.cmdArgs = ["Rscript", "--vanilla"]
        gdc_sample_report = resource_filename("gdctools","lib/GDCSampleReport.R")
        self.cmdArgs.extend([ gdc_sample_report,        # From gdctools pkg
                              redactions_dir,           # From config
                              sample_counts_file,       # Inferred from dicer + timestamp
                              opts.timestamp,           # Specified from cli
                              filtered_samples_file,    # From config
                              heatmaps_dir,            # Infered from dicer + timestamp
                              blacklist_file,           # From config
                              sample_loadfile,          # Inferred from loadfile dir + timestamp
                              reference_dir,            # From config
                              report_dir,               # From config
                              aggregates_file           # Created with aggregates in config
                            ])





    def execute(self):
        super(sample_report, self).execute()
        self.parse_args()
        opts = self.options
        common.init_logging()
        # TODO: better error handling
        print(self.cmdArgs)
        #logging.info("CMD Args: " + " ".join(self.cmdArgs))
        #report_stdout = subprocess.check_output(self.cmdArgs)

def get_counts_file():
    pass

def get_heatmaps_dir():
    pass

def get_sample_loadfile():
    pass

def get_aggregates_file():
    pass

if __name__ == "__main__":
    sample_report().execute()
