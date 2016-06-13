#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

meta.py: Functions for working with gdc metadata

@author: Timothy DeFreitas
@date:  2016_05_26
'''

# }}}
from __future__ import print_function

import os
import json

def append_metadata(file_dicts, metafile):
    ''' Merge the list of filedicts with any filedicts in metafile,
        Then overwrite the metafile with the combined contents'''
    dicts = []
    if os.path.isfile(metafile):
        with open(metafile) as f:
            dicts.extend(json.load(f))

    # Add file_dicts and overwrite
    dicts.extend(file_dicts)
    with open(metafile, 'w') as out:
        json.dump(dicts, out, indent=2)


def latest_metadata(stamp_dir):
    metadata_files = [f for f in os.listdir(stamp_dir)
                      if os.path.isfile(os.path.join(stamp_dir, f))
                      and "metadata" in f]
    # Get the chronologically latest one, in case there is more than one,
    # Should just be a sanity check
    latest = sorted(metadata_files)[-1]
    latest = os.path.join(stamp_dir, latest)
    with open(latest) as jsonf:
        return json.load(jsonf)


def get_timestamp(proj_dir, date_prefix=None):
    '''Get the timestamp of the last project mirror run'''
    latest_tstamp = None

    timestamps = [d for d in os.listdir(proj_dir)
                      if os.path.isdir(os.path.join(proj_dir, d))]
    if date_prefix is not None:
        timestamps = filter(lambda d: d.startswith(date_prefix), timestamps)

    return sorted(timestamps)[-1]


def md5_matches(file_dict, md5file):
    """Returns true if the one-line md5file matches the md5 data in file_dict"""
    if not os.path.isfile(md5file):
        return False
    filename = file_basename(file_dict)
    md5_basename = os.path.basename(md5file)
    if filename + ".md5" != md5_basename: return False

    with open(md5file) as md5f:
        line = md5f.next()
        md5value, fname = line.strip().split('  ')
        return fname == filename and md5value == file_dict['md5sum']

def file_basename(file_dict):
    # Since GDC doesn't have unique filenames, prepend uuid
    name = file_dict['file_name']
    uuid = file_dict['file_id']
    return uuid + "." + name

def mirror_path(root, file_dict):
    '''Return the file location relative to a root folder.

    This location is equivalent to:
    <root>/<category>/<type>/<uuid>.<filename>'''
    category = file_dict['data_category']
    data_type = file_dict['data_type']
    name = file_basename(file_dict)
    return os.path.join(root, category, data_type, name).replace(' ', '_')

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


def get_entity_type(file_dict):
    '''Parse the dicer metadata for this file.

    Returns the Entity ID and entity type.'''
    if file_dict['data_category'] in ['Clinical', 'Biospecimen']:
        proj_id = project_id(file_dict)
        #TODO: Make this more generic
        if proj_id == 'TCGA-LAML':
            entity_type = "Primary Blood Derived Cancer - Peripheral Blood"
        elif proj_id == 'TCGA-SKCM':
            entity_type = 'Metastatic'
        else:
            entity_type = 'Primary Tumor'
    else:
        entity_type = sample_type(file_dict)

    return entity_type

def _check_dict_array_size(d, name, size=1):
    assert len(d[name]) == size, 'Array "%s" should be length %d' % (name, size)
