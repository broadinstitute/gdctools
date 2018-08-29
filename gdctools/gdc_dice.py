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

import logging
import json
import csv
import os
import sys
import gzip
from collections import defaultdict, Counter
from pkg_resources import resource_filename
from glob import iglob
from future.utils import viewitems, viewvalues

from gdctools.lib.convert import seg as gdac_seg
from gdctools.lib.convert import py_clinical as gdac_clin
from gdctools.lib.convert import tsv2idtsv as gdac_tsv2idtsv
from gdctools.lib.convert import tsv2magetab as gdac_tsv2magetab
from gdctools.lib.convert import copy as gdac_copy
from gdctools.lib.convert import maf as maf
from gdctools.lib import common, meta
from gdctools.GDCtool import GDCtool

class gdc_dice(GDCtool):

    def __init__(self):
        super(gdc_dice, self).__init__(version="0.5.4")
        cli = self.cli

        desc =  'Dice data from a Genomic Data Commons (GDC) mirror'
        cli.description = desc
        cli.add_argument('-d', '--dice-dir', help='Root of diced data tree')
        cli.add_argument('--dry-run', action='store_true',
               help="Show expected operations, but don't perform dicing")
        cli.add_argument('-f', '--force', action='store_true',
                help="Force dicing of all files, even those already diced")
        cli.add_argument('-m', '--mirror-dir',
               help='Root folder of mirrored GDC data')

    def config_customize(self):
        opts = self.options
        config = self.config
        if opts.mirror_dir: config.mirror.dir = opts.mirror_dir
        if opts.dice_dir: config.dice.dir = opts.dice_dir
        self.force = opts.force

        # If undefined, discover which GDC program(s) data to dice
        if not config.programs:
            config.programs = common.immediate_subdirs(config.mirror.dir)

        # Even though program is a list, only check the first one, since
        # providing more than one will be caught as an error
        if not config.projects:
            program = config.programs[0]
            mirror_prog_root = os.path.join(config.mirror.dir, program)
            config.projects = common.immediate_subdirs(mirror_prog_root)

    def dice(self):
        logging.info("GDC Dicer Version: %s", self.version)
        logging.info("Command: " + " ".join(sys.argv))
        trans_dict = build_translation_dict(resource_filename(__name__,
                                  os.path.join("lib", "annotations_table.tsv")))
        config = self.config
        # Get cohort to aggregate map
        cohort_agg_dict = self.cohort_aggregates()

        # Programs is a list, but with only one element
        program = config.programs[0]
        diced_prog_root = os.path.join(config.dice.dir, program)
        mirror_prog_root = os.path.join(config.mirror.dir, program)

        # Ensure no simultaneous mirroring/dicing
        with common.lock_context(diced_prog_root, "dice"), \
             common.lock_context(mirror_prog_root, "mirror"):

            logging.info("Dicing : " + program)
            logging.info("Projects: {0}".format(config.projects))

            # datestamp set by GDCtool base class
            datestamp = self.datestamp

            logging.info("Mirror date: " + datestamp)


            diced_prog_metadata = os.path.join(diced_prog_root, 'metadata')
            if not os.path.isdir(diced_prog_metadata):
                os.makedirs(diced_prog_metadata)
            all_counts_file = os.path.join(diced_prog_metadata,
                                           '.'.join(['sample_counts', datestamp,
                                                     'tsv']))
            all_counts = dict()
            all_totals = Counter()

            agg_case_data = defaultdict(dict)
            for project in sorted(config.projects):
                # Load metadata from mirror, getting the latest metadata
                # earlier than the given datestamp
                raw_project_root = os.path.join(mirror_prog_root, project)
                meta_dir = os.path.join(raw_project_root, "metadata", datestamp)
                #TODO: This is a very redundant format, and doesn't fix the ls issue
                # Should reorganize the metadata folder structure to
                # .../proj/metadata/YYYY/metadata.project.<date>.json
                meta_file = os.path.join(meta_dir,
                                         '.'.join(["metadata", project,
                                                   datestamp, "json"]))

                # Sanity check, there must be saved metadata for each
                # project in order to dice
                if not os.path.exists(meta_file):
                    raise ValueError("No metadata found for %s on %s" %
                                     (project, datestamp))

                # Read metadata into a dict
                with open(meta_file) as mf:
                    metadata = json.load(mf)

                # Subset data to dice by obeying constraints given in CLI/config
                metadata = constrain(metadata, config)

                diced_project_root = os.path.join(diced_prog_root, project)
                logging.info("Dicing " + project + " to " + diced_project_root)

                # The natural form of the metadata is a list of file dicts,
                # which makes it easy to mirror on a project by project
                # basis. However, the dicer should insist that only one
                # file per case per annotation exists, and therefore we must
                # generate a data structure in this form by iterating over
                # the metadata before dicing.
                tcga_lookup, multi_sample_files  = _tcgaid_file_lookup(metadata,
                                                                       trans_dict)

                # Diced Metadata
                diced_meta_dir = os.path.join(diced_project_root,
                                              "metadata", datestamp)
                diced_meta_fname = ".".join([project, datestamp,
                                            'diced_metadata', 'tsv'])
                if not os.path.isdir(diced_meta_dir):
                    os.makedirs(diced_meta_dir)
                diced_meta_file = os.path.join(diced_meta_dir, diced_meta_fname)

                # Count project annotations
                with open(diced_meta_file, 'w') as mf:
                    # Header
                    META_HEADERS = ['case_id', 'tcga_barcode', 'sample_type',
                                    'annotation', 'file_name', 'center',
                                    'platform', 'report_type', 'is_ffpe']
                    mfw = csv.DictWriter(mf, fieldnames=META_HEADERS,
                                         delimiter='\t')
                    mfw.writeheader()

                    for tcga_id in tcga_lookup:
                        # Dice single sample files first
                        for file_d in viewvalues(tcga_lookup[tcga_id]):
                            dice_one(file_d, trans_dict, raw_project_root,
                                     diced_project_root, mfw,
                                     dry_run=self.options.dry_run,
                                     force=self.force)

                    #Then dice the multi_sample_files
                    for file_d in multi_sample_files:
                        dice_one(file_d, trans_dict, raw_project_root,
                                 diced_project_root, mfw,
                                 dry_run=self.options.dry_run,
                                 force=self.force)

                # Bookkeeping code -- write some useful tables
                # and figures needed for downstream sample reports.
                # Count available data per sample
                logging.info("Generating counts for " + project)
                case_data = meta.extract_case_data(diced_meta_file)
                counts_file = ".".join([project, datestamp,
                                        "sample_counts.tsv"])
                counts_file = os.path.join(diced_meta_dir, counts_file)
                counts, totals = _write_counts(case_data, counts_file)
                all_counts.update((project + '-' + sample_type, count) for
                                  (sample_type, count) in viewitems(counts))
                all_counts[project] = totals
                for (data_type, count) in viewitems(totals):
                    all_totals[data_type] += count

                # Keep track of aggregate case data
                project_aggregates = cohort_agg_dict[project]
                for agg in project_aggregates:
                    agg_case_data[agg].update(case_data)

            # Create aggregate diced_metadata.tsvs
            self.aggregate_diced_metadata(diced_prog_root, datestamp)

            # As well as aggregate counts and heatmaps
            for agg in agg_case_data:
                ac_data = agg_case_data[agg]
                meta_dir = os.path.join(diced_prog_root, agg, "metadata",
                                        datestamp)

                logging.info("Generating aggregate counts for " + agg)
                counts_file = ".".join([agg, datestamp, "sample_counts.tsv"])
                counts_file = os.path.join(meta_dir, counts_file)
                counts, totals = _write_counts(ac_data, counts_file)
                all_counts.update((agg + '-' + sample_type, count) for
                                  (sample_type, count) in viewitems(counts))
                all_counts[agg] = totals

            logging.info("Combining all sample counts into one file ...")
            _write_combined_counts(all_counts_file, all_counts, all_totals)
            _link_to_prog(all_counts_file, datestamp, diced_prog_root)

        logging.info("Dicing completed successfuly")

    def execute(self):
        super(gdc_dice, self).execute()
        try:
            self.validate()
            self.dice()
        except:
            logging.exception("Dicing FAILED:")
            sys.exit(1)

    def cohort_aggregates(self):
        '''Invert the Aggregate->Cohort dictionary to list all aggregates for
        a cohort.'''
        cohort_agg = defaultdict(list)
        for (agg, cohorts) in viewitems(self.config.aggregates):
            for c in cohorts.split(','):
                cohort_agg[c].append(agg)
        return cohort_agg

    def aggregate_diced_metadata(self, prog_dir, datestamp):
        '''Aggregates the diced metadata files for aggregate cohorts'''
        # Note we can only aggregate data where each cohort in the aggregate
        # has the same datestamp for the diced metadata

        aggregates = self.config.aggregates
        for (agg, cohorts) in viewitems(aggregates):
            cohorts = sorted(cohorts.split(','))
            agg_meta_folder = os.path.join(prog_dir, agg, "metadata", datestamp)
            if not os.path.isdir(agg_meta_folder):
                os.makedirs(agg_meta_folder)
            agg_meta_file = ".".join([agg, datestamp, 'diced_metadata', 'tsv'])
            agg_meta_file = os.path.abspath(os.path.join(agg_meta_folder,
                                                        agg_meta_file))
            skip_header = False

            # check to see if all the necessary diced files exist
            cohort_diced_tsvs = []
            for c in cohorts:
                c_meta_folder = os.path.join(prog_dir, c, "metadata", datestamp)
                c_meta_file = ".".join([c, datestamp, 'diced_metadata', 'tsv'])
                c_meta_file = os.path.abspath(os.path.join(c_meta_folder,
                                                           c_meta_file))
                cohort_diced_tsvs.append(c_meta_file)

            # Further sanity check
            if not all(os.path.exists(f) for f in cohort_diced_tsvs):
                logging.warning("Cohorts in aggregate " + agg + " have differing datestamps")
                return

            # otherwise, merge as normal
            with open(agg_meta_file, 'w') as out:
                for meta_f in cohort_diced_tsvs:
                    with open(meta_f, 'r') as f_in:
                        if skip_header:
                            next(f_in)
                        for line in f_in:
                            out.write(line)
                    skip_header = True

    def validate(self):
        '''Validate programs & projects by ensuring a folder exists for each'''

        config = self.config
        if len(config.programs) != 1:
            raise RuntimeError("Dicer only supports dicing a single program but "
                + str(len(config.programs)) + " were provided.")

        possible_programs = common.immediate_subdirs(config.mirror.dir)
        program = config.programs[0]
        if program not in possible_programs:
            raise RuntimeError("Program " + program + " not found in mirror")

        prog_dir = os.path.join(config.mirror.dir, program)
        possible_projects = common.immediate_subdirs(prog_dir)

        projects = config.projects
        for proj in projects:
            if proj not in possible_projects:
                raise RuntimeError("Project " + proj + " not found in mirror")

