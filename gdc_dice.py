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
import json
import csv
import os
import sys
import gzip
from pkg_resources import resource_filename #@UnresolvedImport

from lib.convert import util as convert_util
from lib.convert import seg as gdac_seg
from lib.convert import py_clinical as gdac_clin
from lib.convert import tsv2idtsv as gdac_tsv2idtsv
from lib.convert import tsv2magetab as gdac_tsv2magetab
from lib.report import draw_heatmaps
from lib import common
from lib import meta

from GDCtool import GDCtool

class gdc_dicer(GDCtool):

    def __init__(self):
        super(gdc_dicer, self).__init__(version="0.3.0")
        cli = self.cli

        desc =  'Dice data from a Genomic Data Commons (GDC) mirror'
        cli.description = desc

        cli.add_argument('-m', '--mirror-dir',
                         help='Root folder of mirrored GDC data')
        cli.add_argument('-d', '--dice-dir',
                         help='Root of diced data tree')
        cli.add_argument('--dry-run', action='store_true',
                         help="Show expected operations, but don't perform dicing")
        cli.add_argument('datestamp', nargs='?',
                         help='Dice using metadata from a particular date.'\
                         'If omitted, the latest version will be used')

    def parse_args(self):
        opts = self.options

        if opts.log_dir: self.dice_log_dir = opts.log_dir
        if opts.mirror_dir: self.mirror_root_dir = opts.mirror_dir
        if opts.dice_dir: self.dice_root_dir = opts.dice_dir
        if opts.programs: self.dice_programs = opts.programs
        if opts.projects: self.dice_projects = opts.projects

        # Figure out timestamp
        mirror_root = self.mirror_root_dir
        dstamp = opts.datestamp

        # Discover which GDC program(s) data will be diced
        latest_tstamps = set()
        if not self.dice_programs:
            self.dice_programs = common.immediate_subdirs(mirror_root)

        # Discover which GDC projects (within programs) to dice
        for program in self.dice_programs:
            mirror_prog_root = os.path.join(mirror_root, program)
            if self.dice_projects:
                projects = self.dice_projects
            else:
                projects = common.immediate_subdirs(mirror_prog_root)
                if "metadata" in projects:
                    projects.remove("metadata")
            for project in projects:
                # For each project, get timestamp of last mirror that matches
                proj_dir = os.path.join(mirror_prog_root, project)
                tstamp = meta.latest_timestamp(proj_dir, dstamp)
                if tstamp:
                    latest_tstamps.add(tstamp)
                else:
                    print("No dicing for %s, is it a valid project name?" % project)

        if len(latest_tstamps) > 1:
            raise ValueError("Multiple timestamps discovered for single mirror: " + str(latest_tstamps))
        elif len(latest_tstamps) < 1:
            raise ValueError("No valid programs/projects/dicings discovered")

        # Set the timestamp for this run
        self.timestamp = latest_tstamps.pop() if latest_tstamps else "9999_99_99"

    def dice(self):
        logging.info("GDC Dicer Version: %s", self.cli.version)
        logging.info("Command: " + " ".join(sys.argv))
        mirror_root = self.mirror_root_dir
        diced_root = self.dice_root_dir
        trans_dict = build_translation_dict(resource_filename("gdctools",
                                                "config/annotations_table.tsv"))
        # Set in init_logs()
        timestamp = self.timestamp
        logging.info("Mirror timestamp: " + timestamp)
        # Iterable of programs, either user specified or discovered from folder names in the diced root
        if self.dice_programs:
            programs = self.dice_programs
        else:
            programs = common.immediate_subdirs(mirror_root)

        for program in programs:
            diced_prog_root = os.path.join(diced_root, program)
            mirror_prog_root = os.path.join(mirror_root, program)

            # Ensure no simultaneous mirroring/dicing
            with common.lock_context(diced_prog_root, "dice"), \
                 common.lock_context(mirror_prog_root, "mirror"):
                if self.dice_projects:
                    projects = self.dice_projects
                else:
                    projects = common.immediate_subdirs(mirror_prog_root)
                    if "metadata" in projects:
                        projects.remove("metadata")
                for project in sorted(projects):
                    # Load metadata from mirror
                    raw_project_root = os.path.join(mirror_prog_root, project)
                    stamp_root = os.path.join(raw_project_root, "metadata", timestamp)
                    metadata = meta.latest_metadata(stamp_root)
                    diced_project_root = os.path.join(diced_prog_root, project)
                    logging.info("Dicing " + project + " to " + diced_project_root)

                    # The natural form of the metadata is a list of file dicts,
                    # which makes it easy to mirror on a project by project
                    # basis. However, the dicer should insist that only one
                    # file per case per annotation exists, and therefore we must
                    # generate a data structure in this form by iterating over
                    # the metadata before dicing.

                    tcga_lookup = _tcgaid_file_lookup(metadata, trans_dict)

                    # Diced Metadata
                    diced_meta_dir = os.path.join(diced_project_root,
                                                  "metadata", timestamp)
                    diced_meta_fname = ".".join(['diced_metadata', timestamp, 'tsv'])
                    if not os.path.isdir(diced_meta_dir):
                        os.makedirs(diced_meta_dir)
                    meta_file = os.path.join(diced_meta_dir, diced_meta_fname)

                    # Count project annotations
                    annots = set()
                    with open(meta_file, 'w') as mf:
                        # Header
                        mf.write("case_id\tsample_type\tannotation\tfile_name\n")

                        for tcga_id in tcga_lookup:
                            for annot, file_d in tcga_lookup[tcga_id].iteritems():
                                annots.add(annot)
                                dice_one(file_d, trans_dict, raw_project_root,
                                         diced_project_root, mf,
                                         dry_run=self.options.dry_run)

                    # Count available data per sample
                    logging.info("Generating counts for " + project)
                    proj_counts, proj_annots = _count_samples(meta_file)
                    counts_file = ".".join([project, 'sample_counts', timestamp, "tsv"])
                    counts_file = os.path.join(diced_meta_dir, counts_file)

                    # Counts are written on a per-cohort (project) basis during
                    # dicing, as these are the way the data are naturally
                    # organized. Aggregate cohorts are not created during
                    # dicing, so no aggregate counts file is generated until a
                    # freeze (loadfile) specifying these groups is also created.
                    _write_counts(proj_counts, project, proj_annots, counts_file)

                    # Heatmaps for each individual project
                    logging.info("Generating heatmaps for " + project)
                    create_heatmaps(meta_file, annots, project, timestamp, diced_meta_dir)

        logging.info("Dicing completed successfuly")

    def execute(self):
        super(gdc_dicer, self).execute()
        opts = self.options
        self.parse_args()
        common.init_logging(self.timestamp, self.dice_log_dir, "gdcDice")
        try:
            self.dice()
        except Exception as e:
            logging.exception("Dicing FAILED:")

