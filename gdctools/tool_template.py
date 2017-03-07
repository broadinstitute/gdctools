#!/usr/bin/env python
# encoding: utf-8

# Template file for gdctools: to use this, simply copy to <TOOLNAME>.py
# and edit as follows:
#   global search/replace TOOLNAME with name of GDC tool (e.g. gdcls)
#   edit the <DATE> field in the header
#   customize __init__() to add/change: version, flags and description
#   write custom content,functions etc to perform the work of the tool
#   customize execute() as needed to reflect those custom functions etc
#   then remove this entire comment section

# Front Matter {{{
'''
Copyright (c) 2017 The Broad Institute, Inc.  All rights are reserved.

TOOLNAME: this file is part of gdctools.  See the <root>/COPYRIGHT
file for the SOFTWARE COPYRIGHT and WARRANTY NOTICE.

@author: Michael S. Noble
@date:  <DATE>
'''

# }}}

from GDCtool import GDCtool

class TOOLNAME(GDCtool):

    def __init__(self):
        super(TOOLNAME, self).__init__(version="0.2.0")

        #desc = 'TOOLNAME description \n\n'
        #desc += 'MORE TOOLNAME description ...\n'
        #opts.description = desc

        # Optional arguments (if any)
        #opts = self.options
        #opts.add_argument('-w', '--what', default='all',

        # Positional (required) arguments (if any)
        #opts.add_argument('-w', '--what', default='all',

    def execute(self):
        super(TOOLNAME, self).execute()

if __name__ == "__main__":
    tool = TOOLNAME()
    tool.execute()