def _tcgaid_file_lookup(metadata, translation_dict):
    '''Builds a dictionary mapping tcga_ids to their file info,
    stratified by annotation type. This enables the dicer to ensure one diced
    file per sample or case. However, certain files (MAFs, e.g.) have more
    than one case per file, and must be treated separately.'''
    single_barcode_lookup = defaultdict(dict)
    multi_barcode_files = []
    for file_dict in metadata:
        if not meta.has_multiple_samples(file_dict):
            # Normal file, one barcode per sample/annotation
            tcga_id = meta.tcga_id(file_dict)
            annot, _ = get_annotation_converter(file_dict, translation_dict)
            # Note that this overwrites any previous value.
            # FIXME: More sophisticated reasoning
            if annot in single_barcode_lookup[tcga_id]:
                logging.warning("Multiple files found for %s %s" %(tcga_id,
                                                                   annot))
            single_barcode_lookup[tcga_id][annot] = file_dict
        else:
            # Multiple barcode file, return separately
            multi_barcode_files.append(file_dict)

    return single_barcode_lookup, multi_barcode_files

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
             meta_file_writer, dry_run=False, force=False):
    """Dice a single file from a GDC mirror.

    Diced data will be placed in /<diced_root>/<annotation>/. If dry_run is
    true, a debug message will be displayed instead of performing the actual
    dicing operation.
    """
    mirror_path = meta.mirror_path(mirror_proj_root, file_dict)
    if not os.path.isfile(mirror_path):
        # Bad, this means there are integrity issues
        raise ValueError("Expected mirror file missing: " + mirror_path)
    else:
        ## Get the right annotation and converter for this file
        annot, convert = get_annotation_converter(file_dict, translation_dict)
        # FIXME: Handle this better
        if annot != 'UNRECOGNIZED':
            dice_path = os.path.join(diced_root, annot)
            # convert expected path to a relative path from the diced_root
            expected_paths = meta.diced_file_paths(dice_path, file_dict)
            expected_paths = [os.path.abspath(p) for p in expected_paths]

            if not dry_run:
                # Dice if force is enabled or not all expected files exist
                already_diced = all(os.path.isfile(p) for p in expected_paths)
                if force or not already_diced:
                    logging.info("Dicing file " + mirror_path)
                    try:
                        convert(file_dict, mirror_path, dice_path)
                    except Exception as e:
                        logging.info("Skipping file " + mirror_path + " (ERROR during dicing)")
                        logging.info(e)
                else:
                    logging.info("Skipping file " + mirror_path + " (already diced)")

                append_diced_metadata(file_dict, expected_paths,
                                      annot, meta_file_writer)
        else:
            # To verbose to log the entire json, log just log data_type and file_id
            warning_info = {
                'data_type' : file_dict["data_type"],
                'data_category' : file_dict["data_category"],
                'file_id' : file_dict["file_id"],
                'file_name': file_dict['file_name']
            }
            logging.warn('Unrecognized data:\n%s' % json.dumps(warning_info,
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
        "data_type"             : data_type,
        "data_category"         : data_category,
        "experimental_strategy" : experimental_strategy,
        "platform"              : platform,
        "tags"                  : tags,
        "center_namespace"      : center_namespace,
        "workflow_type"         : workflow_type
    }.items())

