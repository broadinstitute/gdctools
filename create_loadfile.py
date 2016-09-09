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
from functools import cmp_to_key

from lib import common
from lib import meta

class create_loadfile(GDCtool):

    def __init__(self):
        super(create_loadfile, self).__init__(version="0.3.0")
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
                projdate = meta.latest_timestamp(projpath, self.options.datestamp)

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

                metapath = get_diced_metadata(projname, projpath, self.datestamp)
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

                        # Make sure there is always an entry for this case in
                        # case samples, even if no samples will be added
                        case_samples[case_id] = case_samples.get(case_id, [])

                        if row['sample_type'] == '':
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
                        case_samples[case_id].append(samp_id)

                        if samp_id not in project:
                            project[samp_id] = master_load_entry(projname, row)

                        # Note that here each annotation has a list of potential
                        # diced files. When we generate the loadfile, we will
                        # choose the correct file based on the barcode
                        if annot not in project[samp_id]:
                            project[samp_id][annot] = [filepath]
                        else:
                            project[samp_id][annot].append(filepath)

                # Now that all samples are known, back-fill case-level files for each
                for case_id in case_samples:
                    # Insert each file into each sample in master_load_dict
                    files = case_files.get(case_id, [])
                    samples = case_samples.get(case_id, [])

                    # Here we have a problem, there is no data on this case besides
                    # clinical or biospecimen. We therefore cannot assign the BCR/clin
                    # data to any row in the master load table. Instead, we must create
                    # a new master load entry with a default sample type
                    # (whatever the default analysis type is)
                    if len(samples) == 0:
                        pseudo_row = dict()
                        pseudo_row['case_id'] = case_id
                        default_type = meta.main_tumor_sample_type(projname)
                        pseudo_row['sample_type'] = default_type
                        # Is this dangerous??
                        pseudo_row['is_ffpe'] = False

                        samp_id = sample_id(projname, pseudo_row)
                        project[samp_id] = master_load_entry(projname, pseudo_row)
                        samples = [samp_id]

                    for s in samples:
                        for f, annot in files:
                            # Must be a list of files for congruity, although
                            # there should always be exactly one here.
                            project[s][annot] = [f]

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

        # and the filtered samples file
        filtered_samples_file = projname + "." + datestamp + ".filtered_samples.txt"
        filtered_samples_file = os.path.join(loadfile_root, filtered_samples_file)
        filtered_lfp = open(filtered_samples_file, 'w+')

        # ... column headers for each
        headers =  ["sample_id", "individual_id" ]
        headers += ["sample_type", "tcga_sample_id"] + annotations
        samples_lfp.write("\t".join(headers) + "\n")

        filtered_headers = ["Participant Id", "Tumor Type", "Annotation",
                            "Filter Reason", "Removed Samples","Chosen Sample"]
        filtered_lfp.write('\t'.join(filtered_headers) + "\n")

        # ... then the rows (samples) for each cohort (project) in cohorts list
        for samples_in_this_cohort in cohorts:
            write_samples(samples_lfp, filtered_lfp,
                          headers, samples_in_this_cohort)

        # Second: now the sample set loadfile, derived from the samples loadfile
        sset_loadfile = projname + "." + datestamp + ".Sample_Set.loadfile.txt"
        sset_loadfile = os.path.join(loadfile_root, sset_loadfile)
        logging.info("Writing sample set loadfile to " + sset_loadfile)
        write_sampleset(samples_lfp, sset_loadfile, projname)

    def generate_master_loadfiles(self, projects, annotations):
        # Generate master loadfiles for all samples & sample sets
        # Do this by concatenating the individual sample(set) loadfiles
        program = self.program
        datestamp = self.datestamp

        logging.info("Generating master loadfiles for {0}".format(program))
        loadfile_root = os.path.abspath(self.load_dir)
        loadfile_root = os.path.join(loadfile_root, program, datestamp)
        if not os.path.isdir(loadfile_root):
            os.makedirs(loadfile_root)

        all_samp_loadfile = program + '.' + datestamp + ".Sample.loadfile.txt"
        all_samp_loadfile = os.path.join(loadfile_root, all_samp_loadfile)

        all_sset_loadfile = program + '.' + datestamp + ".Sample_Set.loadfile.txt"
        all_sset_loadfile = os.path.join(loadfile_root, all_sset_loadfile)

        all_filter_file   = program + '.' + datestamp + ".filtered_samples.txt"
        all_filter_file   = os.path.join(loadfile_root, all_filter_file)

        with open(all_samp_loadfile, 'w') as aslfp, \
             open(all_sset_loadfile, 'w') as sslfp, \
             open(all_filter_file, 'w') as fflfp:
            #Write headers for samples loadfile
            headers =  ["sample_id", "individual_id" ]
            headers += ["sample_type", "tcga_sample_id"] + sorted(annotations)
            aslfp.write("\t".join(headers) + "\n")

            # Write headers for sample set loadfile
            sslfp.write("sample_set_id\tsample_id\n")

            # write headers for filtered samples
            filtered_headers = ["Participant Id", "Tumor Type", "Annotation",
                                "Filter Reason", "Removed Samples","Chosen Sample"]
            fflfp.write('\t'.join(filtered_headers) + "\n")

            # loop over each project, concatenating loadfile data from each
            for projname in sorted(projects.keys()):
                proj_samples = projname + "." + datestamp + ".Sample.loadfile.txt"
                proj_samples = os.path.join(loadfile_root, proj_samples)
                with open(proj_samples) as ps:
                     # Skip header, and copy the rest of the file
                    ps.next()
                    for line in ps:
                        aslfp.write(line)

                proj_sset = projname + "." + datestamp + ".Sample_Set.loadfile.txt"
                proj_sset = os.path.join(loadfile_root, proj_sset)
                with open(proj_sset) as psset:
                     # Skip header, and copy the rest of the file
                    psset.next()
                    for line in psset:
                        sslfp.write(line)

                # combine filtered samples, but don't do this for aggregates
                # to avoid double counting
                if projname not in self.aggregates:
                    proj_filtered = projname + "." + datestamp + ".filtered_samples.txt"
                    proj_filtered = os.path.join(loadfile_root, proj_filtered)
                    with open(proj_filtered) as pf:
                        # skip header, copy the rest
                        pf.next()
                        for line in pf:
                            fflfp.write(line)

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

        # ... then, generate any aggregate loadfiles (>1 project/cohort)
        for aggr_name, aggr_definition in self.aggregates.items():
            print("Aggregate: {0} = {1}".format(aggr_name, aggr_definition))
            aggregate = []
            for project in aggr_definition.split(","):
                aggregate.append(projects[project])
            self.generate_loadfiles(aggr_name, annotations, aggregate)

        # ... finally, assemble a compositle loadfile for all available samples
        # and sample sets
        self.generate_master_loadfiles(projects, annotations)

