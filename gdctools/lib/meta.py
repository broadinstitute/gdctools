#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

meta.py: Functions for working with gdc metadata

@author: Timothy DeFreitas, Michael S. Noble
@date:  2016_05_26
'''

# }}}
import os
import json
import logging
import csv
from gdctools.lib.common import DATESTAMP_REGEX, ANNOT_TO_DATATYPE
from collections import namedtuple, defaultdict

# Lightweight class to enable handling of aggregate projects
Case = namedtuple('Case', ['proj_id', 'case_data'])

def extract_case_data(diced_metadata_file):
    '''Create a case-based lookup of available data types'''
    # Use a case-based dictionary to count each data type on a case/sample basis
    # cases[<case_id>][<sample_type>] = set([REPORT_DATA_TYPE, ...])
    cases = dict()
    case_proj_map = dict()
    cases_with_clinical = set()
    cases_with_biospecimen = set()

    with open(diced_metadata_file, 'r') as dmf:
        reader = csv.DictReader(dmf, delimiter='\t')
        # Loop through counting non-case-level annotations
        for row in reader:
            annot = row['annotation']
            case_id = row['case_id']
            proj_id = row['file_name'].split(os.path.sep)[-3]
            report_dtype = ANNOT_TO_DATATYPE[annot]

            if case_id not in case_proj_map:
                case_proj_map[case_id] = proj_id

            if report_dtype == 'BCR':
                cases_with_biospecimen.add(case_id)
            elif report_dtype == 'Clinical':
                cases_with_clinical.add(case_id)
            else:
                # FIXME: Temporary Hack due to GDC bug on a LUAD case
                if row['sample_type'] == "FFPE Scrolls":
                    logging.warning("SKIPPING BAD FFPE SCROLLS SAMPLE TYPE")
                    continue
                _, sample_type = tumor_code(row['sample_type'])
                # Filter out ffpe samples into a separate sample_type
                if row['is_ffpe'] == 'True':
                    sample_type = 'FFPE'
                case = cases.get(case_id, Case(proj_id, defaultdict(set)))
                case.case_data[sample_type].add(report_dtype)
                cases[case_id] = case

    # Now go back through and add BCR & Clinical to all sample_types, but first,
    # we must insert cases in for samples who only have clinical data
    possible_cases = cases_with_clinical | cases_with_biospecimen
    for c in possible_cases:
        proj_id = case_proj_map[c]
        main_type = tumor_code(main_tumor_sample_type(proj_id)).symbol
        if c not in cases:
            # Have to create a new entry with the default sample type
            cases[c] = Case(proj_id, {main_type : set()})
        elif main_type not in cases[c].case_data:
            # Each sample must have an entry for the main tumor type
            cases[c].case_data[main_type] = set()

    for c in cases:
        for st in cases[c].case_data:
            if c in cases_with_clinical:
                cases[c].case_data[st].add('Clinical')
            if c in cases_with_biospecimen:
                cases[c].case_data[st].add('BCR')
    return cases

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

def files_diff(proj_root, new_files, old_files, strict=True):
    '''Returns the file dicts in new_files that aren't in old_files.
    Also checks that the file is present on disk.'''
    old_uuids = {fd['file_id'] for fd in old_files
                if os.path.isfile(mirror_path(proj_root, fd, strict))}
    new_dicts = [fd for fd in new_files if fd['file_id'] not in old_uuids]
    return new_dicts

def latest_datestamp(proj_dir, date_prefix=None, ignore=None):
    '''Get the timestamp of the last mirror or dicer run for a project.

    Will only return a date matching date_prefix, but can ignore an explicit
    stamp. Returns none if no timestamp matches
    '''
    meta_dir = os.path.join(proj_dir, "metadata")
    if not os.path.isdir(meta_dir):
        # new mirror, no existing timestamps
        return None
    timestamps = [d for d in os.listdir(meta_dir)
                  if DATESTAMP_REGEX.match(d) is not None
                  and os.path.isdir(os.path.join(meta_dir, d))
                  and d != ignore]
    if date_prefix is not None:
        timestamps = filter(lambda d: d.startswith(date_prefix), timestamps)

    if len(timestamps) == 0:
        return None
    return sorted(timestamps)[-1]

def latest_prog_timestamp(prog_dir, date_prefix=None, ignore=None):
    project_dirs = [os.path.join(prog_dir, d) for d in os.listdir(prog_dir)
                    if os.path.isdir(os.path.join(prog_dir, d))]
    proj_timestamps = [latest_datestamp(proj_dir, date_prefix, ignore)
                       for proj_dir in project_dirs]
    # Filter out None's
    proj_timestamps = [t for t in proj_timestamps if t is not None]

    # No latest timestamp
    if len(proj_timestamps) == 0:
        return None
    else:
        return sorted(proj_timestamps)[-1]

def md5_matches(file_dict, md5file, strict=True):
    """Returns true if the one-line md5file matches the md5 data in file_dict"""
    if not os.path.isfile(md5file):
        return False
    filename = file_basename(file_dict, strict)
    md5_basename = os.path.basename(md5file)
    if filename + ".md5" != md5_basename: return False

    with open(md5file) as md5f:
        line = next(md5f)
        md5value, fname = line.strip().split('  ')
        return fname == filename and md5value == file_dict['md5sum']

_SUPPORTED_FILE_TYPES = {'xml', 'txt', 'tar', 'gz', 'md5', 'xlsx', 'xls'}

def file_basename(file_dict, strict=True):
    '''Generate a filename based on the file dict.

    Each file_dict reports a file_name, into which the uuid is inserted.
    The function attempts to insert the uuid between the human-readable name
    and the natural file extension.

    E.g:
        nationwidechildrens.org_biospecimen.TCGA-NA-A4QY.xml
    becomes
        nationwidechildrens.org_biospecimen.TCGA-NA-A4QY.<uuid>.xml
    and
        isoforms.quantification.txt
    becomes
        isoforms.quantification.<uuid>.txt


    This is done by specifying a list of known extension strings and finding
    the first extension from left to right, splitting on periods (.)
    in order to preserve compound extensions such as '.tar.gz'

    If no correct file basename can be found, raises ValueError and dumps
    the offending file_dict.
    '''
    name = file_dict['file_name']
    uuid = file_dict['file_id']

    if not strict:
        return name

    namelist = name.split('.')
    try:
        for i in range(len(namelist) + 1):
            if namelist[i] in _SUPPORTED_FILE_TYPES:
                break
    except IndexError:
        if strict or True:
            raise ValueError("unsupported file type: " + name)

    # i is now the index of the first extension, insert uuid right before
    namelist.insert(i, uuid)
    return ".".join(namelist)

def file_id(file_dict):
    '''Get the file uuid.'''
    return file_dict['file_id']

def mirror_path(proj_root, file_dict, strict=True):
    '''Return the file location relative to a root folder.

    This location is equivalent to:
    <root>/<category>/<type>/<uuid>.<filename>'''
    category = file_dict['data_category']
    data_type = file_dict['data_type']
    name = file_basename(file_dict, strict)
    return os.path.join(proj_root, category, data_type, name).replace(' ', '_')

def diced_file_paths(root, file_dict):
    '''Return the name of the diced file to be created'''
    _ext = dice_extension(file_dict)
    _uuid = file_id(file_dict)
    if has_multiple_samples(file_dict):
        if file_dict['data_format'] == "MAF":
            # For MAFs, we separate into one file per tumor sample.
            # So iterate over cases -> samples, and filter to get the non-normal samples
            tumor_samples = samples(file_dict, tumor_only=True)
            diced_paths = []
            _aliquot_ids = aliquot_ids(tumor_samples)
            for _tcga_id in _aliquot_ids:
                fname = '.'.join([_tcga_id, _uuid, _ext])
                diced_paths.append(os.path.join(root, fname))

            return diced_paths

        else:
            # Don't know how to guess filenames
            raise ValueError("Could not get diced file paths for " + json.dumps(file_dict, indent=2))
    else:
        _tcga_id = tcga_id(file_dict)

        fname = '.'.join([_tcga_id, _uuid, _ext])
        return [os.path.join(root, fname)]

def has_multiple_samples(file_dict):
    '''Return true if this file is associated with multiple samples.
    Most file_dicts are not, but certain data types (like MAFs) are.
    '''
    cases = file_dict.get('cases',[])
    samples = [s for c in cases for s in c.get('samples',[])]
    return len(samples) > 1

def portion_id(file_dict):
    '''Return the portion associated with the file. Raise an exception if more
    than one exists.'''
    try:
        _check_dict_array_size(file_dict, 'cases')
        _check_dict_array_size(file_dict['cases'][0], 'samples')
        _check_dict_array_size(file_dict['cases'][0]['samples'][0], 'portions')
    except:
        logging.exception(json.dumps(file_dict['cases'], indent=2))
        raise

    return file_dict['cases'][0]['samples'][0]['portions'][0]['submitter_id']

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
        logging.exception(json.dumps(file_dict['cases'], indent=2))
        raise

    return file_dict['cases'][0]['samples'][0]['portions'][0]['analytes'][0]['aliquots'][0]['submitter_id']

def aliquot_ids(sample_dicts):
    '''Return all aliquot ids from the given list of sample dicts,
    such as those returned by meta.samples()'''
    aliquots = []
    for s in sample_dicts:
        for p in s['portions']:
            for an in p['analytes']:
                for aliquot in an['aliquots']:
                    #TCGA ID is the aliquot ID
                    aliquots.append(aliquot['submitter_id'])
    return aliquots

def case_id(file_dict):
    '''Return the case_id associated with the file. Raise an exception if
    more than one exists.'''
    try:
        _check_dict_array_size(file_dict, 'cases')
    except:
        logging.exception(json.dumps(file_dict['cases'], indent=2))
        raise

    return file_dict['cases'][0]['submitter_id']

def sample_type(file_dict):
    '''Return the sample type associated with the file.'''

    try:
        _check_dict_array_size(file_dict, 'cases')
        _check_dict_array_size(file_dict['cases'][0], 'samples')
    except:
        logging.exception(json.dumps(file_dict['cases'], indent=2))
        raise

    return file_dict['cases'][0]['samples'][0]["sample_type"]

def is_ffpe(file_dict):
    '''Return true if the file_dict is an ffpe sample'''
    try:
        _check_dict_array_size(file_dict, 'cases')
    except:
        logging.exception(json.dumps(file_dict['cases'], indent=2))
        raise

    return file_dict['cases'][0].get('samples', [{}])[0].get("is_ffpe", False)

def project_id(file_dict):
    '''Return the project_id associated with the file. Raise an exception if
    more than one case exists.'''
    try:
        _check_dict_array_size(file_dict, 'cases')
    except:
        logging.exception(json.dumps(file_dict, indent=2))
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
            logging.exception(json.dumps(file_dict, indent=2))
            raise

def center(file_dict):
    '''Returns the analysis center that submitted the data (or 'GDC')'''
    # TODO: get this info from the file_dict
    return '(TODO) -- GDC'

def platform(file_dict):
    return file_dict.get('platform', None)

def has_sample(file_dict):
    '''Returns true if there is exactly one sample associated with this file.'''

    # EAFP: accessing the first sample only succeeds if there is no
    # IndexError, KeyError, or AssertionError
    try:
        _check_dict_array_size(file_dict['cases'][0], 'samples')
        return True
    except (KeyError, IndexError, AssertionError):
        return False

def samples(file_dict, tumor_only=False):
    '''Returns a list of samples in this file. Useful for file_dicts such as
    MAFs which encompass multiple samples'''
    samples = list()
    for case in file_dict['cases']:
        samples.extend(case['samples'])
    if tumor_only:
        return [s for s in samples if "Normal" not in s['sample_type']]
    return samples

def dice_extension(file_dict):
    '''Get the expected diced file extension for this file.'''
    ext = "txt"
    dtype = file_dict['data_type']

    if dtype in ['Biospecimen', 'Clinical']:
        ext = "clin.txt"
    elif dtype in ['Copy Number Variation']:
        ext = "seg.txt"
    elif dtype in ['Methylation Beta Value', 'Transcriptome Profiling']:
        ext = "data.txt"
    elif dtype in ['Masked Somatic Mutation']:
        ext = "maf.txt"
    return ext

#TODO: Configurable?
def main_tumor_sample_type(proj_id):
    '''The sample type used by most analyses in a project.
    'Primary Tumor' for everything except LAML and SKCM.
    '''
    if proj_id in ('TCGA-LAML', 'CPTAC3-AML'):
        stype = "Primary Blood Derived Cancer - Peripheral Blood"
    elif proj_id in ('TCGA-SKCM', 'CPTAC3-CM'):
        stype = 'Metastatic'
    else:
        stype = 'Primary Tumor'
    return stype

#TODO: This should come from a config file
# Currently copied from https://tcga-data.nci.nih.gov/datareports/codeTablesReport.htm?codeTable=Sample%20Type
Tumor_IDs = namedtuple('Tumor_IDs', ['code', 'symbol'])
_TUMOR_CODES = {
    "Additional - New Primary" : Tumor_IDs('05', 'TAP'),
    "Additional Metastatic" : Tumor_IDs('07', 'TAM'),
    "Blood Derived Normal" : Tumor_IDs('10', 'NB'),
    "Bone Marrow Normal" : Tumor_IDs('14', 'NBM'),
    "Buccal Cell Normal" : Tumor_IDs('12', 'NBC'),
    "Cell Line Derived Xenograft Tissue" : Tumor_IDs('61', 'XCL'),
    "Cell Lines" : Tumor_IDs('50', 'CELL'),
    "Control Analyte" : Tumor_IDs('20', 'CELLC'),
    "EBV Immortalized Normal" : Tumor_IDs('13', 'NEBV'),
    "Human Tumor Original Cells" : Tumor_IDs('08', 'THOC'),
    "Metastatic" : Tumor_IDs('06', 'TM'),
    "Primary Blood Derived Cancer - Bone Marrow" : Tumor_IDs('09', 'TBM'),
    "Primary Blood Derived Cancer - Peripheral Blood" : Tumor_IDs('03', 'TB'),
    "Primary Xenograft Tissue" : Tumor_IDs('60', 'XP'),
    "Primary Tumor" : Tumor_IDs('01', 'TP'),
    "Recurrent Blood Derived Cancer - Bone Marrow" : Tumor_IDs('04', 'TRBM'),
    "Recurrent Blood Derived Cancer - Peripheral Blood" : Tumor_IDs('40', 'TRB'),
    "Recurrent Solid Tumor" : Tumor_IDs('02', 'TR'),
    "Recurrent Tumor" : Tumor_IDs('02', 'TR'), # GDC had new name for this
    "Solid Tissue Normal" : Tumor_IDs('11', 'NT'),
    # FIXME: Hack, Some late TCGA submissions include this new type
    "FFPE Scrolls" : Tumor_IDs('01', 'TP')
}
def tumor_code(tumor_type):
    return _TUMOR_CODES[tumor_type]

def _check_dict_array_size(d, name, size=1):
    assert len(d[name]) == size, 'File %s, expected len(%s) array to be %d' % \
                                 (d['file_name'], name, size)
