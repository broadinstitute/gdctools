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
import sys
import csv
import errno
import stat
import fnmatch
from cStringIO import StringIO
from codecs import getincrementalencoder
from argparse import RawDescriptionHelpFormatter, SUPPRESS, OPTIONAL, ZERO_OR_MORE

from gdac_lib.Constants import SAMPLE_STAMP_EXTENSION

#===============================================================================
# Return True if the path exists, otherwise return False or throw an exception.
#===============================================================================
def ensurePathExists(path, throwException=True):
    if path is not None and os.path.exists(path):
        return True
    elif throwException:
        raise Exception("Path doesn't exist: %s" % path)
    else:
        return False
    
#===============================================================================
# Return True if the directory exists, otherwise return False or throw an exception.
#===============================================================================
def ensureDirectoryExists(path, throwException=True):
    if path is not None and os.path.isdir(path):
        return True
    elif throwException:
        raise Exception("Path isn't a directory: %s" % path)
    else:
        return False
    
#===============================================================================
# Return True if the file exists, otherwise return False or throw an exception.
#===============================================================================
def ensureFileExists(file, throwException=True):
    if file is not None and os.path.isfile(file):
        return True
    elif throwException:
        raise Exception("File doesn't exist: %s" % file)
    else:
        return False

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
            os.makedirs(dir_name, getPythonMode(permissions))
            os.umask(curUmask)
    except OSError, value:
        error_num = value.errno
        # what is 183? don't know... came from legacy code.
        if  error_num==errno.EEXIST or error_num==183 :
            pass  # Directory already existed
        else:
            raise  # Reraise other errors

#===============================================================================
# Create a symbolic link to a file. If a current symbolic link exists, remove
# it. If the provided symbolic link is an actual file or the provided file doesn't
# exists, then return False - otherwise return True if successful.
#===============================================================================
def updateSymlink(dir, symlinkFilename, filename):
    symlinkPath = os.path.join(dir, symlinkFilename)
    # Remove current symbolic link or return False if it isn't a link
    if os.path.exists(symlinkPath):
        if not os.path.islink(symlinkPath):
            return False
        else:
            os.remove(symlinkPath)
    
    # Check that the file we're linking to exists
    path = os.path.join(dir, filename)
    if not os.path.isfile(path):
        return False
    
    os.symlink(path, symlinkPath)
    return True

#===============================================================================
# Create a symlink from input_path to output_path which can be either a file or
# a directory. If input_path doesn't exist, raise an exception. If output_path
# already exists and is not a link or delete_if_already_exists is False, raise
# an exception. Otherwise, delete the existing output_path symlink before 
# creating it anew.
#===============================================================================
def safe_make_symlink(input_path, output_path, delete_if_already_exists=False):
    # Verify the input file is actually there
    if not os.path.exists(input_path):
        raise Exception("can't find file %s"%input_path)
    
    if os.path.exists(output_path):
        if delete_if_already_exists and os.path.islink(output_path):
            os.remove(output_path)
        elif not os.path.islink(output_path):
            raise Exception("Link destination already exists and is not a symbolic link: %s." % output_path)
        else:
            # link already exists, check that it is identical to the one we are trying to put down
            old = os.path.realpath(input_path)
            new = os.path.realpath(output_path)
            if old == new:
                return False
            else:
                raise Exception('Existing file is different than the new symlink. old: %s  new: %s'%(old,new))
    else:
        safe_make_dirs(os.path.dirname(output_path))
    
    os.symlink(input_path,output_path)
    
    return True

#===============================================================================
# Makes directory structure, or ends gracefully if directory already exists
#===============================================================================
def safe_make_dirs(dir_name):
    try:
        os.makedirs(dir_name)
    except OSError, value:
        error_num = value.errno
        if error_num==183 or error_num==17 or error_num==errno.EEXIST:
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
#
#===============================================================================
def findFileInPath(filename,pathlist=None):
    if pathlist==None:
        syspath = sys.path
    else:
        syspath = pathlist
    for dirname in syspath:
        if dirname == '':
            dirname = os.getcwd()
        filepath = os.path.join(dirname,filename)
        if os.path.exists(filepath):
            break
    else:
        raise Exception ('Could not find file %s in search path'%filename)
    return filepath

#===============================================================================
# Write string to file, ensuring file is closed properly upon completion.
#===============================================================================
def writeStringToFile(filename, fileContents):
    with open(filename, "w") as f:
        f.write(fileContents)

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

#===============================================================================
# Given an array of permissions ([user, group, other] where 1=execute, 2=write, 
# and 4=read), change the mode of the provided path.
#===============================================================================
def changeMod(path, permissions):
    os.chmod(path, getPythonMode(permissions))
    
