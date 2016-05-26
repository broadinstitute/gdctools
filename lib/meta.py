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