#!/usr/bin/env python

import csv
from lib.convert import util as convert_util
from lib.common import safeMakeDirs, getTabFileHeader
from lib.meta import tcga_id
from os.path import basename

def process(infile, file_dict, outdir, fpkm=False):
    filepath = convert_util.diced_file_paths(outdir, file_dict)[0]
    safeMakeDirs(outdir)
    _tcga_id = tcga_id(file_dict)

    hdr1, hdr2 = generate_headers(infile, _tcga_id, fpkm)

    rawfile = open(infile, 'rb')
    csvfile = csv.reader(fpkm_reader(rawfile) if fpkm else rawfile,
                         dialect='excel-tab')

    csvfile_with_hdr = convert_util.change_header__generator(csvfile, hdr1,
                                                             hdr2)
    csvfile_with_NAs = convert_util.map_blank_to_na(csvfile_with_hdr)

    safeMakeDirs(outdir)
    convert_util.writeCsvFile(filepath, csvfile_with_NAs)

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
