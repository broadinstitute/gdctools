#!/usr/bin/env python

import csv
from os.path import basename

from ..common import safeMakeDirs, getTabFileHeader, map_blank_to_na, writeCsvFile, rearrange_columns
from ..meta import tcga_id, diced_file_paths


def process(file_dict, infile, outdir, fpkm=False, col_order=None, data_cols=None):
    '''
col_order : list of int
    E.g.: col_order = [0, 2, 3, 1] will cause column 1 of the input to be column 3 of the output. 
    col_order = None leaves column order unchanged.
data_cols : list of int
    Columns listed in data_cols get a sample name in the top header row, other
    columns are treated as header columns and do not get a sample name. 
    If data_cols is None, treat column 0 as a header and all others as data columns.
    '''


    filepath = diced_file_paths(outdir, file_dict)[0]
    safeMakeDirs(outdir)
    _tcga_id = tcga_id(file_dict)

    hdr1, hdr2 = generate_headers(infile, _tcga_id, fpkm, data_cols)


    rawfile = open(infile, 'r')
    csvfile = csv.reader(fpkm_reader(rawfile) if fpkm else rawfile,
                         dialect='excel-tab')

    csvfile_with_hdr = change_header__generator(csvfile, hdr1, hdr2)
    csvfile_with_NAs = map_blank_to_na(csvfile_with_hdr)
    if col_order is not None:
        csvfile_with_new_column_order = rearrange_columns(csvfile_with_NAs, col_order)
    else:
        csvfile_with_new_column_order = csvfile_with_NAs

    safeMakeDirs(outdir)
    writeCsvFile(filepath, csvfile_with_new_column_order)

    rawfile.close()

def generate_headers(infile, tcga_id, fpkm, data_cols):
    old_hdr = fpkm_header(infile).split() if fpkm else getTabFileHeader(infile)
    new_hdr = ['Hybridization REF']
    for i in range(1, len(old_hdr)):
        if data_cols is None or i in data_cols:
            new_hdr += [tcga_id]
        else:
            new_hdr += ['']

    return new_hdr, old_hdr

def fpkm_header(filename):
    return "gene_id\t" + ("raw_count" if "htseq.counts" in basename(filename)
                          else "FPKM") + "\n"

def fpkm_reader(rawfile):
    yield fpkm_header(rawfile.name)
    for line in rawfile:
        yield line

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

    next(csvfile)
    for row in csvfile:
        yield row