#===============================================================================
# Given an array of permissions ([user, group, other] where 1=execute, 2=write, 
# and 4=read), determine the mode python can interpret to set the mode of a 
# path correctly.
#===============================================================================
def getPythonMode(permissions):
    if len(permissions) != 3:
        raise Exception("Permissions array must contain 3 integer modes that are 1 <= mode <= 7, but array contained %s" % str(permissions))
    
    user  = permissions[0]
    group = permissions[1]
    other = permissions[2]
    
    mode = None
    if user == 1:
        mode = stat.S_IXUSR
    elif user == 2:
        mode = stat.S_IWUSR
    elif user == 3:
        mode = stat.S_IXUSR | stat.S_IWUSR
    elif user == 4:
        mode = stat.S_IRUSR
    elif user == 5:
        mode = stat.S_IXUSR | stat.S_IRUSR
    elif user == 6:
        mode = stat.S_IWUSR | stat.S_IRUSR
    elif user == 7:
        mode = stat.S_IXUSR | stat.S_IWUSR | stat.S_IRUSR
    else:
        raise Exception("User mode must be 1 <= mode <= 7 but is: %d" % mode)
    
    if group == 1:
        mode = mode | stat.S_IXGRP
    elif group == 2:
        mode = mode | stat.S_IWGRP
    elif group == 3:
        mode = mode | stat.S_IXGRP | stat.S_IWGRP
    elif group == 4:
        mode = mode | stat.S_IRGRP
    elif group == 5:
        mode = mode | stat.S_IXGRP | stat.S_IRGRP
    elif group == 6:
        mode = mode | stat.S_IWGRP | stat.S_IRGRP
    elif group == 7:
        mode = mode | stat.S_IXGRP | stat.S_IWGRP | stat.S_IRGRP
    else:
        raise Exception("Group mode must be 1 <= mode <= 7 but is: %d" % mode)
    
    if other == 1:
        mode = mode | stat.S_IXOTH
    elif other == 2:
        mode = mode | stat.S_IWOTH
    elif other == 3:
        mode = mode | stat.S_IXOTH | stat.S_IWOTH
    elif other == 4:
        mode = mode | stat.S_IROTH
    elif other == 5:
        mode = mode | stat.S_IXOTH | stat.S_IROTH
    elif other == 6:
        mode = mode | stat.S_IWOTH | stat.S_IROTH
    elif other == 7:
        mode = mode | stat.S_IXOTH | stat.S_IWOTH | stat.S_IROTH
    else:
        raise Exception("Other mode must be 1 <= mode <= 7 but is: %d" % mode)
    
    return mode

#===============================================================================
# Python version of tail stolen from 
# http://stackoverflow.com/questions/136168/get-last-n-lines-of-a-file-with-python-similar-to-tail
# Return None if file doesn't exist.
#===============================================================================
def tail( path, window=2 ):
    if os.path.isfile(path):
        f = open(path, 'r')
        BUFSIZ = 1024
        f.seek(0, 2)
        num_bytes = f.tell()
        size = window
        block = -1
        data = []
        while size > 0 and num_bytes > 0:
            if (num_bytes - BUFSIZ > 0):
                # Seek back one whole BUFSIZ
                f.seek(block*BUFSIZ, 2)
                # read BUFFER
                data.append(f.read(BUFSIZ))
            else:
                # file too small, start from begining
                f.seek(0,0)
                # only read what was not read
                data.append(f.read(num_bytes))
            linesFound = data[-1].count('\n')
            size -= linesFound
            num_bytes -= BUFSIZ
            block -= 1
        f.close()
        return '\n'.join(''.join(data).splitlines()[-window:])
    return None

#===========================================================================
# In the given samplestamps directory, grab the latest one (or more).
#===========================================================================
def get_latest_samplestamp_paths(file_list, filedir):
    #file every samplestamp file into 2D dict
    ss_file_dict = {}
    for current_samplestamp_file in fnmatch.filter(file_list, '*%s' % 
                                                   SAMPLE_STAMP_EXTENSION):
        current_ver = parse_samplestamp_version(current_samplestamp_file)
        if current_ver[0] not in ss_file_dict:
            ss_file_dict[current_ver[0]] = {}
        ss_file_dict[current_ver[0]][current_ver[1]] = current_samplestamp_file

    #get latest version of each batch/series
    samplestamp_files = []
    for batch in ss_file_dict.iterkeys():
        revs = ss_file_dict[batch].keys()
        revs.sort()
        maxrev = revs[-1]
        samplestamp_files.append(ss_file_dict[batch][maxrev])
        
    return [os.path.join(filedir, samplestamp_file) for samplestamp_file in 
            samplestamp_files]
    
#===========================================================================
# Parse the version out of a samplestamp filename
#===========================================================================    
def parse_samplestamp_version(samplestamp_filename):
    samplestamp_filename_split = samplestamp_filename.split('.')
    if len(samplestamp_filename_split) < 5:
        raise Exception("Invalid samplestamp filename (%s), must be of the form *.mage-tab.2.4.0.samplestamp.txt")
    ver_nums = samplestamp_filename_split[-5:-2]
    ver_nums_int = [int(ver) for ver in ver_nums]
    return ver_nums_int

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

#===========================================================================
# replacement for csv.writer when strings include unicode characters
# from https://docs.python.org/2/library/csv.html
#===========================================================================
class UnicodeWriter:
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = getincrementalencoder(encoding)()

    def writerow(self, row):
        self.writer.writerow([s.encode("utf-8") for s in row])
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)