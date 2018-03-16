import csv
import logging
import gzip
import os
import sys

from .. import meta
from ..common import safeMakeDirs, safe_open

_TUMOR_SAMPLE_COLNAME_LC    = 'Tumor_Sample_Barcode'
_TUMOR_SAMPLE_COLNAME_UC    = 'TUMOR_SAMPLE_ID'
_DEFAULT_SAMPLE_INDEX       = 15

# Sample barcode pattern to handle various forms found in MAFs (i.e. LUAD-35-5375-Tumor,
# LUAD-35-3615-D-Tumor, LUAD-44-2656_DN-Tumor, TCGA-E2-A154-01A-11D-A10Y-09) There are
# two capture groups: TSS ([0-9A-Za-z]{2}) and the Participant ([0-9A-Za-z]{4}). These are
# used to form the standard TCGA individual id (TCGA-<TSS>-<Participant>-01) we place in
# our SDRFs and processed MAFs.
# _INVALID_PATTERN = re.compile("^[A-Z]+-([0-9A-Za-z]{2})-([0-9A-Za-z]{4})(-|_).+$")

# Remove these columns from the MAF if found
# _COLUMNS_TO_REMOVE = ['patient_name', 'patient']

def process(file_dict, mafFile, outdir, is_compressed=True):
    safeMakeDirs(outdir)
    logging.info("Processing MAF %s...", mafFile)
    # First unzip the maf File to the outdir
    if is_compressed:
        tmpMAF = file_dict['file_id'] + ".maf.txt"
        tmpMAF = os.path.join(outdir, tmpMAF)
        with safe_open(tmpMAF, 'w') as mafout, gzip.open(mafFile, 'rt') as cmaf:
            mafout.write(cmaf.read())
        mafFile = tmpMAF
    tumor_samples = meta.samples(file_dict, tumor_only=True)

    # Get all aliquot ids
    sample_ids = meta.aliquot_ids(tumor_samples)

    tcgaSampleIdToMafLinesMap = map_sample_ids_to_MAF_lines(mafFile, sample_ids)

    maf_uuid = file_dict['file_id']

    for sample_id in tcgaSampleIdToMafLinesMap:
        # TODO: Insert maf center into filename?
        sample_maf_filename = ".".join([sample_id, maf_uuid, "maf.txt"])
        logging.info("Writing sample MAF: " + sample_maf_filename)
        sample_maf_filename = os.path.join(outdir, sample_maf_filename)
        with safe_open(sample_maf_filename, 'w') as smf:
            outwriter = csv.writer(smf, delimiter='\t')
            outwriter.writerows(tcgaSampleIdToMafLinesMap[sample_id])


#===============================================================================
# Extract unique samples from MAF and reformat
#===============================================================================
# def processMAF(mafFilename, extension, hyb2tcga, outdir, ref_dir, test_short, tmp_dir_root, debug_max_count):
#     logging.info("Processing MAF %s...", mafFilename)
#
#     # Map each MAF line to an updated sample barcode
#     logging.info("generate new sample barcode to maf lines map")
#     tcgaSampleIdToMafLinesMap = generateTcgaSampleIdToMafLinesMap(mafFilename)
#     logging.info("Done generating new sample barcode to maf lines map")
#
#     # Create new MAF files (one sample per MAF) in temp space
#     mafTmpPaths = []
#     tmpdir = tempfile.mkdtemp(prefix='split_maf_',dir=tmp_dir_root)
#     try:
#         for index, tcgaSampleId in enumerate(tcgaSampleIdToMafLinesMap.keys()):
#             if test_short and index >= debug_max_count:
#                 break
#             mafTmpFilename = '.'.join([tcgaSampleId,extension,'txt'])
#             mafTmpPath = os.path.join(tmpdir,mafTmpFilename)
#             mafTmpPaths.append(mafTmpPath)
#
#             outfid = open(mafTmpPath,'w')
#             outwriter = csv.writer(outfid, dialect='excel-tab',lineterminator='\n')
#             outwriter.writerows(tcgaSampleIdToMafLinesMap[tcgaSampleId])
#             outfid.close()
#
#         # Copy MAF files created in temp space to final output directory
#         ioUtilities.safeMakeDirs(outdir)
#         for index, mafTmpPath in enumerate(mafTmpPaths):
#             if test_short and index >= debug_max_count:
#                 break
#             mafFilename = os.path.basename(mafTmpPath)
#             mafPath = os.path.join(outdir,mafFilename)
#             shutil.copy(mafTmpPath, mafPath)
#
#         # Create empty (except for header) MAFs for those samples with no mutations.
#         # TODO DICARA hyb2tcga may contain malformatted TCGA ids
#         # PERHAPS RUN THROUGH ALL HYB2TCGA VALUES AND IF DON"T MATCH PATTERN THEN THROW OUT
#         tcgaIdSet              = set(tcgaSampleIdToMafLinesMap.keys())
#         allSamples             = set(hyb2tcga.values())
#         samplesWithNoMutations = allSamples.difference(tcgaIdSet)
#         missingSamples         = tcgaIdSet.difference(allSamples)
#
#         for sampleBarcode in missingSamples:
#             logging.warning("Skipping - processed sample not found in hyb2tcga map: %s", sampleBarcode)
#
#         blank_maf_filepath = os.path.join(ref_dir,'maf_blank_header.txt')
#         for sampleBarcode in samplesWithNoMutations:
#             logging.warning("Mutations missing for sample - creating blank maf for: %s", sampleBarcode)
#             filename = '.'.join([sampleBarcode,extension,'txt'])
#             filepath = os.path.join(outdir,filename)
#             shutil.copy(blank_maf_filepath,filepath)
#
#         logging.info("Finished processing MAF %s...", mafFilename)
#     finally:
#         # Clean up
#         shutil.rmtree(tmpdir)

