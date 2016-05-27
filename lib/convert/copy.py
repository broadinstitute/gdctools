#!/usr/bin/env python

from lib.convert import util as converterUtils
from lib.common import safeMakeDirs, safe_make_hardlink

def process(infile, extension, hyb2tcga, outdir, binary):
    for tcga_id in hyb2tcga.itervalues():
        filepath = converterUtils.constructPath(outdir, tcga_id, extension, binary)
        
        safeMakeDirs(outdir)
        safe_make_hardlink(infile, filepath)
