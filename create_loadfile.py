#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

gdc_mirror: this file is part of gdctools.  See the <root>/COPYRIGHT
file for the SOFTWARE COPYRIGHT and WARRANTY NOTICE.

@author: Timothy DeFreitas, Michael S. Noble
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

        self.datestamp = None   # FIXME: rationalize this with datestamp optional arg
        self.program = None

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
            if cfg.has_option('loadfiles', 'load_dir'):
                self.load_dir = cfg.get('loadfiles', 'load_dir')
            if cfg.has_option('loadfiles', 'heatmaps_dir'):
                self.heatmaps_dir = cfg.get('loadfiles', 'heatmaps_dir')
            
            self.aggregates = dict()
            if cfg.has_section('aggregates'):
                for aggr in cfg.options('aggregates'):
                    aggr = aggr.upper()
                    self.aggregates[aggr] = cfg.get('aggregates', aggr)

        if opts.dice_dir: self.dice_root_dir = opts.dice_dir
        if opts.load_dir: self.load_dir = opts.load_dir

    def inspect_data(self):

        # GDC organizes data into Programs-->Projects-->Cases-->Data_Categories
        # Given a processed (aka diced) mirror of the data corpus for a single
        # program, this walker iterates over that dicing to build a map of:
        #
        #   all projects that have been mirrored/diced
        #       then all cases within each project
        #           then all samples for each case
        #
        # Note that "project" is effectively a proxy term for "disease cohort,"
        # or more simply "cohort".
        #
        # The map created here is later used to generate so-called loadfiles.
        # which are TSV tables where the first column of each row describes a
        # unique tissue sample collected for a case (e.g. primary solid tumor,
        # blood normal, etc) and each subsequent column points to a file of data
        # derived from that tissue sample (e.g. copy number, gene expression,
        # miR expression, etc).
        #
        # FIXME: I'm intentionally trying to describe this in a Firehose-agnostic
        #        way, because I'm now leaning heavily in the direction that loadfile
        #        generation may indeed be something of value to others outside the
        #        Broad; because they are equivalent to sample freeze lists as used
        #        in TCGA, for example.

        diced_root = os.path.abspath(self.dice_root_dir)
        projects = dict()                       # dict of dicts, one per project

        for program in common.immediate_subdirs(diced_root):

            # Auto-generated loadfiles should not mix data across >1 program
            if self.program:
                if program != self.program:
                        raise ValueError("Loadfiles cannot span >1 program")
            else:
                self.program = program

            program_dir = os.path.join(diced_root, program)
            annotations = set()

            for projname in sorted(common.immediate_subdirs(program_dir)):

                # Each project dict contains all the loadfile rows for the
                # given project/cohort.  Keys are the entity_ids, values are
                # dictionaries for the columns in a loadfile
                project = dict()


                projpath = os.path.join(program_dir, projname)
                projdate = latest_timestamp(projpath, self.options.datestamp)

                # Auto-generated loadfiles should not mix data across >1 datestamp
                if self.datestamp:
                    if projdate != self.datestamp:
                        raise ValueError("Datestamp of {0} for {1} conflicts "\
                                    "with existing datestamp of {2}\n"\
                                    .format(projname, projdate, self.datestamp))
                else:
                    self.datestamp = projdate

                logging.info("Inspecting data for {0} version {1}"\
                                .format(projname, self.datestamp))

                metapath = get_diced_metadata(projpath, self.datestamp)
                with open(metapath) as metafile:
                    reader = csv.DictReader(metafile, delimiter='\t')
                    # Stores the files and annotations for each case
                    case_files = dict()
                    case_samples = dict()

                    for row in reader:
                        case_id = row['case_id']
                        annot = row['annotation']
                        filepath = row['file_name']
                        annotations.add(annot)

                        if row['sample_type'] == "None":
                            # This file exists only at the case-level (e.g.
                            # clinical data) and so does not have a tissue
                            # sample type (e.g. Primary Tumor).  Therefore
                            # it will be attached to every sample of every
                            # tissue type for this case; but that can only
                            # be done after we know what those are, so we
                            # save these files for now and back-fill later
                            case_files[case_id] = case_files.get(case_id, [])
                            case_files[case_id].append((filepath, annot))
                            continue

                        samp_id = sample_id(projname, row)
                        case_samples[case_id] = case_samples.get(case_id, [])
                        case_samples[case_id].append(samp_id)

                        if samp_id not in project:
                            project[samp_id] = master_load_entry(projname, row)

                        # Filenames in metadata begin with diced root
                        project[samp_id][annot] = filepath

                # Now that all samples are known, back-fill case-level files for each
                for case_id in case_samples:
                    # Insert each file into each sample in master_load_dict
                    files = case_files.get(case_id, [])
                    samples = case_samples.get(case_id, [])
                    for s in samples:
                        for f, annot in files:
                            project[s][annot] = f

                # Finally, retain this project data for later loadfile generation
                projects[projname] = project

        return projects, sorted(annotations)

    def generate_loadfiles(self, projname, annotations, cohorts):
        # Generate a sample and sample_set loadfile for the given list of
        # cohorts (i.e. GDC projects).  Note that singleton cohorts will
        # have 1 entry in cohort list, and aggregate cohorts more than 1.
        # Specifying each case (singleton vs aggregate) as a sequence 
        # allows them both to be treated the same manner below.

        program = self.program
        datestamp = self.datestamp

        logging.info("Generating loadfile for {0}".format(projname))
        loadfile_root = os.path.abspath(self.load_dir)
        loadfile_root = os.path.join(loadfile_root, program, datestamp)
        if not os.path.isdir(loadfile_root):
            os.makedirs(loadfile_root)

        # First: the samples loadfile
        samples_loadfile = projname + "." + datestamp + ".Sample.loadfile.txt"
        samples_loadfile = os.path.join(loadfile_root, samples_loadfile)
        logging.info("Writing samples loadfile to " + samples_loadfile)
        samples_lfp = open(samples_loadfile, 'w+')

        # ... column headers
        headers =  ["sample_id", "individual_id" ]
        headers += ["sample_type", "tcga_sample_id"] + annotations
        samples_lfp.write("\t".join(headers) + "\n")

        # ... then the rows (samples) for each cohort (project) in cohorts list
        for samples_in_this_cohort in cohorts:
            write_samples(samples_lfp, headers, samples_in_this_cohort)

        # Second: now the sample set loadfile, derived from the samples loadfile
        sset_loadfile = projname + "." + datestamp + ".Sample_Set.loadfile.txt"
        sset_loadfile = os.path.join(loadfile_root, sset_loadfile)
        logging.info("Writing sample set loadfile to " + sset_loadfile)
        write_sampleset(samples_lfp, sset_loadfile, projname)

        #logging.info("Writing sample heatmaps")
        #write_heatmaps(master_load_dict, annots, project, datestamp, load_date_root)

    def execute(self):

        super(create_loadfile, self).execute()
        self.parse_args()
        opts = self.options

        common.init_logging()

        # Discern what data is available for given program on given datestamp
        (projects, annotations) = self.inspect_data()

        # ... then generate singleton loadfiles (one per project/cohort)
        for project in sorted(projects.keys()):
            self.generate_loadfiles(project, annotations, [projects[project]])

        # ... lastly, generate any aggregate loadfiles (>1 project/cohort)
        for aggr_name, aggr_definition in self.aggregates.items():
            print("Aggregate: {0} = {1}".format(aggr_name, aggr_definition))
            aggregate = []
            for project in aggr_definition.split(","):
                aggregate.append(projects[project])
            self.generate_loadfiles(aggr_name, annotations, aggregate)

