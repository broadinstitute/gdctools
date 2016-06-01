from lib.convert import util as converterUtils
from lib.clinxml import parse_clinical_xml
from lib.common import safeMakeDirs

def process(infile, extension, hyb2tcga, outdir, gdac_bin_dir):
    if len(hyb2tcga) != 1:
        raise Exception ("multiple samples found for one clinical file")
    tcga_id = hyb2tcga.itervalues().next()
    filepath = converterUtils.constructPath(outdir, tcga_id, extension)
    safeMakeDirs(outdir)
    parse_clinical_xml(infile, filepath)

    return filepath

