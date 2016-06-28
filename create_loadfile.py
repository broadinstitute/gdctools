#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

gdc_mirror: this file is part of gdctools.  See the <root>/COPYRIGHT
file for the SOFTWARE COPYRIGHT and WARRANTY NOTICE.

@author: Timothy DeFreitas
@date:  2016_05_25
'''

# }}}
from __future__ import print_function

from GDCtool import GDCtool
import logging
import os
import csv
import ConfigParser
from lib import common
from lib.meta import latest_timestamp
from lib.report import draw_heatmaps

class create_loadfile(GDCtool):

    def __init__(self):
        super(create_loadfile, self).__init__(version="0.2.0")
        cli = self.cli

        desc =  'Create a Firehose loadfile from diced Genomic Data Commons (GDC) data'
        cli.description = desc

        cli.add_argument('-d', '--dice-dir',
                         help='Root of diced data directory')
        cli.add_argument('-o', '--load-dir',
                         help='Where generated loadfiles will be placed')
        cli.add_argument('datestamp', nargs='?',
                         help='Dice using metadata from a particular date.'\
                         'If omitted, the latest version will be used')

    def parse_args(self):
        opts = self.options

        # Parse custom [load] section from config.
        # This logic is intentionally omitted from GDCtool:parse_config, since
        # loadfiles are only useful to FireHose, and this tool is not distributed
        if opts.config is not None:
            cfg = ConfigParser.ConfigParser()
            cfg.read(opts.config)

            if cfg.has_option('firehose', 'load_dir'):
                self.load_dir = cfg.get('firehose', 'load_dir')
            if cfg.has_option('firehose', 'heatmaps_dir'):
                self.heatmaps_dir = cfg.get('firehose', 'heatmaps_dir')


        if opts.dice_dir is not None: self.dice_root_dir = opts.dice_dir
        if opts.load_dir is not None: self.load_dir = opts.load_dir

    def create_loadfiles(self):
        #Iterate over programs/projects in diced root
        diced_root = os.path.abspath(self.dice_root_dir)
        load_root = os.path.abspath(self.load_dir)

        for program in common.immediate_subdirs(diced_root):
            prog_root = os.path.join(diced_root, program)
            projects = common.immediate_subdirs(prog_root)

            for project in projects:
                #This dictionary contains all the data for the loadfile.
                #Keys are the entity_ids, values are dictionaries for the columns in a loadfile
                master_load_dict = dict()

                proj_path = os.path.join(prog_root, project)
                timestamp = latest_timestamp(proj_path, self.options.datestamp)
                logging.info("Generating loadfile data for {0} -- {1}".format( project, timestamp))
                # Keep track of the created annotations
                annots = set()

                metapath = get_diced_metadata(proj_path, timestamp)
                with open(metapath) as metafile:
                    reader = csv.DictReader(metafile, delimiter='\t')
                    #Stores the files and annotations for each case
                    case_files = dict()
                    case_samples = dict()
                    for row in reader:
                        case_id = row['case_id']
                        annot = row['annotation']
                        annots.add(annot)

                        if row['sample_type'] == "None":
                            # This is a case-level file, save until all the
                            # samples are known
                            case_files[case_id] = case_files.get(case_id, [])
                            case_files[case_id].append((row['file_name'], annot))
                            continue

                        #Add entry for this entity into the master load dict
                        samp_id = sample_id(project, row)
                        case_samples[case_id] = case_samples.get(case_id, [])
                        case_samples[case_id].append(samp_id)

                        if samp_id not in master_load_dict:
                            master_load_dict[samp_id] = master_load_entry(project, row)
                        #Filenames in metadata begin with diced root,
                        filepath = os.path.join(os.path.dirname(diced_root), row['file_name'])
                        master_load_dict[samp_id][annot] = filepath

                # Now all the samples are known, insert case-level files to each
                for case_id in case_samples:
                    # Insert each file into each sample in master_load_dict
                    files = case_files.get(case_id, [])
                    samples = case_samples.get(case_id, [])
                    for s in samples:
                        for f, annot in files:
                            master_load_dict[s][annot] = f

                load_date_root = os.path.join(load_root, program, timestamp)
                if not os.path.isdir(load_date_root):
                    os.makedirs(load_date_root)

                samples_loadfile_name = ".".join([project, timestamp, "Sample", "loadfile", "txt"])
                sset_loadfile_name = ".".join([project, timestamp, "Sample_Set", "loadfile", "txt"])
                samples_loadfile = os.path.join(load_date_root, samples_loadfile_name)
                sset_loadfile = os.path.join(load_date_root, sset_loadfile_name)

                logging.info("Writing samples loadfile to " + samples_loadfile)
                write_master_load_dict(master_load_dict, annots, samples_loadfile)
                logging.info("Writing sample set loadfile to " + sset_loadfile)
                write_sample_set_loadfile(samples_loadfile, sset_loadfile)

                #logging.info("Writing sample heatmaps")
                #write_heatmaps(master_load_dict, annots, project, timestamp, load_date_root)


    def execute(self):
        super(create_loadfile, self).execute()
        self.parse_args()
        opts = self.options
        print(dir(self))
        common.init_logging()
        self.create_loadfiles()

# Could use get_metadata, but since the loadfile generator is separate, it makes sense to divorce them
def get_diced_metadata(project_root, timestamp):
    stamp_dir = os.path.join(project_root, "metadata", timestamp)

    metadata_files = [f for f in os.listdir(stamp_dir)
                      if os.path.isfile(os.path.join(stamp_dir, f))
                      and "metadata" in f]
    # Get the chronologically latest one, in case there is more than one,
    # Should just be a sanity check
    latest = sorted(metadata_files)[-1]
    latest = os.path.join(stamp_dir, latest)
    return latest

#TODO: This should come from a config file
def sample_type_lookup(etype):
    '''Convert long form sample types into letter codes.'''
    lookup = {
        "Blood Derived Normal" : ("NB", "10"),
        "Primary Tumor" : ("TP", "01"),
        "Primary Blood Derived Cancer - Peripheral Blood" : ("TB", "03"),
        "Metastatic" : ("TM", "06"),
        "Solid Tissue Normal": ("NT", "11"),
        "Recurrent Tumor" : ("TR", "02"),
        "Buccal Cell Normal": ("NBC", "12"),
        "Bone Marrow Normal" : ("NBM", "14"),
        "Additional - New Primary" : ("TAP", "05")

    }

    return lookup[etype]

def sample_id(project, row_dict):
    '''Create a sample id from a row dict'''
    if not project.startswith("TCGA-"):
        raise ValueError("Only TCGA data currently supported, (project = {0})".format(project))

    cohort = project.replace("TCGA-", "")
    case_id = row_dict['case_id']
    indiv_base = case_id.replace("TCGA-", "")
    sample_type = row_dict['sample_type']
    sample_type_abbr, sample_code = sample_type_lookup(sample_type)

    samp_id = "-".join([cohort, indiv_base, sample_type_abbr])
    return samp_id

def master_load_entry(project, row_dict):
    d = dict()
    if not project.startswith("TCGA-"):
        raise ValueError("Only TCGA data currently supported, (project = {0})".format(project))

    cohort = project.replace("TCGA-", "")
    case_id = row_dict['case_id']
    indiv_base = case_id.replace("TCGA-", "")
    sample_type = row_dict['sample_type']
    sample_type_abbr, sample_code = sample_type_lookup(sample_type)

    samp_id = "-".join([cohort, indiv_base, sample_type_abbr])
    indiv_id = "-".join([cohort, indiv_base])
    tcga_sample_id = "-".join([case_id, sample_code])

    d['sample_id'] = samp_id
    d['individual_id'] = indiv_id
    d['sample_type'] = sample_type_abbr
    d['tcga_sample_id'] = tcga_sample_id

    return d

def write_master_load_dict(ld, annots, outfile):
    _FIRST_HEADERS = ["sample_id", "individual_id", "sample_type", "tcga_sample_id"]
    annots = sorted(annots)
    with open(outfile, 'w') as out:
        #Header line
        out.write("\t".join(_FIRST_HEADERS) + "\t" + "\t".join(annots)+"\n")


        #Loop over sample ids, writing entries in outfile
        #NOTE: requires at least one annot
        for sid in sorted(ld):
            this_dict = ld[sid]
            line = "\t".join([this_dict[h] for h in _FIRST_HEADERS]) + "\t"
            line += "\t".join([this_dict.get(a, "__DELETE__") for a in annots]) + "\n"
            out.write(line)

# def write_heatmaps(ld, annots, project, timestamp, outdir):
#     rownames, matrix = _build_heatmap_matrix(ld, annots)
#     draw_heatmaps(rownames, matrix, project, timestamp, outdir)
#
# def _build_heatmap_matrix(ld, annots):
#     '''Build a 2d matrix and rownames from annotations and load dict'''
#     rownames = list(annots)
#     matrix = [[] for row in rownames]
#     for r in range(len(rownames)):
#         for sid in sorted(ld.keys()):
#             # append 1 if data is present, else 0
#             matrix[r].append( 1 if rownames[r] in ld[sid] else 0)
#
#     return rownames, matrix


def write_sample_set_loadfile(sample_loadfile, outfile):
    sset_data = "sample_set_id\tsample_id\n"
    with open(sample_loadfile) as slf:
        reader = csv.DictReader(slf, delimiter='\t')
        for row in reader:
            samp_id = row['sample_id']
            #This sample belongs to the cohort sample set
            sset_data += samp_id.split("-")[0] + "\t" + samp_id + "\n"
            #And the type-specific set
            sset_data += samp_id.split("-")[0] + "-" + samp_id.split("-")[-1] + "\t" + samp_id + "\n"

    with open(outfile, "w") as out:
        out.write(sset_data)

if __name__ == "__main__":
    create_loadfile().execute()