def _tcgaid_file_lookup(metadata, translation_dict):
    '''Builds a dictionary mapping tcga_ids to their file info,
    stratified by annotation type. This enables the dicer to ensure one diced
    file per sample or case'''
    d = dict()
    for file_dict in metadata:
        tcga_id = meta.tcga_id(file_dict)
        annot, _ = get_annotation_converter(file_dict, translation_dict)
        d[tcga_id] = d.get(tcga_id, dict())
        # Note that this overwrites any previous value.
        # FIXME: More sophisticated reasoning
        d[tcga_id][annot] =  file_dict

    return d

def build_translation_dict(translation_file):
    """Builds a translation dictionary from a translation table.

    First column of the translation_file is the Annotation name,
    remaining columns are signatures in the file metadata that indicate a file is of this annotation type.
    """

    with open(translation_file, 'rU') as tsvfile:
        reader = csv.DictReader(tsvfile, delimiter='\t')
        d = dict()

        # Duplicate detection
        dupes = False
        for row in reader:
            annot = row.pop("Firehose_annotation")
            converter_name = row.pop("converter")

            ## Parse list fields into frozensets
            row['tags'] = frozenset(row['tags'].split(',') if row['tags'] != '' else [])

            # Only add fields from the row if they are present in the row_dict
            # Give a warning if overwriting an existing tag, and don't add the new one
            key = frozenset(row.items())
            if key not in d:
                d[key] = (annot, converter(converter_name))
            else:
                dupes = True
    if dupes:
        logging.warning("duplicate annotation definitions detected")
    return d

def dice_one(file_dict, translation_dict, mirror_proj_root, diced_root,
             meta_file, dry_run=True):
    """Dice a single file from a GDC mirror.

    Diced data will be placed in /<diced_root>/<annotation>/. If dry_run is
    true, a debug message will be displayed instead of performing the actual
    dicing operation.
    """
    mirror_path = meta.mirror_path(mirror_proj_root, file_dict)
    if os.path.isfile(mirror_path):
        ## Get the right annotation and converter for this file
        annot, convert = get_annotation_converter(file_dict, translation_dict)
        # FIXME: Handle this better
        if annot != 'UNRECOGNIZED':
            dice_path = os.path.join(diced_root, annot)
            # convert expected path to a relative path from the diced_root
            expected_path = convert_util.diced_file_path(dice_path, file_dict)
            expected_path = os.path.abspath(expected_path)
            logging.info("Dicing file {0} to {1}".format(mirror_path,
                                                         expected_path))
            if not dry_run:
                if not os.path.isfile(expected_path):
                    convert(file_dict, mirror_path, dice_path)
                else:
                    logging.info('Diced file exists')

                append_diced_metadata(file_dict, expected_path,
                                      annot, meta_file)
        else:
            logging.warn('Unrecognized data:\n%s' % json.dumps(file_dict,
                                                               indent=2))

