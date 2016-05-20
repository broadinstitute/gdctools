#!/usr/bin/env python

import hashlib
import time
from itertools import chain, izip_longest
import subprocess
import yaml
import os
import fnmatch
import csv
from pkg_resources import resource_stream #@UnresolvedImport

#===============================================================================
# Case-Insensitive DictReader Class
#===============================================================================
class CIDictReader(csv.DictReader):
    @property
    def orig_fieldnames(self):
        return csv.DictReader.fieldnames().fget(self)

    @property
    def fieldnames(self):
        return [field.lower() for field in self.orig_fieldnames]

def load_yaml(filename):
    '''Returns a dict of items defined in the given yaml configuration file.'''
    with open(filename, 'r') as fd:
        return yaml.load(fd)

def CONSTANTS():
    '''Returns a dict of items defined in the yaml file Constants.cfg stored in
    the same directory as this module'''
    return yaml.load(resource_stream(__name__, 'Constants.cfg'))

CONSTANTS = CONSTANTS()

# from http://stackoverflow.com/a/11143944
def md5sum(filename):
    '''Return the md5sum for a given file.'''
    md5 = hashlib.md5()
    with open(filename, 'rb') as f: 
        for chunk in iter(lambda: f.read(128 * md5.block_size), b''): 
            md5.update(chunk)
    return md5.hexdigest()

# from http://stackoverflow.com/a/1094933
def sizeof_fmt(num):
    '''Put a value for bytes into human-readable format.'''
    for x in ['bytes','KB','MB','GB']:
        if num < 1024.0 and num > -1024.0:
            return "%3.1f%s" % (num, x)
        num /= 1024.0
    return "%3.1f%s" % (num, 'TB')

def print_indented(tsv):
    '''print a row of data indented one tab space'''
    print '\t'.join(chain(('',), tsv))

def confirm(prompt=None):
    '''Confirmation prompt.  Returns True/False depending on user's choice.'''
    options = ['y','n','yes','no']
    option_string = '|'.join(options)
    if prompt is None:
        prompt = 'Enter %s: ' % option_string
    else:
        prompt = prompt + "? (%s) " % option_string
    while True:
        choice = raw_input(prompt).lower()
        if choice in options:
            return choice in {'y', 'yes'}
        else:
            print 'Invalid choice: %s' % choice

def timestamp2tuple(timestamp):
    '''Takes a timestamp of the format YYYY_MM_DD__HH_MM_SS and converts it to
    a time-tuple usable by built in datetime functions. HH is in 24hr format.'''
    if CONSTANTS['timestamp_regex'].match(timestamp) is None:
        raise ValueError('%s is not in expected format: YYYY_MM_DD__HH_MM_SS' % timestamp)
    return time.strptime(timestamp, '%Y_%m_%d__%H_%M_%S')

def timetuple2stamp(timetuple=time.localtime()):
    '''Takes a time-tuple and converts it to the standard GDAC timestamp
    (YYYY_MM_DD__HH_MM_SS). No argument will generate a current time
    timestamp.'''
    return time.strftime('%Y_%m_%d__%H_%M_%S', timetuple)

def current_dicing():
    '''Returns a time-tuple of the most recently completed dicing run'''
    timestamp2tuple(subprocess.check_output([os.path.join(CONSTANTS['bin'], 'gdac_data'), '-L']).split('\n')[-2])

def increment_file(filepath):
    '''Returns filepath if filepath doesn't exist. Otherwise returns
    <filepath>.<matches + 1>. e.g. if only one file matches filepath*,
    filepath.2 is returned; two files: filepath.3, etc.'''
    if os.path.exists(filepath):
        dirname, filename = os.path.split(filepath)
        count = sum((1 for _ in fnmatch.filter(os.listdir(dirname), filename + '*')), 1)
        filepath = '.'.join((filepath, str(count)))
    return filepath

# From https://docs.python.org/2/library/itertools.html#recipes
def grouper(iterable, n, fillvalue=None):
    ''''Collect data into fixed-length chunks or blocks'''
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx
    args = [iter(iterable)] * n
    return izip_longest(fillvalue=fillvalue, *args)
    