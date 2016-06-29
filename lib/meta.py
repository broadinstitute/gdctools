
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
import sys
from lib.constants import TIMESTAMP_REGEX

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


def latest_timestamp(proj_dir, date_prefix=None, ignore=None):
    '''Get the timestamp of the last mirror or dicer run for a project.

    Will only return a date matching date_prefix, but can ignore an explicit
    stamp. Returns none if no timestamp matches
    '''
    latest_tstamp = None
    meta_dir = os.path.join(proj_dir, "metadata")

    timestamps = [d for d in os.listdir(meta_dir)
                  if TIMESTAMP_REGEX.match(d) is not None
                  and os.path.isdir(os.path.join(meta_dir, d))
                  and d != ignore]
    if date_prefix is not None:
        timestamps = filter(lambda d: d.startswith(date_prefix), timestamps)

    if len(timestamps) == 0:
        return None
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
    '''Generate a filename based on the file dict.

    Each file_dict reports a file_name, into which the uuid is inserted.
    The function attempts to insert the uuid between the human-readable name
    and the natural file extension.

    E.g:
        nationwidechildrens.org_biospecimen.TCGA-NA-A4QY.xml
        becomes
        nationwidechildrens.org_biospecimen.TCGA-NA-A4QY.<uuid>.xml
        &
        isoforms.quantification.txt
        becomes
        isoforms.quantification.<uuid>.txt


    This is done by specifying a list of known extension strings and finding
    the first extension from left to right, splitting on periods (.)
    in order to preserve compound extensions such as '.tar.gz'

    If no correct file basename can be found, raises ValueError and dumps
    the offending file_dict.
    '''
    EXTENSIONS = {'xml', 'txt', 'tar', 'gz', 'md5'}
    name = file_dict['file_name']
    uuid = file_dict['file_id']

    namelist = name.split('.')
    try:
        for i in range(len(namelist) + 1):
            if namelist[i] in EXTENSIONS:
                break
    except IndexError:
        # We went too far, must not have found an extension
        raise ValueError("No valid extension found for file: " + name)

    # i is now the index of the first extension, insert uuid right before
    namelist.insert(i, uuid)
    return ".".join(namelist)

def file_id(file_dict):
    '''Get the file uuid.'''
    return file_dict['file_id']

def mirror_path(proj_root, file_dict):
    '''Return the file location relative to a root folder.

    This location is equivalent to:
    <root>/<category>/<type>/<uuid>.<filename>'''
    category = file_dict['data_category']
    data_type = file_dict['data_type']
    name = file_basename(file_dict)
    return os.path.join(proj_root, category, data_type, name).replace(' ', '_')


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


def case_id(file_dict):
    '''Return the case_id associated with the file. Raise an exception if
    more than one exists.'''
    try:
        _check_dict_array_size(file_dict, 'cases')
    except:
        print(json.dumps(file_dict['cases'], indent=2), file=sys.stderr)
        raise

    return file_dict['cases'][0]['submitter_id']


def sample_type(file_dict):
    '''Return the sample type associated with the file.'''
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

def tcga_id(file_dict):
    '''Returns the expected tcga_id for the file.

    The exact field depends on the data type, for clinical this will be a
    patient id, for CNV this will be a sample id.
    '''
    if file_dict['data_category'] in ['Biospecimen', 'Clinical']:
        return case_id(file_dict)
    else:
        try:
            return aliquot_id(file_dict)
        except:
            print(json.dumps(file_dict, indent=2))
            raise

def has_sample(file_dict):
    '''Returns true if there is exactly one sample associated with this file.'''

    # EAFP: accessing the first sample only succeeds if there is no
    # IndexError, KeyError, or AssertionError
    try:
        _check_dict_array_size(file_dict['cases'][0], 'samples')
        return True
    except (KeyError, IndexError, AssertionError):
        return False

def dice_extension(file_dict):
    '''Get the expected diced file extension for this file.'''
    ext = "txt"
    dtype = file_dict['data_type']

    if dtype in ['Biospecimen', 'Clinical']:
        ext = "clin.txt"
    elif dtype in ['Copy Number Variation']:
        ext = "seg.txt"
    elif dtype in ['Transcriptome Profiling']:
        ext = "data.txt"
    return ext

#TODO: Configurable?
def main_tumor_sample_type(proj_id):
    '''The sample type used by most analyses in a project.
    'Primary Tumor' for everything except LAML and SKCM.
    '''
    if proj_id == 'TCGA-LAML':
        stype = "Primary Blood Derived Cancer - Peripheral Blood"
    elif proj_id == 'TCGA-SKCM':
        stype = 'Metastatic'
    else:
        stype = 'Primary Tumor'
    return stype


#TODO: This should come from a config file
# Currently copied from https://tcga-data.nci.nih.gov/datareports/codeTablesReport.htm?codeTable=Sample%20Type
def tumor_code(tumor_type):
    lookup = {
        "Additional - New Primary" : ('05', 'TAP'),
        "Additional Metastatic" : ('07', 'TAM'),
        "Blood Derived Normal" : ('10', 'NB'),
        "Bone Marrow Normal" : ('14', 'NBM'),
        "Buccal Cell Normal" : ('12', 'NBC'),
        "Cell Line Derived Xenograft Tissue" : ('61', 'XCL'),
        "Cell Lines" : ('50', 'CELL'),
        "Control Analyte" : ('20', 'CELLC'),
        "EBV Immortalized Normal" : ('13', 'NEBV'),
        "Human Tumor Original Cells" : ('08', 'THOC'),
        "Metastatic" : ('06', 'TM'),
        "Primary Blood Derived Cancer - Bone Marrow" : ('09', 'TBM'),
        "Primary Blood Derived Cancer - Peripheral Blood" : ('03', 'TB'),
        "Primary Xenograft Tissue" : ('60', 'XP'),
        "Primary Tumor" : ('01', 'TP'),
        "Recurrent Blood Derived Cancer - Bone Marrow" : ('04', 'TRBM'),
        "Recurrent Blood Derived Cancer - Peripheral Blood" : ('40', 'TRB'),
        "Recurrent Solid Tumor" : ('02', 'TR'),
        "Solid Tissue Normal" : ('11', 'NT'),
    }
    return lookup.get(tumor_type, None)


# def sample_counts(metadata):
#     '''Create a dictionary of sample counts for each type.
#
#     E.g.: { "TP" : 100, "TR" : 50, "NT" : 50 }
#     '''
#     counts = dict()
#     for file_d in metadata:
#         _, code = tumor_code(sample_type(file_d))
#         counts[code] = counts.get(code, 0) + 1
#     return counts


def _check_dict_array_size(d, name, size=1):
    assert len(d[name]) == size, 'Array "%s" should be length %d' % (name, size)
