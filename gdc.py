#! /usr/bin/env python
from __future__ import print_function

import requests
import subprocess
import json
import os
import sys

COHORT = "TCGA-UVM"
ROOT_FOLDER = "TCGA_UVM"

CATEGORIES = {
                'Redaction' : {
                    'Tumor tissue origin incorrect',
                    'Tumor type incorrect',
                    'Genotype mismatch',
                    'Subject withdrew consent',
                    'Subject identity unknown',
                    'Duplicate case'
                },
                'Notification' : {
                    'Prior malignancy',
                    'Neoadjuvant therapy',
                    'Qualification metrics changed',
                    'Pathology outside specification',
                    'Molecular analysis outside specification',
                    'Sample compromised',
                    'Item does not meet study protocol',
                    'Item in special subset',
                    'Qualified in error',
                    'Item is noncanonical'
                },
                'Observation' : {
                    'Tumor class but appears normal',
                    'Normal class but appears diseased',
                    'Item may not meet study protocol',
                    'General'
                },
                'Rescission' : {
                    'Previous Redaction rescinded',
                    'Previous Notification rescinded'
                },
                'Center Notification' : {
                    'Center QC failed',
                    'Item flagged DNU'
                }

}

def download_project(project):
    COHORT = project
    ROOT_FOLDER = project.replace('-', '_')
    
    if not os.path.isdir(ROOT_FOLDER):
        os.mkdir(ROOT_FOLDER)

    dcats = data_categories(COHORT)

    ## Get cases
    cases = cases_in_project(COHORT)
    with open(ROOT_FOLDER + "/cases.txt", 'w') as cf:
        for c in cases:
            print(c["submitter_id"], file=cf)


    for data_type in dcats:
        folder = ROOT_FOLDER + "/" + data_type.replace(' ', '_')
        if not os.path.isdir(folder):
            os.mkdir(folder)
        files_to_download = get_files(COHORT, data_type)

        total = len(files_to_download)

        print("\n\n\t\tDownloading {0} to {1} ({2} files)...\n\n".format(
            data_type, folder, total))

        i = 1
        mapping = ""

        for f in files_to_download:
            print("Downloading " + str(i) + " of " + str(total))
            file_name = f['file_name']
            uuid = f['file_id']
            tcga_id = f['cases'][0]['submitter_id']

            sample_id = ""
            if 'samples' in f['cases'][0]:
                sample_id = f['cases'][0]['samples'][0]['submitter_id']


            # Skip actual download
            # curl_download(uuid, folder + "/" + file_name)
            mapping += file_name + '\t' + tcga_id + '\t' + sample_id + '\n'
            i += 1

        mappingfile = folder + '/sample_map.txt'
        with open(mappingfile, 'w') as out:
            out.write(mapping)

        fredactions = filter(_file_has_redact, files_to_download)
        with open(folder + "/redactions.txt", 'w') as redactfile:
            for r in fredactions:
                file_name = r['file_name']
                uuid = r['file_id']
                tcga_id = r['cases'][0]['submitter_id']
                redactfile.write('\t'.join([file_name, uuid, tcga_id]) + '\n')

    # Get the redacted samples
    redacted_cases = get_redacted_cases(COHORT)
    with open(ROOT_FOLDER + '/redacted_cases.txt', 'w') as redactions:
        for case in redacted_cases:
            redactions.write(case['submitter_id'] + '\n')

    print("DONE.")



def get_redacted_files(project, data_category):
    endpoint = 'https://gdc-api.nci.nih.gov/files'

    proj_filter = _eq_filter("cases.project.project_id", project)
    data_filter = _eq_filter("data_category", data_category)
    #acc_filter = _eq_filter("access", "open")
    qfilter = _and_filter([proj_filter, data_filter])

    params = {
                'fields': 'file_id,file_name,annotations.category,annotations.created_datetime',
                'filters' : json.dumps(proj_filter),
                #'facets' : 'category',
                'expand' : 'annotations'
             }

    return filter(_file_has_redact, _query_paginator(endpoint, params, 500))

def _file_has_redact(file_d):
    if "annotations" in file_d:
        for annot in file_d['annotations']:
            if annot['category'] in CATEGORIES['Redaction']:
                return True
    return False

def get_redacted_cases(project):
    endpoint = 'https://gdc-api.nci.nih.gov/cases'

    proj_filter = _eq_filter("project.project_id", project)

    #qfilter = _and_filter([proj_filter])

    params = {
                'filters' : json.dumps(proj_filter),
                'expand' : 'annotations'
    }

    def _case_redacted(case_d):
        if "annotations" in case_d:
            for annot in case_d['annotations']:
                if annot['category'] in CATEGORIES['Redaction']:
                    return True
        return False 


    return filter(_case_redacted, _query_paginator(endpoint, params, 500))


def curl_download(uuid, file_name):
    """Download a single file from GDC."""
    curl_args =  ["curl", "-o", file_name, "https://gdc-api.nci.nih.gov/data/" + uuid]
    return subprocess.check_call(curl_args)