def get_diced_metadata(project, project_root, datestamp):
    # At this point the datestamp has been vetted to be the latest HH_MM_SS
    # dicing for the given YYYY_MM_DD date; and so there MUST be EXACTLY 1
    # 1 metadata file summarizing that given YYYY_MM_DD__HH_MM_SS dicing.
    mpath = os.path.join(project_root, "metadata", datestamp)
    mpath = os.path.join(mpath, project + '.' + datestamp + ".diced_metadata.tsv")
    if os.path.exists(mpath):
        return mpath
    raise ValueError("Could not find dicing metadata: "+mpath)

# def sample_type_lookup(etype):
#     '''Convert long form sample types into letter codes.'''
#     # FIXME: ideally this should come from a config file section, and
#     #        the config file parser could/should be updated to support
#     #        custom "program-specific" content
#     lookup = {
#         "Primary Tumor" : ("TP", "01"),
#         "Recurrent Tumor" : ("TR", "02"),
#         "Blood Derived Normal" : ("NB", "10"),
#         "Primary Blood Derived Cancer - Peripheral Blood" : ("TB", "03"),
#         "Additional - New Primary" : ("TAP", "05"),
#         "Metastatic" : ("TM", "06"),
#         "Additional Metastatic" : ("TAM", "07"),
#         "Solid Tissue Normal": ("NT", "11"),
#         "Buccal Cell Normal": ("NBC", "12"),
#         "Bone Marrow Normal" : ("NBM", "14"),
#     }
#
#     return lookup[etype]

def sample_id(project, row_dict):
    '''Create a sample id from a row dict'''
    if not project.startswith("TCGA-"):
        raise ValueError("Only TCGA data currently supported, (project = {0})".format(project))

    cohort = project.replace("TCGA-", "")
    case_id = row_dict['case_id']
    indiv_base = case_id.replace("TCGA-", "")
    sample_type = row_dict['sample_type']
    sample_code, sample_type_abbr = meta.tumor_code(sample_type)

    # FFPE samples get seggregated regardless of actual sample_type
    if row_dict['is_ffpe'] == 'True':
        samp_id = "-".join([cohort + 'FFPE', indiv_base, sample_type_abbr])
    else:
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
    sample_code, sample_type_abbr = meta.tumor_code(sample_type)

    # FFPE samples get seggregated regardless of actual sample_type
    if row_dict['is_ffpe'] == 'True':
        samp_id = "-".join([cohort + 'FFPE', indiv_base, sample_type_abbr])
    else:
        samp_id = "-".join([cohort, indiv_base, sample_type_abbr])

    indiv_id = "-".join([cohort, indiv_base])
    tcga_sample_id = "-".join([case_id, sample_code])

    d['sample_id'] = samp_id
    d['individual_id'] = indiv_id
    d['sample_type'] = sample_type_abbr
    d['tcga_sample_id'] = tcga_sample_id

    return d

