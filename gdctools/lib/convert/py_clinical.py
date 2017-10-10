from ..meta import diced_file_path, diced_file_path_partial
from ..clinxml import parse_clinical_xml
from ..common import safeMakeDirs
import os

def process(file_dict, infile, outdir):
    # should only produce one file
    filepath = diced_file_path(outdir, file_dict)
    filepath_partial = diced_file_path_partial(outdir, file_dict)
    safeMakeDirs(outdir)
    parse_clinical_xml(infile, filepath_partial)
    os.rename(filepath_partial, filepath)
    return filepath