def get_cases_samples(project):
    """Create a loadfile for sample_sets"""
    endpoint = 'https://gdc-api.nci.nih.gov/cases'
    
    proj_filter = _eq_filter("project.project_id", project)

    #qfilter = _and_filter([proj_filter])

    params = {
                'fields' : 'submitter_id',
                'filters' : json.dumps(proj_filter),
                'expand' : 'samples'
    }    
    return _query_paginator(endpoint, params, 500)

def case_sample_map(project, outfile):
    """ Writes a two-column tsv mapping samples to cases (participants in FireCloud, individuals in Firehose) """
    cases_samples = get_cases_samples(project)

    tot_samples = 0
    with open(outfile, 'w') as f:
        for case in cases_samples:
            case_id = case["submitter_id"]
            if 'samples' in case:
                for samp in case['samples']:
                    tot_samples += 1
                    f.write(case_id + '\t' + samp['submitter_id'] + '\n')

    return tot_samples

def sample_sets(project, outfile):
    """ Create a sample-set membership tsv

    """
    sample_type_dict = { "10" : "NB",
                         "01" : "TP"
                       }
    cases_samples = get_cases_samples(project)
    with open(outfile, 'w') as f:
        for case in cases_samples:
            case_id = case["submitter_id"]
            if 'samples' in case:
                for samp in case['samples']:
                    # Add to project sample_set
                    f.write(project + '\t' + samp['submitter_id'] + '\n')

                    # Get the set for this sample type
                    stype = sample_type_dict[samp['sample_type_id']]
                    f.write(project + '-' + stype + '\t' + samp['submitter_id'] + '\n')




def get_files(project_id, data_category, no_ffpe=True, page_size=500):
    endpoint = 'https://gdc-api.nci.nih.gov/files'

    proj_filter = _eq_filter("cases.project.project_id", project_id)
    data_filter = _eq_filter("data_category", data_category)
    acc_filter = _eq_filter("access", "open")
    filter_list = [proj_filter, data_filter, acc_filter]
    if no_ffpe:
        filter_list.append(_eq_filter("cases.samples.is_ffpe", "false"))
    qfilter = _and_filter(filter_list)

    fields = [ 'file_id', 'file_name', 'cases.submitter_id', 'cases.samples.sample_id',
               'data_type', 'data_category', 'data_format', 'experimental_strategy',
               'platform','tags', 'center.namespace']

    params = {
                'fields' : ','.join(fields),
                'expand' : 'cases,annotations,cases.samples',
                'filters' : json.dumps(qfilter),
             }

    return _query_paginator(endpoint, params, page_size)

def _query_paginator(endpoint, params, size, from_idx=1):

    p = params.copy()

    p['from'] = from_idx
    p['size'] = size

    # Make initial call
    r = requests.get(endpoint, params=p)

    # Get pagination data
    data = r.json()['data']
    all_hits = data['hits']
    pagination = data['pagination']
    total = pagination['total']
    
    #print(json.dumps(r.json(), indent=2))
    # TODO: log warnings?
    #warnings = r.json()['warnings']
    #print(warnings)

    for from_idx in range(size+1, total, size):
        #print("FROM: " + str(from_idx))
        #Iterate over pages to get the remaning hits
        p['from'] = from_idx
        r = requests.get(endpoint, params=p)

        hits = r.json()['data']['hits']

        all_hits.extend(hits)

    return all_hits

def data_categories(project):
    endpoint = 'https://gdc-api.nci.nih.gov/projects'
    filt = _eq_filter("project_id", project)
    params = { 
                'fields' : 'summary.data_categories.data_category',
                'filters' : json.dumps(filt)
             }

    r = requests.get(endpoint, params=params)

    hits = r.json()['data']['hits']

    if len(hits) != 1:
        raise ValueError("Uh oh, there was more than one project for this name!")

    categories = [obj['data_category'] for obj in hits[0]['summary']['data_categories']]

    return categories

def cases_in_project(project):
    endpoint = 'https://gdc-api.nci.nih.gov/cases'

    filt = _eq_filter("project.project_id", project)

    params = { 
                'fields' : 'case_id,cases.annotations.case_id,submitter_id,project_id',
                'filters' : json.dumps(filt),
                #'size' : "50" 
             }

    return _query_paginator(endpoint, params, 200)

def _eq_filter(field, value):
    return {"op" : "=", "content" : {"field" : field, "value" : [value]}}

def _and_filter(filters):
    return {"op" : "and", "content" : filters}

