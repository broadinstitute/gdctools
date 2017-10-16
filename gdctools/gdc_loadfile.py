#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016-2017 The Broad Institute, Inc.  All rights are reserved.

gdc_mirror: this file is part of gdctools.  See the <root>/COPYRIGHT
file for the SOFTWARE COPYRIGHT and WARRANTY NOTICE.

@author: Timothy DeFreitas, Michael S. Noble
@date:  2016_05_25
'''

# }}}

from __future__ import print_function
import logging
import os
import sys
import csv
from functools import cmp_to_key

from gdctools.lib import common
from gdctools.lib import meta
from gdctools.GDCtool import GDCtool

class gdc_loadfile(GDCtool):

    formats = {
        'firecloud' :
        {
        'entity_prefix' : 'entity:',
        'membership_prefix' : 'membership:',
        'name_of_case_identifier' : 'participant_id',
        'create_case_loadfile' : True,
        'prepend_program_name_to_cohort_name' : True,
        },
        'firehose' :
        {
        'entity_prefix' : '',
        'membership_prefix' : '',
        'name_of_case_identifier' : 'individual_id',
        'create_case_loadfile' : False,
        'prepend_program_name_to_cohort_name' : False,
        }
    }

    def __init__(self):
        description = 'Create a loadfile from diced GDC data, suitable for '\
                      'importing diced GDC data\ninto analysis pipeline '\
                      'platforms.  The presently supported platforms are:\n\t'+\
                      '\n\t'.join(sorted(self.formats.keys()))
        super(gdc_loadfile, self).__init__("0.3.5", description)
        cli = self.cli
        cli.add_argument('-d', '--dice-dir',
                help='Dir from which diced data will be read')
        cli.add_argument('-f', '--format', default='firecloud',
                help='format of loadfile to generate [%(default)s]')
        cli.add_argument('-o', '--load-dir',
                help='Where generated loadfiles will be placed')
        cli.add_argument('-p', '--file_prefix', help='Path prefix of each file'\
                ' referenced in loadfile [defaults to value of dice_dir]')

        self.program = None

    def config_customize(self):
        '''Parse CLI args, potentially overriding config file settings'''
        opts = self.options
        config = self.config
        if opts.dice_dir: config.dice.dir = opts.dice_dir
        if opts.load_dir: config.loadfile.dir = opts.load_dir
        if opts.file_prefix: config.loadfile.file_prefix = opts.file_prefix
        if opts.format: config.loadfile.format = opts.format
        if opts.projects: config.projects = opts.projects
        self.validate_config(["dice.dir", "loadfile.dir"])
        self.format = self.formats.get(config.loadfile.format, None)
        if not self.format:
            raise ValueError('Unsupported format: '+config.loadfile.format)
        # Ensure that critical root directories are utilized in absolute form
        config.dice.dir = os.path.abspath(self.config.dice.dir)
        config.loadfile.dir = os.path.abspath(self.config.loadfile.dir)

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
            attributes = set()

            projnames = self.config.projects
            if not projnames:
                projnames = common.immediate_subdirs(program_dir)

            for projname in sorted(projnames):

                # Ignore metadata dir created by GDCtools during its operation
                if projname.lower() == "metadata":
                    continue

                # Each project dict contains all the loadfile rows for the
                # given project/cohort.  Keys are the entity_ids, values are
                # dictionaries for the columns in a loadfile
                project = dict()
                projpath = os.path.join(program_dir, projname)

                logging.info("Inspecting data for {0} with version datestamp {1}"\
                                .format(projname, self.datestamp))

                metapath = get_diced_metadata(projname, projpath, self.datestamp)
                with open(metapath) as metafile:
                    reader = csv.DictReader(metafile, delimiter='\t')
                    # Stores the files and attributes for each case
                    case_files = dict()
                    case_samples = dict()

                    for row in reader:
                        case_id = row['case_id']
                        annot = row['annotation']
                        attributes.add(annot)

                        filepath = row['file_name']
                        if file_prefix:
                            filepath = filepath.replace(dice_dir,file_prefix, 1)

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

                        samp_id = get_sample_id(self, projname, row)
                        case_samples[case_id].append(samp_id)

                        if samp_id not in project:
                            project[samp_id] = self.sample_new(projname, row)

                        # Note that here each annotation has a list of potential
                        # diced files. When we generate the loadfile, we will
                        # choose the correct file based on the barcode
                        if annot not in project[samp_id]:
                            project[samp_id][annot] = [filepath]
                        else:
                            project[samp_id][annot].append(filepath)

                # Now that all samples are known, back-fill case-level files for each
                for case_id in case_samples:
                    # Insert each file into each sample descriptor
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

                        samp_id = get_sample_id(self, projname, pseudo_row)
                        project[samp_id] = self.sample_new(projname, pseudo_row)
                        samples = [samp_id]

                    for s in samples:
                        for f, annot in files:
                            # Must be a list of files for congruity, although
                            # there should always be exactly one here.
                            project[s][annot] = [f]

                # Finally, retain this project data for later loadfile generation
                projects[projname] = project

        return projects, sorted(attributes)

    def required_headers(self, file_type):
        format = self.format
        if file_type == "Sample":
            name_of_program_specific_sample_id = self.program.lower() + "_sample_id"
            return [ 'sample_id',
                     format['name_of_case_identifier'],     # Keep order as is
                    'sample_type',
                    name_of_program_specific_sample_id]
        elif file_type == "Sample_Set":
            return [ 'sample_set_id', 'sample_id']
        elif file_type in ["Case", "Participant", "Individual"]:
            return [ format['name_of_case_identifier'] ]
        elif file_type == "filtered_samples":
            return ["Participant Id", "Cohort", "Annotation",
                    "Filter Reason", "Removed Samples","Chosen Sample"]

        raise ValueError("Unsupported loadfile type: " + str(file_type))

    def loadfile_name(self, prefix, file_type, suffix='.loadfile.txt'):
        if file_type in ['Sample', 'Sample_Set']:
            stem = file_type
        elif file_type in ["Case", "Participant", "Individual"]:
            stem = self.format['name_of_case_identifier']
            stem = stem.replace('_id', '')
            stem = stem[0].upper() + stem[1:]
        elif file_type == 'filtered_samples':
            stem = file_type
            suffix = ".txt"
        else:
            raise ValueError("Unsupported loadfile type: " + str(file_type))

        return prefix + '.' + stem + suffix

    def sample_new(self, project, row):
        # Fabricate a sample descriptor (dict) from a row (dict) from the
        # timestamp-versioned metadata table (constructed by gdc_dice), using
        # the chosen file format (dict) to customize column headers, etc

        program_and_cohort = project.split("-")
        program_name = program_and_cohort[0]

        if self.format['prepend_program_name_to_cohort_name']:
            cohort_name  = project
        else:
            cohort_name  = program_and_cohort[1]

        # Ensure FFPE samples can be easily identified & segregated downstream
        if row['is_ffpe'] == 'True':
            cohort_name += 'FFPE'

        gdc_case_id = row['case_id']                # <program>-<unique_barcode>
        gdc_sample_type = row['sample_type']        # long, textual description

        short_case_id = gdc_case_id.replace(program_name + '-', '')
        our_sample_code, our_sample_type_abbrev = meta.tumor_code(gdc_sample_type)
        our_sample_id = "-".join([cohort_name, short_case_id, our_sample_type_abbrev])
        name_of_case_id = self.format['name_of_case_identifier']
        name_of_program_specific_sample_id = program_name.lower() + "_sample_id"

        s = dict()
        s['sample_id'] = our_sample_id
        s['sample_type'] = our_sample_type_abbrev
        s[name_of_case_id] = "-".join([cohort_name, short_case_id])
        s[name_of_program_specific_sample_id] = "-".join([gdc_case_id, our_sample_code])

        return s

    def generate_loadfiles(self, projname, sample_attributes, cohorts):
        # Generate a sample and sample_set loadfile for the given list of
        # cohorts (i.e. GDC projects).  Note that singleton cohorts will
        # have 1 entry in cohort list, and aggregate cohorts more than 1.
        # Specifying each case (singleton vs aggregate) as a sequence
        # allows them both to be treated the same manner below.

        program = self.program
        datestamp = self.datestamp
        config = self.config

        logging.info('Generating loadfile for {0}'.format(projname))
        loadfile_dir = os.path.join(config.loadfile.dir, program, datestamp)
        if not os.path.isdir(loadfile_dir):
            latest = os.path.join(config.loadfile.dir, program, 'latest')
            os.makedirs(loadfile_dir)
            common.silent_rm(latest)
            os.symlink(loadfile_dir, latest)

        # First the cases/participants loadfile, if needed
        if self.format['create_case_loadfile']:
            cases_filename = self.loadfile_name(projname, "Case")
            cases_filename = os.path.join(loadfile_dir, cases_filename)
            logging.info('Writing cases loadfile to ' + cases_filename)
            cases_filep = open(cases_filename, 'w+')
            required_case_headers = self.required_headers("Case")
            header = '\t'.join(required_case_headers) + '\n'
            cases_filep.write(self.format['entity_prefix'] + header)
        else:
            cases_filep = None

        # ... then the samples loadfile
        samples_filename = self.loadfile_name(projname, 'Sample')
        samples_filename = os.path.join(loadfile_dir, samples_filename)
        logging.info('Writing samples loadfile to ' + samples_filename)
        samples_filep = open(samples_filename, 'w+')
        required_sample_headers = self.required_headers("Sample")
        header = '\t'.join(required_sample_headers + sample_attributes) + '\n'
        samples_filep.write(self.format['entity_prefix'] + header)

        # ... and the filtered samples list file
        filtered_filename = self.loadfile_name(projname, 'filtered_samples')
        filtered_filename = os.path.join(loadfile_dir, filtered_filename)
        logging.info('Writing filtered samples to ' + filtered_filename)
        filtered_filep = open(filtered_filename, 'w+')
        filtered_sample_headers = self.required_headers("filtered_samples")
        filtered_filep.write('\t'.join(filtered_sample_headers) + '\n')

        # Now populate each file in parallel, from the samples in each cohort
        for samples_in_this_cohort in cohorts:
            write_samples(projname, samples_filep, filtered_filep,
                        required_sample_headers, sample_attributes,
                        samples_in_this_cohort, self.config.missing_file_value)

        # Now do sample set & cases loadfiles by iterating over samples loadfile
        sset_filename = self.loadfile_name(projname, 'Sample_Set')
        sset_filename = os.path.join(loadfile_dir, sset_filename)
        logging.info('Writing sample set loadfile to ' + sset_filename)
        sset_filep = open(sset_filename, 'w')
        header = '\t'.join( self.required_headers('Sample_Set')) + '\n'
        sset_filep.write( self.format['membership_prefix'] + header)
        write_sset_and_cases(samples_filep, sset_filep, cases_filep, projname)

    def generate_pan_cohort_loadfiles(self, projects, attributes):
        # Fabricate pan-cohort aggregate loadfiles, for all samples and
        # sample sets, by concatenating the singleton sample(set) loadfiles
        program = self.program
        datestamp = self.datestamp
        lfname = self.loadfile_name

        logging.info("Generating pan-cohort loadfiles for {0}".format(program))
        loadfile_root = os.path.abspath(self.config.loadfile.dir)
        loadfile_root = os.path.join(loadfile_root, program, datestamp)
        if not os.path.isdir(loadfile_root):
            os.makedirs(loadfile_root)

        all_samp_loadfile = lfname(program, 'Sample')
        all_samp_loadfile = os.path.join(loadfile_root, all_samp_loadfile)

        all_sset_loadfile = lfname(program, 'Sample_Set')
        all_sset_loadfile = os.path.join(loadfile_root, all_sset_loadfile)

        all_filter_file   = lfname(program, 'filtered_samples')
        all_filter_file   = os.path.join(loadfile_root, all_filter_file)

        if self.format['create_case_loadfile']:
            write_cases = True
            all_case_loadfile = lfname(program, 'Case')
            all_case_loadfile = os.path.join(loadfile_root, all_case_loadfile)
        else:
            write_cases = False
            all_case_loadfile = os.devnull

        with open(all_samp_loadfile, 'w') as aslfp, \
             open(all_sset_loadfile, 'w') as asslfp, \
             open(all_filter_file, 'w') as affp, \
             open(all_case_loadfile, 'w') as aclfp:

            # Write headers for samples, sset and filtered samples loadfiles
            headers = self.required_headers("Sample") + sorted(attributes)
            aslfp.write("\t".join(headers) + "\n")

            headers = self.required_headers("Sample_Set")
            asslfp.write("\t".join(headers) + "\n")

            headers = self.required_headers("filtered_samples")
            affp.write('\t'.join(headers) + "\n")

            headers = self.required_headers("Case")
            aclfp.write('\t'.join(headers) + "\n")

            # loop over each project, concatenating loadfile data from each
            for projname in sorted(projects.keys()):
                # Write to sample file, but avoid duplicates if its an aggregate
                if projname not in self.config.aggregates:
                    proj_samples = lfname(projname, 'Sample')
                    proj_samples = os.path.join(loadfile_root, proj_samples)
                    with open(proj_samples) as ps:
                        # Skip header, then copy rest of file
                        next(ps)
                        for line in ps:
                            aslfp.write(line)

                proj_sset = lfname(projname, 'Sample_Set')
                proj_sset = os.path.join(loadfile_root, proj_sset)
                with open(proj_sset) as psset:
                    # Skip header then copy rest of file
                    next(psset)
                    for line in psset:
                        asslfp.write(line)

                # Combine filtered samples, but again not for aggregates
                if projname not in self.config.aggregates:
                    proj_filtered = lfname(projname, 'filtered_samples')
                    proj_filtered = os.path.join(loadfile_root, proj_filtered)
                    with open(proj_filtered) as pf:
                        # Skip header then copy rest of file
                        next(pf)
                        for line in pf:
                            affp.write(line)

                # Combine cases, but once again not for aggregates
                if write_cases and projname not in self.config.aggregates:
                    proj_cases = lfname(projname, 'Case')
                    proj_cases = os.path.join(loadfile_root, proj_cases)
                    with open(proj_cases) as pc:
                        # Skip header then copy rest of file
                        next(pc)
                        for line in pc:
                            aclfp.write(line)

    def execute(self):

        try:
            super(gdc_loadfile, self).execute()
            opts = self.options

            # Discern what data is available for given program on given datestamp
            (projects, attributes) = self.inspect_data()

            # ... then make singleton cohort loadfiles (one project/cohort per)
            for project in sorted(projects.keys()):
                self.generate_loadfiles(project, attributes, [projects[project]])

            # ... and aggregate cohort loadfiles (multiple project/cohorts per)
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
                    self.generate_loadfiles(aggr_name, attributes, aggregate)

            # ... lastly, make pan-cohort loadfile for all samples & sample sets
            self.generate_pan_cohort_loadfiles(projects, attributes)
        except Exception as e:
            logging.exception("Create Loadfile FAILED:")
            sys.exit(1)

def get_diced_metadata(project, project_root, datestamp):
    # At this point the datestamp has been vetted to be the latest HH_MM_SS
    # dicing for the given YYYY_MM_DD date; and so there MUST be EXACTLY 1
    # 1 metadata file summarizing that given YYYY_MM_DD__HH_MM_SS dicing.
    mpath = os.path.join(project_root, "metadata", datestamp)
    mpath = os.path.join(mpath, project + '.' + datestamp + ".diced_metadata.tsv")
    if os.path.exists(mpath):
        return mpath
    raise ValueError("Could not find dice metadata for " + project + " on " + datestamp)

def get_sample_id(self, project, row_dict):
    '''Discern sample id from a row dictionary'''
    return self.sample_new(project, row_dict)['sample_id']

def diced_file_comparator(a, b):
    '''Comparator function for barcodes, using the rules described in the GDAC
    FAQ entry for replicate samples: https://confluence.broadinstitute.org/display/GDAC/FAQ
    '''

    # Convert files to barcodes by splitting (removing any path prefix first)
    a = os.path.basename(a).split('.')[0]
    b = os.path.basename(b).split('.')[0]

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
    # NB: the files argument is a list of files prefixed with absolute paths

    # Example files value, drawn from TCGA-LUAD CNV__snp6 data:
    #  ['TCGA-44-2668-01A-01D-1549-01.6a5b9b87-ff2c-4596-b399-5a80299e50f8.txt',
    #   'TCGA-44-2668-01A-01D-A273-01.ed7bdfbc-a87a-4772-b38a-de9ed547d6db.txt',
    #   'TCGA-44-2668-01A-01D-0944-01.06a3821c-ce0c-405a-ad7e-61cb960651d9.txt']
    preferred_order = sorted(files, key=cmp_to_key(diced_file_comparator))
    selected, ignored = preferred_order[0], preferred_order[1:]
    return selected, ignored

def write_samples(cohort_name, samples_fp, filtered_fp,
                  required_headers, attribute_names, samples, missing_file_value):
    ''' Here each sample is output to its own row in the loadfile, with each key
        of the sample dict corresponding to the column name/header and the value
        for each key populating the respective cells of each row. The first N
        columnss are required by the respective loadfile format, while the
        remaining columns are attributes attached to each sample'''

    for sample_id in sorted(samples):
        sample = samples[sample_id]
        chosen_row = "\t".join([sample[c] for c in required_headers])

        attrib_columns = []
        filtered_rows = []
        for attrib in attribute_names:
            files = sample.get(attrib, None)
            # The missing_file_value is anlogous to NA values as used in R,
            # a placeholder so that a given cell in the table is not empty
            # This value can be configured in the [DEFAULT] config section
            if files is None:
                attrib_columns.append(missing_file_value)
            else:
                # If >1 file is a candidate for this attribute (column),
                # pick the most appropriate and record the remainder of
                # the unselected files into the replicates pile
                chosen, ignored = choose_file(files)
                attrib_columns.append(chosen)
                chosen_barcode = os.path.basename(chosen).split('.')[0]
                ignored_barcodes = [os.path.basename(i).split('.')[0] for i in ignored]
                # Create a row for each filtered barcode
                for i in ignored_barcodes:
                    participant_id = chosen_barcode[:12]
                    filter_reason = "Analyte Replicate Filter"
                    removed_sample = i
                    filtered_rows.append([participant_id, cohort_name, attrib,
                                          filter_reason, removed_sample, chosen_barcode])

        # Write row of chosen attributes
        if len(attrib_columns) > 0:
            chosen_row += '\t' + '\t'.join(attrib_columns)
        samples_fp.write(chosen_row + '\n')

        # Write row(s) of filtered barcodes
        for row in filtered_rows:
            row = "\t".join(row)
            filtered_fp.write(row + '\n')

def write_sset_and_cases(samples_filep, sset_filep, cases_fp, sset_name):
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
    samples_filep.seek(0)

    # Iteratively write each sample to multiple sample sets:
    #    First, to the full cohort sample set (e.g. TCGA-COAD)
    #    Then to the respective tissue-specific sample set (e.g TCGA-COAD-TP)
    # While iterating, also accumulate the set of unique cases so that they
    # can also be written to a cases/participants loadfile (if format allows)

    reader = csv.DictReader(samples_filep, delimiter='\t')
    sample_id_field = reader.fieldnames[0]           # See order required_headers()
    case_id_field = reader.fieldnames[1]
    cases = set()

    for sample in reader:
        samp_id = sample[sample_id_field]
        cases.add(sample[case_id_field])

        # Get the tumor type from the last field of the sample id
        # e.g. ACC-OR-A5J1-NB is in the ACC-NB sample set
        sset_type = samp_id.split('-')[-1]

        # A sample is FFPE if the cohort name ends with FFPE
        # e.g. BRCAFFPE-A7-A0DB-TP is FFPE, ACC-OR-A5J1-NB is not
        if not 'FFPE-' in samp_id:
            # Typically samples are included in the sample-type-specific set
            # AND the aggregate sample set: e.g. all TCGA-UCEC-*-NB samples
            # would appear in both TCGA-UCEC-NB AND TCGA-UCEC sample sets
            sset_data = sset_name + "-" + sset_type + "\t" + samp_id + "\n"
            sset_data += sset_name + "\t" + samp_id + "\n"
        else:
            # But FFPE samples are not included in the aggregate sample set
            sset_data = sset_name + "-FFPE" + '\t' + samp_id + '\n'

        sset_filep.write(sset_data)

    if cases_fp:
        for row in sorted(list(cases)):
            cases_fp.write(row + '\n')

def main():
    gdc_loadfile().execute()

if __name__ == "__main__":
    main()