def append_diced_metadata(file_dict, diced_paths, annot, meta_file_writer):
    '''Write one or more rows for the given file_dict using meta_file_writer.
    The number of rows will be equal to the length of diced_paths.


    meta_file_writer must be a csv.DictWriter
    '''
    
    # These fields will be shared regardless of the number of diced files
    rowdict = {
        'annotation'   : annot,
        'center'       : meta.center(file_dict),
        'platform'     : meta.platform(file_dict),
        'report_type'  : common.ANNOT_TO_DATATYPE[annot]
    }

    if len(diced_paths) == 1 and not meta.has_multiple_samples(file_dict):
        # Easy case, one file for this case or sample
        diced_path = diced_paths[0]
        sample_type = None
        if meta.has_sample(file_dict):
            sample_type = meta.sample_type(file_dict)

        # Write row with csv.DictWriter.writerow()
        rowdict.update({
            'case_id'      : meta.case_id(file_dict),
            'tcga_barcode' : meta.tcga_id(file_dict),
            'sample_type'  : sample_type,
            'file_name'    : diced_path,
            'is_ffpe'      : meta.is_ffpe(file_dict)
        })

        meta_file_writer.writerow(rowdict)
    else:
        # Harder case, have to write a line for each unique file
        # We need to match the diced filenames back to the original samples
        # to get the sample type and whether the file is ffpe
        samples = meta.samples(file_dict)
        barcode_to_sample_dict = dict()
        for s in samples:
            for tcga_barcode in meta.aliquot_ids([s]):
                barcode_to_sample_dict[tcga_barcode] = (s['sample_type'], s['is_ffpe'])

        for diced_path in diced_paths:
            tcga_barcode = os.path.basename(diced_path).split('.')[0]
            # case_id is the first twelve digits of the TCGA barcode
            case_id = tcga_barcode[:12]
            sample_type, is_ffpe = barcode_to_sample_dict[tcga_barcode]

            rowdict.update({
                'case_id'      : case_id,
                'tcga_barcode' : tcga_barcode,
                'sample_type'  : sample_type,
                'file_name'    : diced_path,
                'is_ffpe'      : is_ffpe
            })
            meta_file_writer.writerow(rowdict)

