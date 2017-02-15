#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

sample_report: wrapper around SampleSummaryReport.R for GDC-derived data
See the <root>/COPYRIGHT file for the SOFTWARE COPYRIGHT and WARRANTY NOTICE.

@author: Timothy DeFreitas, Michael S. Noble
@date:  2016_09_11
'''

# }}}

from __future__ import print_function
import subprocess
import logging
import os
import csv
from pkg_resources import resource_filename

from gdctools.lib import common
from gdctools.lib import meta
from gdctools.GDCtool import GDCtool

class sample_report(GDCtool):

    def __init__(self):
        super(sample_report, self).__init__(version="0.3.0")
        cli = self.cli

        cli.description = 'Generate a sample report for a snapshot of data '\
                        'mirrored & diced\nfrom the Genomic Data Commons (GDC)'

        # FIXME: add options for each config setting

    def parse_args(self):
        config = self.config

        # Ensure tool has sufficient configuration info to run
        mandatory_config  =  ["dice.dir", "loadfiles.dir", "reference_dir"]
        mandatory_config +=  ["reports.dir", "reports.blacklist"]
        self.validate_config(mandatory_config)

        #FIXME: Hardcoded to just TCGA for now...
        diced_prog_root = os.path.join(config.dice.dir, 'TCGA')

        datestamp = self.datestamp

        config.reports.dir = os.path.join(config.reports.dir, 'report_'+datestamp)
        if not os.path.isdir(config.reports.dir):
            os.makedirs(config.reports.dir)

        # Now infer certain values from the diced data directory
        logging.info("Linking diced metadata...")
        link_diced_metadata(diced_prog_root, config.reports.dir, datestamp)

        #FIXME: only works for TCGA
        sample_loadfile = link_loadfile_metadata(config.loadfiles.dir, "TCGA",
                                            config.reports.dir, datestamp)

        if config.aggregates:
            logging.info("Writing aggregate cohort definitions to report dir...")
            self.write_aggregate_definitions()
            logging.info("Writing aggregate counts ...")
            self.write_aggregate_counts(diced_prog_root,datestamp)

        # Command line arguments for report generation
        self.cmdArgs = ["Rscript", "--vanilla"]
        gdc_sample_report = resource_filename("gdctools","lib/GDCSampleReport.R")
        self.cmdArgs.extend([ gdc_sample_report,        # From gdctools pkg
                              datestamp,                # Specified from cli
                              config.reports.dir,
                              config.reference_dir,
                              config.reports.blacklist
                            ])

    def execute(self):
        super(sample_report, self).execute()
        self.parse_args()
        # TODO: better error handling
        logging.info("Running GDCSampleReport.R ")
        logging.info("CMD Args: " + " ".join(self.cmdArgs))
        try:
            p = subprocess.Popen(self.cmdArgs, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for line in iter(p.stdout.readline, ''):
                logging.info(line.rstrip())
        except Exception as e:
            logging.exception("Sample report generation FAILED:")

    def write_aggregate_counts(self, diced_prog_root, datestamp):
        '''Create a program-wide counts file combining all cohorts, including aggregates'''
        # FIXME: TCGA hardcoded here
        aggregate_cohorts = self.config.aggregates.keys()
        aggregate_cohorts = [ag.replace('TCGA-', '') for ag in aggregate_cohorts]

        agg_counts_file = '.'.join(['sample_counts', datestamp, 'tsv'])
        agg_counts_file = os.path.join(self.config.reports.dir, agg_counts_file)

        agg_annots = set()
        agg_counts = dict()
        agg_totals = dict()
        # NOTE: There is a lot of similarity between this inspection and
        # inspect_data in create_loadfile
        for cf in _counts_files(diced_prog_root, datestamp):
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

    def write_aggregate_definitions(self):
        '''Creates an aggregates.txt file in the reports directory. aggregates
        information is read from the [aggregates] section of the config file.
        '''
        aggregates = self.config.aggregates
        file = os.path.join(self.config.reports.dir, 'aggregates.txt')
        with open(file, 'w') as f:
            f.write('Aggregate Name\tTumor Types\n')
            for agg in sorted(aggregates.keys()):
                f.write(agg + '\t' + aggregates[agg] + '\n')

def _counts_files(diced_prog_root, datestamp):
    '''Generate the counts files for each project in a program'''
    # 'dirs' will be the diced project names
    root, dirs, files = os.walk(diced_prog_root).next()

    for project in dirs:
        meta_dir = os.path.join(root, project, 'metadata')

        # Find the appropriate datestamp to use for the latest counts.
        # The correct file is the one with the latest datestamp that is
        # earlier than the given datestamp
        meta_dirs = [d for d in os.listdir(meta_dir) if d <= datestamp]

        # If no such meta_dir exists, then there was no data for this project
        # as of the provided date
        if len(meta_dirs) > 0:
            latest_tstamp = sorted(meta_dirs)[-1]
            count_f = '.'.join([project, latest_tstamp, 'sample_counts','tsv'])
            count_f = os.path.join(meta_dir, latest_tstamp, count_f)

            # Final sanity check, file must exist
            if os.path.isfile(count_f):
                yield count_f

def link_diced_metadata(diced_prog_root, report_dir, datestamp):
    '''Symlink all heatmaps into <reports_dir>/report_<datestamp> and return
    that directory'''
    root, dirs, files = os.walk(diced_prog_root).next()
    for project in dirs:
        meta_dir = os.path.join(root, project, 'metadata', datestamp)

        # Link high and low res heatmaps to the report dir
        heatmap_high = '.'.join([project, datestamp, 'high_res.heatmap.png'])
        heatmap_low = '.'.join([project, datestamp, 'low_res.heatmap.png'])
        link_metadata_file(meta_dir, report_dir, heatmap_high)
        link_metadata_file(meta_dir, report_dir, heatmap_low)

        #Link project-level sample counts
        samp_counts = '.'.join([project, datestamp, 'sample_counts', 'tsv'])
        link_metadata_file(meta_dir, report_dir, samp_counts)

        # Link the diced metadata TSV
        diced_meta = '.'.join([project, datestamp, 'diced_metadata', 'tsv'])
        link_metadata_file(meta_dir, report_dir, diced_meta)

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
    loadfile = program + '.' + datestamp + ".Sample.loadfile.txt"
    link_metadata_file(from_dir, report_dir, loadfile)
    filtered = program + '.' + datestamp + ".filtered_samples.txt"
    link_metadata_file(from_dir, report_dir, filtered)

def main():
    sample_report().execute()

if __name__ == "__main__":
    main()