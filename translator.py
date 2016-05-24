#! /usr/bin/env python
from __future__ import print_function
import logging
import gdc
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

def get_annotation_converter(file_dict, translation_dict):
    k = metadata_to_key(file_dict)
    if k in translation_dict:
        return translation_dict[k]
    else:
        #TODO: Gracefully handle this instead of creating a new annotation type
        return "UNRECOGNIZED", None #TODO: handle this better

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

def download_and_dice(file_dict, translation_dict, raw_root, diced_root, dry_run=True):
    """Dice a single file from the GDC.

    Raw file will be downloaded into /<raw_root>/<data_category>/<data_type>, and the diced data 
    will be placed in /<diced_root>/<annotation>/. If dry_run is true, a debug message will be displayed 
    instead of performing the actual curl call & dicing operation.
    """
    ##Get the right annotation and converter for this file
    annot, convert = get_annotation_converter(file_dict, translation_dict)

    mirror_path = os.path.join(raw_root, file_dict['data_category'],
                               file_dict['data_type']).replace(' ', '_')

    #print("Downloading file {0} to {1}".format(file_dict['file_name'], mirror_path))
    if not dry_run:
        mirror_file = os.path.join(mirror_path, file_dict['file_name'])
        gdc.get_file(file_dict['file_id'], mirror_file)

    dice_path = os.path.join(diced_root, annot)
    #print("Dicing file {0} to {1}".format(file_dict['file_name'], dice_path))

    if not dry_run:
        convert(file_dict, mirror_path, dice_path) #actually do it

    return annot

def dice(file_dict, translation_dict, raw_root, diced_root, timestamp, dry_run=True):
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

def get_entity_type(file_dict):
    '''Parse the dicer metadata for this file.

    Returns the Entity ID and entity type.'''
    entity_type = "NOTIMPLEMENTED"

    return entity_type

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
    
def _read_md5file(md5file):
    with open(md5file, 'r') as md5fd:
        for line in md5fd:
            if len(line.strip()) > 1:
                return line.split(' ', 1)[0]

## Parsing tags out of file dict
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


def main():
    logging.basicConfig(format='%(asctime)s[%(levelname)s]: %(message)s',
                        level=logging.INFO)
    RAW_ROOT="/broad/hptmp/gdac/fh2gdc/gdctools/gdc_mirror_root/TCGA"
    DICED_ROOT="/broad/hptmp/gdac/fh2gdc/gdctools/gdc_diced"
    # For testing...
    # cats = gdc.data_categories("TCGA-UVM")
    trans_dict = build_translation_dict(resource_filename(__name__,
                                                          "Harmonized_GDC_translation_table_FH.tsv"))
    timestamp = timetuple2stamp()
    for project in gdc.get_projects('TCGA'):
        raw_project_root = os.path.join(RAW_ROOT, project)
        diced_project_root = os.path.join(DICED_ROOT, project)
        for files in get_metadata(raw_project_root, '2016_05_24'):
#         for category in gdc.get_data_categories(project):
#             files = gdc.get_files(project, category)
            if len(files) > 0:
#                 metadata_dir = os.path.join(raw_project_root, category,
#                                             'meta')
#                 safeMakeDirs(metadata_dir)
#                 with open(os.path.join(metadata_dir, timestamp + '.json'),
#                           'w') as meta_fd:
#                     print(json.dumps(files, indent=2), file=meta_fd)
                # print(json.dumps(files[:10], indent=2))
                for f in files:
                    #print(json.dumps(f, indent=2))
#                     a = download_and_dice(f, trans_dict, raw_project_root,
#                                           diced_project_root)
                    dice(f, trans_dict, raw_project_root, diced_project_root,
		         timestamp, dry_run=False)
#                     if a == 'UNRECOGNIZED':
#                         print(json.dumps(f, indent=2))

if __name__ == '__main__':
    main()

