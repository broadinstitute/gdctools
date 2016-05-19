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
from GDCcore import *

# Stop Python from complaining when I/O pipes are closed
from signal import signal, SIGPIPE, SIG_DFL
signal(SIGPIPE, SIG_DFL)

class GDCcli(argparse.ArgumentParser):
    ''' Encapsulates interactions with the command line, making it easy for
    all mdbtools to share a core set of common CLI self.args.  '''

    ALL_REMAINING_ARGS = argparse.REMAINDER

    def __init__(self, descrip=None, version=None):
    
        if not descrip:
            descrip =  'GDCtools: a suite of CLI tools to simplify interaction\n'
            descrip += 'with MongoDB, directly from the *NIX command line and\n'
            descrip += 'little to no JavaScript coding required.\n'

        if not version:
            version = GDCT_VERSION

        super(GDCcli,self).__init__(description=descrip,
                formatter_class=argparse.RawDescriptionHelpFormatter)

        self.add_argument('--verbose', dest='verbose', action='count', 
                help='set verbosity level [%(default)s]')
        self.add_argument('--version',action='version',version=version)
        self.version = version

    def parse_args(self):

        args = super(GDCcli,self).parse_args()
        return args

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
