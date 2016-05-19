#===============================================================================
# Copyright (c) 2013 The Broad Institute, Inc. 
# SOFTWARE COPYRIGHT NOTICE 
# This software and its documentation are the copyright of the Broad Institute, Inc. 
# All rights are reserved.
#
# This software is supplied without any warranty or guaranteed support whatsoever. 
# The Broad Institute is not responsible for its use, misuse, or functionality.
# 
# @author: Dan DiCara
# @date:   Mar 12, 2013
#===============================================================================

import os
import re
from collections import namedtuple

#===============================================================================
# TCGA Barcode, UUID, and Firehose ID 
#===============================================================================

PARTICIPANT_BARCODE_PATTERN  = re.compile("^TCGA-([0-9A-Za-z]{2})-([0-9A-Za-z]{4})$")
SAMPLE_BARCODE_PATTERN       = re.compile("^TCGA-([0-9A-Za-z]{2})-([0-9A-Za-z]{4})-([0-9A-Za-z]{2})$")
VIAL_BARCODE_PATTERN         = re.compile("^TCGA-([0-9A-Za-z]{2})-([0-9A-Za-z]{4})-([0-9A-Za-z]{3})$")
PORTION_BARCODE_PATTERN      = re.compile("^TCGA-([0-9A-Za-z]{2})-([0-9A-Za-z]{4})-([0-9A-Za-z]{3})-([0-9A-Za-z]{2})$")
ANALYTE_BARCODE_PATTERN      = re.compile("^TCGA-([0-9A-Za-z]{2})-([0-9A-Za-z]{4})-([0-9A-Za-z]{3})-([0-9A-Za-z]{3})$")
PLATE_BARCODE_PATTERN        = re.compile("^TCGA-([0-9A-Za-z]{2})-([0-9A-Za-z]{4})-([0-9A-Za-z]{3})-([0-9A-Za-z]{3})-([0-9A-Za-z]{4})$")
ALIQUOT_BARCODE_PATTERN      = re.compile("^TCGA-([0-9A-Za-z]{2})-([0-9A-Za-z]{4})-([0-9A-Za-z]{3})-([0-9A-Za-z]{3})-([0-9A-Za-z]{4})-([0-9A-Za-z]{2})$")
SLIDE_BARCODE_PATTERN        = re.compile("^TCGA-([0-9A-Za-z]{2})-([0-9A-Za-z]{4})-([0-9A-Za-z]{3})-([0-9A-Za-z]{2})-([TBM]S[0-9A-Za-z])$")
RPPA_PLATE_BARCODE_PATTERN   = re.compile("^TCGA-([0-9A-Za-z]{2})-([0-9A-Za-z]{4})-([0-9A-Za-z]{3})-([0-9A-Za-z]{2})-([0-9A-Za-z]{4})$")
RPPA_ALIQUOT_BARCODE_PATTERN = re.compile("^TCGA-([0-9A-Za-z]{2})-([0-9A-Za-z]{4})-([0-9A-Za-z]{3})-([0-9A-Za-z]{2})-([0-9A-Za-z]{4})-([0-9A-Za-z]{2})$")

# Order is based on frequency that I've seen these in data files. Full barcodes are most frequent in my experience.
VALID_BARCODE_PATTERNS = [ ALIQUOT_BARCODE_PATTERN,
                           SAMPLE_BARCODE_PATTERN,
                           PARTICIPANT_BARCODE_PATTERN,
                           VIAL_BARCODE_PATTERN,
                           PORTION_BARCODE_PATTERN,
                           ANALYTE_BARCODE_PATTERN,
                           PLATE_BARCODE_PATTERN,
                           RPPA_ALIQUOT_BARCODE_PATTERN,
                           RPPA_PLATE_BARCODE_PATTERN,
                           SLIDE_BARCODE_PATTERN
                         ]

# Example UUID (32 hexadecimal digits) : 0a013412-4929-4c11-a37a-643ef86c9c31
UUID_PATTERN = re.compile("^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$")

# Firehose sample id: BLCA-BL-A0C8-TP
FIREHOSE_SAMPLE_ID_PATTERN = re.compile("^([A-Z0-9]+-[A-Z0-9]{2}-[A-Z0-9]{4})-[A-Z0-9]+$")

# Firehose sample id: BLCAFFPE-BL-A0C8
FIREHOSE_FFPE_INDIVIDUAL_ID_PATTERN = re.compile("^([A-Z0-9]+)FFPE(-[A-Z0-9]{2}-[A-Z0-9]{4})$")