#===============================================================================
# Return a map of tcga sample id to all corresponding MAF lines.
# If the TCGA barcode is valid, leave it alone. Otherwise, reformat the barcode
# (i.e. LUAD-44-2657-Tumor) to a standard TCGA sample id
# (i.e. TCGA-44-2657-01) and replace all occurrences of TSS and
# Participant (i.e. -44-2657) in all fields with this reformatted barcode.
#===============================================================================
def map_sample_ids_to_MAF_lines(mafFilename, sample_ids):
    ''' Return a dictionary whose keys are TCGA sample ids, and whose
    values are the lines in the MAF for that sample. Also reformats the barcode
    if necessary to match a common format
    '''

    # Prevent choking on abberrant files with enormous (and likely wrong) mutations
    original_field_size_limit = csv.field_size_limit(sys.maxsize)

    # Open MAF file for reading
    mafFile   = open(mafFilename)
    mafReader = csv.reader(mafFile,dialect='excel-tab')
    header    = next(mafReader)

    # Ignore leading comments (i.e. #version 2.2) in MAF file
    while header[0].startswith('#'):
        header = next(mafReader)

    ### TODO: reintroduce column removal later...
    # # Determine indices of unwanted columns for removal
    # columnIndicesToRemove = list()
    # for columnName in _COLUMNS_TO_REMOVE:
    #     if columnName in header:
    #         columnIndicesToRemove.append(header.index(columnName))
    #
    # # Remove in-place, so need to pop off elements from last to first
    # columnIndicesToRemove.sort(reverse=True)
    #
    # # Remove unwanted columns from header
    # _removeColumns(header, columnIndicesToRemove)

    # Determine index of tumor sample barcode column
    sampleIndex = _DEFAULT_SAMPLE_INDEX
    if _TUMOR_SAMPLE_COLNAME_LC in header:
        sampleIndex = header.index(_TUMOR_SAMPLE_COLNAME_LC)
    elif _TUMOR_SAMPLE_COLNAME_UC in header:
        sampleIndex = header.index(_TUMOR_SAMPLE_COLNAME_UC)

    unmatched_sample_barcodes     = set()
    # Initialize entry for each possible sample id. This list of sample ids
    # comes from the GDC metadata, so every row should map to one of these ids
    # Also include header here, since it is easier than adding it later, plus
    # gives the benefit of requiring each sample to have a non-zero number of
    # lines
    tcgaSampleIdToMafLinesMap     = {s:[header] for s in sample_ids}

    lineno = 0
    for line in mafReader:
        lineno += 1
        # Skip blank and commented out lines
        if line == [] or line[0].startswith('#'):
            continue

        # Filter abberrant genes/lines with enormous (and likely wrong) mutations
        sequence_length = len(line[10])
        if sequence_length >= original_field_size_limit:
            logging.warning('Omitting gene %s mutation (line %d): nucleotide ' \
                'sequence is very long (%d) and probably incorrectly called' % \
                (line[0], lineno, sequence_length))
            continue

        # tcgaSampleId is the 15 digit barcode containing the sample type
        # (i.e. TCGA-44-2657-01). The sampleBarcode is a generic name for
        # whatever barcode is in the MAF - it may range from 12 to 28
        # characters and may even be invalid. That is what we're
        # attempting to standardize here.
        # tcgaSampleId  = None
        # participant   = None
        # valid         = None
        sampleBarcode = line[sampleIndex]
        if sampleBarcode not in tcgaSampleIdToMafLinesMap:
            # Not good, the GDC metadata does not match the sample id
            unmatched_sample_barcodes.add(sampleBarcode)
            continue
        else:
            # Good the line matches a sample, add the line to the map
            tcgaSampleIdToMafLinesMap[sampleBarcode].append(line)
        # elif sampleBarcode in sampleBarcodeToSampleInfoMap:
        #     tcgaSampleId = sampleBarcodeToSampleInfoMap[sampleBarcode][0]
        #     participant  = sampleBarcodeToSampleInfoMap[sampleBarcode][1]
        #     valid        = sampleBarcodeToSampleInfoMap[sampleBarcode][2]
        # else:
        #     # Try and match TCGA barcode with a valid format
        #     for pattern in VALID_BARCODE_PATTERNS:
        #         matchObject = pattern.match(sampleBarcode)
        #         if matchObject is not None:
        #             participant = "-%s-%s" % (matchObject.group(1), matchObject.group(2))
        #             # If the id contains the sample type, use it. Otherwise, assume it's a primary tumor (-01).
        #             if matchObject.lastindex > 2:
        #                 tcgaSampleId = sampleBarcode[:15]
        #             else:
        #                 tcgaSampleId = 'TCGA%s-01' % (participant)
        #             valid            = True
        #             sampleBarcodeToSampleInfoMap[sampleBarcode] = [tcgaSampleId, participant, valid]
        #             break
        #
        #     # Special case to handle invalid, yet recognisable TCGA barcodes
        #     if tcgaSampleId is None:
        #         # Sample barcode pattern to handle various forms found in MAFs (i.e. LUAD-35-5375-Tumor,
        #         # LUAD-35-3615-D-Tumor, LUAD-44-2656_DN-Tumor, TCGA-E2-A154-01A-11D-A10Y-09) There are
        #         # two capture groups: TSS ([0-9A-Za-z]{2}) and the Participant ([0-9A-Za-z]{4}). These are
        #         # used to form the standard TCGA individual id (TCGA-<TSS>-<Participant>-01) we place in
        #         # our SDRFs and processed MAFs.
        #         matchObject = _INVALID_PATTERN.match(sampleBarcode)
        #         if matchObject is not None:
        #             participant  = "-%s-%s" % (matchObject.group(1), matchObject.group(2))
        #             tcgaSampleId = 'TCGA%s-01' % (participant)
        #             valid        = False
        #             sampleBarcodeToSampleInfoMap[sampleBarcode] = [tcgaSampleId, participant, valid]
        #
        # if tcgaSampleId:
        #     # _removeColumns(line, columnIndicesToRemove)
        #     if len(header) != len(line):
        #         raise Exception("uneven number of fields in each line of maf file")
        #
        #     # If TCGA barcode is invalid, then fix all instances similarly in the given row.
        #     if not valid:
        #         _updateSampleBarcodes(line, participant, tcgaSampleId)
        #
        #     # First line in individual MAF should be a header.
        #     if tcgaSampleId not in tcgaSampleIdToMafLinesMap:
        #         tcgaSampleIdToMafLinesMap[tcgaSampleId]=[header]
        #
        #     # Add mutation to individual's MAF
        #     tcgaSampleIdToMafLinesMap[tcgaSampleId].append(line)
        # else:
        #     unmatchedSamples.add(sampleBarcode)
        #     logging.warning("Skipping unmatched sample: %s.", sampleBarcode)
    if len(unmatched_sample_barcodes) > 0:
        logging.warning("Unmatched sample barcodes found in MAF:\n"
                        + "\n".join(sorted(unmatched_sample_barcodes)))

    # Reset CSV reader buffer size back to original value
    csv.field_size_limit(original_field_size_limit)

    mafFile.close()
    return tcgaSampleIdToMafLinesMap

#===============================================================================
# Remove columns from line - columnIndicesToRemove must be sorted in reverse order
#===============================================================================
# def _removeColumns(line, columnIndicesToRemove):
#     for index in columnIndicesToRemove:
#         line.pop(index)

#===============================================================================
# Checks every field in a MAF row to see if it contains the given participant
# (e.g. TSS and Participant portion of barcode: -01-2345). If it does, replace
# field with the new TCGA individual id (eg TCGA-01-2345-01).
#===============================================================================
# def _updateSampleBarcodes(line, participant, tcgaSampleId):
#     indicesToUpdate = list()
#     for index, field in enumerate(line):
#         # If field contains the participant id (i.e. -01-2345), then replace with
#         # new TCGA individual id
#         if participant in field:
#             indicesToUpdate.append(index)
#     for index in indicesToUpdate:
#         line[index] = tcgaSampleId

#===============================================================================
# Run Main
#===============================================================================
# if __name__=='__main__':
#     main(sys.argv[1:])