def get_annotation_converter(file_dict, translation_dict):
    k = metadata_to_key(file_dict)
    if k in translation_dict:
        return translation_dict[k]
    else:
        # FIXME: Gracefully handle this instead of creating a new annotation type
        return "UNRECOGNIZED", None

def metadata_to_key(file_dict):
    """Converts the file metadata in file_dict into a key in the TRANSLATION_DICT"""
    # Required fields
    data_type = file_dict.get("data_type", '')
    data_category = file_dict.get("data_category", '')
    experimental_strategy = file_dict.get("experimental_strategy", '')
    platform = file_dict.get("platform", '')
    tags = _parse_tags(file_dict.get("tags",[]))
    center_namespace = file_dict['center']['namespace'] if 'center' in file_dict else ''
    workflow_type = file_dict['analysis']['workflow_type'] if 'analysis' in file_dict else ''

    return frozenset({
        "data_type" : data_type,
        "data_category": data_category,
        "experimental_strategy": experimental_strategy,
        "platform": platform,
        "tags": tags,
        "center_namespace": center_namespace,
        "workflow_type" : workflow_type
    }.items())

def append_diced_metadata(file_dict, diced_path, annot, meta_file):
    if meta.has_sample(file_dict):
        sample_type = meta.sample_type(file_dict)
    else:
        sample_type = "None" # Case_level
    cid = meta.case_id(file_dict)

    meta_file.write("\t".join([cid, sample_type, annot, diced_path]) + "\n")

def _count_samples(diced_metadata_file):
    '''Count the number of diced files for each annotation/tumor-type'''
    counts = dict()
    cases_with_clinical = set()
    cases_with_biospecimen = set()
    case_codes = dict()
    annotations = set()

    with open(diced_metadata_file, 'r') as dmf:
        reader = csv.DictReader(dmf, delimiter='\t')
        # Loop through counting non-case-level annotations
        for row in reader:

            annot = row['annotation']
            case_id = row['case_id']

            annotations.add(annot)

            # FIXME: This should probably not be hard-coded
            if 'clinical__primary' == annot:
                cases_with_clinical.add(case_id)
            elif 'clinical__biospecimen' == annot:
                cases_with_biospecimen.add(case_id)
            else:
                _, sample_type = meta.tumor_code(row['sample_type'])
                counts[sample_type] = counts.get(sample_type, dict())
                counts[sample_type][annot] = counts[sample_type].get(annot, 0) + 1
                if case_id not in case_codes: case_codes[case_id] = set()
                case_codes[case_id].add(sample_type)

    # Now go back through and count the Biospecimen and Clinical data
    # Each sample type is counted as 1 if present
    for case in case_codes:
        codes = case_codes[case]
        for c in codes:
            if case in cases_with_clinical:
                count = counts[c].get('clinical__primary', 0) + 1
                counts[c]['clinical__primary'] = count
            if case in cases_with_biospecimen:
                count = counts[c].get('clinical__biospecimen', 0) + 1
                counts[c]['clinical__biospecimen'] = count

    return counts, annotations

def _write_counts(sample_counts, proj_name, annots, f):
    '''Write sample counts dict to file.
    counts = { 'TP' : {'clinical__primary' : 10, '...': 15, ...},
               'TR' : {'clinical__primary' : 10, '...': 15, ...},
               ...}
    '''

    # FIXME: insert short data type codes, rather than full type names
    # E.g. BCR instead of Biospecimen

    annots = sorted(annots)
    # Abbreviate data types, if possible
    with open(f, "w") as out:
        # Write header
        out.write("Sample Type\t" + "\t".join(annots) + '\n')
        for code in sample_counts:
            line = code + "\t"
            # Headers can use abbreviated data types
            abbr_types = [meta.type_abbr(dt) for dt in annots]
            line += "\t".join([str(sample_counts[code].get(t, 0)) for t in annots]) + "\n"

            out.write(line)

        # Write totals. Totals is dependent on the main analyzed tumor type
        main_code = meta.tumor_code(meta.main_tumor_sample_type(proj_name))[1]
        tots = [str(sample_counts.get(main_code,{}).get(t, 0)) for t in annots]
        out.write('Totals\t' + '\t'.join(tots) + "\n")

def create_heatmaps(diced_metadata_file, annots, project, timestamp, outdir):
    rownames, matrix = _build_heatmap_matrix(diced_metadata_file, annots)
    draw_heatmaps(rownames, matrix, project, timestamp, outdir)

