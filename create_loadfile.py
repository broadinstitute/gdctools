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

from GDCtool import GDCtool
import translator
import gdc

import os
import csv

class create_loadfile(GDCtool):

    def __init__(self):
        super(create_loadfile, self).__init__(version="0.1.0")
        cli = self.cli

        desc =  'Create a Firehose loadfile from diced Genomic Data Commons (GDC) data'
        cli.description = desc

        cli.add_argument('-d', '--dice-directory', 
                         help='Root of diced data directory')
        cli.add_argument('-l', '--loadfile-directory', 
                         help='Where generated loadfiles will be placed')
        cli.add_argument('datestamp', nargs='?',
                         help='Dice using metadata from a particular date.'\
                         'If omitted, the latest version will be used')

    def create_loadfiles(self):
        #Iterate over programs/projects in diced root
        diced_root = os.path.abspath(self.options.dice_directory)
        load_root = os.path.abspath(self.options.loadfile_directory)

        for program in immediate_subdirs(diced_root):
            prog_root = os.path.join(diced_root, program)
            projects = immediate_subdirs(prog_root)
            
            for project in projects:
                for annot, reader in get_diced_metadata(project, self.options.datestamp):
                    print(annot, len(reader))




    def execute(self):
        super(create_loadfile, self).execute()
        opts = self.options
        logging.basicConfig(format='%(asctime)s[%(levelname)s]: %(message)s',
                            level=logging.INFO)
        self.create_loadfiles()

# Could use get_metadata, but since the loadfile generator is separate, it makes sense to divorce them
def get_diced_metadata(project_root, datestamp=None):
    project_root = project_root.rstrip(os.path.sep)
    project = os.path.basename(project_root)

    for dirpath, dirnames, filenames in os.walk(project_root, topdown=True):
        # Recurse to meta subdirectories 
        if os.path.basename(os.path.dirname(dirpath)) == project:
            for n, subdir in enumerate(dirnames):
                if subdir != 'meta': del dirnames[n]

        if os.path.basename(dirpath) == 'meta':
            #If provided, only use the metadata for a given date, otherwise use the latest metadata file
            meta_files =  sorted(filename for filename in filenames \
                                 if datestamp is None or datestamp in filename)

            annot="Unknown"
            print(dirpath)
            
            if len(meta_files) > 0:
                with open(os.path.join(dirpath, meta_files[-1])) as f:
                    #Return the annotation name, and a dictReader for the metadata
                    yield  annot, csv.DictReader(f, delimiter='\t')

def immediate_subdirs(path):
    return [d for d in os.listdir(path) 
            if os.path.isdir(os.path.join(path, d))]


if __name__ == "__main__":
    create_loadfile().execute()
