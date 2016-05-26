#!/usr/bin/env python

import os
import csv
import subprocess
import tempfile

from lib.util import io as ioUtilities

def writeCsvFile(filename, data):
    """
    Write a row iterator's data to a csv file.
    """
    rawfile = open(filename, 'wb')
    csvfile = csv.writer(rawfile, dialect='excel-tab', lineterminator='\n')
    csvfile.writerows(data)
    rawfile.close()

def constructPath(directory, tcga_id, extension, binary=False):
    if binary:
        filename = '.'.join([tcga_id, extension])
    else:
        filename = '.'.join([tcga_id, extension, 'txt'])
    
    return os.path.join(directory, filename)

def split_columns(infile, num_info_columns, num_sample_columns, 
                  out_file_prelim_path, out_file_ext, header_format, 
                  gdac_bin_dir):
    filelist_path = tempfile.mktemp()
    cmd_str = " ".join([
        os.path.join(gdac_bin_dir, "split_columns2"),
        infile,
        str(num_info_columns),
        str(num_sample_columns),
        out_file_prelim_path,
        out_file_ext,
        header_format,
        filelist_path
        ])
    
    out_file_dir = os.path.dirname(out_file_prelim_path)
    ioUtilities.safeMakeDirs(out_file_dir)

    p = subprocess.Popen(cmd_str, shell=True, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    stdout, stderr = p.communicate()
    stdout = str(stdout)
    stderr = str(stderr)
                            
    if p.returncode != 0:
        status = 'Error when calling %s\n' % cmd_str
        status += 'stderr: %s\n' % stderr
        status += 'stdout: %s\n' % stdout
        raise Exception(status)
    
    
    filelist_fid = open(filelist_path,'r')
    filelist_raw = filelist_fid.readlines()
    filelist_fid.close()
    os.remove(filelist_path)
    filelist = [filename.rstrip() for filename in filelist_raw]
    return filelist

def change_header(infile,outfile,gdac_bin_dir,header1,header2=None):
    change_header = os.path.join(gdac_bin_dir,  "change_header")
    cmd_str = " ".join([change_header, infile, outfile, "'" + header1 + "'"])
    if header2 != None:
        cmd_str = " ".join([cmd_str, "'" + header2 + "'"])
        
    out_file_dir = os.path.dirname(outfile)
    ioUtilities.safeMakeDirs(out_file_dir)

    p = subprocess.Popen(cmd_str, shell=True, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    stdout, stderr = p.communicate()
    stdout = str(stdout)
    stderr = str(stderr)
                            
    if p.returncode != 0:
        status = 'Error when calling %s\n' % cmd_str
        status += 'stderr: %s\n' % stderr
        status += 'stdout: %s\n' % stdout
        raise Exception(status)

def change_header__generator(csvfile, header1, header2=None):
    """
    Replace a csv header row with a new one (or two).
    
    Skip the first row of the input csv file;
    in its place, yield one (or two) new header(s),
    and then yield the remainder of the input file.
    """
    yield header1
    if header2:
        yield header2
    
    csvfile.next()
    for row in csvfile:
        yield row

def compare_initial_columns(ref_file,test_file, gdac_bin_dir):
    # TODO add check (in C) that the number of columns is uniform across all lines
    if os.path.getsize(ref_file)==0:
        #empty ref file indicates that we should skip formalities and always pass
        return
    
    compare_initial_columns = os.path.join(gdac_bin_dir, "compare_initial_columns")
    cmd_str = " ".join([compare_initial_columns, ref_file, test_file])

    p = subprocess.Popen(cmd_str, shell=True, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    stdout, stderr = p.communicate()
    stdout = str(stdout)
    stderr = str(stderr)
                            
    if p.returncode != 0:
        status = 'Error when calling %s\n' % cmd_str
        status += 'stderr: %s\n' % stderr
        status += 'stdout: %s\n' % stdout
        raise Exception(status)
    
def check_for_suspicious_data(filepath, num_header_columns, num_data_columns):
    '''
    Check magetab data matrix files for excessively uniform data.
    
    If a data column consists of a single non-zero value,
    there was probably a data entry problem.
    
    Raises an exception for univalued columns.
    In the typical case, ie good files, only needs to read a few rows.
    '''
    rawfile = open(filepath, 'r')
    csvfile = csv.reader(rawfile, dialect='excel-tab')
    
    try:
        # must have minimum 2 header rows and 1 data row.
        csvfile.next()
        csvfile.next()
        first_row = csvfile.next()
    except Exception:
        raise Exception('magetab data matrix files must have minimum 2 header lines and 1 data line: %s' % filepath)
    
    assert len(first_row) == num_header_columns + num_data_columns
    
    # Construct a set of indices of data columns starting with a non-zero value.
    unchanged_data_columns = set(index
                                 for index, value in enumerate(first_row)
                                 if index >= num_header_columns
                                 and value != '0')
    
    for current_row in csvfile:
        changed_data_columns = set(n
                                   for n in unchanged_data_columns
                                   if current_row[n] != first_row[n])
        
        unchanged_data_columns -= changed_data_columns
        if len(unchanged_data_columns) == 0:
            break
    
    if csvfile.line_num > 3 and len(unchanged_data_columns) > 0:
        raise Exception ('The columns %s have unchanged data in the data file %s' % (str(unchanged_data_columns), filepath))
    
    rawfile.close()

def blank_to_na(field):
    """
    Convert an empty string to 'NA'.
    """
    if field == '':
        return 'NA'
    else:
        return field

def map_blank_to_na(csvfile):
    """
    Convert all blank csv fields to 'NA'.
    
    Yield the csv header,
    and then yield each csv row with
    all blank fields replaced by NAs.
    """
    yield csvfile.next()
    for row in csvfile:
        yield map(blank_to_na, row)

def detect_single_sample_file(infile, num_header_columns, num_data_columns):
    header_line = ioUtilities.getTabFileHeader(infile)
    return len(header_line) == (num_header_columns + num_data_columns)
