#!/usr/bin/env python

import csv

from ..common import safeMakeDirs, writeCsvFile
from .. import meta


def process(file_dict, infile, outdir, dialect='seg_broad'):
    # Should only produce one outfile
    outfile = meta.diced_file_paths(outdir, file_dict)[0]
    hyb_id = file_dict['file_name'].split('.',1)[0]
    tcga_id = meta.aliquot_id(file_dict)

    rawfile = open(infile, 'r')
    csvfile = csv.DictReader(rawfile, dialect='excel-tab')

    converter = find_converter(dialect)
    seg_file_data = generate_seg_file(csvfile, converter, tcga_id, hyb_id)

    safeMakeDirs(outdir)
    writeCsvFile(outfile, seg_file_data)

    rawfile.close()
    return outfile

def find_converter(dialect):
    """
    Given a dialect (eg, seg_broad), return the corresponding converter.

    This script defines a number of functions to convert different seg
    file dialects to a common format.

    find_converters() gathers a list of all converters defined in this
    script and returns the one corresponding to the specified dialect.
    """
    # List all variables in this script.
    global_vars = globals()

    if dialect not in global_vars:
        raise Exception('unexpected segfile dialect: %s' % dialect)

    return global_vars[dialect]

def generate_seg_file(csvdict, converter, tcga_id, hyb_id):
    yield ['Sample', 'Chromosome', 'Start', 'End', 'Num_Probes', 'Segment_Mean']
    for row in csvdict:
        new_row = converter(row, tcga_id, hyb_id)
        if new_row:
            yield new_row

def seg_hudsonalpha(row, tcga_id, hyb_id):
    if row['Normalization Name'] != hyb_id:
        return None

    Sample       = tcga_id
    Chromosome   = fix_chromosome(row['chrom'])
    Start        = row['loc.start']
    End          = row['loc.end']
    Num_Probes   = 'NA'
    Segment_Mean = row['mean']

    return [Sample, Chromosome, Start, End, Num_Probes, Segment_Mean]

def seg_mskcc(row, tcga_id, hyb_id):
    if row['sample'] != hyb_id:
        return None

    Sample       = tcga_id
    Chromosome   = fix_chromosome(row['chrom'])
    Start        = row['loc.start']
    End          = row['loc.end']
    Num_Probes   = row['num.mark']
    Segment_Mean = row['seg.mean']

    return [Sample, Chromosome, Start, End, Num_Probes, Segment_Mean]

def seg_mskcc2(row, tcga_id, hyb_id):
    Sample       = tcga_id
    Chromosome   = fix_chromosome(row['chrom'])
    Start        = row['loc.start']
    End          = row['loc.end']
    Num_Probes   = row['num.mark']
    Segment_Mean = row['seg.mean']

    return [Sample, Chromosome, Start, End, Num_Probes, Segment_Mean]

def seg_broad(row, tcga_id, hyb_id):
    if row['Sample'] != hyb_id:
        raise Exception('unexpected hybridization id mismatch... expected %s, found %s in file' % (hyb_id, row['Sample']))

    Sample       = tcga_id
    Chromosome   = fix_chromosome(row['Chromosome'])
    Start        = row['Start']
    End          = row['End']
    Num_Probes   = row['Num_Probes']
    Segment_Mean = row['Segment_Mean']

    return [Sample, Chromosome, Start, End, Num_Probes, Segment_Mean]

def seg_harvard(row, tcga_id, hyb_id):
    Sample       = tcga_id
    Chromosome   = fix_chromosome(row['Chromosome'])
    Start        = row['Start']
    End          = row['End']
    Num_Probes   = row['Probe_Number']
    Segment_Mean = row['Segment_Mean']

    return [Sample, Chromosome, Start, End, Num_Probes, Segment_Mean]

def seg_harvardlowpass(row, tcga_id, hyb_id):
    Sample       = tcga_id
    Chromosome   = fix_chromosome(row['Chromosome'])
    Start        = row['Start']
    End          = row['End']
    Num_Probes   = 'NA'
    Segment_Mean = row['Segment_Mean']

    return [Sample, Chromosome, Start, End, Num_Probes, Segment_Mean]

def fix_chromosome(chrom):
    chrom = chrom.lower()
    chrom = chrom.lstrip("chr")

    if chrom.isdigit():
        chrom_out = chrom
    elif chrom == 'x':
        chrom_out = '23'
    elif chrom == 'y':
        chrom_out = '24'
    elif chrom == 'm' or chrom == 'mt':
        chrom_out = '25'
    elif chrom == 'xy':
        chrom_out = '26'
    else:
        raise Exception('unexpected chromosome value: %s' % chrom)

    return chrom_out
