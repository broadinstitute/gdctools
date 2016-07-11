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
