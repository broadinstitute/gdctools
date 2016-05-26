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
import logging
import json
import csv
import os
import sys
from pkg_resources import resource_filename #@UnresolvedImport

from gdac_lib.converters import seg as gdac_seg
from gdac_lib.converters import clinical as gdac_clin
from gdac_lib.Constants import GDAC_BIN_DIR
from gdac_lib.utilities.CommonFunctions import timetuple2stamp
from gdac_lib.utilities.ioUtilities import safeMakeDirs

from GDCtool import GDCtool
#import translator

class gdc_dicer(GDCtool):

    def __init__(self):
        super(gdc_dicer, self).__init__(version="0.2.0")
        cli = self.cli

        desc =  'Dice data from a Genomic Data Commons (GDC) mirror'
        cli.description = desc

        cli.add_argument('-m', '--mirror-directory',
                         help='Root folder of mirrored GDC data')
        cli.add_argument('-d', '--dice-directory', 
                         help='Root of diced data tree')
        cli.add_argument('--dry-run', action='store_true', 
                         help="Show expected operations, but don't perform dicing")
        cli.add_argument('-g', '--programs', nargs='+', metavar='program',
                         help='Mirror data from these cancer programs')
        cli.add_argument('-p', '--projects', nargs='+', metavar='project',
                         help='Mirror data from these projects')
        cli.add_argument('datestamp',
                         help='Dice using metadata from a particular date.'\
                         'If omitted, the latest version will be used')


    def dice(self):
        mirror_root = self.options.mirror_directory
        diced_root = self.options.dice_directory
        trans_dict = build_translation_dict(resource_filename(__name__,
                                                       "Harmonized_GDC_translation_table_FH.tsv"))

        #Iterable of programs, either user specified or discovered from folder names in the diced root
        if self.options.programs is not None:
            programs = self.options.programs
        else:
            programs = immediate_subdirs(mirror_root)

        for program in programs:
            diced_prog_root = os.path.join(diced_root, program)
            mirror_prog_root = os.path.join(mirror_root, program)


            if self.options.projects is not None:
                projects = self.options.projects
            else:
                projects = immediate_subdirs(mirror_prog_root)

            for project in projects:
                raw_project_root = os.path.join(mirror_prog_root, project)
                diced_project_root = os.path.join(diced_prog_root, project)
                logging.info("Dicing " + project + " to " + diced_project_root)
                timestamp = get_mirror_timestamp(raw_project_root, self.options.datestamp)
                logging.info("Timestamp: " + timestamp)
                metadata = get_metadata(raw_project_root, self.options.datestamp)

                for files in metadata:
                    if len(files) > 0:
                        for f in files:
                            dice_one(f, trans_dict, raw_project_root, diced_project_root,
                                     timestamp, dry_run=self.options.dry_run)


    def execute(self):
        super(gdc_dicer, self).execute()
        opts = self.options
        logging.basicConfig(format='%(asctime)s[%(levelname)s]: %(message)s',
                            level=logging.INFO)
        self.dice()

def build_translation_dict(translation_file):
    """Builds a translation dictionary from a translation table.

    First column of the translation_file is the Annotation name, 
    remaining columns are signatures in the file metadata that indicate a file is of this annotation type.
    """

    with open(translation_file, 'rU') as tsvfile:
        reader = csv.DictReader(tsvfile, delimiter='\t')
        d = dict()

        #Duplicate detection
        dupes = False
        for row in reader:
            annot = row.pop("Firehose_annotation")
            converter_name = row.pop("converter")

            ##Parse list fields into frozensets
            row['tags'] = frozenset(row['tags'].split(',') if row['tags'] != '' else [])

            #Only add complete rows
            #Give a warning if overwriting an existing tag, and don't add the new one
            key = frozenset(row.items())
            if key not in d:
                d[key] = (annot, converter(converter_name))
            else:
                dupes = True
    if dupes: print("WARNING: duplicate annotation definitions detected")
    return d

def _load_json_metadata(json_file):
    with open(json_file, 'r') as metadata:
        return json.load(metadata)
        
