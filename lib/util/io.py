#===============================================================================
# The Broad Institute
# SOFTWARE COPYRIGHT NOTICE AGREEMENT
# This software and its documentation are copyright 2007 by the
# Broad Institute/Massachusetts Institute of Technology. All rights are reserved.
#
# This software is supplied without any warranty or guaranteed support whatsoever. Neither
# the Broad Institute nor MIT can be responsible for its use, misuse, or functionality.
# 
# @author: Dan DiCara
# @date:   Feb 23, 2012
#===============================================================================

import os
import csv
import errno
from argparse import RawDescriptionHelpFormatter, SUPPRESS, OPTIONAL, ZERO_OR_MORE

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