def download_PAAD():
    COHORT = "TCGA-PAAD"
    ROOT_FOLDER = "TCGA_PAAD"
    
    if not os.path.isdir(ROOT_FOLDER):
        os.mkdir(ROOT_FOLDER)

    dcats = data_categories(COHORT)

    ## Get cases
    cases = cases_in_project(COHORT)
    with open(ROOT_FOLDER + "/cases.txt", 'w') as cf:
        for c in cases:
            print(c["submitter_id"], file=cf)


    for data_type in dcats:
        folder = ROOT_FOLDER + "/" + data_type.replace(' ', '_')
        if not os.path.isdir(folder):
            os.mkdir(folder)
        files_to_download = get_files(COHORT, data_type)

        total = len(files_to_download)

        print("\n\n\t\tDownloading {0} to {1} ({2} files)...\n\n".format(
            data_type, folder, total))

        i = 1
        mapping = ""

        for f in files_to_download:
            print("Downloading " + str(i) + " of " + str(total))
            file_name = f['file_name']
            uuid = f['file_id']
            tcga_id = f['cases'][0]['submitter_id']

            # Skip actual download
            curl_download(uuid, folder + "/" + file_name)
            mapping += file_name + '\t' + tcga_id + '\n'
            i += 1

        mappingfile = folder + '/sample_map.txt'
        with open(mappingfile, 'w') as out:
            out.write(mapping)

        fredactions = filter(_file_has_redact, files_to_download)
        with open(folder + "/redactions.txt", 'w') as redactfile:
            for r in fredactions:
                file_name = r['file_name']
                uuid = r['file_id']
                tcga_id = r['cases'][0]['submitter_id']
                redactfile.write('\t'.join([file_name, uuid, tcga_id]) + '\n')

    # Get the redacted samples
    redacted_cases = get_redacted_cases(COHORT)
    with open(ROOT_FOLDER + '/redacted_cases.txt', 'w') as redactions:
        for case in redacted_cases:
            redactions.write(case['submitter_id'] + '\n')

def get_annotation(fdict):
    """ Determine the annotation name for this file by inspecting metadata.

    """
    pass


def main():
    files = get_files("TCGA-UVM", "Clinical")

    print(json.dumps(files, indent=2))
    # cohort = sys.argv[1]
    # download_project("TCGA-UVM")

    #cases = get_sample_sets("TCGA-UVM")
    #print(json.dumps(cases, indent=2))

    #n = case_sample_map("TCGA-UVM", "sample_indiv_map.txt")
    #sample_sets("TCGA-UVM", "sample_sets.txt")
    #print(n)

if __name__ == '__main__':
    main()

#/xchip/gdac_data/normalized/diced/uvm/snp__genome_wide_snp_6__broad_mit_edu__Level_3__segmented_scna_minus_germline_cnv_hg19__seg/broad.mit.edu_UVM.Genome_Wide_SNP_6.Level_3.417.2003.0/TCGA-RZ-AB0B-01A-11D-A39V-01.seg.txt


## Notes

# Get all the case_ids/submitter_ids (TCGA IDS) for a project
# curl 'https://gdc-api.nci.nih.gov/cases?fields=case_id%2Csubmitter_id%2Cproject_id&filters=%7B%22content%22%3A+%7B%22field%22%3A+%22project.project_id%22%2C+%22value%22%3A+%5B%22TCGA-UVM%22%5D%7D%2C+%22op%22%3A+%22%3D%22%7D'
# curl 'https://gdc-api.nci.nih.gov/cases?fields=case_id,submitter_id,project_id&filters={"content": {"field": "project.project_id", "value": ["TCGA-UVM"]}, "op": "="}'

# Get all files for a project_id
# curl https://gdc-api.nci.nih.gov/files?fields=file_name,file_id,data_type,data_subtype,data_format&filters={"content": {"field": "cases.project.project_id", "value": ["TCGA-UVM"]}, "op": "="}
# curl https://gdc-api.nci.nih.gov/files?fields=file_name%2Cfile_id%2Cdata_type%2Cdata_subtype%2Cdata_format&filters=%7B%22content%22%3A+%7B%22field%22%3A+%22cases.project.project_id%22%2C+%22value%22%3A+%5B%22TCGA-UVM%22%5D%7D%2C+%22op%22%3A+%22%3D%22%7D

# Download a file by uuid
# curl 'https://gdc-api.nci.nih.gov/data/7998b100-6785-4a40-83d9-e74d1ff5e42f'

# Get Multiple files by comma separated, list, downloads a .tar.gz
# curl -O -J 'https://gdc-api.nci.nih.gov/data/7998b100-6785-4a40-83d9-e74d1ff5e42f,59113624-7a2d-43a7-a2c0-966a4747ae52'

# Get all files from a single project with a given data type
# curl 'https://gdc-api.nci.nih.gov/files?fields=file_name%2Cfile_size%2Cfile_id%2Cdata_type%2Cdata_subtype&filters=%7B%22content%22%3A+%5B%7B%22content%22%3A+%7B%22field%22%3A+%22cases.project.project_id%22%2C+%22value%22%3A+%5B%22TCGA-UVM%22%5D%7D%2C+%22op%22%3A+%22%3D%22%7D%2C+%7B%22content%22%3A+%7B%22field%22%3A+%22data_type%22%2C+%22value%22%3A+%5B%22Copy+number+variation%22%5D%7D%2C+%22op%22%3A+%22%3D%22%7D%5D%2C+%22op%22%3A+%22and%22%7D
# curl 'https://gdc-api.nci.nih.gov/files?fields=file_name,file_size,file_id,data_type,data_subtype&filters={"content": [{"content": {"field": "cases.project.project_id", "value": ["TCGA-UVM"]}, "op": "="}, {"content": {"field": "data_type", "value": ["Copy number variation"]}, "op": "="}], "op": "and"}

