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
from lib.common import timetuple2stamp, init_logging, lock_context
from lib.meta import md5_matches


class gdc_mirror(GDCtool):

    def __init__(self):
        super(gdc_mirror, self).__init__(version="0.5.0")
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


    #TODO: Move config parsing to GDCtool
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


            #Optional configuration parameters
            if cfg.has_option('mirror', 'LOG_DIR'):
                self.log_dir = cfg.get('mirror', 'LOG_DIR')
            if cfg.has_option('mirror', 'ROOT_DIR'):
                self.root_dir = cfg.get('mirror', 'ROOT_DIR')

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

        if self.projects is None:
            if self.programs is None:
                logging.info("No programs or projects specified, using GDC API to discover available programs")
                self.programs = api.get_programs()
                logging.info(str(len(self.programs)) + " program(s) found: " + ",".join(self.programs))

            logging.info("No projects specified, using GDC API to discover available projects")
            self.projects = []
            for prgm in self.programs:
                new_projects = api.get_projects(prgm)

                logging.info(str(len(new_projects)) + " project(s) found for " + prgm + ": " + ",".join(new_projects))
                self.projects.extend(new_projects)

        # Make list of which projects belong to each program
        program_projects = dict()
        for project in self.projects:
            prgm = api.get_program(project)
            if prgm not in program_projects: program_projects[prgm] = []
            program_projects[prgm].append(project)

        # Now loop over each program, acquiring lock
        for prgm in program_projects:
            projects = program_projects[prgm]
            prgm_root = os.path.abspath(os.path.join(self.root_dir, prgm))
            
            with lock_context(prgm_root, "mirror"):
                for project in projects:
                    self.mirror_project(prgm_root, prgm, project)

        logging.info("Mirror completed successfully.")
    
    @staticmethod
    def __download_if_missing(file_d, folder, n, total, retry_count=3):

        uuid = file_d['file_id']
        name = file_d['file_name']
        savepath = os.path.join(folder, name)
        md5path = savepath + ".md5"
        logging.info("Mirroring file {0} : {1} of {2}".format(savepath,n,total))

        #Only download if not present
        if not (os.path.isfile(md5path) and md5_matches(file_d, md5path)):
            while retry_count > 0:
                try:
                    #Download file
                    api.get_file(uuid, savepath)
                    break
                except subprocess.CalledProcessError as e:
                    logging.warning("Curl call failed: " + str(e))
                    retry_count = retry_count - 1

            if retry_count == 0:
                logging.error("Error downloading file {0}, too many retries ({1})".format(savepath, retry_count))
            else:
                #Save md5 checksum on success
                md5sum = file_d['md5sum']
                with open(md5path, 'w') as mf:
                    mf.write(md5sum + "  " + name )


    def mirror_project(self, prog_root, program, project):
        '''Mirror one project folder'''
        logging.info("Mirroring started for {0} ({1})".format(project, program))
        if self.options.data_categories is not None:
            data_categories = self.options.data_categories
        else:
            logging.info("No data_categories specified, using GDC API to discover available categories")
            data_categories = api.get_data_categories(project)
        logging.info("Found " + str(len(data_categories)) + " data categories: " + ",".join(data_categories))

        proj_root = os.path.join(prog_root, project)
        logging.info("Mirroring data to " + proj_root)

        for cat in data_categories:
            self.mirror_category(proj_root, project, cat)


    def mirror_category(self, proj_root, project, cat):
        '''Mirror one data category in a project'''
        data_dir = os.path.join(proj_root, cat.replace(' ', '_'))
        logging.info("Mirroring: {0} - {1} data".format(project, cat))

        #Create data and meta folders
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
            
            for n, file_d in enumerate(file_metadata):
                self.__download_if_missing(file_d, data_dir, n, total_files)

    def execute(self):
        super(gdc_mirror, self).execute()
        opts = self.options
        self.parseConfig(opts.config)
        self.set_timestamp()
        self.init_logs()
        self.mirror()


if __name__ == "__main__":
    gdc_mirror().execute()