def get_metadata(raw_project_root, datestamp=timetuple2stamp().split('__')[0],
                 loader=_load_json_metadata):
    '''Load file metadata object(s) for given project. Default is current
    date.'''
    raw_project_root = raw_project_root.rstrip(os.path.sep)
    project = os.path.basename(raw_project_root)
    
    for dirpath, dirnames, filenames in os.walk(raw_project_root, topdown=True):
        # Only recurse down to meta subdirectories
        if os.path.basename(os.path.dirname(dirpath)) == project:
            for n, subdir in enumerate(dirnames):
                if subdir != 'meta': del dirnames[n]
        # Take the most recent version of the given datestamp
        if os.path.basename(dirpath) == 'meta':
            meta_files = sorted(filename for filename in filenames if \
                                datestamp in filename)
            if len(meta_files) > 0:
                yield loader(os.path.join(dirpath, meta_files[-1]))

def dice_one(file_dict, translation_dict, raw_root, diced_root, timestamp, dry_run=True):
    """Dice a single file from the GDC.

    Diced data will be placed in /<diced_root>/<annotation>/. If dry_run is
    true, a debug message will be displayed instead of performing the actual
    dicing operation.
    """

    mirror_path = os.path.join(raw_root, file_dict['data_category'],
                               file_dict['data_type'],
                               file_dict['file_name']).replace(' ', '_')

    if os.path.isfile(mirror_path):    
        ##Get the right annotation and converter for this file
        annot, convert = get_annotation_converter(file_dict, translation_dict)
        if annot != 'UNRECOGNIZED':
            dice_path = os.path.join(diced_root, annot)
            logging.info("Dicing file {0} to {1}".format(mirror_path, dice_path))
            dice_meta_path = os.path.join(dice_path, "meta")
        if not dry_run:
            diced_files_dict = convert(file_dict, mirror_path, dice_path) #actually do it
            write_diced_metadata(file_dict, dice_meta_path, timestamp, diced_files_dict)
        else:
            logging.warn('Unrecognized data:\n%s' % json.dumps(file_dict,
                                                               indent=2))

def get_annotation_converter(file_dict, translation_dict):
    k = metadata_to_key(file_dict)
    if k in translation_dict:
        return translation_dict[k]
    else:
        #TODO: Gracefully handle this instead of creating a new annotation type
        return "UNRECOGNIZED", None #TODO: handle this better

def metadata_to_key(file_dict):
    """Converts the file metadata in file_dict into a key in the TRANSLATION_DICT""" 

    data_type = file_dict.get("data_type", '')
    data_category = file_dict.get("data_category", '')
    experimental_strategy = file_dict.get("experimental_strategy", '')
    platform = file_dict.get("platform", '')
    tags = _parse_tags(file_dict.get("tags",[]))
    center_namespace = file_dict['center']['namespace'] if 'center' in file_dict else ''

    return frozenset({
        "data_type" : data_type,
        "data_category": data_category,
        "experimental_strategy": experimental_strategy,
        "platform": platform,
        "tags": tags,
        "center_namespace": center_namespace
    }.items())

def write_diced_metadata(file_dict, dice_meta_path, timestamp, diced_files_dict):
    if not os.path.isdir(dice_meta_path):
        os.makedirs(dice_meta_path)

    meta_filename = os.path.join(dice_meta_path, ".".join(["dicedMetadata", timestamp, "tsv"]))
    if os.path.isfile(meta_filename):
        #File exists, open in append mode
        metafile = open(meta_filename, 'a')
    else:
        #File doesn't exist, create and add header
        metafile = open(meta_filename, 'w')
        metafile.write('filename\tentity_id\tentity_type\n')
        
    entity_type = get_entity_type(file_dict)

    for entity_id in diced_files_dict:
        filename = diced_files_dict[entity_id]
        metafile.write("\t".join([filename, entity_id, entity_type]) + "\n")

    metafile.close()

def get_mirror_timestamp(proj_root, datestamp):
    """Get the timestamp of the last mirror run on the given date.

    Does this by iterating over the meta folders and grabs the latest value.

    TODO: Move the meta iterator to a util file
    """
    raw_project_root = proj_root.rstrip(os.path.sep)
    project = os.path.basename(raw_project_root)

    latest_tstamp = None

    for dirpath, dirnames, filenames in os.walk(raw_project_root, topdown=True):
        # Only recurse down to meta subdirectories
        if os.path.basename(os.path.dirname(dirpath)) == project:
            for n, subdir in enumerate(dirnames):
                if subdir != 'meta': del dirnames[n]
        # Take the most recent version of the given datestamp
        if os.path.basename(dirpath) == 'meta':
            meta_files = sorted(filename for filename in filenames if \
                                datestamp in filename)
            if len(meta_files) > 0 :
                # meta filenames = "metadata.<timestamp>.json"
                timestamp = meta_files[-1].split(".")[1]
                if latest_tstamp is None or timestamp > latest_tstamp:
                    latest_tstamp = timestamp
    return latest_tstamp

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
        'tsv2magetab': tsv2magetab 
    }

    return CONVERTERS[converter_name]