#===============================================================================
# Loadfiles 
#===============================================================================
TUMOR                        = "Tumor"
NORMAL                       = "Normal"
CONTROL                      = "Control"
TOTALS                       = "Totals"
PRIMARY_TUMOR_SAMPLE_TYPE    = "01"
FILE_ABSENT_CODE             = "__DELETE__"
SAMPLE_STAMP_EXTENSION      = ".samplestamp.txt"
SAMPLESTAMP_FILENAME_PATTERN = re.compile("^normalized\.([A-Za-z0-9]+)\.[0-9]{4}_[0-9]{2}_[0-9]{2}__[0-9]{2}_[0-9]{2}_[0-9]{2}\.samplestamp\.txt$")

SAMPLE_SET_TUPLE          = namedtuple('Sample_Set', 
                                       ["sample_set_id", "sample_id"])
SAMPLESTAMP_TUPLE         = namedtuple('Samplestamp',
                                       ['tcga_id',
                                        'platform',
                                        'tumor_type',
                                        'tumor_normal',
                                        'annotation_id',
                                        'hybridization_id',
                                        'archive',
                                        'archivefile',
                                        'sdrf_id',
                                        'extension',
                                        'httparchive',
                                        'httparchivefile',
                                        'httpsdrf',
                                        'firehose_id'])
SAMPLESTAMP_FIELDS        = SAMPLESTAMP_TUPLE(*SAMPLESTAMP_TUPLE._fields)
DATA_TYPE_TUPLE           = namedtuple('DataType',
                                       ['BCR',
                                        'CLINICAL',
                                        'CN',
                                        'LOWP',
                                        'METHYLATION',
                                        'MRNA',
                                        'MRNASEQ',
                                        'MRNASEQV2',
                                        'MIR',
                                        'MIRSEQ',
                                        'RPPA',
                                        'MAF',
                                        'WIG',
                                        'RAWMAF',
                                        'RAWWIG'])
DATA_TYPES                 = DATA_TYPE_TUPLE("BCR",
                                            "Clinical",
                                            "CN",
                                            "LowP",
                                            "Methylation",
                                            "mRNA",
                                            "mRNASeq",
                                            "mRNASeqV2",
                                            "miR",
                                            "miRSeq",
                                            "RPPA",
                                            "MAF",
                                            "WIG",
                                            "rawMAF",
                                            "rawWIG")
COLLAPSED_DATA_TYPES = list([DATA_TYPES.BCR, 
                            DATA_TYPES.CLINICAL, 
                            DATA_TYPES.CN, 
                            DATA_TYPES.LOWP, 
                            DATA_TYPES.METHYLATION, 
                            DATA_TYPES.MRNA, 
                            DATA_TYPES.MRNASEQ, 
                            DATA_TYPES.MIR, 
                            DATA_TYPES.MIRSEQ, 
                            DATA_TYPES.RPPA, 
                            DATA_TYPES.MAF,
                            DATA_TYPES.RAWMAF])
CORE_DATA_TYPES     = set([DATA_TYPES.CLINICAL, 
                           DATA_TYPES.CN, 
                           DATA_TYPES.METHYLATION, 
                           DATA_TYPES.MRNA, 
                           DATA_TYPES.MIR, 
                           DATA_TYPES.RPPA, 
                           DATA_TYPES.MAF,
                           DATA_TYPES.RAWMAF])
CORE_DATA_TYPES_SEQ = set([DATA_TYPES.CLINICAL, 
                           DATA_TYPES.CN, 
                           DATA_TYPES.METHYLATION, 
                           DATA_TYPES.MRNASEQ, 
                           DATA_TYPES.MIRSEQ, 
                           DATA_TYPES.RPPA, 
                           DATA_TYPES.MAF,
                           DATA_TYPES.RAWMAF])

#===============================================================================
# SDRF 
#===============================================================================
SDRF_PATHS_FILE_NAME               = 'sdrfPathsNew.txt'
SDRF_STATUS_FILE_NAME              = 'sdrfStatus.txt'
SDRF_UNPROCESSED_FILE_NAME         = 'sdrfUnprocessed.txt'
SDRF_CACHED_FILE_NAME              = 'sdrfPathsCached.txt'
SDRF_ERRORS_FILE_NAME              = 'sdrfErrors.txt'

#===============================================================================
# PATHS 
#===============================================================================
NORMALIZED = "normalized"
REDACTIONS = "redactions"
REF_DIR    = "ref_dir"

GDAC_BIN_DIR = "/xchip/tcga/Tools/gdac/bin/"
HTML2PNG     = os.path.join(GDAC_BIN_DIR, "html2png")
FISS         = os.path.join(GDAC_BIN_DIR, "fiss")

