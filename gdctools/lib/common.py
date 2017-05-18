#!/usr/bin/env python

import time
import os
import fnmatch
import csv
import errno
import logging
import re
import sys
import contextlib
from argparse import RawDescriptionHelpFormatter, SUPPRESS, OPTIONAL, ZERO_OR_MORE
from fasteners import InterProcessLock

# Helpful constants
DATESTAMP_REGEX = re.compile("^\d{4}_[01]\d_[0-3]\d$")

#TODO: Configurable?
REPORT_DATA_TYPES = ('BCR', 'Clinical', 'CN', 'mRNA', 'miR', 'MAF', 'Methylation')


ANNOT_TO_DATATYPE = {
    'clinical__primary'         : 'Clinical',
    'clinical__biospecimen'     : 'BCR',
    'CNV__unfiltered__snp6'                 : 'CN',
    'CNV__snp6'     : 'CN',
    'methylation__HM27' : 'Methylation',
    'methylation__HM450' : 'Methylation',
    'miR__geneExp'              : 'miR',
    'miR__isoformExp'           : 'miR',
    'mRNA__geneExp__FPKM'       : 'mRNA',
    'mRNA__geneExpNormed__FPKM' : 'mRNA',
    'mRNA__counts__FPKM'        : 'mRNA',
    'SNV__mutect'               : 'MAF'
}

__PY3__ = sys.version_info > (3,)
if __PY3__:
    def safe_open(file, *args, **kwargs):
        # Used to interpret newlines correctly: since CSV etc modules etc do
        # their own/universal newline handling, it's safe to specify newline=''
        kwargs['newline'] = ''
        return open(file, *args, **kwargs)
else:
    safe_open = open

def silent_rm(filename):
    try:
        os.remove(filename)
    except OSError as e:
        #ENOENT means file doesn't exist, ignore
        if e.errno != errno.ENOENT:
            raise

def datestamp(timetuple=time.localtime()):
    '''Takes a time-tuple and converts it to the standard GDAC datestamp
    (YYYY_MM_DD). No argument will generate current date'''
    return time.strftime('%Y_%m_%d', timetuple)

def increment_file(filepath):
    '''Returns filepath if filepath doesn't exist. Otherwise returns
    <filepath>.<matches + 1>. e.g. if only one file matches filepath*,
    filepath.2 is returned; two files: filepath.3, etc.'''
    if os.path.exists(filepath):
        dirname, filename = os.path.split(filepath)
        count = sum((1 for _ in fnmatch.filter(os.listdir(dirname), filename + '*')), 1)
        filepath = '.'.join((filepath, str(count)))
    return filepath

def immediate_subdirs(path):
    subdirs = [d for d in os.listdir(path)
            if os.path.isdir(os.path.join(path, d))]
    return sorted(subdirs)

def safeMakeDirs(dir_name, permissions=None):
    """
    Makes directory structure, or ends gracefully if directory already exists.
    If permissions passed, then honor them, however os.makedirs ignores the
    sticky bit. Use changeMod if this matters.
    """
    try:
        if permissions is None:
            os.makedirs(dir_name)
        else:
            # Current process umask affects mode (mode & ~umask & 0777) so set to 0
            curUmask = os.umask(0)
            os.makedirs(dir_name, permissions)
            os.umask(curUmask)
    except OSError as value:
        error_num = value.errno
        # what is 183? don't know... came from legacy code.
        if  error_num==errno.EEXIST or error_num==183 or error_num==17:
            pass  # Directory already existed
        else:
            raise  # Reraise other errors

def safe_make_hardlink(input_file_path,output_file_path):
    output_file_dir = os.path.dirname(output_file_path)
    # Verify the input file is actually there
    if not os.path.exists(input_file_path):
        raise Exception("can't find file %s"%input_file_path)
    safeMakeDirs(output_file_dir)
    try:
        os.link(input_file_path,output_file_path)
    except OSError as err:
        if err.errno == errno.EEXIST:
            # link already exists, check that it is identical to the one we are trying to put down
            if not os.path.samefile(input_file_path,output_file_path):
                raise Exception('Existing file %s is different than the new hardlink %s' % (input_file_path, output_file_path))
        else:
            msg = '%s\n' % err
            msg += 'Input file: %s\n' % input_file_path
            msg += 'Output file: %s\n' % output_file_path
            raise Exception(msg)

def getTabFileHeader(filepath):
    '''Return the column names of a tsv as a list'''
    with open(filepath) as f:
        header = f.readline()
        if header:
            header = header.strip().split('\t')
    return header

def map_blank_to_na(csvfile):
    """
    Convert all blank csv fields to 'NA'.

    Yield the csv header,
    and then yield each csv row with
    all blank fields replaced by NAs.
    """
    yield next(csvfile)
    for row in csvfile:
        yield map(lambda f: f if f != '' else 'NA', row)

def rearrange_columns(csvfile, col_order):
    """
    csvfile : iterable of list
    col_order : list of int
        E.g.: col_order = [0, 2, 3, 1] will cause column 1 of the input to be column 3 of the output.
    """
    min_expected = max(col_order) + 1
    for row in csvfile:
        if len(row) < min_expected:
            raise ValueError('Unexpected number of columns, expected at least %d but found %d' % (min_expected, len(row)))
        new_row = [row[i] for i in col_order]
        yield new_row

def writeCsvFile(filename, data):
    """
    Write a row iterator's data to a csv file.
    """
    with safe_open(filename, "w") as f:
        csvfile = csv.writer(f, dialect='excel-tab', lineterminator='\n')
        csvfile.writerows(data)

@contextlib.contextmanager
def lock_context(path, name="gdctool"):
    '''Process level lock context, to prevent access to path by other processes

    Sample Usage:
    with lock_context(dice_root, "dicer"):
        dice()

    '''
    lockname = os.path.join(path, ".".join(["", name, "lock"]))
    lock = InterProcessLock(lockname)
    logging.info("Attempting to acquire lock: " + lockname)
    with lock:
        logging.info("Lock acquired.")
        yield
        logging.info("Releasing lock: " + lockname)