#Converters
def copy(file_dict, mirror_path, dice_path):
    print("Dicing with 'copy'")
    pass

def clinical(file_dict, mirror_path, dice_path):
#     print("Dicing with 'clinical'")
    infile = mirror_path
    extension = 'clin'
    tcga_id = patient_id(file_dict)
    return {tcga_id: gdac_clin.process(infile, extension, {tcga_id: tcga_id},
                                       dice_path, GDAC_BIN_DIR)}

def maf(file_dict, mirror_path, dice_path):
    pass

def magetab_data_matrix(file_dict, mirror_path, dice_path):
    pass

def seg_broad(file_dict, mirror_path, dice_path):
    infile = mirror_path
    extension = 'seg'
    hyb_id = file_dict['file_name'].split('.',1)[0]
    tcga_id = aliquot_id(file_dict)
    return {patient_id(file_dict):
            gdac_seg.process(infile, extension, hyb_id, tcga_id, dice_path,
                             'seg_broad')}

def seg_harvard(file_dict, mirror_path, dice_path):
    pass
def seg_harvardlowpass(file_dict, mirror_path, dice_path):
    pass
def seg_mskcc2(file_dict, mirror_path, dice_path):
    pass
def tsv2idtsv(file_dict, mirror_path, dice_path):
    pass
def tsv2magetab(file_dict, mirror_path, dice_path):
    pass

def _parse_tags(tags_list):
    return frozenset('' if len(tags_list)==0 else tags_list)

def aliquot_id(file_dict):
    '''Return the aliquot associated with the file. Raise an exception if more
    than one exists.'''
    try:
        _check_dict_array_size(file_dict, 'cases')
        _check_dict_array_size(file_dict['cases'][0], 'samples')
        _check_dict_array_size(file_dict['cases'][0]['samples'][0], 'portions')
        _check_dict_array_size(file_dict['cases'][0]['samples'][0]['portions'][0],
                               'analytes')
        _check_dict_array_size(file_dict['cases'][0]['samples'][0]['portions'][0]['analytes'][0],
                               'aliquots')
    except:
        print(json.dumps(file_dict['cases'], indent=2), file=sys.stderr)
        raise
    
    return file_dict['cases'][0]['samples'][0]['portions'][0]['analytes'][0]['aliquots'][0]['submitter_id']

def patient_id(file_dict):
    '''Return the patient_id associated with the file. Raise an exception if
    more than one exists.'''
    try:
        _check_dict_array_size(file_dict, 'cases')
    except:
        print(json.dumps(file_dict['cases'], indent=2), file=sys.stderr)
        raise
    
    return file_dict['cases'][0]['submitter_id']

def sample_type(file_dict):
    '''Return the sample_type associated with the file. Raise an exception if
    more than one exists.'''
    try:
        _check_dict_array_size(file_dict, 'cases')
        _check_dict_array_size(file_dict['cases'][0], 'samples')
    except:
        print(json.dumps(file_dict['cases'], indent=2), file=sys.stderr)
        raise
    
    return file_dict['cases'][0]['samples'][0]["sample_type"]

def project_id(file_dict):
    '''Return the project_id associated with the file. Raise an exception if
    more than one case exists.'''
    try:
        _check_dict_array_size(file_dict, 'cases')
    except:
        print(json.dumps(file_dict['cases'], indent=2), file=sys.stderr)
        raise
    return file_dict['cases'][0]['project']['project_id']
        
def _check_dict_array_size(d, name, size=1):
    assert len(d[name]) == size, 'Array "%s" should be length %d' % (name, size)
    

def immediate_subdirs(path):
    return [d for d in os.listdir(path) 
            if os.path.isdir(os.path.join(path, d))]

if __name__ == "__main__":
    gdc_dicer().execute()