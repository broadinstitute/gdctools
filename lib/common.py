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
from lib.constants import LOGGING_FMT, TIMESTAMP_REGEX


# Initialize logging to stdout and to logfile
# see http://stackoverflow.com/a/13733863
def init_logging(tstamp=None, log_dir=None, logname="", link_latest=True):
    '''Initialize logging to stdout and to a logfile'''
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    log_formatter = logging.Formatter(LOGGING_FMT)

    # Write logging data to file
    if log_dir is not None and tstamp is not None:
        if not os.path.isdir(log_dir):
            os.makedirs(log_dir)
        logfile = os.path.join(log_dir, ".".join([logname, tstamp, "log"]))
        # TODO: For a dicing, this can append to an existing log, is
        # this a good thing, or not?
        # Pro: All dicing attempts for a given timestamp are colocated,
        #     no data is lost
        # Cons: Logs can get very large, and it's difficult to tell if it
        #     succeeded or failed, and to tell the difference between dice
        #     runs.
        file_handler = logging.FileHandler(logfile)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(log_formatter)
        root_logger.addHandler(file_handler)

        logging.info("Logfile:" + logfile)
        # Symlink a '*.latest.log' to logfile
        if link_latest:
            lf_base = os.path.basename(logfile)
            # Logfiles should be of the format *.<timestamp>.log
            timestamp = lf_base.split('.')[-2]
            # For easier eyeballing & CLI tab-completion, symlink to latest.log
            latest = "latest.log"
            silent_rm(latest)
            os.symlink(os.path.abspath(logfile), latest)


    # Write logging data to console
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


def timestamp2tuple(timestamp):
    '''Takes a timestamp of the format YYYY_MM_DD__HH_MM_SS and converts it to
    a time-tuple usable by built in datetime functions. HH is in 24hr format.'''
    if TIMESTAMP_REGEX.match(timestamp) is None:
        raise ValueError('%s is not in expected format: YYYY_MM_DD__HH_MM_SS' % timestamp)
    return time.strptime(timestamp, '%Y_%m_%d__%H_%M_%S')


def timetuple2stamp(timetuple=time.localtime()):
    '''Takes a time-tuple and converts it to the standard GDAC timestamp
    (YYYY_MM_DD__HH_MM_SS). No argument will generate a current time
    timestamp.'''
    return time.strftime('%Y_%m_%d__%H_%M_%S', timetuple)


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


#===============================================================================
#
#===============================================================================
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


#===============================================================================
# Retrieve the first line of the provided tab-delimited file. If the file is
# empty, return None.
#===============================================================================
def getTabFileHeader(filepath):
    header = None
    if os.path.getsize(filepath) != 0:
        with open(filepath) as f:
            reader = csv.reader(f, dialect='excel-tab')
            header = reader.next()
    return header


#===========================================================================
# The same as argparse.ArgumentDefaultsHelpFormatter, except using
# RawDescriptionHelpFormatter as the base class
#===========================================================================
class RawDescriptionArgumentDefaultsHelpFormatter(RawDescriptionHelpFormatter):
    """Help message formatter which retains any formatting in descriptions and
    adds default values to argument help.

    Only the name of this class is considered a public API. All the methods
    provided by the class are considered an implementation detail.
    """

    def _get_help_string(self, action):
        help = action.help
        if '%(default)' not in action.help:
            if action.default is not SUPPRESS:
                defaulting_nargs = [OPTIONAL, ZERO_OR_MORE]
                if action.option_strings or action.nargs in defaulting_nargs:
                    help += ' (default: %(default)s)'
        return help

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