def _build_heatmap_matrix(diced_metadata_file, annots):
    '''Build a 2d matrix and rownames from annotations and load dict'''
    rownames = sorted(list(annots))
    annot_sample_data = dict()
    # Extract a matrix of whether each annotation has a sample id
    with open(diced_metadata_file, 'r') as dmf:
        reader = csv.DictReader(dmf, delimiter='\t')
        for row in reader:
            case_id = row['case_id']
            annot = row['annotation']
            annot_sample_data[case_id] = annot_sample_data.get(case_id, set())
            annot_sample_data[case_id].add(annot)

    matrix = [[] for row in rownames]
    # Now iterate over samples, inserting a 1 if data is presente
    for r in range(len(rownames)):
        for sid in sorted(annot_sample_data.keys()):
            # append 1 if data is present, else 0
            matrix[r].append( 1 if rownames[r] in annot_sample_data[sid] else 0)

    return rownames, matrix

## Converter mappings
def converter(converter_name):
    """Returns the converter function by name using a dictionary lookup."""
    CONVERTERS = {
        'clinical' : clinical,
        'copy' : copy,
        'magetab_data_matrix': magetab_data_matrix,
        'maf': maf,
        'seg_broad': seg_broad,
        'seg_harvard': seg_harvard,
        'seg_harvardlowpass': seg_harvardlowpass,
        'seg_mskcc2' : seg_mskcc2,
        'tsv2idtsv' : tsv2idtsv,
        'unzip_tsv2idtsv': unzip_tsv2idtsv,
        'tsv2magetab': tsv2magetab,
        'unzip_tsv2magetab': unzip_tsv2magetab,
        'fpkm2magetab': fpkm2magetab,
        'unzip_fpkm2magetab': unzip_fpkm2magetab
    }

    return CONVERTERS[converter_name]

# Converters
# Each must return a dictionary mapping case_ids to the diced file paths
def copy(file_dict, mirror_path, dice_path):
    print("Dicing with 'copy'")
    pass

def clinical(file_dict, mirror_path, outdir):
    case_id = meta.case_id(file_dict)
    return {case_id: gdac_clin.process(mirror_path, file_dict, outdir)}

def maf(file_dict, mirror_path, dice_path):
    pass

def magetab_data_matrix(file_dict, mirror_path, dice_path):
    pass

def seg_broad(file_dict, mirror_path, dice_path):
    infile = mirror_path
    hyb_id = file_dict['file_name'].split('.',1)[0]
    tcga_id = meta.aliquot_id(file_dict)
    case_id = meta.case_id(file_dict)
    return {case_id: gdac_seg.process(infile, file_dict, hyb_id,
                                      tcga_id, dice_path, 'seg_broad')}

def seg_harvard(file_dict, mirror_path, dice_path):
    pass
def seg_harvardlowpass(file_dict, mirror_path, dice_path):
    pass
def seg_mskcc2(file_dict, mirror_path, dice_path):
    pass

def tsv2idtsv(file_dict, mirror_path, dice_path):
    case_id = meta.case_id(file_dict)
    return {case_id : gdac_tsv2idtsv.process(mirror_path, file_dict, dice_path)}

def unzip_tsv2idtsv(file_dict, mirror_path, dice_path):
    return _unzip(file_dict, mirror_path, dice_path, tsv2idtsv)

def tsv2magetab(file_dict, mirror_path, dice_path):
    case_id = meta.case_id(file_dict)
    return {case_id : gdac_tsv2magetab.process(mirror_path, file_dict,
                                               dice_path)}

def unzip_tsv2magetab(file_dict, mirror_path, dice_path):
    return _unzip(file_dict, mirror_path, dice_path, tsv2magetab)

def fpkm2magetab(file_dict, mirror_path, dice_path):
    case_id = meta.case_id(file_dict)
    return {case_id : gdac_tsv2magetab.process(mirror_path, file_dict,
                                               dice_path, fpkm=True)}

def unzip_fpkm2magetab(file_dict, mirror_path, dice_path):
    return _unzip(file_dict, mirror_path, dice_path, fpkm2magetab)

def _unzip(file_dict, mirror_path, dice_path, _converter):
    # First unzip the mirror_path, which is a .gz
    if not mirror_path.endswith('.gz'):
        raise ValueError('Unexpected gzip filename: ' +
                         os.path.basename(mirror_path))
    uncompressed = mirror_path.rstrip('.gz')
    with gzip.open(mirror_path, 'rb') as mf, open(uncompressed, 'w') as out:
        out.write(mf.read())
    # Now dice extracted file
    diced = _converter(file_dict, uncompressed, dice_path)
    # Remove extracted file to save disk space
    os.remove(uncompressed)
    return diced

def _parse_tags(tags_list):
    return frozenset('' if len(tags_list)==0 else tags_list)

if __name__ == "__main__":
    gdc_dicer().execute()
