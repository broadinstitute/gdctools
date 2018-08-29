#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

gdc_list: List/query operational features of GDCtools, EITHER from a
          a local instance or the remote GDC server.

@author: Michael S. Noble, Timothy DeFreitas
@date:  2017_05_08
'''

from __future__ import print_function
import json
import types
from collections import defaultdict
from gdctools.GDCtool import GDCtool
from gdctools.GDCcore import *
from gdctools.lib.api import GDCQuery, _eq_filter as eq_filter, _and_filter as and_filter

# }}}

features = defaultdict(lambda:None)

def features_identify():
    for name,sym in globals().items():
        if name.startswith("feature_") and isinstance(sym, types.FunctionType):
            features[name[8:]] = sym

def feature_what(args):
    ''' Display entire set of GDCtools features that may be queried'''
    for name in sorted(features.keys()):
        print("%-12s %s" % (name, features[name].func_doc))

def feature_submitted(args):
    ' List the names of programs which have submitted data to the GDC.\n'\
    '\t      The difference between this and \'programs\' is that the latter\n'\
    '\t      is a subset of \'submitted,\' indicating which submissions have\n'\
    '\t      been processed by GDC and exposed for public download.'
    call_gdc_api("submission", args)

def feature_annotations(args):
    ''' List annotations attached to patient cases at the GDC'''
    call_gdc_api("annotations", args)

def feature_cases(args):
    ''' List the patient cases across all projects/programs at the GDC'''
    def walk(results_list):
        print("feature_cases: length(results) = %d" % len(results_list))
        print("Submitter_Case_ID\tDisease_Type\tSubmitter_Sample_ID\tGDC_Sample_ID")
        for case in sorted(results_list, key=lambda case: case["disease_type"]):
            case = attrdict(case)
            if not case.sample_ids:
                case.sample_ids = case.submitter_sample_ids = [None]
            for i in xrange(len(case.sample_ids)):
                print("%s\t%s\t%s\t%s" % ( case.submitter_id, case.disease_type,
                            case.submitter_sample_ids[i], case.sample_ids[i]))
    call_gdc_api("cases", args, walk)

def feature_files(args):
    ''' List the files in all projects/programs at the GDC'''
    call_gdc_api("files", args)

def feature_projects(args):
    ''' Give name/disease/site (in TSV form) of projects stored at GDC'''

    def walk(results_list):
        print("Project_ID\tDisease\tPrimary_Site")
        for p in sorted(results_list, key=lambda proj: proj["project_id"]):
            p = attrdict(p)
            print("%s\t%s\t%s" % (p.project_id, p.name, p.primary_site[0]))

    call_gdc_api("projects", args, walk)

def feature_programs(args):
    ''' List the names of all programs (data sets) warehoused at the GDC'''
    call_gdc_api("programs", args)

def call_gdc_api(feature, args, callback=None):
    ''' Issue GDC API call, first parsing filters/fields/expand args from CLI'''

    query = GDCQuery(feature)

    # Ask that result set be pruned, by applying KEY=VALUE filters
    for filt in args.filters:
        key, value = filt.split("=")
        query.add_eq_filter(key, value)

    # Additional fields to include in each item of result set
    #if args.fields:
    #    query.add_fields(*(tuple(args.fields)))

    # See GDC docs for meaning of expand
    #if args.expand:
    #    query.add_expansions(*(tuple(args.expand)))

    results = query.get()
    if not callback or args.raw:
        print(json.dumps(results, indent=2))
    else:
        callback(results)

class gdc_list(GDCtool):

    def __init__(self):

        description = 'Quicklook tool for examining datasets available at the '\
            'GDC, following the\nsyntax of portal.gdc.cancer.gov/query.  '\
            'Examples:\n\n'\
            '    # Show datasets exposed via the GDC public API\n' \
            '    gdc_list programs\n\n' \
            '    # Show all datasets submitted to GDC, including non-public\n' \
            '    gdc_list submitted\n\n' \
            '    # Shows patient cases in the TCGA adrenocortical cohort\n'\
            '    gdc_list cases project.project_id=TCGA-ACC\n\n' \
            '    # Shows metadata of all files in TCGA uveal melanoma cohort\n'\
            '    gdc_list files cases.project.project_id=TCGA-UVM\n\n' \
            '    # Show what queries may be performed, in summary form\n'\
            '    gdc_list what\n\n' \
            '    # Show open-accss clinical data in TCGA ovarian cohort\n'\
            '    gdc_list files cases.project.project_id=TCGA-OV files.data_category=Clinical files.access=open'

        super(gdc_list, self).__init__("0.1.2", description)
        cli = self.cli
        #cli.add_argument('-e', '--expand', nargs='+',
        #    help='Expand these nested fields')
        #cli.add_argument('-f', '--fields', nargs='+')
        cli.add_argument('-n', '--num-results', default=-1, type=int,
            help='return at most this many results')
        cli.add_argument('-r', '--raw', action='store_true',
            help='Some features process the payload returned by the GDC API '\
                 'to simplify interpretion; this flag turns that off, '\
                 'permitting direct inspection of the raw payload')
        cli.add_argument('-s', '--page-size', default=500, type=int,
            help='Server page size')
        cli.add_argument('feature',
            help='Which feature to query/list (case insensitive). The special '\
                 'feature of \'what\' may be given here, to display the names '\
                 'of all features that may be queried')
        cli.add_argument('filters', nargs='*', metavar='filter',
            help="Prune with key=value filters, e.g. program.name=TCGA")

        features_identify()

    def execute(self):
        super(gdc_list, self).execute()
        args = self.options
        feature = features[args.feature]
        if feature:
            feature(args)
        else:
            gabort(1, "Unsupported feature: " + args.feature)

    def config_supported(self):
        return False

def main():
    gdc_list().execute()

if __name__ == "__main__":
    main()
