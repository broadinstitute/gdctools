#!/usr/bin/env python

import csv
from lib.convert import util as converterUtils
from lib.util import io as ioUtilities

def process(infile, extension, hyb2tcga, outdir):
    if len(hyb2tcga) != 1:
        raise Exception("multiple samples found for one tsv file")
    
    tcga_id = hyb2tcga.itervalues().next()
    filepath = converterUtils.constructPath(outdir, tcga_id, extension)
    
    rawfile = open(infile, 'rb')
    csvfile = csv.reader(rawfile, dialect='excel-tab')
    
    csvfile_with_ids = tsv2idtsv(csvfile, tcga_id)
    csvfile_with_NAs = converterUtils.map_blank_to_na(csvfile_with_ids)
    
    ioUtilities.safeMakeDirs(outdir)
    converterUtils.writeCsvFile(filepath, csvfile_with_NAs)
    
    rawfile.close()

def tsv2idtsv(csvfile, sampleName):
    header = csvfile.next()
    yield ['SampleId'] + header
    
    for row in csvfile:
        yield [sampleName] + row
