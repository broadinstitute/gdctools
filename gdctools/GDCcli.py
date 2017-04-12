#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

This file is part of GDCtools.  See the <root>/COPYRIGHT file for the
SOFTWARE COPYRIGHT and WARRANTY NOTICE.

@author: Michael S. Noble
@date:  2016-05-18
'''

# }}}

import sys
import argparse
from gdctools.GDCcore import *

# Stop Python from complaining when I/O pipes are closed
from signal import signal, SIGPIPE, SIG_DFL
signal(SIGPIPE, SIG_DFL)

class GDCcli(argparse.ArgumentParser):
    ''' Encapsulates interactions with the command line, making it easy for
    all gdctools to share a core set of common CLI self.args.  '''

    ALL_REMAINING_ARGS = argparse.REMAINDER

    def __init__(self, descrip=None, version=""):

        if not descrip:
            descrip =  'GDCtools: a suite of CLI tools plus Python bindings\n'
            descrip += 'to simplify interaction with the Genomic Data Commons\n'
            descrip += 'and perform useful data processing operations.  The\n'
            descrip += 'GDCtools suite was inspired by the data processing\n'
            descrip += 'done by Firehose & FireBrowse in the Broad Institute\n'
            descrip += 'GDAC, as part of the The Cancer Genome Atlast.\n'

        version = version + " (GDCtools: " + GDCT_VERSION + ")"
        self.version = version
        super(GDCcli, self).__init__(description=descrip,
                formatter_class=argparse.RawDescriptionHelpFormatter)

        # Note that args with nargs=+ will be instantiated as lists
        self.add_argument('--verbose', dest='verbose', action='count', help=\
                'Each time specified, increment verbosity level [%(default)s]')
        self.add_argument('--version',action='version', version=version)
        self.add_argument('-c','--config', nargs='+', type=argparse.FileType('r'),
                            help='One or more configuration files')

        self.add_argument('-l', '--log-dir',
                            help='Directory where logfiles will be written')
        self.add_argument('-g', '--programs', nargs='+', metavar='program',
                         help='Process data ONLY from these GDC programs')
        self.add_argument('-p', '--projects', nargs='+', metavar='project',
                         help='Process data ONLY from these GDC projects')
        self.add_argument('--cases', nargs='+', metavar='case_id',
                         help='Process data ONLY from these GDC cases')
        self.add_argument('datestamp', nargs='?', help='Use GDC data for a'
                          ' specific date. If omitted, the latest available'
                          ' data will be used.')

    def parse_args(self):
        return super(GDCcli,self).parse_args()

    def ok_to_continue(self, message=None):

        if message:
            gprint(message)

        gprint("If this is OK, shall I continue? (Y/N) [N]",end=' ')
        sys.stdout.flush()
        answer = sys.stdin.readline().rstrip('\n')
        gprint('')
        if answer not in ["y", "yes", "Y", "Yes", '1', 'true']:
            gprint("OK, exiting without doing anything further.")
            sys.exit(0)

if __name__ == "__main__":
    cli = GDCcli()
    options = cli.parse_args()
    gprint(str(options))
