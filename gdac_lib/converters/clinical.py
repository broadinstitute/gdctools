import csv
import os
import tempfile
import subprocess

from gdac_lib.converters import converterUtils
from gdac_lib.utilities import ioUtilities

def process(infile, extension, hyb2tcga, outdir, gdac_bin_dir):
    if len(hyb2tcga) != 1:
        raise Exception ("multiple samples found for one clinical file")
    
    tcga_id = hyb2tcga.itervalues().next()
    filepath = converterUtils.constructPath(outdir, tcga_id, extension)
    
    tmp_out_filepath = filepath + '.tmp'
    
    ioUtilities.safeMakeDirs(outdir)
    _clinical_xml_2_tsv(infile, tmp_out_filepath, gdac_bin_dir)
    
    rawfile = open(tmp_out_filepath, 'rb')
    csvfile = csv.reader(rawfile, dialect='excel-tab')
    
    csv_with_NAs = converterUtils.map_blank_to_na(csvfile)
    
    converterUtils.writeCsvFile(filepath, csv_with_NAs)
    
    os.remove(tmp_out_filepath)

def _clinical_xml_2_tsv(xml_in, tsv_out, gdac_bin_dir):
    #create tempfiles that vanish upon closing
    stdout_file = tempfile.TemporaryFile(prefix='converter_stdout')
    stderr_file = tempfile.TemporaryFile(prefix='converter_stderr')
    
    rsrc_path = os.path.join(gdac_bin_dir, "TCGAClinicalXMLParser.R")
    cmd_str = 'Rscript -e \'source("%s"); set.seed(0); options(error=expression(q(status=1))); ClinicalParser("%s","%s"); q()\'' % (rsrc_path, xml_in, tsv_out)
    
    out_file_dir = os.path.dirname(tsv_out)
    ioUtilities.safeMakeDirs(out_file_dir)
    
    try:
        subprocess.check_call(cmd_str, shell=True, stdout=stdout_file, stderr=stderr_file)
    except Exception, ex:
        status = 'exception %s when calling %s\n' % (str(ex), cmd_str)
        
        if stderr_file.tell() > 0:
            stderr_file.seek(0)
            status += 'stderr:\n'
            for line in stderr_file:
                status += line + '\n'
            status += '\n'
        
        if stdout_file.tell() > 0:
            stdout_file.seek(0)
            status += 'stdout:\n'
            for line in stdout_file:
                status += line + '\n'
        
        raise Exception(status)
