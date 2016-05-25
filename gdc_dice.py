#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

gdc_mirror: this file is part of gdctools.  See the <root>/COPYRIGHT
file for the SOFTWARE COPYRIGHT and WARRANTY NOTICE.

@author: Timothy DeFreitas
@date:  2016_05_25
'''

# }}}
from __future__ import print_function
import logging
import json
import csv
import os
import sys
from pkg_resources import resource_filename #@UnresolvedImport
from gdac_lib.converters import seg as gdac_seg
from gdac_lib.converters import clinical as gdac_clin
from gdac_lib.Constants import GDAC_BIN_DIR
from gdac_lib.utilities.CommonFunctions import timetuple2stamp
from gdac_lib.utilities.ioUtilities import safeMakeDirs

from GDCtool import GDCtool
import translator
import gdc

class gdc_dicer(GDCtool):

    def __init__(self):
        super(gdc_dicer, self).__init__(version="0.1.0")
        cli = self.cli

        desc =  'Dice data from a Genomic Data Commons (GDC) mirror'
        cli.description = desc

        cli.add_argument('-m', '--mirror-directory',
                         help='Root folder of mirrored GDC data')
        cli.add_argument('-d', '--dice-directory', 
                         help='Root ')
        cli.add_argument('--dry-run', action='store_true', 
                         help="Show expected operations, but don't perform dicing")
        cli.add_argument('-g', '--programs', nargs='+', metavar='program',
                         help='Mirror data from these cancer programs')
        cli.add_argument('-p', '--projects', nargs='+', metavar='project',
                         help='Mirror data from these projects')
        cli.add_argument('datestamp', nargs='?',
                         help='Dice using metadata from a particular date.'\
                         'If omitted, the latest version will be used')



    def dice(self):
        mirror_root = self.options.mirror_directory
        diced_root = self.options.dice_directory
        trans_dict = translator.build_translation_dict(resource_filename(__name__,
                                                       "Harmonized_GDC_translation_table_FH.tsv"))
        timestamp = timetuple2stamp()

        #Iterable of programs, either user specified or discovered from folder names in the diced root
        if self.options.programs is not None:
            programs = self.options.programs
        else:
            programs = immediate_subdirs(mirror_root)

        for program in programs:
            diced_prog_root = os.path.join(diced_root, program)
            mirror_prog_root = os.path.join(mirror_root, program)
            if self.options.projects is not None:
                projects = self.options.projects
            else:
                projects = immediate_subdirs(mirror_prog_root)

            for project in projects:
                raw_project_root = os.path.join(mirror_prog_root, project)
                diced_project_root = os.path.join(diced_prog_root, project)

                if self.options.datestamp is None:
                    metadata = translator.get_metadata(raw_project_root)
                else:
                    metadata = translator.get_metadata(raw_project_root, self.options.datestamp)

                for files in metadata:
                    if len(files) > 0:
                        for f in files:
                            translator.dice(f, trans_dict, raw_project_root, diced_project_root,
                         timestamp, dry_run=self.options.dry_run)



    def execute(self):
        super(gdc_dicer, self).execute()
        opts = self.options
        logging.basicConfig(format='%(asctime)s[%(levelname)s]: %(message)s',
                            level=logging.INFO)
        self.dice()


def immediate_subdirs(path):
    return [d for d in os.listdir(path) 
            if os.path.isdir(os.path.join(path, d))]

if __name__ == "__main__":
    gdc_dicer().execute()
