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

    def set_timestamp(self):
        '''Creates a timestamp for the current mirror'''
        self.timestamp = common.timetuple2stamp() #'2017_02_01__00_00_00'
        return self.timestamp


    def init_logs(self):
        log_dir = self.mirror_log_dir
        if log_dir is not None:
            logfile_name = ".".join(["gdcMirror", self.timestamp, "log"])
            if not os.path.isdir(log_dir):
                os.makedirs(log_dir)
            logfile_path = os.path.join(log_dir, logfile_name)
        else:
            logfile_path = None # Logfile is disabled
        common.init_logging(logfile_path, True)


    def parse_args(self):
        """Read options from config, and optionally override them with args"""
        # Config options that can be overridden by cli args
        opts = self.options
        if opts.log_dir is not None: self.mirror_log_dir = opts.log_dir
        if opts.root_dir is not None: self.mirror_root_dir = opts.root_dir
        if opts.projects is not None: self.mirror_projects = opts.projects
        if opts.programs is not None: self.mirror_programs = opts.programs


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
                for project in projects:
                    self.mirror_project(prgm, project)

        logging.info("Mirror completed successfully.")


    def __mirror_file(self, file_d, proj_root, prev_tstamp, n, total, retries=3):
        '''Mirror a file into <proj_root>/<timestamp>.

        If the file exists in the previous root, then a symlink is created to
        the first time the file was downloaded. Otherwise, the file is downloaded
        to the current timestamp folder.
        '''
        tstamp = self.timestamp
        tstamp_root = os.path.join(proj_root, tstamp)

        uuid = file_d['file_id']
        savepath = meta.mirror_path(tstamp_root, file_d)
        dirname, basename = os.path.split(savepath)
        logging.info("Mirroring {0} | {1} of {2}".format(basename, n, total))

        #Ensure <root>/<cat>/<type>/ exists
        if not os.path.isdir(dirname):
            os.makedirs(dirname)

        md5path = savepath + ".md5"
        prev_path = _file_loc(file_d, proj_root, prev_tstamp)

        # Possible States:
        # 1. Fresh mirror, prev_path=None, md5=None --> Download file
        # 2. Existing Mirror, prev_md5 doesn't match --> Download new file
        # 3. prev_md5 matches --> Symlink file to realpath(prev_path)

        if prev_path is None or not meta.md5_matches(file_d, prev_path + ".md5"):
            logging.info("Downloading new file to " + savepath)

            # New file, mirror to this folder
            while retries > 0:
                try:
                    #Download file
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

        # Safety check, should be near impossible to have identical timestamps
        elif tstamp != prev_tstamp:
            # Old file, symlink savepath to the prev_path
            # *But only if this is a new tstamp
            logging.info("Exsting file, symlinking from " + prev_path)
            os.symlink(prev_path, savepath)
            os.symlink(prev_path + '.md5', savepath + '.md5')


    def mirror_project(self, program, project):
        '''Mirror one project folder'''
        tstamp = self.timestamp
        logging.info("Mirroring started for {0} ({1})".format(project, program))
        if self.options.data_categories is not None:
            data_categories = self.options.data_categories
        else:
            logging.info("No data_categories specified, using GDC API to discover available categories")
            data_categories = api.get_data_categories(project)
        logging.info("Found " + str(len(data_categories)) + " data categories: " + ",".join(data_categories))


        tstamp_root = os.path.join(self.mirror_root_dir, program, project, tstamp)
        tstamp_root = os.path.abspath(tstamp_root)
        logging.info("Mirroring data to " + tstamp_root)
        #Ensure timestamp dir exists
        os.makedirs(tstamp_root)

        proj_counts = dict()

        for cat in data_categories:
            cat_counts = self.mirror_category(program, project, cat)
            for code in cat_counts:
                if code not in proj_counts: proj_counts[code] = dict()
                proj_counts[code][cat] = cat_counts[code]

        # Write sample counts
        countsfile = ".".join([project, "sample_counts", tstamp, "tsv"])
        countspath = os.path.join(tstamp_root, countsfile)
        _write_counts(proj_counts, countspath)

        #Symlink /program/project/latest to /program/project/timestamp
        sym_path = os.path.join(self.mirror_root_dir, program, project, "latest")
        common.silent_rm(sym_path)

        logging.info("Symlinking {0} -> {1}".format(sym_path, tstamp_root))
        os.symlink(tstamp_root, sym_path)


    def mirror_category(self, program, project, category):
        '''Mirror one category of data in a particular project.
        Return a dictionary of counts for each sample type, e.g.:
        { "TP" : 100, "TR" : 50, "NT" : 50 }
        '''
        tstamp = self.timestamp
        proj_dir = os.path.join(self.mirror_root_dir, program, project)
        tstamp_dir = os.path.join(proj_dir, tstamp)
        cat_dir = os.path.join(tstamp_dir, category.replace(' ', '_'))

        #Use the last mirror to check for presence of files, and to symlink to
        last_mirror = self.last_mirror_tstamp(program, project)

        logging.info("Mirroring: {0} - {1} data".format(project, category))

        #Create data folder
        if not os.path.isdir(cat_dir):
            logging.info("Creating folder: " + cat_dir)
            os.makedirs(cat_dir)

        file_metadata = api.get_files(project, category)

        # Save metadata in json format for dicing reference, in <data_category>/meta/
        metadata_filename = '.'.join(["metadata", self.timestamp, "json"])
        metadata_path = os.path.join(tstamp_dir, metadata_filename)

        # Merge existing metadata with this category
        meta.append_metadata(file_metadata, metadata_path)

        if self.options.meta_only:
            logging.info("Metadata only option enabled, skipping file mirroring")
        else:
            total_files = len(file_metadata)
            logging.info("Mirroring " + str(total_files) + " " + category + " files")

            for n, file_d in enumerate(file_metadata):
                self.__mirror_file(file_d, proj_dir, last_mirror, n, total_files)

        #Finally, return sample counts
        return meta.sample_counts(file_metadata)

    def last_mirror_tstamp(self, program, project):
        '''Returns the timestamp of the last mirroring run for a project.
        '''
        # If a symlink to latest exists, use the one pointed to by latest.
        proj_dir = os.path.join(self.mirror_root_dir, program, project)
        if not os.path.isdir(proj_dir):
            return None

        latest_sym = os.path.join(proj_dir, "latest")
        if os.path.islink(latest_sym):
            tstamp = os.path.basename(os.readlink(latest_sym))
        else:
            #Otherwise, get the latest folder chronologically
            prev_tstamps = sorted(common.immediate_subdirs(proj_dir))
            tstamp = prev_tstamps[-1] if len(prev_tstamps) > 0 else None

        return tstamp

    def execute(self):
        super(gdc_mirror, self).execute()
        self.parse_args()
        self.set_timestamp()
        self.init_logs()
        self.mirror()

