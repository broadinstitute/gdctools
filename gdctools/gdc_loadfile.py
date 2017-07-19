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
import logging
import os
import csv
from functools import cmp_to_key

from gdctools.lib import common
from gdctools.lib import meta
from gdctools.GDCtool import GDCtool

class gdc_loadfile(GDCtool):

    def __init__(self):
        description = 'Create a Firehose-style loadfile from diced GDC data'
        super(gdc_loadfile, self).__init__("0.3.2", description)
        cli = self.cli
        cli.add_argument('-f', '--file_prefix', help='Path prefix of each file'\
                ' referenced in loadfile [defaults to value of dice_dir]')
        cli.add_argument('-d', '--dice-dir',
                help='Dir from which diced data will be read')
        cli.add_argument('-o', '--load-dir',
                help='Where generated loadfiles will be placed')

        self.program = None

    def config_customize(self):
        '''Parse CLI args, potentially overriding config file settings'''
        opts = self.options
        config = self.config
        if opts.dice_dir: config.dice.dir = opts.dice_dir
        if opts.load_dir: config.loadfile.dir = opts.load_dir
        if opts.file_prefix: config.loadfile.file_prefix = opts.file_prefix
        if opts.projects: config.projects = opts.projects
        self.validate_config(["dice.dir", "loadfile.dir"])

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
        # Loadfiles are intentionally described in a Firehose-agnostic way, b/c
        # loadfile generation may indeed be something of value to others outside
        # of Broad/Firehose context; because they are essentially equivalent to
        # sample freezelists as used in TCGA AWGs, for example.

        projects = dict()
        dice_dir = self.config.dice.dir
        file_prefix = self.config.loadfile.file_prefix

        # FIXME: this should respect PROGRAM setting(s) from config file or CLI
        for program in common.immediate_subdirs(dice_dir):

            # Auto-generated loadfiles should not mix data across >1 program
            if self.program:
                if program != self.program:
                        raise ValueError("Loadfiles cannot span >1 program")
            else:
                self.program = program

            program_dir = os.path.join(dice_dir, program)
            annotations = set()

            projnames = self.config.projects
            if not projnames:
                projnames = common.immediate_subdirs(program_dir)

            for projname in sorted(projnames):

                # Ignore metadata stored by GDCtools about program/projects
                if projname.lower() == "metadata":
                    continue

                # Each project dict contains all the loadfile rows for the
                # given project/cohort.  Keys are the entity_ids, values are
                # dictionaries for the columns in a loadfile
                project = dict()
                projpath = os.path.join(program_dir, projname)

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
                        annotations.add(annot)

                        filepath = row['file_name']
                        if file_prefix:
                            filepath = filepath.replace(dice_dir,file_prefix,1)

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
        loadfile_root = os.path.abspath(self.config.loadfile.dir)
        latest = os.path.join(loadfile_root, program, "latest")
        loadfile_root = os.path.join(loadfile_root, program, datestamp)
        if not os.path.isdir(loadfile_root):
            os.makedirs(loadfile_root)
            common.silent_rm(latest)
            os.symlink(os.path.abspath(loadfile_root), latest)

        # First: the samples loadfile
        samples_loadfile = projname + ".Sample.loadfile.txt"
        samples_loadfile = os.path.join(loadfile_root, samples_loadfile)
        logging.info("Writing samples loadfile to " + samples_loadfile)
        samples_lfp = open(samples_loadfile, 'w+')

        # and the filtered samples file
        filtered_samples_file = projname + ".filtered_samples.txt"
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
            write_samples(samples_lfp, filtered_lfp, headers,
                        samples_in_this_cohort, self.config.missing_file_value)

        # Second: now the sample set loadfile, derived from the samples loadfile
        sset_loadfile = projname + ".Sample_Set.loadfile.txt"
        sset_loadfile = os.path.join(loadfile_root, sset_loadfile)
        logging.info("Writing sample set loadfile to " + sset_loadfile)
        write_sset(samples_lfp, sset_loadfile, projname)

    def generate_master_loadfiles(self, projects, annotations):
        # Generate master loadfiles for all samples & sample sets
        # Do this by concatenating the individual sample(set) loadfiles
        program = self.program
        datestamp = self.datestamp

        logging.info("Generating master loadfiles for {0}".format(program))
        loadfile_root = os.path.abspath(self.config.loadfile.dir)
        loadfile_root = os.path.join(loadfile_root, program, datestamp)
        if not os.path.isdir(loadfile_root):
            os.makedirs(loadfile_root)

        all_samp_loadfile = program + ".Sample.loadfile.txt"
        all_samp_loadfile = os.path.join(loadfile_root, all_samp_loadfile)

        all_sset_loadfile = program + ".Sample_Set.loadfile.txt"
        all_sset_loadfile = os.path.join(loadfile_root, all_sset_loadfile)

        all_filter_file   = program + ".filtered_samples.txt"
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
                # Write to sample file, but avoid duplicates if its an aggregate
                if projname not in self.config.aggregates:
                    proj_samples = projname + ".Sample.loadfile.txt"
                    proj_samples = os.path.join(loadfile_root, proj_samples)
                    with open(proj_samples) as ps:
                        # Skip header, and copy the rest of the file
                        next(ps)
                        for line in ps:
                            aslfp.write(line)

                proj_sset = projname + ".Sample_Set.loadfile.txt"
                proj_sset = os.path.join(loadfile_root, proj_sset)
                with open(proj_sset) as psset:
                    # Skip header, and copy the rest of the file
                    next(psset)
                    for line in psset:
                        sslfp.write(line)

                # combine filtered samples, but don't do this for aggregates
                # to avoid double counting
                if projname not in self.config.aggregates:
                    proj_filtered = projname + ".filtered_samples.txt"
                    proj_filtered = os.path.join(loadfile_root, proj_filtered)
                    with open(proj_filtered) as pf:
                        # skip header, copy the rest
                        next(pf)
                        for line in pf:
                            fflfp.write(line)

    def execute(self):

        super(gdc_loadfile, self).execute()
        opts = self.options

        try:
            # Discern what data is available for given program on given datestamp
            (projects, annotations) = self.inspect_data()

            # ... then generate singleton loadfiles (one per project/cohort)
            for project in sorted(projects.keys()):
                self.generate_loadfiles(project, annotations, [projects[project]])

            # ... then, generate any aggregate loadfiles (>1 project/cohort)
            for aggr_name, aggr_definition in self.config.aggregates.items():
                aggregate = []
                for project in aggr_definition.split(","):
                    # Guard against case where project/cohort was not inspected due
                    # to omission from --projects flag, but is STILL in aggregates
                    project = projects.get(project, None)
                    if project:
                        aggregate.append(project)
                # Also guard against extreme version of above edge case, where NONE
                # of the projects/cohorts in this aggregate definition were loaded
                if aggregate:
                    print("Aggregate: {0} = {1}".format(aggr_name, aggr_definition))
                    self.generate_loadfiles(aggr_name, annotations, aggregate)

            # ... finally, assemble a composite loadfile for all available samples
            # and sample sets
            self.generate_master_loadfiles(projects, annotations)
        except Exception as e:
            logging.exception("Create Loadfile FAILED:")

