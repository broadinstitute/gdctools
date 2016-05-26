#!/usr/bin/env python

import time
import os
import fnmatch

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

def increment_file(filepath):
    '''Returns filepath if filepath doesn't exist. Otherwise returns
    <filepath>.<matches + 1>. e.g. if only one file matches filepath*,
    filepath.2 is returned; two files: filepath.3, etc.'''
    if os.path.exists(filepath):
        dirname, filename = os.path.split(filepath)
        count = sum((1 for _ in fnmatch.filter(os.listdir(dirname), filename + '*')), 1)
        filepath = '.'.join((filepath, str(count)))
    return filepath
