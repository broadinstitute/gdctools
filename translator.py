#! /usr/bin/env python
from __future__ import print_function
import gdc
import json
import csv
import os


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
        pass #Actually do it

    dice_path = os.path.join(diced_root, annot)
    #print("Dicing file {0} to {1}".format(file_dict['file_name'], dice_path))

    if not dry_run:
        convert() #actually do it

    return annot

## Parsing tags out of file dict
def _parse_tags(tags_list):
    return frozenset('' if len(tags_list)==0 else tags_list)

#Converters
def copy():
    print("Dicing with 'copy'")
    pass

def clinical():
    print("Dicing with 'clinical'")
    pass

def maf():
    pass

def magetab_data_matrix():
    pass

def seg_broad():
    pass
def seg_harvard():
    pass
def seg_harvardlowpass():
    pass
def seg_mskcc2():
    pass
def tsv2idtsv():
    pass
def tsv2magetab():
    pass


def main():
    RAW_ROOT="./TCGA-UVM/raw/"
    DICED_ROOT="./TCGA-UVM/diced/"
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