def get_diced_metadata(project, project_root, datestamp):
    # At this point the datestamp has been vetted to be the latest HH_MM_SS
    # dicing for the given YYYY_MM_DD date; and so there MUST be EXACTLY 1
    # 1 metadata file summarizing that given YYYY_MM_DD__HH_MM_SS dicing.
    mpath = os.path.join(project_root, "metadata", datestamp)
    mpath = os.path.join(mpath, project + '.' + datestamp + ".diced_metadata.tsv")
    if os.path.exists(mpath):
        return mpath
    # sanity check
    raise ValueError("Could not find dice metadata for " + project + " on " + datestamp)

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
        return -1
    elif analyte1 == "R":
        # Prefer R over T
        return -1 if analyte2 == "T" else 1
    elif analyte1 == "T":
        # Prefer H and R over T
        return 1
    elif analyte1 == "D":
        # Prefer D over G,W,X, unless plate number is higher
        return -1 if plate2 <= plate1 else 1
    elif analyte2 == "D":
        return 1 if plate1 <= plate2 else -1
    else:
        # Default back to highest lexicographical sort value
        return -1 if a >= b else 1

def choose_file(files):
    # The files param is a list, but we first remove the path from each file to
    # promote robustness in comparator (only sample ID value should be compared)
    files = [os.path.basename(f) for f in files]
    # Example files value, drawn from TCGA-LUAD CNV__snp6 data:
    #  ['TCGA-44-2668-01A-01D-1549-01.6a5b9b87-ff2c-4596-b399-5a80299e50f8.txt',
    #   'TCGA-44-2668-01A-01D-A273-01.ed7bdfbc-a87a-4772-b38a-de9ed547d6db.txt',
    #   'TCGA-44-2668-01A-01D-0944-01.06a3821c-ce0c-405a-ad7e-61cb960651d9.txt']
    preferred_order = sorted(files, key=cmp_to_key(diced_file_comparator))
    selected, ignored = preferred_order[0], preferred_order[1:]
    return selected, ignored

