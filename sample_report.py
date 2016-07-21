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

        tstmp_help = 'Use the available data as of this date. Default is the'
        tstmp_help += ' current time.'
        cli.add_argument('timestamp', nargs='?',
                         default=common.timetuple2stamp(), help=tstmp_help)

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

        self.report_dir = os.path.join(self.reports_dir, 'report_' + opts.timestamp)
        if not os.path.isdir(self.report_dir):
            os.makedirs(self.report_dir)

        #FIXME: Hardcoded to just TCGA for now...
        diced_prog_root = os.path.join(self.dice_root_dir, 'TCGA')

        # Now infer certain values from the diced data directory
        sample_counts_file = self.create_agg_counts_file(diced_prog_root,
                                                        opts.timestamp)
        heatmaps_dir = link_heatmaps(diced_prog_root, self.report_dir,
                                     opts.timestamp)
        #FIXME: only works for TCGA
        sample_loadfile = link_sample_loadfile("TCGA", self.load_dir,
                                               self.report_dir, opts.timestamp)
        aggregates_file = self.aggregates_file()

        # Command line arguments for report generation
        self.cmdArgs = ["Rscript", "--vanilla"]
        gdc_sample_report = resource_filename("gdctools","lib/GDCSampleReport.R")
        self.cmdArgs.extend([ gdc_sample_report,        # From gdctools pkg
                              redactions_dir,           # From config
                              sample_counts_file,       # Inferred from dicer + timestamp
                              opts.timestamp,           # Specified from cli
                              filtered_samples_file,    # From config
                              heatmaps_dir,             # Infered from dicer + timestamp
                              blacklist_file,           # From config
                              sample_loadfile,          # Inferred from loadfile dir + timestamp
                              reference_dir,            # From config
                              self.report_dir,          # From config
                              aggregates_file           # Created with aggregates in config
                            ])

    def execute(self):
        super(sample_report, self).execute()
        common.init_logging()
        self.parse_args()
        opts = self.options
        # TODO: better error handling
        logging.info("CMD Args: " + " ".join(self.cmdArgs))
        #report_stdout = subprocess.check_output(self.cmdArgs)


    def create_agg_counts_file(self, diced_prog_root, timestamp):
        '''Create a program-wide counts file combining all cohorts, including aggregates'''
        # TODO: Add aggregate cohort counts
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
                        if row['Sample Type'] == 'Totals':
                            agg_totals[a] = agg_totals.get(a,0) + count

        # Now loop through aggregate cohorts if present, combining entries for those
        for agg_cohort in self.aggregates:
            sub_cohorts = self.aggregates[agg_cohort].split(',')
            agg_counts[agg_cohort] = {a: sum(agg_counts.get(s,{}).get(a, 0) for a in agg_counts)
                                      for s in sub_cohorts}

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


def link_heatmaps(diced_prog_root, report_dir, timestamp):
    '''Symlink all heatmaps into <reports_dir>/report_<timestamp> and return
    that directory'''
    root, dirs, files = os.walk(diced_prog_root).next()
    for project in dirs:
        meta_dir = os.path.join(root, project, 'metadata')
        # Uses the latest available timestamp to get the latest counts
        #TODO: This logic is repeated several places
        meta_dirs = [d for d in os.listdir(meta_dir) if d <= timestamp]
        if len(meta_dirs) < 1:
            _warning =  "No metadata found for " + project
            _warning += " earlier than " + timestamp
            logging.warning(_warning)
            continue
        latest_tstamp = sorted(meta_dirs)[-1]


        # Link high and low res heatmaps to the report dir
        heatmap_high = '.'.join([project, latest_tstamp, 'high_res.heatmap.png'])
        heatmap_high_dice = os.path.join(meta_dir, latest_tstamp, heatmap_high)
        heatmap_high_rpt = heatmap_high.replace(latest_tstamp, timestamp)
        heatmap_high_rpt = os.path.join(report_dir, heatmap_high_rpt)

        if os.path.isfile(heatmap_high_dice):
            os.symlink(heatmap_high_dice, heatmap_high_rpt)

        heatmap_low = '.'.join([project, latest_tstamp, 'low_res.heatmap.png'])
        heatmap_low_dice = os.path.join(meta_dir, latest_tstamp, heatmap_low)
        heatmap_low_rpt = heatmap_low.replace(latest_tstamp, timestamp)
        heatmap_low_rpt = os.path.join(report_dir, heatmap_low_rpt)
        if os.path.isfile(heatmap_low_dice):
            os.symlink(heatmap_low_dice, heatmap_low_rpt)

    return report_dir


def link_sample_loadfile(program, load_dir, report_dir, timestamp=None):
    if timestamp is None:
        latest_tstamp = sorted(os.listdir(load_dir))[-1]
    else:
        latest_tstamp = timestamp

    lf = program + '.' + timestamp + ".Sample.loadfile.txt"
    lf_report_path = os.path.join(report_dir, lf)
    lf = os.path.join(load_dir, timestamp, lf)

    # Symlink to report folder
    os.symlink(lf, lf_report_path)
    return lf_report_path


if __name__ == "__main__":
    sample_report().execute()