def constrain(metadata, config):
    cases_chosen = set(config.cases)
    categories_chosen = config.categories

    # Accept everything if no case/category constraints were specified
    if not (cases_chosen or categories_chosen):
        return metadata

    result = []
    for this in metadata:
        cases = {c['submitter_id'] for c in this['cases']}
        if cases_chosen and (cases.isdisjoint(cases_chosen)):
            # If none of the case IDs for this have been chosen, skip
            this = None
        elif categories_chosen and this['data_category'] not in categories_chosen:
            # Ditto for data category: skip if not chosen
            this = None
        if this:
            result.append(this)
    return result

def _write_counts(case_data, counts_file):
    '''
    Write case data as counts, return counting data for use in generating
    program counts.
    '''
    # First, put the case data into an easier format:
    # { 'TP' : {'BCR' : 10, '...': 15, ...},
    #   'TR' : {'Clinical' : 10, '...': 15, ...},
    #           ...}
    rdt = common.REPORT_DATA_TYPES
    counts = defaultdict(Counter)
    totals = Counter()
    for case in viewvalues(case_data):
        main_type = meta.tumor_code(meta.main_tumor_sample_type(case.proj_id)).symbol
        c_dict = case.case_data
        for sample_type in c_dict:
            for report_type in c_dict[sample_type]:
                counts[sample_type][report_type] += 1
                if sample_type == main_type:
                    totals[report_type] += 1

    # Now write the counts table
    with open(counts_file, 'w') as out:
        # Write header
        out.write("Sample Type\t" + "\t".join(rdt) + '\n')
        for code in counts:
            line = code + "\t"
            # Headers can use abbreviated data types
            line += "\t".join([str(counts[code][t]) for t in rdt]) + "\n"

            out.write(line)

        # Write totals. Totals is dependent on the main analyzed tumor type
        out.write('Totals\t' + '\t'.join(str(totals[t]) for t in rdt) + "\n")

    return (counts, totals)

