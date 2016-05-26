#!/usr/bin/env python

from lib.convert import util as converterUtils
from lib.util import io as ioUtilities

def process(infile, extension, hyb2tcga, outdir, binary):
    for tcga_id in hyb2tcga.itervalues():
        filepath = converterUtils.constructPath(outdir, tcga_id, extension, binary)
        
        ioUtilities.safeMakeDirs(outdir)
        ioUtilities.safe_make_hardlink(infile, filepath)
