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

def metadata_filenames(root_dir, datestamp=None):
    '''Return an generator listing the latest metadata filenames.

    Returns absolute paths. If no datestamp is provided yields the latest available.
    root_dir: root of a project mirror or dicing
    '''
    root_dir = root_dir.rstrip(os.path.sep)
    project = os.path.basename(root_dir)


    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True):
        # Only recurse down to meta subdirectories
        if os.path.basename(os.path.dirname(dirpath)) == project:
            for n, subdir in enumerate(dirnames):
                if subdir != 'meta': del dirnames[n]
        # Take the most recent version of the given datestamp
        if os.path.basename(dirpath) == 'meta':
            meta_files = sorted(filename for filename in filenames if \
                                datestamp is None or datestamp in filename)
            if len(meta_files) > 0 :
                yield os.path.join(dirpath, meta_files[-1])

def get_timestamp(root_dir, datestamp=None):
    '''Get the timestamp of the last mirror run on the given date. '''
    latest_tstamp = None

    for metafname in metadata_filenames(root_dir, datestamp):
        tstamp = os.path.basename(metafname).split('.')[1]
        if latest_tstamp is None or tstamp > latest_tstamp:
            latest_tstamp = tstamp

    return latest_tstamp

def iter_mirror_file_dicts(root_dir, datestamp=None):
    '''Iterate over json metadata in a mirrored project'''
    for metafname in metadata_filenames(root_dir, datestamp):
        with open(metafname) as jsonf:
            yield json.load(jsonf)

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
