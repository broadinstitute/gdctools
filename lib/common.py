#!/usr/bin/env python

import time
import os
import fnmatch
import csv
import errno
import logging
import sys
import contextlib
from argparse import RawDescriptionHelpFormatter, SUPPRESS, OPTIONAL, ZERO_OR_MORE
from fasteners import InterProcessLock
from lib.constants import LOGGING_FMT

def init_logging(tstamp=None, log_dir=None, logname=""):
    '''Initialize logging to stdout and to a logfile
       (see http://stackoverflow.com/a/13733863)'''
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    log_formatter = logging.Formatter(LOGGING_FMT)

    # Write logging data to file
    if log_dir is not None and tstamp is not None:
        if not os.path.isdir(log_dir):
            os.makedirs(log_dir)
        logfile = os.path.join(log_dir, ".".join([logname, tstamp, "log"]))
        logfile = increment_file(logfile)
        # TODO: Increment so we have files like date.log.1 instead of overwriting
        file_handler = logging.FileHandler(logfile)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(log_formatter)
        root_logger.addHandler(file_handler)

        logging.info("Logfile:" + logfile)
        # For easier eyeballing & CLI tab-completion, symlink to latest.log
        latest = os.path.join(log_dir, logname + ".latest.log")
        silent_rm(latest)
        os.symlink(os.path.abspath(logfile), latest)

    # Send to console, too, if running at valid TTY (e.g. not cron job)
    if os.isatty(sys.stdout.fileno()):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(log_formatter)
        root_logger.addHandler(console_handler)

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

#===============================================================================
# Makes directory structure, or ends gracefully if directory already exists.
# If permissions passed, then honor them, however os.makedirs ignores the
# sticky bit. Use changeMod if this matters.
#===============================================================================
def safeMakeDirs(dir_name, permissions=None):
    try:
        if permissions is None:
            os.makedirs(dir_name)
        else:
            # Current process umask affects mode (mode & ~umask & 0777) so set to 0
            curUmask = os.umask(0)
            os.makedirs(dir_name, permissions)
            os.umask(curUmask)
    except OSError, value:
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
    except OSError,err:
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
    yield csvfile.next()
    for row in csvfile:
        yield map(lambda f: f if f != '' else 'NA', row)

def writeCsvFile(filename, data):
    """
    Write a row iterator's data to a csv file.
    """
    rawfile = open(filename, 'wb')
    csvfile = csv.writer(rawfile, dialect='excel-tab', lineterminator='\n')
    csvfile.writerows(data)
    rawfile.close()


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