def write_samples(samples_fp, filtered_fp, headers, samples, missing_file_value):
    '''Loop over sample ids, filling in annotation columns for each'''
    for sample_id in sorted(samples):
        sample = samples[sample_id]

        # Each row must at minimum have sample_id, individual_id,
        # sample_type, and tcga_sample_id
        required_columns = headers[:4]
        chosen_row = "\t".join([sample[c] for c in required_columns])

        annot_columns = []
        filtered_rows = []
        for annot in headers[4:]:
            files = sample.get(annot, None)
            # The missing_file_value is anlogous to NA values as used in R,
            # a placeholder so that a given cell in the table is not empty
            # This value can be configured in the [DEFAULT] config section
            if files is None:
                annot_columns.append(missing_file_value)
            else:
                # If >1 file is a candidate for this annotation (column),
                # pick the most appropriate and record the remainder of
                # the unselected files into the replicates pile
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

        # Write row of chosen annotations
        if len(annot_columns) > 0:
            chosen_row += "\t" + "\t".join(annot_columns)
        samples_fp.write(chosen_row + "\n")

        # Write row(s) of filtered barcodes
        for row in filtered_rows:
            row = "\t".join(row)
            filtered_fp.write(row + "\n")

def write_sset(samples_lfp, sset_filename, sset_name):
    '''
    Emit a sample set file, which is just a 2-column table where each row
    contains the ID of a sample and the name of a sample set in which that
    sample will be a member.  Note that it is valid for a sample to be listed
    in more than 1 sample set; e.g. consider the sample sets colon and rectal
    sample sets COAD and READ, then imagine combining them into an aggregate
    colorectal sample set COADREAD.  Each of the samples listed in COAD and
    READ sample sets will also be listed in the aggregate COADREAD sample set.
    '''

    # Rewind samples loadfile to beginning
    samples_lfp.seek(0)

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
        if not samp_id.split('-')[0].endswith('FFPE'):
            # Typically samples are included in the sample-type-specific set
            # AND the aggregate sample set: e.g. all TCGA-UCEC-*-NB samples
            # would appear in both TCGA-UCEC-NB AND TCGA-UCEC sample sets
            sset_data = sset_name + "-" + sset_type + "\t" + samp_id + "\n"
            sset_data += sset_name + "\t" + samp_id + "\n"
        else:
            # But FFPE samples are not included in the aggregate sample set
            sset_data = sset_name + "-FFPE" + '\t' + samp_id + '\n'

        outfile.write(sset_data)

def main():
    gdc_loadfile().execute()

if __name__ == "__main__":
    main()
