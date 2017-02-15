from ..meta import diced_file_paths
from ..clinxml import parse_clinical_xml
from ..common import safeMakeDirs

def process(file_dict, infile, outdir):
    # should only produce one file
    filepath = diced_file_paths(outdir, file_dict)[0]
    safeMakeDirs(outdir)
    parse_clinical_xml(infile, filepath)
    return filepath
