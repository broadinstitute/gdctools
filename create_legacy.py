#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

create_legacy: this file is part of gdctools.  See the <root>/COPYRIGHT
file for the SOFTWARE COPYRIGHT and WARRANTY NOTICE.

@author: Michael S. Noble
@date:  2016_06_02
'''

# }}}

from GDCtool import GDCtool
from GDCcore import gprint, gabort
import glob

# FIXME: this needs to stay in sync (grow) with our other code as GDC exposes more data(types)
LEGACY_ANNOTATION_NAMES= "sample_id\tindividual_id\tsample_type\ttcga_sample_id\tsnp__genome_wide_snp_6__broad_mit_edu__Level_3__segmented_scna_hg19__seg\tsnp__genome_wide_snp_6__broad_mit_edu__Level_3__segmented_scna_minus_germline_cnv_hg19__seg\tclin__bio__nationwidechildrens_org__Level_1__biospecimen__clin\tclin__bio__nationwidechildrens_org__Level_1__clinical__clin\n"

class create_legacy(GDCtool):

    def __init__(self):
        super(create_legacy, self).__init__(version="0.2.0")
        cli = self.cli

        desc  = 'This tool aids in the transitioning of Firehose runs from\n'
        desc += "the TCGA DCC to the GDC.  It's purpose is to generate old-\n"
        desc += 'style (legacy) Firehose loadfiles and related artifacts,\n'
        desc += 'as points of comparison with new GDC-style loadfiles, etc.\n'
        desc += 'As such, this tool is not intended for general use.\n'
        cli.description = desc

        # Optional arguments (if any)
        cli.add_argument('-d', '--dir', default='.', help=\
            'directory housing a set of GDC-based loadfiles, from which '\
            'the legacy files will be generated [default: .]')

        # Positional (required) arguments (if any)
        #opts.add_argument('-w', '--what', default='all',

    def execute(self):
        super(create_legacy, self).execute()

        SAMPLE_FILES = glob.glob('TCGA-*.Sample.loadfile.txt')
        SAMPLE_SET_FILES = glob.glob('TCGA-*.Sample_Set.loadfile.txt')

        if not SAMPLE_FILES:
            gabort(1, "No sample loadfile(s) found")
        if not SAMPLE_SET_FILES:
            gabort(2, "No sample set loadfile(s) found")

        DATESTAMP = SAMPLE_FILES[0].split('.')[1]
        print("There are %d sample files" % len(SAMPLE_FILES))
        print("DATESTAMP IS " + DATESTAMP)

        stem = "normalized.tcga_"
        all_sets = stem + "sample_sets.%s.Sample_Set.loadfile.txt" % DATESTAMP
        all_samples = stem + "all_samples.%s.Sample.loadfile.txt"  % DATESTAMP

        # Generate the file containing all samples
        outfile = open(all_samples, 'w')
        outfile.write(LEGACY_ANNOTATION_NAMES)
        for fname in SAMPLE_FILES:
            print("Processing sample file: "+fname)
            infile = open(fname, 'r')
            infile.next() # skip header
            for line in infile:
                outfile.write(line)


        # Generate the file containing all sample set definitions
        outfile = open(all_sets_file, 'w')
        for fname in SAMPLE_SET_FILES:
            infile = open(fname, 'r')
            for line in infile:
                outfile.write(line)

if __name__ == "__main__":
    tool = create_legacy()
    tool.execute()