def get_diced_metadata(project_root, datestamp):
    # Could use get_metadata here, but since the loadfile generator is
    # separate, it makes sense to divorce them
    stamp_dir = os.path.join(project_root, "metadata", datestamp)

    metadata_files = [f for f in os.listdir(stamp_dir)
                      if os.path.isfile(os.path.join(stamp_dir, f))
                      and "metadata" in f]
    # Get the chronologically latest one, in case there is more than one,
    # Should just be a sanity check
    latest = sorted(metadata_files)[-1]
    latest = os.path.join(stamp_dir, latest)
    return latest

def sample_type_lookup(etype):
    '''Convert long form sample types into letter codes.'''
    # FIXME: ideally this should come from a config file section, and
    #        the config file parser could/should be updated to support
    #        custom "program-specific" content
    lookup = {
        "Primary Tumor" : ("TP", "01"),
        "Recurrent Tumor" : ("TR", "02"),
        "Blood Derived Normal" : ("NB", "10"),
        "Primary Blood Derived Cancer - Peripheral Blood" : ("TB", "03"),
        "Additional - New Primary" : ("TAP", "05"),
        "Metastatic" : ("TM", "06"),
        "Additional Metastatic" : ("TAM", "07"),
        "Solid Tissue Normal": ("NT", "11"),
        "Buccal Cell Normal": ("NBC", "12"),
        "Bone Marrow Normal" : ("NBM", "14"),
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

def write_samples(fp, headers, samples):
    # FIXME: touch up comments here
    # Loop over sample ids, writing entries in outfile
    # FIXME: presently assumes/requires at least one annot is defined
    for sample_id in sorted(samples):
        sample = samples[sample_id]
        row = "\t".join([sample.get(h, "__DELETE__") for h in headers]) + "\n"
        fp.write(row)

def write_sampleset(samples_lfp, sset_filename, sset_name):

    # Rewind samples loadfile to beginning
    samples_lfp.seek(0)

    # Create new sample set file
    outfile = open(sset_filename, "w")
    outfile.write("sample_set_id\tsample_id\n")

    # Iteratively write each sample to multiple sample sets:
    #   First, to the full cohort sample set (e.g. TCGA-COAD)
    #   Then to the respective tissue-specific sample set (e.g TCGA-COAD-TP)
    reader = csv.DictReader(samples_lfp, delimiter='\t')
    for sample in reader:
        samp_id = sample['sample_id']
        # FIXME: clarify this code a little
        sset_data = sset_name + "\t" + samp_id + "\n"
        sset_data += sset_name + "-" + samp_id.split("-")[-1] + "\t" + samp_id + "\n"
        outfile.write(sset_data)

# def write_heatmaps(ld, annots, project, datestamp, outdir):
#     rownames, matrix = _build_heatmap_matrix(ld, annots)
#     draw_heatmaps(rownames, matrix, project, datestamp, outdir)
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

if __name__ == "__main__":
    create_loadfile().execute()
