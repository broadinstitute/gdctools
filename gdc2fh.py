'''
Copyright (c) 2016 The Broad Institute, Inc. 
SOFTWARE COPYRIGHT NOTICE 
This software and its documentation are the copyright of the Broad Institute,
Inc. All rights are reserved.

This software is supplied without any warranty or guaranteed support
whatsoever. The Broad Institute is not responsible for its use, misuse, or
functionality.

@author: David Heiman
@date:   Apr 29, 2016
'''

import json
from gdc import _query_paginator, _eq_filter, _and_filter, data_categories
from pprint import pprint

def _neq_filter(field, value):
    return {"op" : "!=", "content" : {"field" : field, "value" : [value]}}

def get_files(case_id, project_id, data_category, page_size=500):
    endpoint = 'https://gdc-api.nci.nih.gov/files'

    proj_filter = _eq_filter("cases.project.project_id", project_id)
    data_filter = _eq_filter("data_category", data_category)
    acc_filter = _eq_filter("access", "open")
    case_filter = _eq_filter("cases.submitter_id", case_id)
    center_filter = _neq_filter("center.namespace", "hudsonalpha.org")
    qfilter = _and_filter([proj_filter, data_filter, acc_filter, case_filter,
                           center_filter])

    params = {
                'fields' : 'file_name,data_type,' + \
                           'data_category,data_format,center.namespace,' + \
                           'tags,experimental_strategy,platform,' + \
                           'cases.samples.portions.analytes.aliquots.submitter_id',
                'expand' : 'archive',
                #'expand' : 'cases,annotations,cases.samples',
                'filters' : json.dumps(qfilter),
             }

    return _query_paginator(endpoint, params, page_size)

if __name__ == '__main__':
    pprint(get_files("TCGA-13-1489", 'TCGA-OV', 'Gene expression'))
    #pprint(data_categories('TCGA-OV'))