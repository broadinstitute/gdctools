#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

gdc_mirror: this file is part of gdctools.  See the <root>/COPYRIGHT
file for the SOFTWARE COPYRIGHT and WARRANTY NOTICE.

@author: Michael S. Noble, Timothy DeFreitas
@date:  2016_05_18
'''

# }}}
from __future__ import print_function


import sys
import os
import logging
import time
import ConfigParser
import json
import requests

from GDCtool import GDCtool
import gdc

class gdc_mirror(GDCtool):

    def __init__(self):
        super(gdc_mirror, self).__init__(version="0.3.0")
        cli = self.cli

        desc =  'Create local mirror of the data from arbitrary programs '\
                'and projects warehoused at the Genomic Data Commons (GDC)\n'
        cli.description = desc

        #Optional overrides of config file
        #cli.add_argument('-l', '--log-directory', help='Folder to store logfiles')
        
        cli.add_argument('config', help='GDC mirror configuration file')

    def set_timestamp(self):
        '''Creates a timestamp for the current mirror'''
        self.timestamp = time.strftime('%Y_%m_%d__%H_%M_%S')
        return self.timestamp 

    def init_logging(self):
        logfile_name = ".".join(["gdcMirror", self.timestamp, "log"])
        if not os.path.isdir(self.log_dir):
            os.makedirs(self.log_dir)
        logfile_path = os.path.join(self.log_dir, logfile_name)
        logging.basicConfig(filename=logfile_path, 
                            format='%(asctime)s::%(levelname)s  %(message)s',
                            datefmt='%Y-%m-%d %I:%M:%S %p', 
                            level=logging.INFO)
        
        #Create a symlink indicating this is the latest log
        latest_path = os.path.join(self.log_dir, "gdcMirror.latest.log")
        try:
            os.unlink(latest_path)
        except OSError:
            #Symlink didn't exist, no problem
            pass
        os.symlink(os.path.abspath(logfile_path), latest_path)


    def parseConfig(self, config_file):
        """Read options from config, and optionally override them with args"""
        cfg = ConfigParser.ConfigParser()
        cfg.read(config_file)

        self.config = cfg
        cwd = os.getcwd()

        #Required configuration parameters
        # self.gdc_api_root = cfg.get('general', 'GDC_API_ROOT')

        #Optional configuration parameters
        if cfg.has_option('general', 'LOG_DIRECTORY'):
            self.log_dir = cfg.get('general', 'LOG_DIRECTORY')
        else:
            self.log_dir = cwd
        
        if cfg.has_option('general', 'MIRROR_ROOT_DIR'):
            self.root_dir = cfg.get('general', 'MIRROR_ROOT_DIR')
        else:
            self.root_dir = os.path.join(cwd, "gdc_mirror_root")

        #Get list of programs
        if cfg.has_option('mirror', 'PROGRAMS'):
            self.programs = cfg.get('mirror', 'PROGRAMS').strip().split(",")
        else:
            self.programs = None

        if cfg.has_option('mirror', 'PROJECTS'):
            self.projects = cfg.get('mirror', 'PROJECTS').strip().split(",")
        else:
            self.projects = None

    def mirror(self):
        logging.info("GDC Mirror Version: %s", self.cli.version)
        logging.info("Configuration File: %s", os.path.abspath(self.options.config))

        if not os.path.isdir(self.root_dir):
            os.makedirs(self.root_dir)

        ## Mirror Pseudocode:
        # Get Program(s) + Project(s) from CFG, or if not present, issue API call to get all available
        # For each Program prgm:
        #    For each project prj:
        #        cats = get_data_categories()
        #        For each cat in cats:
        #           file_metadata = get_files(prgm, proj, cat, "open_access")
        #           Save file_metadata json to /<root>/<prgm>/<prj>/<cat>/metadata.<timestamp>.json
        #           For each file:
        #               Download each file to /<root>/<prgm>/<prj>/<cat>/<file>
        #               Save MD5 checksum to  /<root>/<prgm>/<prj>/<cat>/<file>.md5

        if self.programs is None:
            logging.info("No programs specified, using GDC API to discover available programs")
            self.programs = get_GDC_programs()
            logging.info(str(len(self.programs)) + " program(s) found: " + ",".join(self.programs))
        logging.info("Mirroring data from the following programs: " + ",".join(self.programs))

        #Get projects/cohorts from config, or dynamically
        if self.projects is None:
            logging.info("No projects specified, using GDC API to discover available projects")
            self.projects = []
            for prgm in self.programs:
                new_projects = gdc.get_projects(prgm)

                logging.info(str(len(new_projects)) + " project(s) found for " + prgm + ": " + ",".join(new_projects))
                self.projects.extend(new_projects)
        logging.info("Mirroring " + str(len(self.projects)) + " total projects")

        for project in self.projects:
            logging.info("Mirroring started for " + project)
            prgm = get_program(project)
            data_categories = gdc.get_data_categories(project)
            logging.info("Found " + str(len(data_categories)) + " data categories: " + ",".join(data_categories))
            proj_root = os.path.abspath(os.path.join(self.root_dir, prgm, project))
            logging.info("Mirroring data to " + proj_root)
            for cat in data_categories:
                #Replace spaces with underscores for better folder names
                data_dir = os.path.join(proj_root, cat.replace(' ', '_'))
                if not os.path.isdir(data_dir):
                    logging.info("Creating folder: " + data_dir)
                    os.makedirs(data_dir)

                file_metadata = gdc.get_files(project, cat)
                metadata_filename = '.'.join(["metadata", self.timestamp, "json"])
                metadata_path = os.path.join(data_dir, metadata_filename)
                # Save metadata in json format for dicing reference 
                with open(metadata_path, 'w') as f:
                    f.write(json.dumps(file_metadata, indent=2))

                # Download actual files
                total_files = len(file_metadata)
                logging.info("Downloading " + str(total_files) + " " + cat + " files")
                for file_d in file_metadata:
                    uuid = file_d['file_id']
                    name = file_d['file_name']

                    savepath = os.path.join(data_dir, name)
                    md5path = savepath + ".md5"

                    #If we don't already have a checksum for this file, download both the file and md5
                    if os.path.isfile(md5path):
                        logging.info("File " + name + " already exists, skipping download")
                    else:
                        logging.info("Downloading file " + name ) 

                        retry_count = 3
                        while retry_count > 0:
                            try:
                                #Download file
                                gdc.get_file(uuid, savepath)
                                break
                            except subprocess.CalledProcessError as e:
                                logging.warning("Curl call failed: " + str(e))
                                retry_count = retry_count - 1

                        if retry_count == 0:
                            logging.error("Error downloading file " + savepath + ", too many retries (3)")
                        else:
                            #Save md5 checksum on success
                            md5sum = file_d['md5sum']
                            with open(md5path, 'w') as mf:
                                mf.write(md5sum + "  " + name )



    def execute(self):
        super(gdc_mirror, self).execute()
        opts = self.options
        self.parseConfig(opts.config)
        self.set_timestamp()
        self.init_logging()
        self.mirror()

## API Calls
# TODO: Consolidate api calls into gdc-api.py or equivalent

def get_GDC_programs():
    ##TODO: No direct API, hard-coded for now...
    return ["TCGA", "TARGET"]

def get_program(project):
    endpoint = 'https://gdc-api.nci.nih.gov/projects'
    filt = gdc._eq_filter("project_id", project)
    params = { 
                'fields' : 'program.name',
                'filters' : json.dumps(filt)
             }

    r = requests.get(endpoint, params=params)
    hits = r.json()['data']['hits']

    if len(hits) != 1:
        raise ValueError("Uh oh, there was more than one project for this name!")
    return hits[0]['program']['name']



if __name__ == "__main__":
    gdc_mirror().execute()
