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
import subprocess

from GDCtool import GDCtool
import lib.api as api
from lib.constants import LOGGING_FMT
from lib.common import timetuple2stamp, init_logging
from lib.meta import md5_matches


class gdc_mirror(GDCtool):

    def __init__(self):
        super(gdc_mirror, self).__init__(version="0.4.0")
        cli = self.cli

        desc =  'Create local mirror of the data from arbitrary programs '\
                'and projects warehoused at the Genomic Data Commons (GDC)\n'
        cli.description = desc

        #Optional overrides of config file
        cli.add_argument('-l', '--log-directory', help='Folder to store logfiles')
        cli.add_argument('-r', '--root-directory', help='Root of mirrored data folder tree')
        cli.add_argument('-g', '--programs', nargs='+', metavar='program',
                         help='Mirror data from these cancer programs')
        cli.add_argument('-p', '--projects', nargs='+', metavar='project',
                         help='Mirror data from these projects')
        cli.add_argument('-c', '--data-categories', nargs='+', metavar='category',
                         help='Mirror only these data categories. Many data categories have spaces, use quotes to delimit')

        cli.add_argument('-m', '--meta-only', action='store_true',
                         help="Only retrieve metadata, skip file download")

        cli.add_argument('config', nargs='?', default=None,
                         help='GDC mirror configuration file')

    def set_timestamp(self):
        '''Creates a timestamp for the current mirror'''
        self.timestamp = timetuple2stamp()
        return self.timestamp 


    def init_logs(self):
        if self.log_dir is not None:
            logfile_name = ".".join(["gdcMirror", self.timestamp, "log"])
            if not os.path.isdir(self.log_dir):
                os.makedirs(self.log_dir)
            logfile_path = os.path.join(self.log_dir, logfile_name)
        else:
            logfile_path = None # Logfile is disabled
        init_logging(logfile_path, True)


    def parseConfig(self, config_file):
        """Read options from config, and optionally override them with args"""
        #Initialize defaults 
        cwd = os.getcwd()
        self.root_dir = os.path.join(cwd, "gdc_mirror_root")
        self.log_dir = None
        self.programs = self.projects = None

        if config_file is not None:
            cfg = ConfigParser.ConfigParser()
            cfg.read(config_file)

            # self.config = cfg

            #Optional configuration parameters
            if cfg.has_option('general', 'LOG_DIRECTORY'):
                self.log_dir = cfg.get('general', 'LOG_DIRECTORY')
            if cfg.has_option('general', 'MIRROR_ROOT_DIR'):
                self.root_dir = cfg.get('general', 'MIRROR_ROOT_DIR')

            #Get list of programs, projects
            if cfg.has_option('mirror', 'PROGRAMS'):
                self.programs = cfg.get('mirror', 'PROGRAMS').strip().split(",")
            if cfg.has_option('mirror', 'PROJECTS'):
                self.projects = cfg.get('mirror', 'PROJECTS').strip().split(",")

        # Config options can be overridden by cli args
        opts = self.options
        if opts.log_directory is not None: self.log_dir = opts.log_directory
        if opts.root_directory is not None: self.root_dir = opts.root_directory
        if opts.programs is not None: self.programs = opts.programs
        if opts.projects is not None: self.projects = opts.projects


    def mirror(self):
        logging.info("GDC Mirror Version: %s", self.cli.version)
        logging.info("Command: " + " ".join(sys.argv))
        if self.options.config is not None:
            logging.info("Configuration File: %s", os.path.abspath(self.options.config))

        if not os.path.isdir(self.root_dir):
            os.makedirs(self.root_dir)

        ## Mirror Pseudocode:
        # Get Program(s) + Project(s) from CFG, or if not present, issue API call to get all available
        # For each project prj:
        #    cats = get_data_categories()
        #    For each cat in cats:
        #       file_metadata = get_files(prj, cat)
        #       Save file_metadata json to <root>/<prgm>/<prj>/<cat>/meta/metadata.<timestamp>.json
        #       For each file:
        #           Download each file to <root>/<prgm>/<prj>/<cat>/<type>/<file>
        #           Save MD5 checksum to  <root>/<prgm>/<prj>/<cat>/<type>/<file>.md5

        if self.programs is None and self.projects is None:
            logging.info("No programs or projects specified, using GDC API to discover available programs")
            self.programs = api.get_programs()
            logging.info(str(len(self.programs)) + " program(s) found: " + ",".join(self.programs))

        #Get projects/cohorts from config, or dynamically
        if self.projects is None:
            logging.info("No projects specified, using GDC API to discover available projects")
            self.projects = []
            for prgm in self.programs:
                new_projects = api.get_projects(prgm)

                logging.info(str(len(new_projects)) + " project(s) found for " + prgm + ": " + ",".join(new_projects))
                self.projects.extend(new_projects)
        logging.info("Mirroring " + str(len(self.projects)) + " total projects")

        for project in self.projects:
            prgm = api.get_program(project)
            logging.info("Mirroring started for {0} ({1})".format(project, prgm))
            if self.options.data_categories is not None:
                data_categories = self.options.data_categories
                logging.info("Data categories: " + ",".join(data_categories))
            else:
                logging.info("No data_categories specified, using GDC API to discover available categories")
                data_categories = api.get_data_categories(project)
                logging.info("Found " + str(len(data_categories)) + " data categories: " + ",".join(data_categories))
            

            proj_root = os.path.abspath(os.path.join(self.root_dir, prgm, project))
            logging.info("Mirroring data to " + proj_root)
            for cat in data_categories:
                #Replace spaces with underscores for better folder names
                data_dir = os.path.join(proj_root, cat.replace(' ', '_'))
                meta_dir = os.path.join(data_dir, "meta")
                if not os.path.isdir(data_dir):
                    logging.info("Creating folder: " + data_dir)
                    os.makedirs(data_dir)
                if not os.path.isdir(meta_dir):
                    logging.info("Creating metadata folder: " + meta_dir)
                    os.makedirs(meta_dir)

                file_metadata = api.get_files(project, cat)
                
                # Save metadata in json format for dicing reference, in <data_category>/meta/
                metadata_filename = '.'.join(["metadata", self.timestamp, "json"])
                metadata_path = os.path.join(meta_dir, metadata_filename)
                with open(metadata_path, 'w') as f:
                    f.write(json.dumps(file_metadata, indent=2))

                if self.options.meta_only:
                    logging.info("Metadata only option enabled, skipping file mirroring")
                else:
                    total_files = len(file_metadata)
                    logging.info("Mirroring " + str(total_files) + " " + cat + " files")
                    file_num = 0
                    for file_d in file_metadata:
                        file_num += 1
                        uuid = file_d['file_id']
                        name = file_d['file_name']
                        dtype = file_d['data_type']


                        type_folder = os.path.join(data_dir, dtype.replace(' ', '_'))
                        
                        #if the data type folder doesn't yet exist, create it
                        if not os.path.isdir(type_folder):
                            os.makedirs(type_folder)

                        # Download actual files to <data_category>/<data_type>/<file>[.md5]
                        savepath = os.path.join(type_folder, name)
                        md5path = savepath + ".md5"

                        #If we don't already have a checksum for this file, download both the file and md5
                        #TODO: verify MD5 matches file metadata, to confirm file identity
                        if os.path.isfile(md5path) and md5_matches(file_d, md5path):
                            logging.info("File " + name + " already exists, skipping download")
                        else:
                            logging.info("Downloading file {0}, {1} of {2}".format(name, file_num, total_files))
                            retry_count = 3
                            while retry_count > 0:
                                try:
                                    #Download file
                                    api.get_file(uuid, savepath)
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
        logging.info("Mirror completed successfully.")


    def execute(self):
        super(gdc_mirror, self).execute()
        opts = self.options
        self.parseConfig(opts.config)
        self.set_timestamp()
        self.init_logs()
        self.mirror()


if __name__ == "__main__":
    gdc_mirror().execute()