GDAC_DATA_DIR            = "/xchip/gdac_data"
NORMALIZED_DIR           = os.path.join(GDAC_DATA_DIR, NORMALIZED)
RUNS_DIR                 = os.path.join(GDAC_DATA_DIR, "runs")
REDACTIONS_DIR           = os.path.join(NORMALIZED_DIR, REDACTIONS)
REF_DIR                  = os.path.join(NORMALIZED_DIR, REF_DIR)
DICED_DATA_DIR           = os.path.join(NORMALIZED_DIR, "diced")
LOADFILE_DIR             = os.path.join(NORMALIZED_DIR, "loadfiles/normalized")
INGESTOR_STATUS_FILE_DIR = os.path.join(GDAC_DATA_DIR, "logs/gdac_ingestor/")
SDRF_STATUS_FILE_DIR     = os.path.join(NORMALIZED_DIR, "sdrf_status/")
NOZZLE_PATH              = "/xchip/tcga/Tools/gdac/bin/nozzle"
GDAC_MIRROR_DIR          = os.path.join(GDAC_DATA_DIR, 'dcc_mirror3/dcc_site')
GDAC_ANON_MIRROR_DIR     = os.path.join(GDAC_MIRROR_DIR,
                                        'tcga-data.nci.nih.gov/tcgafiles/ftp_auth/distro_ftpusers/anonymous/tumor')
GDAC_SECURE_MIRROR_DIR   = os.path.join(GDAC_MIRROR_DIR,
                                        'tcga-data-secure.nci.nih.gov/tcgafiles/ftp_auth/distro_ftpusers/tcga4yeo/tumor')
MIRROR_DCC_WGET_LOG_DIR  = os.path.join(GDAC_DATA_DIR,'logs/dcc_mirror')

MIRROR_ROOT         = "tcga-data.nci.nih.gov/tcgafiles/ftp_auth/distro_ftpusers"
DCC_SITE            = "dcc_site"
MIRROR_DIR          = os.path.join("dcc_mirror3", DCC_SITE, MIRROR_ROOT)
MIRROR_OVERLAY_DIR  = os.path.join("dcc_mirror_overlay", MIRROR_ROOT)
MIRROR_OVERLAY2_DIR = os.path.join("dcc_mirror_overlay2", MIRROR_ROOT)

DCC_MIRROR_DICER_LOCK_FILE = os.path.join(GDAC_DATA_DIR,'dcc_mirror3/control/DCC_MIRROR_DICER.lock')

#===============================================================================
# Timestamps 
#===============================================================================
SHORT_TIMESTAMP_STRING     = "\d{4}_[01]\d_[0-3]\d"
SHORT_TIMESTAMP_PATTERN    = re.compile("^%s$" % SHORT_TIMESTAMP_STRING)
LONG_TIMESTAMP_STRING      = "%s__[0-2]\d_[0-5]\d_[0-5]\d" % SHORT_TIMESTAMP_STRING
LONG_TIMESTAMP_PATTERN     = re.compile("^%s$" % LONG_TIMESTAMP_STRING)
LOADFILE_TIMESTAMP_PATTERN = re.compile("^normalized\.tcga_all_samples\.(%s)\.Sample\.loadfile\.txt$" % LONG_TIMESTAMP_STRING)

#===============================================================================
# DCC Webservices
#===============================================================================
UUID_MAPPING_WEBSERVICE_URL = "https://tcga-data.nci.nih.gov/uuid/uuidws/mapping/json/"
MAPPING_WS_UUID_URL         = UUID_MAPPING_WEBSERVICE_URL + "uuid/"
MAPPING_WS_BARCODE_URL      = UUID_MAPPING_WEBSERVICE_URL + "barcode/"

#===============================================================================
# Miscellaneous 
#===============================================================================
DEFAULT_AGGREGATES = ["PANCAN12", "COADREAD", "GBMLGG", "KIPAN", "STES"]
RUN_FLAGS_TUPLE = namedtuple('Run_Flags',
                             ['DICE',
                              'INJECT_MAF',
                              'MIRROR_DCC',
                              'MIRROR_DCC_XML',
                              'MIRROR_JAMBOREE',
                              'MIRROR_CACHE',
                              'MIRROR_OTHER'])
RUN_FLAGS       = RUN_FLAGS_TUPLE(*RUN_FLAGS_TUPLE._fields)

#===============================================================================
# Main
#===============================================================================
if __name__ == '__main__':
    t = "2013_10_20__12_15_36"
#     t = "2013_10_20"
    a = SHORT_TIMESTAMP_PATTERN.match(t)
    print a
    b = LONG_TIMESTAMP_PATTERN.match(t)
    print b
#     samplestamp_filename = "normalized.UCEC.2013_10_02__00_00_37.samplestamp.txt"
#     match_object = SAMPLESTAMP_FILENAME_PATTERN.match(samplestamp_filename)
#     if match_object:
#         print "Tumor Set: %s" % match_object.group(1)