def _write_combined_counts(all_counts_file, all_counts, all_totals):
    '''
    Create a program-wide counts file combining all cohorts, including
    aggregates.
    '''
    all_annots = common.REPORT_DATA_TYPES
    with open(all_counts_file, 'w') as f:
        header = 'Cohort\t' + '\t'.join(all_annots) + '\n'
        f.write(header)
        # Write row of counts for each annot
        for cohort in sorted(all_counts):
            row = [cohort] + [str(all_counts[cohort].get(a, 0)) for a in all_annots]
            f.write('\t'.join(row) + '\n')

        # Write totals
        tot_row = ['Totals'] + [str(all_totals.get(a, 0)) for a in all_annots]
        f.write('\t'.join(tot_row) + '\n')

def _link_to_prog(prog_meta_file, datestamp, diced_prog_root):
    '''Link the given program metadata file to the to diced program root dir'''
    prog_meta_link = os.path.join(os.path.abspath(diced_prog_root),
                                  os.path.basename(prog_meta_file))

    #remove old links
    for old_link in iglob(prog_meta_link.replace(datestamp, '*')):
        os.unlink(old_link)

    os.symlink(os.path.abspath(prog_meta_file), prog_meta_link)

## Converter mappings
def converter(converter_name):
    '''Returns the file conversion function by name, using dictionary lookup'''

    # FIXME: make smarter by allowing args (like dialect, fpkm) to be overridden
    #        when converter is called, w/o intermediate funcs like seg_wxs etc
    def _unzip(file_dict, mirror_path, dice_path, _converter):
        # When original mirror_path files are compressed, uncompress first
        if not mirror_path.endswith('.gz'):
            raise ValueError('Unexpected gzip filename: ' +
                             os.path.basename(mirror_path))
        uncompressed = mirror_path.rstrip('.gz')
        with gzip.open(mirror_path, 'rt') as mf, open(uncompressed, 'w') as out:
                out.write(mf.read())

        # Now dice extracted file
        diced = _converter(file_dict, uncompressed, dice_path)
        # Remove extracted file to save disk space
        os.remove(uncompressed)
        return diced

    # Specialized converters when we need to supply additional arguments
    def unzip_tsv2idtsv(file_dict, mirror_path, dice_path):
        _unzip(file_dict, mirror_path, dice_path, gdac_tsv2idtsv.process)

    def unzip_tsv2magetab(file_dict, mirror_path, dice_path):
        return _unzip(file_dict, mirror_path, dice_path, gdac_tsv2magetab.process)

    def fpkm2magetab(file_dict, mirror_path, dice_path):
        gdac_tsv2magetab.process(file_dict, mirror_path, dice_path, fpkm=True)

    def usc_meth2magetab(file_dict, mirror_path, dice_path):
        gdac_tsv2magetab.process(file_dict, mirror_path, dice_path,
                                 col_order=[0,2,3,4,5,6,7,8,9,10,1], data_cols=[1])

    def washu_meth2magetab(file_dict, mirror_path, dice_path):
        gdac_tsv2magetab.process(file_dict, mirror_path, dice_path,
                                 col_order=[0,2,3,4,25,26,27,13,5,6,7,8,9,10,
                                            11,12,14,15,16,17,18,19,20,21,22,
                                            23,24,28,29,30,31,32,33,34,35,36,1],
                                 data_cols=[1], id_func=meta.portion_id)

    def unzip_fpkm2magetab(file_dict, mirror_path, dice_path):
        return _unzip(file_dict, mirror_path, dice_path, fpkm2magetab)

    def seg_wxs(file_dict, mirror_path, dice_path):
        gdac_seg.process(file_dict, mirror_path, dice_path, dialect='seg_wxs_washu')

    def maf_uncompressed(file_dict, mirror_path, dice_path):
        # Tolerate pathogical case when file shouldn't be compressed, but is
        # FIXME: maf.process could handle uncompression itself, transparently,
        #        instead of needing to be be told from here (with extra code)
        compressed = mirror_path.endswith('.gz')
        maf.process(file_dict, mirror_path, dice_path, is_compressed=compressed)

    CONVERTERS = {
        'clinical' : gdac_clin.process,
        'copy' : gdac_copy.process,
        'maf': maf.process,                             # mutect, compressed
        'maf_uncompressed': maf_uncompressed,
        'segfile_snp6': gdac_seg.process_snp6,
        'seg_wxs_washu': seg_wxs,
        'tsv2idtsv' : gdac_tsv2idtsv.process,
        'unzip_tsv2idtsv': unzip_tsv2idtsv,
        'tsv2magetab': gdac_tsv2magetab.process,
        'usc_meth2magetab': usc_meth2magetab,
        'washu_meth2magetab': washu_meth2magetab,
        'unzip_tsv2magetab': unzip_tsv2magetab,
        'fpkm2magetab': fpkm2magetab,
        'unzip_fpkm2magetab': unzip_fpkm2magetab,
    }

    return CONVERTERS[converter_name]

def _parse_tags(tags_list):
    return frozenset('' if len(tags_list)==0 else tags_list)

def main():
    gdc_dice().execute()

if __name__ == "__main__":
    main()
