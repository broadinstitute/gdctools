# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

gdc_mirror: this file is part of gdctools.  See the <root>/COPYRIGHT
file for the SOFTWARE COPYRIGHT and WARRANTY NOTICE.

@author: Timothy DeFreitas
@date:  2016_05_26
'''

# }}}

import os
import re

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

# String Formats
LOGGING_FMT = '%(asctime)s[%(levelname)s]: %(message)s'
_TIMESTAMP_PATTERN = "^\d{4}_[01]\d_[0-3]\d__[0-2]\d_[0-5]\d_[0-5]\d$"
TIMESTAMP_REGEX = re.compile(_TIMESTAMP_PATTERN)

#TODO: Configurable?
REPORT_DATA_TYPES = ('BCR', 'Clinical', 'CN', 'mRNA', 'miR', 'MAF')

# Used by the dicer and report generator to map to top-level data types
# TODO: add this as a column in the annotations_table?
ANNOT_TO_DATATYPE = {
    'clinical__primary'         : 'Clinical',
    'clinical__biospecimen'     : 'BCR',
    'CNV__snp6'                 : 'CN',
    'CNV_no_germline__snp6'     : 'CN',
    'miR__geneExp'              : 'miR',
    'miR__isoformExp'           : 'miR',
    'mRNA__geneExp__FPKM'       : 'mRNA',
    'mRNA__geneExpNormed__FPKM' : 'mRNA',
    'mRNA__counts__FPKM'        : 'mRNA',
    'SNV__mutect'               : 'MAF'
}
