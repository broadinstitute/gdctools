import os
import csv
import tempfile
from gdac_lib.converters import converterUtils
from gdac_lib.utilities import ioUtilities

def process(infile, extension, hyb2tcga, outdir, ref_dir, test_short, 
            tmp_dir_root, debug_max_count, annotationInfo, gdac_bin_dir):
    ref_file = converterUtils.constructPath(ref_dir, annotationInfo.getId(),
                                            'ref')
    
    converterUtils.compare_initial_columns(ref_file, infile, gdac_bin_dir)
    
    num_header_columns = annotationInfo.getNumHeaderCols()
    num_data_columns = annotationInfo.getNumDataCols()
    
    is_single_sample_file = converterUtils.detect_single_sample_file(infile, 
                                                                     num_header_columns, 
                                                                     num_data_columns)
    
    if is_single_sample_file:
        datafile = infile
        
        header_line = ioUtilities.getTabFileHeader(datafile)
        
        if header_line[-1] in hyb2tcga.keys():
            new_header = [hyb2tcga.get(hdr, hdr) for hdr in header_line]
            
            tcga_id = new_header[-1]
            filepath = converterUtils.constructPath(outdir, tcga_id, extension)
            
            rawfile = open(datafile, 'rb')
            csvfile = csv.reader(rawfile, dialect='excel-tab')
            
            csvfile_with_hdr = converterUtils.change_header__generator(csvfile, 
                                                                       new_header)
            csvfile_with_NAs = converterUtils.map_blank_to_na(csvfile_with_hdr)
            
            ioUtilities.safeMakeDirs(outdir)
            converterUtils.writeCsvFile(filepath, csvfile_with_NAs)
            
            rawfile.close()
            
            converterUtils.check_for_suspicious_data(filepath, 
                                                     num_header_columns, 
                                                     num_data_columns)
    else:
        if len(hyb2tcga) == 0:
            # already created all the files
            return
        
        tmpdir = tempfile.mkdtemp(prefix='split_columns_', dir=tmp_dir_root)
        prefix = os.path.join(tmpdir, 'split_columns')
        infile_list = converterUtils.split_columns(infile, num_header_columns, 
                                                   num_data_columns, prefix, 
                                                   'txt', 'tsvheader',
                                                   gdac_bin_dir)
        
        for file_index, datafile in enumerate(infile_list):
            if test_short and file_index >= debug_max_count:
                os.remove(datafile)
                continue

            header_line = ioUtilities.getTabFileHeader(datafile)

            if header_line[-1] not in hyb2tcga.keys():
                #unidentified samples, not in sdrf... silently skip them.
                os.remove(datafile)
                continue
            
            new_header = [hyb2tcga.get(hdr, hdr) for hdr in header_line]
            new_header_str = '|'.join(new_header)
            
            new_filename = '.'.join([new_header[-1], extension, 'txt'])
            out_filepath = os.path.join(outdir, new_filename)
            tmp_out_filepath = out_filepath + '.tmp'
            
            #write initially to tmp file, then move to final location
            #more tolerant of interruption in the middle of writing.
            converterUtils.change_header(datafile, tmp_out_filepath,
                                         gdac_bin_dir, new_header_str)
            #TODO ought to add map_blank_to_na() here; omitting for now to save 
            #runtime.
            converterUtils.check_for_suspicious_data(tmp_out_filepath, 
                                                     num_header_columns, 
                                                     num_data_columns)
            
            os.rename(tmp_out_filepath, out_filepath)
            os.remove(datafile)
            
        os.rmdir(tmpdir)
