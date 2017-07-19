#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

gdc_report: wrapper around SampleSummaryReport.R for GDC-derived data
See the <root>/COPYRIGHT file for the SOFTWARE COPYRIGHT and WARRANTY NOTICE.

@author: Timothy DeFreitas, Michael S. Noble
@date:  2016_09_11
'''

# }}}

from __future__ import print_function
import subprocess
import logging
import os
from pkg_resources import resource_filename
from glob import iglob

from gdctools.lib.heatmap import draw_heatmaps
from gdctools.lib.meta import extract_case_data
from gdctools.lib.common import silent_rm

from gdctools.GDCtool import GDCtool

class gdc_report(GDCtool):

    def __init__(self):
        description = 'Generate a sample report for a snapshot of data ' + \
                'mirrored & diced\nfrom the Genomic Data Commons (GDC)'
        super(gdc_report, self).__init__("0.3.2", description)

        # FIXME: add options for each config setting

    def config_customize(self):
        # Ensure tool has sufficient configuration info to run
        mandatory_config  =  ["dice.dir", "loadfile.dir", "reference_dir"]
        mandatory_config +=  ["report.dir", "report.blacklist"]
        self.validate_config(mandatory_config)

    def execute(self):
        super(gdc_report, self).execute()

        config = self.config
        # FIXME: remove TCGA hardcode
        diced_prog_root = os.path.join(config.dice.dir, 'TCGA')
        datestamp = self.datestamp
        latest = os.path.join(config.report.dir, 'latest')
        config.report.dir = os.path.join(config.report.dir,
                                          'report_' + datestamp)
        if not os.path.isdir(config.report.dir):
            os.makedirs(config.report.dir)
            silent_rm(latest)
            os.symlink(os.path.abspath(config.report.dir), latest)

        # Now infer certain values from the diced data directory
        logging.info("Obtaining diced metadata...")
        get_diced_metadata(diced_prog_root, config.report.dir, datestamp)

        # FIXME: remove TCGA hardcode
        link_loadfile_metadata(config.loadfile.dir, "TCGA", config.report.dir,
                               datestamp)

        if config.aggregates:
            logging.info("Writing aggregate cohort definitions to report dir...")
            self.write_aggregate_definitions()

        logging.info("Linking combined sample counts ...")
        all_counts_file = '.'.join(['sample_counts', datestamp, 'tsv'])
        link_metadata_file(os.path.join(diced_prog_root, 'metadata'),
                           self.config.report.dir, all_counts_file)

        # Command line arguments for report generation
        self.cmdArgs = ["Rscript", "--vanilla"]
        report_script = resource_filename(__name__, "lib/GDCSampleReport.R")
        self.cmdArgs.extend([ report_script,            # From gdctools pkg
                              datestamp,                # Specified from cli
                              config.report.dir,
                              config.reference_dir,
                              config.report.blacklist
                            ])

        # TODO: better error handling
        logging.info("Running GDCSampleReport.R ")
        logging.info("CMD Args: " + " ".join(self.cmdArgs))
        try:
            p = subprocess.Popen(self.cmdArgs, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for line in p.stdout:
                logging.info(line.rstrip())
                p.stdout.flush()
        except:
            logging.exception("Sample report generation FAILED:")

    def write_aggregate_definitions(self):
        '''Creates an aggregates.txt file in the reports directory. aggregates
        information is read from the [aggregates] section of the config file.
        '''
        aggregates = self.config.aggregates
        ag_file = os.path.join(self.config.report.dir, 'aggregates.txt')
        with open(ag_file, 'w') as f:
            f.write('Aggregate Name\tTumor Types\n')
            for agg in sorted(aggregates.keys()):
                f.write(agg + '\t' + aggregates[agg] + '\n')

def get_diced_metadata(diced_prog_root, report_dir, datestamp):
    '''
    Create heatmaps and symlinks to dicing metadata in
    <reports_dir>/report_<datestamp>.
    '''
    for meta_dir in iglob(os.path.join(diced_prog_root, '*', 'metadata',
                                       datestamp)):
        project = meta_dir.split(os.path.sep)[-3]

        #Link project-level sample counts
        samp_counts = '.'.join([project, datestamp, 'sample_counts', 'tsv'])
        link_metadata_file(meta_dir, report_dir, samp_counts)

        # Link the diced metadata TSV
        diced_meta = '.'.join([project, datestamp, 'diced_metadata', 'tsv'])
        link_metadata_file(meta_dir, report_dir, diced_meta)

        # Create high and low res heatmaps in the report dir
        logging.info("Generating heatmaps for " + project)
        case_data = extract_case_data(os.path.join(meta_dir, diced_meta))
        draw_heatmaps(case_data, project, datestamp, report_dir)

def link_metadata_file(from_dir, report_dir, filename):
    """ Ensures symlink report_dir/filename -> from_dir/filename exists"""
    from_path = os.path.join(from_dir, filename)
    from_path = os.path.abspath(from_path)
    rpt_path = os.path.join(report_dir, filename)
    rpt_path = os.path.abspath(rpt_path)
    if os.path.isfile(from_path) and not os.path.isfile(rpt_path):
        os.symlink(from_path, rpt_path)

def link_loadfile_metadata(loadfiles_dir, program, report_dir, datestamp):
    """Symlink loadfile and filtered samples into report directory"""
    from_dir = os.path.join(loadfiles_dir, program, datestamp)
    loadfile = program + ".Sample.loadfile.txt"
    link_metadata_file(from_dir, report_dir, loadfile)
    filtered = program + ".filtered_samples.txt"
    link_metadata_file(from_dir, report_dir, filtered)

def main():
    gdc_report().execute()

if __name__ == "__main__":
    main()