def _file_loc(file_d, proj_root, tstamp):
    '''Return the path of the file described in file_d.
    This could be in the given tstamp folder, or symlinked to another
    timestamped folder, or None, if the file does not exist.
    '''
    if tstamp is None:
        return None
    path = meta.mirror_path(os.path.join(proj_root, tstamp), file_d)
    real_path = os.path.realpath(path)
    if os.path.isfile(real_path):
        return real_path
    else:
        return None

#TODO: Handle explicit types, rather than infer them from the available counts
# E.g. if a project reports no data for a type, ensure a column of zeroes
def _write_counts(counts, f):
    '''Write sample counts dict to file.
    counts = { 'TP' : {'Clinical' : 10, 'BCR': 15, ...},
               'TR' : {'Clinical' : 10, 'BCR': 15, ...},
               ...}
    '''
    types = sorted({dtype for code in counts for dtype in counts[code]})

    with open(f, "w") as out:
        # Write header
        out.write("Sample Type\t" + "\t".join(types) + '\n')
        for code in counts:
            line = code + "\t"
            line += "\t".join([str(counts[code].get(t, 0)) for t in types]) + "\n"
            out.write(line)

        # Write totals
        totals = "Totals"
        for t in types:
            tot = sum([counts[code].get(t, 0) for code in counts])
            totals += "\t" + str(tot)
        out.write(totals + "\n")

if __name__ == "__main__":
    gdc_mirror().execute()
