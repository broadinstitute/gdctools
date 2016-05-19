#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

gdc_mirror: this file is part of gdctools.  See the <root>/COPYRIGHT
file for the SOFTWARE COPYRIGHT and WARRANTY NOTICE.

@author: Michael S. Noble
@date:  2016_05_18
'''

# }}}

import sys
from GDCtool import GDCtool

class gdc_mirror(GDCtool):

    def __init__(self):
        super(gdc_mirror, self).__init__(version="0.2.0")
        cli = self.cli

        desc =  'Create local mirror of the data from arbitrary programs '\
                'and projects warehoused at the Genomic Data Commons (GDC)\n'
        cli.description = desc

    def execute(self):
        super(gdc_mirror, self).execute()
        opts = self.options

if __name__ == "__main__":
    gdc_mirror().execute()
