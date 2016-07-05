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

import os
import glob
import re
from GDCtool import GDCtool
from GDCcore import gprint, gabort

# FIXME: this needs to stay in sync (grow) with translation table as GDC exposes
# more data(types) and our annotations grow
LEGACY_ANNOTATION_NAMES = [
    "sample_id",
    "individual_id",
    "sample_type",
    "tcga_sample_id",
    "snp__genome_wide_snp_6__broad_mit_edu__Level_3__segmented_scna_hg19__seg",
    "snp__genome_wide_snp_6__broad_mit_edu__Level_3__segmented_scna_minus_germline_cnv_hg19__seg",
    "clin__bio__nationwidechildrens_org__Level_1__biospecimen__clin",
    "clin__bio__nationwidechildrens_org__Level_1__clinical__clin",

    "rnaseq__illuminahiseq_rnaseq__bcgsc_ca__Level_3__gene_expression__data",               # Technically these 3 expression annotations are incorrect,
    "mirnaseq__illuminahiseq_mirnaseq__bcgsc_ca__Level_3__miR_gene_expression__data",       # b/c GDC blurs the boundaries between GA/HiSeq (does not
    "mirnaseq__illuminahiseq_mirnaseq__bcgsc_ca__Level_3__miR_isoform_expression__data",    # expose which aliquots are from which platforms) and also
                                                                                            # does not expose the submitting center identity.  But this
                                                                                            # is not a concern during GDC testing phase, and we'll switch
                                                                                            # to new annotations & tasks in gdc_dev/gdc_prod spaces for
                                                                                            # later public release.
]

LEGACY_ANNOTATION_NAMES = "\t".join(LEGACY_ANNOTATION_NAMES) + "\n"
LEGACY_SAMPLE_STAMP_NAMES = "sample_set_id\tsamplestamp\tmerge_after_load\ttumor_type\tsample_type_short_letter_code\n"

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

        cli.add_argument('-d', '--dir', default='.', help=\
            'directory housing a set of GDC-based loadfiles, from which '\
            'the legacy files will be generated [default: .]')

    def execute(self):
        super(create_legacy, self).execute()

        stem = os.path.join(self.options.dir,'TCGA-*.')
        SAMPLE_FILES = glob.glob(stem + 'Sample.loadfile.txt')
        SAMPLE_SET_FILES = glob.glob(stem +'Sample_Set.loadfile.txt')

        if not SAMPLE_FILES:
            gabort(1, "No sample loadfile(s) found")
        if not SAMPLE_SET_FILES:
            gabort(2, "No sample set loadfile(s) found")

        stem = "normalized.tcga_"
        DATESTAMP = SAMPLE_FILES[0].split('.')[1]

        print("There are %d projects (i.e. cohorts)" % len(SAMPLE_FILES))
        print("DATESTAMP IS " + DATESTAMP)

        # Generate the file containing all samples
        outfile = stem + "all_samples.%s.Sample.loadfile.txt"  % DATESTAMP
        print("Generating aggregate samples: "+outfile)
        outfile = open(outfile, 'w')
        outfile.write(LEGACY_ANNOTATION_NAMES)

        for fname in SAMPLE_FILES:
            infile = open(fname, 'r')
            infile.next() # skip header
            for line in infile:
                outfile.write(line)

        # Generate the file containing all sample set definitions; and while
        # we're iterating, save each unique sample set name (from column 1)
        outfile = stem + "sample_sets.%s.Sample_Set.loadfile.txt" % DATESTAMP
        print("Generating aggregate sample sets: "+outfile)
        outfile = open(outfile, 'w')
        outfile.write("sample_set_id\tsample_id\n")
        COL1 = re.compile(r'([^\t]+)\t')
        sset_names = {}

        for fname in SAMPLE_SET_FILES:
            infile = open(fname, 'r')
            infile.next() # skip header
            for line in infile:
                outfile.write(line)
                sset_name = COL1.match(line)
                if sset_name:
                    sset_names[sset_name.group(1)] = 1

        # Generate fake samplestamp annotations (and empty stub files)
        sset_names = sorted(sset_names.keys())
        outfile = "normalized.samplestamp.%s.Sample_Set.loadfile.txt" % DATESTAMP
        print("Generating fake samplestamp annotations: "+outfile)

        outfile = open(outfile, 'w')
        outfile.write(LEGACY_SAMPLE_STAMP_NAMES)
        cwd = os.getcwd()

        for sset_name in sset_names:
            fields = sset_name.split("-")
            disease_name = fields[0]
            sample_type = fields[-1]        # Extract -TP, -NB etc
            if sample_type == sset_name:    # If not there, null out
                sample_type = ""
            # Keep SVN Python/gdac/create_sdrf/createMergeDataFilesSDRF.py happy
            stamp = "normalized.%s.%s.samplestamp.txt" % (disease_name, DATESTAMP)
            stamp = os.path.join(cwd, stamp)
            _ = open(stamp, 'w')
            outfile.write("%s\t%s\ttrue\t%s\t%s\n" % (sset_name,stamp,disease_name,sample_type))

if __name__ == "__main__":
    tool = create_legacy()
    tool.execute()
