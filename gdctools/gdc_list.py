#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

gdc_list: List data available in the GDC

@author: Timothy DeFreitas, Michael S. Noble
@date:  2016_10_19
'''

# }}}

from __future__ import print_function
import json
from collections import defaultdict

from gdctools.GDCtool import GDCtool
from gdctools.lib.api import GDCQuery, _eq_filter as eq_filter, _and_filter as and_filter

class gdc_list(GDCtool):

    def __init__(self):
        super(gdc_list, self).__init__(version="0.1.1", logging=False)
        cli = self.cli

        cli.description = 'List metadata available from toplevel endpoints:\n\n'\
            '\tprojects | cases | files | annotations | submission | programs'\
            '\n\nEndpoints will be converted to lowercase before the API call '\
            '\nis issued to GDC. Note that "submission" and "programs" are\n'\
            'related, but only "submission" is an actual GDC endpoint. The\n'\
            'Broad Institute has requested that a "programs" endpoint be\n'\
            'added, but at present it is only implemented as a convenience\n'\
            'function in the GDCtools package.  The difference between them\n'\
            'is that "programs" is a subset of "submission," indicating '\
            'which\nsubmissions have actually been exposed for public download.'

        cli.add_argument('-e', '--expand', nargs='+',
                         help='Expand these nested fields')
        cli.add_argument('-f', '--fields', nargs='+')

        cli.add_argument('-n', '--num-results', default=-1, type=int,
                         help='return at most this many results')

        cli.add_argument('-s', '--page-size', default=500, type=int,
                         help='Server page size')

        #Optional overrides of config file
        cli.add_argument('endpoint', help='Which endpoint to query/list')

        cli.add_argument('filters', nargs='*', metavar='filter',
                         help="Search filters as 'key=value' pairs. E.g. project_id=TCGA-UVM")

    def build_params(self):
        '''Construct request parameters from the expand, fields, and filters arguments'''
        params = defaultdict(lambda:None)

        # Add search filters
        if len(self.options.filters) > 1:
            filters = filter_params(self.options.filters)
            params['filters'] = json.dumps(filters)

        # Add expansions
        if self.options.expand is not None:
            params['expand'] = ','.join(self.options.expand)

        if self.options.fields is not None:
            params['fields'] = ','.join(self.options.fields)

        return params

    def execute(self):
        super(gdc_list, self).execute()
        params = self.build_params()
        query = GDCQuery(self.options.endpoint,
                         filters=params['filters'],
                         fields=params['fields'],
                         expand=params['expand'])
        print(json.dumps(query.get(), indent=2))

def filter_params(filters):
    '''Builds a dictionary of filters passed as 'key=value' pairs'''
    # TODO: make more intelligent expansion of key=value pairs?
    # E.g. project_id --> cases.samples.project_id for the cases endpoint
    if filters is None: return dict()
    eq_filters = []

    #Build individual equals filters
    for filt in filters:
        key, value = filt.split("=")
        eq_filters.append(eq_filter(key, value))

    # If there is only one, return it, otherwise 'and' them together
    if len(eq_filters) == 1:
        return eq_filters[0]
    else:
        return and_filter(eq_filters)

def main():
    gdc_list().execute()

if __name__ == "__main__":
    main()
