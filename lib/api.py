#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

Core API functions to interface with Genome Data Commons

@author: Timothy DeFreitas, David Heiman
@date:  2016_05_26
'''

# }}}
from __future__ import print_function
import requests
import subprocess
import json
import os
import sys

GDC_API_ROOT = 'https://gdc-api.nci.nih.gov/'

def get_programs():
    '''Return list of programs in GDC.'''
    #TODO: eliminate hard coded values (no direct API call yet)
    return ["TCGA", "TARGET"]

def get_program(project):
    '''Return the program name of a project.'''
    endpoint = GDC_API_ROOT + 'projects'
    filt = _eq_filter("project_id", project)
    params = {
                'fields' : 'program.name',
                'filters' : json.dumps(filt)
             }
    r = requests.get(endpoint, params=params)
    hits = r.json()['data']['hits']
    #Sanity Check
    if len(hits) != 1:
        raise ValueError("Uh oh, more than one project matched '" + project + "'")
    return hits[0]['program']['name']

def get_projects(program, page_size=500):
    endpoint = GDC_API_ROOT + 'projects'
    filt = _eq_filter('program.name', program)
    params = {'fields': 'project_id', 'filters': json.dumps(filt)}
    return [obj['project_id'] for obj in _query_paginator(endpoint, params, page_size)]

def get_data_categories(project):
    endpoint = GDC_API_ROOT + 'projects'
    filt = _eq_filter("project_id", project)
    params = {
                'fields' : 'summary.data_categories.data_category',
                'filters' : json.dumps(filt)
             }

    r = requests.get(endpoint, params=params)
    hits = r.json()['data']['hits']

    #Sanity Check
    if len(hits) != 1:
        raise ValueError("Uh oh, more than one project matched '" + project + "'")

    #Some data types still have no data, like TCGA-LCML, so check to see if 'summary' is a valid field
    categories = [obj['data_category'] for obj in hits[0]['summary']['data_categories']] if 'summary' in hits[0] else []
    return categories

def get_files(project_id, data_category, exclude_ffpe=True, page_size=500):
    endpoint = 'https://gdc-api.nci.nih.gov/files'
    proj_filter = _eq_filter("cases.project.project_id", project_id)
    data_filter = _eq_filter("data_category", data_category)
    acc_filter = _eq_filter("access", "open")
    filter_list = [proj_filter, data_filter, acc_filter]
    if 'TCGA' in project_id and exclude_ffpe and data_category not in ['Clinical', 'Biospecimen']:
        filter_list.append(_eq_filter("cases.samples.is_ffpe", "false"))
    qfilter = _and_filter(filter_list)

    fields = ['file_id', 'file_name', 'cases.samples.sample_id', 'data_type',
              'data_category', 'data_format', 'experimental_strategy', 'md5sum',
              'platform','tags', 'center.namespace', 'cases.submitter_id',
              'cases.project.project_id', 'analysis.workflow_type']

    if data_category == 'Protein Expression':
        fields.append('cases.samples.portions.submitter_id')
    elif data_category not in ['Clinical', 'Biospecimen']:
        fields.append('cases.samples.portions.analytes.aliquots.submitter_id')
    # TODO: When MAFs become available, we will need cases.samples.submitter_id
    # in order to determine filenames to create during dicing

    params = {
                'fields' : ','.join(fields),
                'expand' : 'cases,annotations,cases.samples',
                'filters' : json.dumps(qfilter),
             }

    return _query_paginator(endpoint, params, page_size)

def get_file(uuid, file_name):
    """Download a single file from GDC."""
    curl_args =  ["curl", "--fail", "-o", file_name, GDC_API_ROOT+ "data/" + uuid]
    return subprocess.check_call(curl_args)


def _query_paginator(endpoint, params, size=500, from_idx=1, to_idx=-1):
    '''Returns list of hits, iterating over server paging'''
    p = params.copy()
    p['from'] = from_idx
    p['size'] = size

    # Make initial call
    r = requests.get(endpoint, params=p)

    # Get pagination data
    data = r.json()['data']
    all_hits = data['hits']
    pagination = data['pagination']
    total = pagination['total'] if to_idx == -1 else to_idx

    for from_idx in range(size+1, total, size):
        #Iterate over pages to get the remaning hits
        p['from'] = from_idx
        r = requests.get(endpoint, params=p)

        hits = r.json()['data']['hits']

        all_hits.extend(hits)

    return all_hits[:total] # Chop off hits on the last page if they exceed to_idx

## Helpers to generate valid query filters
def _eq_filter(field, value):
    return {"op" : "=", "content" : {"field" : field, "value" : [value]}}

def _and_filter(filters):
    return {"op" : "and", "content" : filters}
