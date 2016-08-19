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
import subprocess
import logging
import os
import csv
import ConfigParser
from pkg_resources import resource_filename

from lib import common
from lib import meta
from GDCtool import GDCtool


class sample_report(GDCtool):

    def __init__(self):
        super(sample_report, self).__init__(version="0.3.0")
        cli = self.cli

        desc =  'Create a Firehose loadfile from diced Genomic Data Commons (GDC) data'
        cli.description = desc

        tstmp_help = 'Use the available data as of this date. Default is the'
        tstmp_help += ' current time.'
        cli.add_argument('timestamp', nargs='?', help=tstmp_help)

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
            # Where redactions are stored
            redactions_dir = cfg.get('loadfiles', 'redactions_dir')
            # Blacklisted samples or aliquots
            blacklist_file = cfg.get('loadfiles', 'blacklist')
            # Reference data
            reference_dir = cfg.get('loadfiles', 'ref_dir')
            # Where the sample reports are stored
            reports_dir = cfg.get('loadfiles', 'reports_dir')
            self.reports_dir = reports_dir

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

        #FIXME: Hardcoded to just TCGA for now...
        diced_prog_root = os.path.join(self.dice_root_dir, 'TCGA')

        # Get the latest timestamp as the sample report date, otherwise use
        # timestamp
        timestamp = opts.timestamp
        if timestamp is None:
            timestamp = meta.latest_prog_timestamp(diced_prog_root)

        self.report_dir = os.path.join(self.reports_dir, 'report_' + timestamp)
        if not os.path.isdir(self.report_dir):
            os.makedirs(self.report_dir)

        logging.info("Creating aggregate counts file...")
        # Now infer certain values from the diced data directory
        sample_counts_file = self.create_agg_counts_file(diced_prog_root,
                                                         timestamp)
        heatmaps_dir = self.report_dir
        logging.info("Linking diced metadata...")
        link_diced_metadata(diced_prog_root, self.report_dir,
                            timestamp)
        #FIXME: only works for TCGA
        sample_loadfile = link_loadfile_metadata(self.load_dir, "TCGA",
                                               self.report_dir, timestamp)
        logging.info("Writing aggregates.txt to report dir...")
        aggregates_file = self.aggregates_file()

        # Command line arguments for report generation
        self.cmdArgs = ["Rscript", "--vanilla"]
        gdc_sample_report = resource_filename("gdctools","lib/GDCSampleReport.R")
        self.cmdArgs.extend([ gdc_sample_report,        # From gdctools pkg
                              timestamp,           # Specified from cli
                              self.report_dir,          # From config
                              reference_dir,            # From config
                              blacklist_file           # From config
                            ])

    def execute(self):
        super(sample_report, self).execute()
        common.init_logging()
        self.parse_args()
        opts = self.options
        # TODO: better error handling
        logging.info("Running GDCSampleReport.R, ")
        logging.info("CMD Args: " + " ".join(self.cmdArgs))
        p = subprocess.Popen(self.cmdArgs, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for line in iter(p.stdout.readline, ''):
            logging.info(line.rstrip())


    def create_agg_counts_file(self, diced_prog_root, timestamp):
        '''Create a program-wide counts file combining all cohorts, including aggregates'''
        # FIXME: TCGA hardcoded here
        aggregate_cohorts = self.aggregates.keys()
        aggregate_cohorts = [ag.replace('TCGA-', '') for ag in aggregate_cohorts]

        agg_counts_file = '.'.join(['sample_counts', timestamp, 'tsv'])
        agg_counts_file = os.path.join(self.report_dir, agg_counts_file)

        agg_annots = set()
        agg_counts = dict()
        agg_totals = dict()
        # NOTE: There is a lot of similarity between this inspection and
        # inspect_data in create_loadfile
        for cf in _counts_files(diced_prog_root, timestamp):
            # Filename is <project>
            cf_base = os.path.basename(cf)
            cohort = cf_base.split('.')[0].replace('TCGA-', '')
            with open(cf, 'r') as cfp:
                d_reader = csv.DictReader(cfp, delimiter='\t')
                annots = list(d_reader.fieldnames)
                annots.remove('Sample Type')
                agg_annots.update(annots)

                for row in d_reader:
                    sample_type = row['Sample Type']
                    cohort_type = cohort

                    if sample_type != 'Totals':
                        cohort_type += '-' + sample_type
                    agg_counts[cohort_type] = dict()
                    for a in annots:
                        count = int(row[a])
                        agg_counts[cohort_type][a] = count
                        # Update totals, but only for base cohorts, not aggregates
                        if row['Sample Type'] == 'Totals' and cohort not in aggregate_cohorts:
                            agg_totals[a] = agg_totals.get(a,0) + count

        # Now write the resulting aggregate counts file
        agg_annots = sorted(agg_annots)
        with open(agg_counts_file, 'w') as f:
            header = 'Cohort\t' + '\t'.join(agg_annots) + '\n'
            f.write(header)
            # Write row of counts for each annot
            for cohort in sorted(agg_counts):
                row = [cohort] + [str(agg_counts[cohort].get(a, 0)) for a in agg_annots]
                row = '\t'.join(row) + '\n'
                f.write(row)

            # Write totals
            tot_row = ['Totals'] + [str(agg_totals.get(a, 0)) for a in agg_annots]
            tot_row = '\t'.join(tot_row) + '\n'
            f.write(tot_row)

        return agg_counts_file

    def aggregates_file(self):
        '''Creates an aggregates.txt file in the reports directory. aggregates
        information is read from the [aggregates] section of the config file.
        '''
        agg_file = os.path.join(self.report_dir, 'aggregates.txt')

        with open(agg_file, 'w') as f:
            f.write('Aggregate Name\tTumor Types\n')
            for agg in sorted(self.aggregates.keys()):
                f.write(agg + '\t' + self.aggregates[agg] + '\n')

        return agg_file


def _counts_files(diced_prog_root, timestamp):
    '''Generate the counts files for each project in a program'''
    # 'dirs' will be the diced project names
    root, dirs, files = os.walk(diced_prog_root).next()

    for project in dirs:
        meta_dir = os.path.join(root, project, 'metadata')

        # Find the appropriate timestamp to use for the latest counts.
        # The correct file is the one with the latest timestamp that is
        # earlier than the given timestamp
        meta_dirs = [d for d in os.listdir(meta_dir) if d <= timestamp]

        # If no such meta_dir exists, then there was no data for this project
        # as of the provided date
        if len(meta_dirs) > 0:
            latest_tstamp = sorted(meta_dirs)[-1]
            count_f = '.'.join([project, latest_tstamp, 'sample_counts','tsv'])
            count_f = os.path.join(meta_dir, latest_tstamp, count_f)

            # Final sanity check, file must exist
            if os.path.isfile(count_f):
                yield count_f


def link_diced_metadata(diced_prog_root, report_dir, timestamp):
    '''Symlink all heatmaps into <reports_dir>/report_<timestamp> and return
    that directory'''
    root, dirs, files = os.walk(diced_prog_root).next()
    for project in dirs:
        meta_dir = os.path.join(root, project, 'metadata', timestamp)

        # Link high and low res heatmaps to the report dir
        heatmap_high = '.'.join([project, timestamp, 'high_res.heatmap.png'])
        heatmap_low = '.'.join([project, timestamp, 'low_res.heatmap.png'])
        link_metadata_file(meta_dir, report_dir, heatmap_high)
        link_metadata_file(meta_dir, report_dir, heatmap_low)

        #Link project-level sample counts
        samp_counts = '.'.join([project, timestamp, 'sample_counts', 'tsv'])
        link_metadata_file(meta_dir, report_dir, samp_counts)

        # Link the diced metadata TSV
        diced_meta = '.'.join([project, timestamp, 'diced_metadata', 'tsv'])
        link_metadata_file(meta_dir, report_dir, diced_meta)

    return report_dir

def link_metadata_file(from_dir, report_dir, filename):
    """ Ensures symlink report_dir/filename -> from_dir/filename exists"""
    from_path = os.path.join(from_dir, filename)
    from_path = os.path.abspath(from_path)
    rpt_path = os.path.join(report_dir, filename)
    rpt_path = os.path.abspath(rpt_path)
    if os.path.isfile(from_path) and not os.path.isfile(rpt_path):
        os.symlink(from_path, rpt_path)

def link_loadfile_metadata(load_dir, program, report_dir, timestamp):
    """Symlink loadfile and filtered samples into report directory"""
    from_dir = os.path.join(load_dir, program, timestamp)
    loadfile = program + '.' + timestamp + ".Sample.loadfile.txt"
    link_metadata_file(from_dir, report_dir, loadfile)
    filtered = program + '.' + timestamp + ".filtered_samples.txt"
    link_metadata_file(from_dir, report_dir, filtered)


if __name__ == "__main__":
    sample_report().execute()
