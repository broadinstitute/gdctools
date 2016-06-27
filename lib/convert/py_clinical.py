from lib.convert import util as convert_util
from lib.clinxml import parse_clinical_xml
from lib.common import safeMakeDirs

def process(infile, file_dict, outdir):
    filepath = convert_util.diced_file_path(outdir, file_dict)
    safeMakeDirs(outdir)
    parse_clinical_xml(infile, filepath)
    return filepath
