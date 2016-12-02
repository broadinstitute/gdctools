from gdctools.lib.meta import diced_file_paths
from gdctools.lib.clinxml import parse_clinical_xml
from gdctools.lib.common import safeMakeDirs

def process(file_dict, infile, outdir):
    # should only produce one file
    filepath = diced_file_paths(outdir, file_dict)[0]
    safeMakeDirs(outdir)
    parse_clinical_xml(infile, filepath)
    return filepath
