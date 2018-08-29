#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.
GDCQuery class and high-level API functions

@author: Timothy DeFreitas, David Heiman, Michael S. Noble
@date:  2016_11_10
'''

# }}}

import requests
import json
import logging
import subprocess
import os

__legacy = False
__verbosity = 0
logging.getLogger("requests").setLevel(logging.WARNING)

class GDCQuery(object):
    # Class variables
    ENDPOINTS = ('cases', 'files', 'programs', 'projects', 'submission')
    GDC_ROOT = 'https://api.gdc.cancer.gov/'

    # Queries returning more than this many results will log a warning
    WARN_RESULT_CT = 5000

    def __init__(self, endpoint, fields=None, expand=None, filters=None):
        self._endpoint = endpoint.lower()               # normalize to lowercase
        assert(endpoint in GDCQuery.ENDPOINTS)
        # Make copies of all mutable
        self._fields   = fields if fields else []
        self._expand   = expand if expand else []
        self._filters  = filters if filters else []

    def add_eq_filter(self, field, value):
        self._filters.append(_eq_filter(field, value))
        return self

    def add_neq_filter(self, field, value):
        self._filters.append(_neq_filter(field, value))
        return self

    def add_in_filter(self, field, values):
        self._filters.append(_in_filter(field,values))

    def filters(self):
        return self._filters

    def add_fields(self, *fields):
        self._fields.extend(fields)
        return self

    def add_expansions(self, *fields):
        self._expand.extend(fields)
        return self

    def url(self):
        '''For debugging purposes, build a PreparedRequest to show the url.'''
        req = requests.Request('GET', self._base_url(), params=self._params())
        r = req.prepare()
        return r.url

    def _base_url(self):
        url = GDCQuery.GDC_ROOT
        if get_legacy(): url += 'legacy/'
        url += self._endpoint
        return url

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

    def _query_paginator(self, page_size=500, from_idx=0, to_idx=-1):
        '''Returns list of hits, iterating over server paging'''
        endpoint = self._base_url()
        p = self._params()
        p['from'] = from_idx
        p['size'] = page_size

        # For pagination to work, the records must specify a sort order. This
        # lookup tells the right field to use based on the endpoint
        sort_lookup = { 'files' : 'file_id',
                        'cases' : 'case_id',
                        'projects' : 'project_id',
                        'submission': 'links'}

        endpoint_name = endpoint.rstrip('/').split('/')[-1]
        p['sort'] = sort_lookup.get(endpoint_name, "")

        # Make initial call
        r = requests.get(endpoint, params=p)
        if get_verbosity():
            print("\nGDC query: %s\n" % r.url)
        r_json = _decode_json(r)

        # Log any warnings in response, but don't raise an error yet
        _log_warnings(r_json, r.url)

        # GDC 'submission' endpoint is inconsistent (does not yet return results
        # within a {"data": {"hits": … } }  JSON block--so we work around here.
        if endpoint_name == 'submission':
            results = r_json['links']
            results = [ program.split('/')[-1] for program in results ]
            self.hits = results
            return results

        # The 'programs' endpoint does not actually exist in GDC api (but has
        # been requested by Broad). Until then we fake it for convenience.
        if endpoint_name == 'programs':
            self.hits = get_programs()
            return self.hits

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

def get_projects(program=None):
    query = GDCQuery('projects')
    if program:
        query.add_eq_filter('program.name', program)
    query.add_fields('project_id')
    projects = [d['project_id'] for d in query.get()]
    return sorted(projects)

def get_project_from_cases(cases, program=None):
    if not cases: return []
    query = GDCQuery('cases')
    query.add_in_filter('submitter_id', cases)
    query.add_fields('project.project_id')
    projects = [p['project']['project_id'] for p in query.get()]
    return sorted(set(projects))

def get_categories(project):
    query = GDCQuery('projects')
    query.add_eq_filter('project_id', project)
    query.add_fields('summary.data_categories.data_category')
    projects = query.get()

    #Sanity check
    if len(projects) > 1:
        raise ValueError("More than one project matched '" + project + "'")

    proj = projects[0]
    if 'summary' in proj:
        return [d['data_category'] for d in proj['summary']['data_categories']]
    else:
        return [] # Needed to protect against projects with no data

def get_project_files(project_id, data_category, workflow_type=None, cases=None,
                      page_size=500):
    query = GDCQuery('files')
    query.add_eq_filter("cases.project.project_id", project_id)
    query.add_eq_filter("files.data_category", data_category)
    query.add_eq_filter("access", "open")

    if not __legacy:
        if workflow_type:
            query.add_eq_filter('analysis.workflow_type', workflow_type)
        query.add_fields('analysis.workflow_type')

    if cases:
        query.add_in_filter('cases.submitter_id', cases)

    query.add_fields('file_id', 'file_name', 'cases.samples.sample_id',
                     'data_type', 'data_category', 'data_format',
                     'experimental_strategy', 'md5sum','platform','tags',
                     'center.namespace', 'cases.submitter_id',
                     'cases.project.project_id',
                     # For protein expression data
                     'cases.samples.portions.submitter_id',
                     # For aliquot-level data
                     'cases.samples.portions.analytes.aliquots.submitter_id')

    # Prune Clinical/Biospecimen data, by avoiding download/mirror of
    #   - path reports/images (Data Type: Slide Image), as they can be huge
    #   - Biotab files, as redundant with BCR XML (and incomplete from TCGA)
    # But note that this is better done with a config file (see issue 73)
    if data_category == "Biospecimen":
        query.add_eq_filter("data_type", "Biospecimen Supplement")
        query.add_neq_filter("data_format", "BCR Biotab")
    elif data_category == "Clinical":
        query.add_neq_filter("data_format", "BCR Biotab")

    query.add_expansions('cases', 'annotations', 'cases.samples')
    return query.get(page_size=page_size)

def curl_exists():
    """ Return true if curl can be executed on this system """
    try:
        DEV_NULL = open(os.devnull, 'w')
        subprocess.check_call(['curl', '-V'],
                               stdout=DEV_NULL, stderr=subprocess.STDOUT)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False

def py_download_file(uuid, file_name, chunk_size=4096):
    """Download a single file from GDC."""
    url = GDCQuery.GDC_ROOT
    if __legacy: url += 'legacy/'
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

def curl_download_file(uuid, file_name, max_time=180):
    """Download a single file from the GDC, using cURL"""
    url = GDCQuery.GDC_ROOT
    if __legacy: url += 'legacy/'
    url += 'data/' + uuid
    curl_args = ['curl', '--max-time', str(max_time), '--fail', '-o', file_name, url]
    return subprocess.check_call(curl_args)

def get_program(project):
    '''Return the program name of a project.'''
    query = GDCQuery('projects')
    query.add_eq_filter('project_id', project)
    query.add_fields('program.name')
    projects = query.get()

    # Sanity check
    if len(projects) > 1:
        raise ValueError("More than one project matched '" + project + "'")
    elif len(projects) == 0:
        raise ValueError("No project matched '" + project + "'")

    return projects[0]['program']['name']

def get_programs(projects=None):
    '''Return list of programs that have data EXPOSED in GDC.  Note that this
       may be different from the set of programs that have SUBMITTED data to
       the GDC, because (a) it takes time to validate submissions before GDC
       will make them public, and (b) GDC does only periodic data releases.
       An optional projects parameter can be passed to prune the list of
       programs to those that have submitted data to the specified project(s)
       '''

    if projects:
        projects = list(set(projects) & set(get_projects()))
    else:
        projects = get_projects()
    programs  = [ proj.split('-')[0] for proj in projects]
    return list(set(programs))

# Module helpers
def _log_warnings(r_json, r_url):
    '''Check for warnings in a server response'''
    warnings = r_json.get('warnings', None)
    if warnings:
        warnmsg =  "GDC query produced a warning:\n"
        warnmsg += json.dumps(warnings, indent=2)
        warnmsg += "\nRequest URL: " + r_url
        logging.warning(warnmsg)

def _eq_filter(field, value):
    return {"op" : "=", "content" : {"field" : field, "value" : [value]}}

def _neq_filter(field, value):
    return {"op" : "!=", "content" : {"field" : field, "value" : [value]}}

def _and_filter(filters):
    return {"op" : "and", "content" : filters}

def _in_filter(field, values):
    return {"op" : "in", "content" : {"field": field, "value": values} }

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

def set_legacy(legacy=False):
    global __legacy
    previous_value = __legacy
    __legacy = True if legacy else False
    return previous_value

def get_legacy():
    return __legacy

def set_verbosity(verbosity):
    global __verbosity
    previous_value = __verbosity
    try:
        __verbosity = int(verbosity)
    except Exception:
        pass                            # simply keep previous value
    return previous_value

def get_verbosity():
    return __verbosity
