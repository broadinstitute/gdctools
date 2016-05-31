#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

gdcls: List data available in the GDC

@author: Timothy DeFreitas
@date:  2016_05_31
'''

# }}}
from __future__ import print_function

import json
import subprocess

from GDCtool import GDCtool
import lib.api as api


class gdcls(GDCtool):

    def __init__(self):
        super(gdcls, self).__init__(version="0.1.0")
        cli = self.cli

        desc =  'List available GDC data'
        cli.description = desc

        cli.add_argument('-e', '--expand', nargs='+',
                         help='Expand these nested fields')
        cli.add_argument('-f', '--fields', nargs='+')

        cli.add_argument('-n', '--num-results', default=-1, type=int,
                         help='return at most this many results')

        cli.add_argument('-p', '--page-size', default=500, type=int,
                         help='Server page size')

        #Optional overrides of config file
        cli.add_argument('endpoint', choices=['projects', 'cases', 'files', 'annotations'],
                         help='GDC mirror configuration file')

        cli.add_argument('filters', nargs='*', metavar='filter',
                         help="Search filters as 'key=value' pairs. E.g. project_id=TCGA-UVM")

    def build_params(self):
        '''Construct request parameters from the expand, fields, and filters arguments'''
        params = dict()

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
        super(gdcls, self).execute()
        opts = self.options
        params = self.build_params()
        endpoint = api.GDC_API_ROOT + self.options.endpoint
        result = api._query_paginator(endpoint, params, self.options.page_size, 1, self.options.num_results)
        print(json.dumps(result, indent=2))

# TODO: make more intelligent expansion of key=value pairs?
# E.g. project_id --> cases.samples.project_id for the cases endpoint
def filter_params(filters):
    '''Builds a dictionary of filters passed as 'key=value' pairs'''
    if filters is None: return d
    eq_filters = []

    #Build individual equals filters
    for filt in filters:
        key, value = filt.split("=")
        eq_filters.append(api._eq_filter(key, value))

    # If there is only one, return it, otherwise 'and' them together
    if len(eq_filters) == 1:
        return eq_filters[0]
    else:
        return api._and_filter(eq_filters)

if __name__ == "__main__":
    gdcls().execute()
