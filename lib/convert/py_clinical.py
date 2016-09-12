from lib.convert import util as convert_util
from lib.clinxml import parse_clinical_xml
from lib.common import safeMakeDirs

def process(file_dict, infile, outdir):
    # should only produce one file
    filepath = convert_util.diced_file_paths(outdir, file_dict)[0]
    safeMakeDirs(outdir)
    parse_clinical_xml(infile, filepath)
    return filepath
