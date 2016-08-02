#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.
GDCQuery class and high-level API functions

@author: Timothy DeFreitas, David Heiman
@date:  2016_08_01
'''

# }}}

import requests
import json
import logging

logging.getLogger("requests").setLevel(logging.WARNING)

# TODO: integrate with lib/api
class GDCQuery(object):
    # Class variables
    ENDPOINTS = ('cases', 'files', 'projects')
    GDC_ROOT = 'https://gdc-api.nci.nih.gov/'

    # Queries returning more than this many results will log a warning
    WARN_RESULT_CT = 5000

    def __init__(self, endpoint, fields=None, expand=None,
                legacy=False, filters=None):
        assert(endpoint in GDCQuery.ENDPOINTS)
        self._endpoint = endpoint
        # Make copies of all mutable
        self._fields   = fields if fields else []
        self._expand   = expand if expand else []
        self._legacy   = legacy
        self._filters  = filters if filters else []

    def add_filter(self, field, value):
        self._filters.append(_eq_filter(field, value))
        return self

    def filters(self):
        return self._filters

    def add_fields(self, *fields):
        self._fields.extend(fields)
        return self

    def expand(self, *fields):
        self._expand.extend(fields)
        return self

    def url(self):
        '''For debugging purposes, build a PreparedRequest to show the url.'''
        req = requests.Request('GET', self._base_url(), params=self._params())
        r = req.prepare()
        return r.url

    def _base_url(self):
        _url = GDCQuery.GDC_ROOT
        if self._legacy: _url += 'legacy/'
        _url += self._endpoint
        return _url

    def _params(self):
        params = dict()
        if self._fields:
            params['fields'] = ','.join(self._fields)
        if self._expand:
            params['expand'] = ','.join(self._expand)
        if self._filters:
            if len(self._filters) == 1:
                params['filters'] = json.dumps(self._filters[0])
            else:
                params['filters'] = json.dumps(_and_filter(self._filters))
        return params

    def _query_paginator(self, page_size=500, from_idx=1, to_idx=-1):
        '''Returns list of hits, iterating over server paging'''
        endpoint = self._base_url()
        p = self._params()
        p['from'] = from_idx
        p['size'] = page_size

        # For pagination to work, the records must specify a sort order. This
        # lookup tells the right field to use based on the endpoint
        sort_lookup = { 'files' : 'file_id',
                        'cases' : 'case_id',
                        'projects' : 'project_id'}

        sort = sort_lookup[endpoint.rstrip('/').split('/')[-1]]
        p['sort'] = sort

        # Make initial call
        r = requests.get(endpoint, params=p)
        r_json = _decode_json(r)

        # Log any warnings in response, but don't raise an error yet
        _log_warnings(r_json)

        # Get first page of hits, and pagination data
        data = r_json['data']
        all_hits = data['hits']
        pagination = data['pagination']
        total = pagination['total'] if to_idx == -1 else to_idx

        # Some queries can return a large number of results, warn here
        if total > GDCQuery.WARN_RESULT_CT:
            logging.warning(str(total) + " files match this query, paging "
                            + "through all results may take some time")

        for from_idx in range(page_size+1, total, page_size):
            #Iterate over pages to get the remaning hits
            p['from'] = from_idx
            r = requests.get(endpoint, params=p)
            hits = _decode_json(r)['data']['hits']
            all_hits.extend(hits)

        self.hits = all_hits
        return all_hits # Chop off hits on the last page if they exceed to_idx

    def get(self, page_size=500):
        return self._query_paginator(page_size=page_size)


def get_projects(program, legacy=False):
    query = GDCQuery('projects', legacy=legacy)
    query.add_filter('program.name', program)
    query.add_fields('project_id')
    projects = [d['project_id'] for d in query.get()]
    return sorted(projects)


def get_data_categories(project, legacy=False):
    query = GDCQuery('projects', legacy=legacy)
    query.add_filter('project_id', project)
    query.add_fields('summary.data_categories.data_category')
    projects = query.get()

    #Sanity check
    if len(projects) != 1:
        raise ValueError("More than one project matched '" + project + "'")

    proj = projects[0]
    if 'summary' in proj:
        return [d['data_category'] for d in proj['summary']['data_categories']]
    else:
        return [] # Needed to protect against projects with no data


def get_project_files(project_id, data_category, workflow_type=None,
                      page_size=500, legacy=False):
    query = GDCQuery('files', legacy=legacy)
    query.add_filter("cases.project.project_id", project_id)
    query.add_filter("files.data_category", data_category)
    query.add_filter("access", "open")
    if workflow_type:
        query.add_filter('analysis.workflow_type', workflow_type)

    query.add_fields('file_id', 'file_name', 'cases.samples.sample_id',
                     'data_type', 'data_category', 'data_format',
                     'experimental_strategy', 'md5sum','platform','tags',
                     'center.namespace', 'cases.submitter_id',
                     'cases.project.project_id', 'analysis.workflow_type',
                     # For protein expression data
                     'cases.samples.portions.submitter_id',
                     # For aliquot-level data
                     'cases.samples.portions.analytes.aliquots.submitter_id')

    query.expand('cases', 'annotations', 'cases.samples')

    return query.get(page_size=page_size)


def download_file(uuid, file_name, legacy=False, chunk_size=4096):
    """Download a single file from GDC."""
    url = GDCQuery.GDC_ROOT
    if legacy: url += 'legacy/'
    url += 'data/' + uuid
    r = requests.get(url, stream=True)
    # TODO: Optimize chunk size
    # Larger chunk size == more memory, but fewer packets
    with open(file_name, 'wb') as f:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)

    # Return the response, which includes status_code, http headers, etc.
    return r


def get_program(project, legacy=False):
    '''Return the program name of a project.'''
    query = GDCQuery('projects', legacy=legacy)
    query.add_filter('project_id', project)
    query.add_fields('program.name')
    projects = query.get()

    #Sanity check
    if len(projects) != 1:
        raise ValueError("More than one project matched '" + project + "'")

    return projects[0]['program']['name']


def get_programs():
    '''Return list of programs in GDC.'''
    #TODO: eliminate hard coded values (no direct API call yet)
    return ["TCGA", "TARGET"]


# Module helpers
def _log_warnings(r_json):
    '''Check for warnings in a server response'''
    warnings = r_json['warnings']
    if warnings:
        warnmsg =  "GDC query produced a warning:\n"
        warnmsg += json.dumps(warnings, indent=2)
        warnmsg += "\nRequest URL: " + r.url
        logging.warning(warnmsg)


def _eq_filter(field, value):
    return {"op" : "=", "content" : {"field" : field, "value" : [value]}}


def _and_filter(filters):
    return {"op" : "and", "content" : filters}


def _decode_json(request):
    """ Attempt to decode response from request using the .json() method.

    If one cannot be decoded, raise a more useful error than the default by
    printing the text content, rather than just raising a ValueError"""
    try:
        return request.json()
    except ValueError:
        emsg = "No JSON object could be decoded from response. Content:\n"
        emsg += request.text
        raise ValueError(emsg)
