#!/usr/bin/env python

import csv
from os.path import basename

from ..common import safeMakeDirs, getTabFileHeader, map_blank_to_na, writeCsvFile
from ..meta import tcga_id, diced_file_paths


def process(file_dict, infile, outdir, fpkm=False):
    filepath = diced_file_paths(outdir, file_dict)[0]
    safeMakeDirs(outdir)
    _tcga_id = tcga_id(file_dict)

    hdr1, hdr2 = generate_headers(infile, _tcga_id, fpkm)

    rawfile = open(infile, 'r')
    csvfile = csv.reader(fpkm_reader(rawfile) if fpkm else rawfile,
                         dialect='excel-tab')

    csvfile_with_hdr = change_header__generator(csvfile, hdr1, hdr2)
    csvfile_with_NAs = map_blank_to_na(csvfile_with_hdr)

    safeMakeDirs(outdir)
    writeCsvFile(filepath, csvfile_with_NAs)

    rawfile.close()

def generate_headers(infile, tcga_id, fpkm):
    old_hdr = fpkm_header(infile).split() if fpkm else getTabFileHeader(infile)
    num_data_cols = len(old_hdr) - 1
    new_hdr = ['Hybridization REF'] + [tcga_id] * num_data_cols

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
