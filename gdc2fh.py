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
from gdc import _query_paginator, _eq_filter, _and_filter, get_data_categories, get_projects
from pprint import pprint

def _neq_filter(field, value):
    return {"op" : "!=", "content" : {"field" : field, "value" : [value]}}

def get_files(case_id, project_id, data_category, page_size=500):
    endpoint = 'https://gdc-api.nci.nih.gov/legacy/files'

    proj_filter = _eq_filter("cases.project.project_id", project_id)
    data_filter = _eq_filter("data_category", data_category)
    data_type_filter = _eq_filter("data_type", "Masked Copy Number Segment")
    acc_filter = _eq_filter("access", "open")
    case_filter = _eq_filter("cases.submitter_id", case_id)
    center_filter = _eq_filter("center.namespace", "unc.edu")
    platform_filter = _eq_filter("platform", "HuEx-1_0-st-v2")
    strategy_filter = _eq_filter("experimental_strategy",
                                  "Exon array")
    ffpe_filter = _eq_filter("cases.samples.is_ffpe", "false")
    filename_filter = _eq_filter("file_name", "lbl.gov_OV.HuEx-1_0-st-v2.11.gene.txt")
    qfilter = _and_filter([proj_filter, data_filter, acc_filter])#, case_filter, ffpe_filter])
                           #platform_filter])#, data_type_filter, center_filter, strategy_filter])

    params = {
                'fields' : 'file_name,data_type,data_category,data_format,' + \
                           'center.namespace,tags,experimental_strategy,' + \
                           'platform,access',
#                            ,cases.samples.is_ffpe,origin,' + \
#                            'md5sum,' + ('cases.submitter_id' if \
#                             data_category == 'Clinical' else \
#                             'cases.samples.portions.submitter_id' if \
#                             data_category == 'Protein Expression' else \
#                             'cases.samples.portions.analytes.aliquots.submitter_id,file_id'),
                'expand' : 'archive,metadata_files',#associated_entities,center', # + \
                           #',cases,annotations,cases.samples,analysis.metadata.read_groups',
                'filters' : json.dumps(qfilter),
             }

    return _query_paginator(endpoint, params, page_size)

if __name__ == '__main__':
    pprint(get_files("TCGA-A2-A0EU", 'TCGA-BRCA', 'Simple nucleotide variation'))
    #pprint(get_data_categories('TCGA-UVM'))
    #pprint(get_projects('TCGA'))