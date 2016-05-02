#! /usr/bin/env python
from __future__ import print_function
import gdc
import json
import csv


def build_translation_dict(translation_file):
    with open(translation_file) as tsvfile:
        reader = csv.DictReader(csv, delimiter='\t')
        for row in reader: 
            print(row)

    return {}



def metadata_to_key(file_dict):
    """Converts the file metadata in file_dict into a key in the TRANSLATION_DICT""" 

    data_type = file_dict.get("data_type", None)
    data_category = file_dict.get("data_category", None)
    experimental_strategy = file_dict.get("experimental_strategy", None)
    platform = file_dict.get("platform", None)
    tags = file_dict.get("tags", [])
    center_namespace = file_dict.get("center.namespace")

    return {
        "data_type" : data_type,
        "data_category": data_category,
        "experimental_strategy": experimental_strategy,
        "platform": platform,
        "tags": tags,
        "center_namespace", center_namespace
    }


def translate(annot_key):
    """Returns the annotation name and converter function for a given file"""
    if annot_key in TRANSLATION_DICT:
        return TRANSLATION_DICT[annot_key]
    pass

## Converts a key from metadata_to_key into an annotation name and dicing converter
##TODO: Build this table from a config file
TRANSLATION_DICT = {
    
    # 
    {
        "data_type" : data_type,
        "data_category": data_category,
        "experimental_strategy": experimental_strategy,
        "platform": platform,
        "tags": tags
    } : 

    

}

## Parsing tags out of file dict
def _relevant_tags(tags_dict):
    return None

#Converters
def hard_copy():
    pass

def clinical():
    pass

def maf():
    pass

def tsv2magetab():
    pass

def main():
    # For testing...
    # cats = gdc.data_categories("TCGA-UVM")
    # files = gdc.get_files("TCGA-UVM", "Gene expression")
    # print(json.dumps(files[:10], indent=2))

if __name__ == '__main__':
    main()

