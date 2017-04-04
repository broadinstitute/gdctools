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

import sys
import os
import logging
import time
import json

from gdctools.GDCcore import *
from gdctools.GDCtool import GDCtool
import gdctools.lib.api as api
import gdctools.lib.meta as meta
import gdctools.lib.common as common

class gdc_mirror(GDCtool):

    def __init__(self):
        super(gdc_mirror, self).__init__(version="0.9.1")
        cli = self.cli
        cli.description = 'Create local mirror of the data from arbitrary '\
                        'programs and projects\nwarehoused at the Genomic Data'\
                        ' Commons (GDC)\n'
        cli.add_argument('-m', '--mirror-dir',
                        help='Root of mirrored data folder tree')
        cli.add_argument('-d', '--data-categories',nargs='+',metavar='category',
                        help='Mirror only these data categories. Many data '+
                        'categories have spaces, use quotes to delimit')
        cli.add_argument('-L', '--LEGACY', default=False, action='store_true',
                        help='Retrieve legacy data (e.g. TCGA HG19), '\
                        'instead of data harmonized at the GDC (the default)')
        cli.add_argument('-w', '--workflow-type',
                        help='Mirror only data of thisworkflow type')
        cli.add_argument('-f', '--force-download', action='store_true',
                        help='Download files even if already mirrored locally.'+
                             ' (DO NOT use during incremental mirroring)')

        # detect if we have curl installed
        self.has_cURL = api.curl_exists()

    def parse_args(self):
        '''Parse CLI args, potentially overriding config file settings'''
        opts = self.options
        config = self.config.mirror
        if opts.mirror_dir: config.dir = opts.mirror_dir
        if opts.log_dir: config.log_dir = opts.log_dir
        if opts.data_categories:
            config.data_categories = opts.data_categories
        config.data_categories = self.get_config_values_as_list(config.data_categories)

        self.force_download = opts.force_download
        self.workflow_type = opts.workflow_type

        if config.legacy:
            # Legacy mode has been requested in config file, coerce to boolean
            value = config.legacy.lower()
            config.legacy = (value in ["1", "true", "on", "yes"])

        # Allow command line flag to override config file
        if opts.LEGACY:
            config.legacy = opts.LEGACY

        # Legacy mode has several effects:
        #   1) Ensures that api requests are routed to the GDC legacy API
        #   2) Ensuring that legacy program data are returned (e.g. TCGA HG19)
        #   3) Turns OFF strict file processing: returned data files are thus
        #      mirrored "as is," i.e. verbatim, regardless of file type (or
        #      extension), with no UUID inserted into names of mirrored files
        #   4) Prohibits subsequent processing, e.g. dicing: the GDCtools suite
        #      ONLY supports MIRRORING of legacy, nothing else
        api.set_legacy(config.legacy)

    def mirror(self):

        config = self.config
        projects = []
        programs = []

        # Validate program and project names, if specified
        if config.projects:
            all_projects = api.get_projects()
            for proj in config.projects:
                if proj not in all_projects:
                    gprint("Project " + proj + " not found in GDC, ignoring")
                else:
                    projects.append(proj)

        if config.programs:
            all_programs = api.get_programs()
            for prog in config.programs:
                if prog not in all_programs:
                    gprint("Program " + prog + " not found in GDC, ignoring")
                else:
                    programs.append(prog)

        # Avoid accidental attempts to download entire GDC. Also note that
        # other tools do not need to be this stringent, because they can
        # infer programs/projects/cases from mirror or derivatives of it
        if not (programs or projects):
            gabort(0, "Cannot determine programs or projects from config "+
                      "file or command line flags")

        # Everything has validated, so let's get mirroring started
        if not os.path.isdir(config.mirror.dir):
            os.makedirs(config.mirror.dir)

        logging.info("GDC Mirror Version: %s", self.cli.version)
        logging.info("Command: " + " ".join(sys.argv))

        if not projects:
            logging.info("No projects specified, inferring from programs")
            projects = []
            for prgm in programs:
                projects_for_this_program = api.get_projects(program=prgm)
                logging.info("%d project(s) found for %s: %s" % \
                             (len(projects_for_this_program),
                              prgm, ",".join(projects_for_this_program)))
                projects.extend(projects_for_this_program)

        # Make list of which projects belong to each program
        program_projects = dict()
        for project in projects:
            prgm = api.get_program(project)
            if prgm not in program_projects: program_projects[prgm] = []
            program_projects[prgm].append(project)

        # Now loop over each program, acquiring lock
        for prgm in program_projects:
            projects = program_projects[prgm]
            prgm_root = os.path.abspath(os.path.join(config.mirror.dir, prgm))

            with common.lock_context(prgm_root, "mirror"):
                for project in sorted(projects):
                    self.mirror_project(prgm, project)

        # Update the datestamps file with this version of the mirror
        self.update_datestamps_file()
        logging.info("Mirror completed successfully.")

    def __mirror_file(self, file_d, proj_root, n, total, retries=3):
        '''Mirror a file into <proj_root>/<cat>/<type>.

        Files are uniquely identified by uuid.
        '''
        strict = not self.config.mirror.legacy
        savepath = meta.mirror_path(proj_root, file_d, strict=strict)
        dirname, basename = os.path.split(savepath)
        logging.info("Mirroring file {0} | {1} of {2}".format(basename, n, total))

        #Ensure <root>/<cat>/<type>/ exists
        if not os.path.isdir(dirname):
            os.makedirs(dirname)

        md5path = savepath + ".md5"

        # Download if force is enabled or if the file is not on disk
        if (self.force_download or not meta.md5_matches(file_d, md5path, strict)
                or not os.path.isfile(savepath)):

            # New file, mirror to this folder
            while retries > 0:
                try:
                    time = 180
                    #Download file
                    uuid = file_d['file_id']
                    if self.has_cURL:
                        api.curl_download_file(uuid, savepath, max_time=time)
                    else:
                        api.py_download_file(uuid, savepath)
                    break
                except Exception as e:
                    logging.warning("Download failed: " + str(e) +'\nRetrying...')
                    retries = retries - 1
                    # Give some more time, in case the file is large...
                    # TODO: is this worth it?
                    time += 180

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

        datestamp = self.datestamp
        config = self.config.mirror
        logging.info("Mirroring started for {0} ({1})".format(project, program))

        data_categories = config.data_categories
        if not data_categories:
            logging.info("No data_categories specified, using GDC API to " + \
                         "discover ALL available categories")
            data_categories = api.get_data_categories(project)

        logging.info("Using %d data categories: %s" % \
                     (len(data_categories), ",".join(data_categories)))
        proj_dir = os.path.join(config.dir, program, project)
        logging.info("Mirroring data to " + proj_dir)

        # Read the previous metadata, if present
        prev_datestamp = meta.latest_datestamp(proj_dir, None)
        prev_metadata = []
        if prev_datestamp is not None:
            prev_stamp_dir = os.path.join(proj_dir, "metadata", prev_datestamp)
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
        stamp_folder = os.path.join(meta_folder, datestamp)
        if not os.path.isdir(stamp_folder):
            os.makedirs(stamp_folder)

        # Write file metadata
        meta_json = ".".join(["metadata", project, datestamp, "json" ])
        meta_json = os.path.join(stamp_folder, meta_json)
        with open(meta_json, 'w') as jf:
            json.dump(file_metadata, jf, indent=2)

    def mirror_category(self, program, project, category,
                        workflow_type, prev_metadata):
        '''Mirror one category of data in a particular project.
        Return the mirrored file metadata.
        '''
        proj_dir = os.path.join(self.config.mirror.dir, program, project)
        cat_dir = os.path.join(proj_dir, category.replace(' ', '_'))
        strict = not self.config.mirror.legacy

        # Create data folder
        if not os.path.isdir(cat_dir):
            logging.info("Creating folder: " + cat_dir)
            os.makedirs(cat_dir)

        # If cases is a list, only files from these cases will be returned,
        # otherwise all files from the category will be
        cases = self.config.cases
        file_metadata = api.get_project_files(project, category,
                                              workflow_type, cases=cases)

        # Filter out extraneous cases from multi-case (e.g. MAF) file metadata
        # if cases have been specified
        if cases:
            for idx, file_dict in enumerate(file_metadata):
                if len(file_dict.get("cases", [])) > 1:
                    file_metadata[idx]["cases"] = \
                    [case for case in file_metadata[idx]["cases"] \
                     if case["submitter_id"] in cases]

        new_metadata = file_metadata

        # If we aren't forcing a full mirror, check the existing metadata
        # to see what files are new
        if not self.force_download:
            new_metadata = meta.files_diff(proj_dir, file_metadata,
                                           prev_metadata, strict)

        num_files = len(new_metadata)
        logging.info("{0} new {1} files".format(num_files, category))

        for n, file_d in enumerate(new_metadata):
            self.__mirror_file(file_d, proj_dir, n+1, num_files)

        return file_metadata

    def execute(self):
        super(gdc_mirror, self).execute()
        self.parse_args()
        try:
            self.mirror()
        except:
            logging.exception("Mirroring FAILED:")

    def update_datestamps_file(self):
        """ Update the datestamps file with this mirror """
        datestamps_file = self.config.datestamps

        logging.info("Updating datestamps in " + datestamps_file)

        # if it doesn't exist, create a blank one
        if not os.path.isfile(datestamps_file):
            open(datestamps_file, 'w')

        # Now read the file
        datestamps_file = open(datestamps_file, 'r+')
        stamps = datestamps_file.read().strip().split('\n')
        if stamps[-1] != self.datestamp:
            datestamps_file.write(self.datestamp + '\n')

def main():
    gdc_mirror().execute()

if __name__ == "__main__":
    main()
