#! /usr/bin/env python
from __future__ import print_function
import gdc
import json
import csv


def build_translation_dict(translation_file):
    """Builds a translation dictionary from a translation table.

    First column of the translation_file is the Annotation name, 
    remaining columns are signatures in the file metadata that indicate a file is of this annotation type.
    """

    with open(translation_file, 'rU') as tsvfile:
        reader = csv.DictReader(tsvfile, delimiter='\t')
        d = dict()

        undef_rows = 0
        for row in reader:
            annot = row.pop("Firehose_annotation")
            converter_name = row.pop("converter")

            #Only add complete rows
            if all([v!='' for v in row.values()]):
                key = frozenset(row.items())
                d[key] = (annot, converter(converter_name))
            else:
                undef_rows += 1
    print("{0} annotations loaded, {1} ignored".format(len(d), undef_rows))
    return d


def metadata_to_key(file_dict):
    """Converts the file metadata in file_dict into a key in the TRANSLATION_DICT""" 

    data_type = file_dict.get("data_type", '')
    data_category = file_dict.get("data_category", '')
    experimental_strategy = file_dict.get("experimental_strategy", '')
    platform = file_dict.get("platform", '')
    tags = _parse_tags(file_dict.get("tags",[]))
    center_namespace = file_dict.get("center.namespace", '')


    return frozenset({
        "data_type" : data_type,
        "data_category": data_category,
        "experimental_strategy": experimental_strategy,
        "platform": platform,
        "tags": tags,
        "center_namespace": center_namespace
    }.items())

def get_annotation(file_dict, translation_dict):
    k = metadata_to_key(file_dict)
    if k in translation_dict:
        return translation_dict[k]
    else:
        #TODO: Gracefully handle this instead of creating a new annotation type
        return "UNRECOGNIZED_FILE_UUID=" + file_dict['file_id']

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


## Parsing tags out of file dict
def _parse_tags(tags_list):
    return ','.join(sorted(tags_list)) # Sort to guarantee accurate matching

#Converters
def copy():
    pass

def clinical():
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
    # For testing...
    # cats = gdc.data_categories("TCGA-UVM")
    # files = gdc.get_files("TCGA-UVM", "Gene expression")
    # print(json.dumps(files[:10], indent=2))
    d = build_translation_dict("GDC_translation_table.tsv")
    #print(d)

if __name__ == '__main__':
    main()