def diced_file_comparator(a, b):
    '''Comparator function for barcodes, using the rules described in the GDAC
    FAQ entry for replicate samples: https://confluence.broadinstitute.org/display/GDAC/FAQ
    '''
    # Convert files to barcodes by splitting
    a = a.split('.')[0]
    b = b.split('.')[0]


    # Get the analytes and plates
    # TCGA-BL-A0C8-01A-11<Analyte>-<plate>-01
    analyte1 = a[19]
    analyte2 = b[19]
    plate1   = a[21:25]
    plate2   = b[21:25]

    # Equals case
    if a == b:
        return 0
    elif analyte1 == analyte2:
        # Prefer the aliquot with the highest lexicographical sort value
        return -1 if a >= b else 1
    elif analyte1 == "H":
        # Prefer H over R and T
        return 1
    elif analyte1 == "R":
        # Prefer R over T
        return -1 if analyte2 == "T" else 1
    elif analyte1 == "T":
        # Prefer H and R over T
        return 1
    elif analyte1 == "D":
        # Prefer D over G,W,X, unless plat enumber is higher
        return -1 if plate2 <= plate1 else 1
    elif analyte2 == "D":
        return 1 if plate1 <= plate2 else -1
    else:
        # Default back to highest lexicographical sort value
        return -1 if a >= b else 1

def choose_file(files):
    preferred_order = sorted(files, key=cmp_to_key(diced_file_comparator))
    selected, ignored = preferred_order[0], preferred_order[1:]
    return selected, ignored

def write_samples(samples_fp, filtered_fp, headers, samples):
    # FIXME: touch up comments here
    # Loop over sample ids, writing entries in outfile
    # FIXME: presently assumes/requires at least one annot is defined
    for sample_id in sorted(samples):
        sample = samples[sample_id]

        # Each row for a sample must have sample_id, individual_id,
        # sample_type, and  tcga_sample_id at minimum
        required_columns = headers[:4]
        chosen_row = "\t".join([sample[c] for c in required_columns])

        annot_columns = []
        filtered_rows = []
        for annot in headers[4:]:
            # Trickier here, there is a list of possible files, use choose_file
            # to pick the write one, and log the ignored files into the replicates
            files = sample.get(annot, None)
            if files is None:
                annot_columns.append("__DELETE__")
            else:
                chosen, ignored = choose_file(files)
                annot_columns.append(chosen)

                chosen_barcode = os.path.basename(chosen).split('.')[0]
                ignored_barcodes = [os.path.basename(i).split('.')[0] for i in ignored]
                # Create a row for each filtered barcode
                for i in ignored_barcodes:
                    participant_id = chosen_barcode[:12]
                    tumor_type = sample_id.split('-')[0]
                    filter_reason = "Analyte Replicate Filter"
                    removed_sample = i
                    filtered_rows.append([participant_id, tumor_type, annot,
                                          filter_reason, removed_sample, chosen_barcode])

        # write row of chosen annotations
        if len(annot_columns) > 0:
            chosen_row += "\t" + "\t".join(annot_columns)
        samples_fp.write(chosen_row + "\n")

        # write row(s) of filtered barcodes
        for row in filtered_rows:
            row = "\t".join(row)
            filtered_fp.write(row + "\n")

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

        # Get the tumor type from the last field of the sample id
        # e.g. ACC-OR-A5J1-NB is in the ACC-NB sample set
        sset_type = samp_id.split('-')[-1]
        sset_data = sset_name + "-" + sset_type + "\t" + samp_id + "\n"

        # A sample is ffpe if the cohort name ends with FFPE.
        # e.g. BRCAFFPE-A7-A0DB-TP is FFPE, ACC-OR-A5J1-NB is not
        # Only add to the full sample set if the sample is not FFPE
        is_ffpe = samp_id.split('-')[0].endswith('FFPE')
        if is_ffpe:
            sset_data += sset_name + "-FFPE" + '\t' + samp_id + '\n'
        else:
            sset_data += sset_name + "\t" + samp_id + "\n"


        outfile.write(sset_data)


if __name__ == "__main__":
    create_loadfile().execute()
