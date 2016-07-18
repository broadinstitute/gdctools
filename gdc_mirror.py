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
import csv
import subprocess

from GDCtool import GDCtool
import lib.api as api
import lib.meta as meta
import lib.common as common
from lib.constants import LOGGING_FMT


class gdc_mirror(GDCtool):

    def __init__(self):
        super(gdc_mirror, self).__init__(version="0.7.0")
        cli = self.cli

        desc =  'Create local mirror of the data from arbitrary programs '\
                'and projects warehoused at the Genomic Data Commons (GDC)\n'
        cli.description = desc

        #Optional overrides of config file
        cli.add_argument('-r', '--root-dir', help='Root of mirrored data folder tree')

        cli.add_argument('-d', '--data-categories', nargs='+', metavar='category',
                         help='Mirror only these data categories. Many data categories have spaces, use quotes to delimit')

        cli.add_argument('-m', '--meta-only', action='store_true',
                         help="Only retrieve metadata, skip file download")

        cli.add_argument('-w', '--workflow-type',
                         help='Mirror only data of thisworkflow type')

    def set_timestamp(self):
        '''Creates a timestamp for the current mirror'''
        self.timestamp = common.timetuple2stamp() #'2017_02_01__00_00_00'
        return self.timestamp

    def parse_args(self):
        """Read options from config, and optionally override them with args"""
        # Config options that can be overridden by cli args
        opts = self.options
        if opts.log_dir is not None: self.mirror_log_dir = opts.log_dir
        if opts.root_dir is not None: self.mirror_root_dir = opts.root_dir
        if opts.projects is not None: self.mirror_projects = opts.projects
        if opts.programs is not None: self.mirror_programs = opts.programs
        self.workflow_type = opts.workflow_type

    def mirror(self):
        logging.info("GDC Mirror Version: %s", self.cli.version)
        logging.info("Command: " + " ".join(sys.argv))
        if self.options.config is not None:
            logging.info("Configuration File: %s",
                         os.path.abspath(self.options.config))

        root_dir = self.mirror_root_dir
        projects = self.mirror_projects
        programs = self.mirror_programs

        if not os.path.isdir(root_dir):
            os.makedirs(root_dir)

        if projects is None:
            if programs is None:
                logging.info("No programs or projects specified, using GDC API"\
                             "to discover available programs")
                programs = api.get_programs()
                logging.info(str(len(programs)) +
                                 " program(s) found: " + ",".join(programs))

            logging.info("No projects specified, using GDC API to discover"\
                         "available projects")
            projects = []
            for prgm in programs:
                new_projects = api.get_projects(prgm)
                logging.info(str(len(new_projects)) + " project(s) found for "
                             + prgm + ": " + ",".join(new_projects))
                projects.extend(new_projects)

        # Make list of which projects belong to each program
        program_projects = dict()
        for project in projects:
            prgm = api.get_program(project)
            if prgm not in program_projects: program_projects[prgm] = []
            program_projects[prgm].append(project)

        # Now loop over each program, acquiring lock
        for prgm in program_projects:
            projects = program_projects[prgm]
            prgm_root = os.path.abspath(os.path.join(root_dir, prgm))

            with common.lock_context(prgm_root, "mirror"):
                for project in sorted(projects):
                    self.mirror_project(prgm, project)

                # Write program-level metadata
                prgm_meta = os.path.join(root_dir, prgm,
                                         "metadata", self.timestamp)
                if not os.path.isdir(prgm_meta):
                    os.makedirs(prgm_meta)

                # # Counts, report, etc.
                # self._aggregate_counts(prgm)

        logging.info("Mirror completed successfully.")

    def __mirror_file(self, file_d, proj_root, n, total, retries=3):
        '''Mirror a file into <proj_root>/<cat>/<type>.

        Files are uniquely identified by uuid.
        '''
        savepath = meta.mirror_path(proj_root, file_d)
        dirname, basename = os.path.split(savepath)
        logging.info("Mirroring {0} | {1} of {2}".format(basename, n, total))

        #Ensure <root>/<cat>/<type>/ exists
        if not os.path.isdir(dirname):
            os.makedirs(dirname)

        md5path = savepath + ".md5"

        if not meta.md5_matches(file_d, md5path):

            # New file, mirror to this folder
            while retries > 0:
                try:
                    #Download file
                    uuid = file_d['file_id']
                    api.get_file(uuid, savepath)
                    break
                except subprocess.CalledProcessError as e:
                    logging.warning("Curl call failed: " + str(e))
                    retries = retries - 1

            if retries == 0:
                logging.error("Error downloading file {0}, too many retries ({1})".format(savepath, retries))
            else:
                #Save md5 checksum on success
                md5sum = file_d['md5sum']
                md5path = savepath + ".md5"
                with open(md5path, 'w') as mf:
                    mf.write(md5sum + "  " + basename)


    def mirror_project(self, program, project):
        '''Mirror one project folder'''
        tstamp = self.timestamp

        logging.info("Mirroring started for {0} ({1})".format(project, program))
        if self.options.data_categories is not None:
            data_categories = self.options.data_categories
        else:
            logging.info("No data_categories specified, using GDC API to "
                         + "discover available categories")
            data_categories = api.get_data_categories(project)
        logging.info("Found " + str(len(data_categories)) + " data categories: "
                     + ",".join(data_categories))

        proj_dir = os.path.join(self.mirror_root_dir, program, project)
        logging.info("Mirroring data to " + proj_dir)

        # Read the previous metadata, if present
        prev_timestamp = meta.latest_timestamp(proj_dir, None, ignore=tstamp)
        prev_metadata = []
        if prev_timestamp is not None:
            prev_stamp_dir = os.path.join(proj_dir, "metadata", prev_timestamp)
            prev_metadata = meta.latest_metadata(prev_stamp_dir)

        # Mirror each category separately, recording metadata (file dicts)
        file_metadata = []
        for cat in sorted(data_categories):
            cat_data = self.mirror_category(program, project, cat,
                                            self.workflow_type,
                                            prev_metadata)
            file_metadata.extend(cat_data)


        # Record project-level metadata
        # file dicts, counts, redactions, blacklist, etc.
        meta_folder = os.path.join(proj_dir,"metadata")
        stamp_folder = os.path.join(meta_folder, tstamp)
        if not os.path.isdir(stamp_folder):
            os.makedirs(stamp_folder)

        # Write file metadata
        meta_json = ".".join(["metadata", project, tstamp, "json" ])
        meta_json = os.path.join(stamp_folder, meta_json)
        with open(meta_json, 'w') as jf:
            json.dump(file_metadata, jf, indent=2)

        # Write sample counts
        # countsfile = ".".join([project, "sample_counts", tstamp, "tsv"])
        # countspath = os.path.join(meta_folder, countsfile)
        #
        # proj_counts = self._sample_counts(program, project, data_categories)
        # _write_counts(proj_counts, project, sorted(data_categories), countspath)

    def mirror_category(self, program, project, category,
                        workflow_type, prev_metadata):
        '''Mirror one category of data in a particular project.
        Return the mirrored file metadata.
        '''
        tstamp = self.timestamp
        proj_dir = os.path.join(self.mirror_root_dir, program, project)
        cat_dir = os.path.join(proj_dir, category.replace(' ', '_'))

        #Create data folder
        if not os.path.isdir(cat_dir):
            logging.info("Creating folder: " + cat_dir)
            os.makedirs(cat_dir)

        file_metadata = api.get_files(project, category, workflow_type)
        new_metadata = meta.files_diff(proj_dir, file_metadata, prev_metadata)

        if self.options.meta_only:
            logging.info("Metadata only option enabled, skipping full mirror")
        else:
            num_files = len(new_metadata)
            logging.info("{0} new {1} files".format(num_files, category))

            for n, file_d in enumerate(new_metadata):
                self.__mirror_file(file_d, proj_dir, n+1, num_files)

        return file_metadata


    def execute(self):
        super(gdc_mirror, self).execute()
        self.parse_args()
        self.set_timestamp()
        common.init_logging(self.timestamp, self.mirror_log_dir, "gdcMirror")
        try:
            self.mirror()
        except Exception as e:
            logging.exception("Mirroring FAILED:")



if __name__ == "__main__":
    gdc_mirror().execute()
