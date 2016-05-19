#! /usr/bin/env python
from __future__ import print_function
import gdc
import json
import csv
import os
import sys
from gdac_lib import converters
from gdac_lib.Constants import GDAC_BIN_DIR

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

    mirror_path = os.path.join(raw_root, file_dict['data_category'], file_dict['data_type'])

    #print("Downloading file {0} to {1}".format(file_dict['file_name'], mirror_path))
    if not dry_run:
        gdc.get_file(file_dict['file_id'],
                     os.path.join(mirror_path, file_dict['file_name']))

    dice_path = os.path.join(diced_root, annot)
    #print("Dicing file {0} to {1}".format(file_dict['file_name'], dice_path))

    if not dry_run:
        convert(file_dict, mirror_path, dice_path) #actually do it

    return annot

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
        
def _check_dict_array_size(d, name, size=1):
    assert len(d[name]) == size, 'Array "%s" should be length %d' % (name, size)
    
#Converters
def copy(file_dict, mirror_path, dice_path):
    print("Dicing with 'copy'")
    pass

def clinical(file_dict, mirror_path, dice_path):
    print("Dicing with 'clinical'")
    infile = os.path.join(mirror_path, file_dict['file_name'])
    extension = 'clin'
    tcga_id = patient_id(file_dict)
    converters.clinical.process(infile, extension, {tcga_id: tcga_id},
                                dice_path, GDAC_BIN_DIR)

def maf(file_dict, mirror_path, dice_path):
    pass

def magetab_data_matrix(file_dict, mirror_path, dice_path):
    pass

def seg_broad(file_dict, mirror_path, dice_path):
    infile = os.path.join(mirror_path, file_dict['file_name'])
    extension = 'seg'
    hyb_id = file_dict['file_name'].split('.',1)[0]
    tcga_id = aliquot_id(file_dict)
    converters.seg.process(infile, extension, hyb_id, tcga_id, dice_path,
                           'seg_broad')

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
    RAW_ROOT="/xchip/gdac_data/gdc_mirror/TCGA-UVM"
    DICED_ROOT="/xchip/gdac_data/gdc_diced/TCGA-UVM"
    # For testing...
    # cats = gdc.data_categories("TCGA-UVM")
    files = gdc.get_files("TCGA-UVM", "Gene expression")
    # print(json.dumps(files[:10], indent=2))
    d = build_translation_dict("GDC_translation_table.tsv")
    for f in files:
        #print(json.dumps(f, indent=2))
        a = download_and_dice(f, d, RAW_ROOT, DICED_ROOT)
        if a == 'UNRECOGNIZED':
            print(json.dumps(f, indent=2))

if __name__ == '__main__':
    main()

