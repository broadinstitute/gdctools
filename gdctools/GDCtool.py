#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

GDCtool.py: this file is part of gdctools.  See the <root>/COPYRIGHT
file for the SOFTWARE COPYRIGHT and WARRANTY NOTICE.

@author: Michael S. Noble, Timothy DeFreitas, David I. Heiman
@date:  2016-05-20
'''

# }}}

import sys
import os
import traceback
import configparser
import time
import logging
from pkg_resources import resource_filename
from gdctools.GDCcore import *
from gdctools.lib import common
from gdctools.lib import api
from signal import signal, SIGPIPE, SIG_DFL
import argparse

# Stop Python from complaining when I/O pipes are closed
signal(SIGPIPE, SIG_DFL)

class GDCtool(object):
    ''' Base class for each tool in the GDCtools suite '''
    def __init__(self, version="", description=None, configureAble=True):
        self.configureAble = configureAble
        self.version = version + " (GDCtools: " + GDCT_VERSION + ")"
        self.cli = argparse.ArgumentParser(version=self.version,
                    description=description,
                    formatter_class=argparse.RawDescriptionHelpFormatter)

        # If caller supports use of config file, add corresponding CLI args
        if configureAble:
            self.addConfigurableArgs()

        self.cli.add_argument('-V', '--verbose', dest='verbose',
                action='count', help=\
                'Each time specified, increment verbosity level [%(default)s]')
        # Derived classes should add custom options & behavior in their
        # respective __init__()/execute() implementations

    def addConfigurableArgs(self):
        # Note that args with nargs=+ will be instantiated as lists
        cli = self.cli
        cli.add_argument('--config', nargs='+', type=argparse.FileType('r'),
                            help='One or more configuration files')
        cli.add_argument('--date', nargs='?', dest='datestamp',
                    help='Use data from a given dated mirror (snapshot) of '
                    'GDC data, specified in YYYY_MM_DD form.  If omitted, '
                    'the latest downloaded snapshot will be used.')
        cli.add_argument('--cases', nargs='+', metavar='case_id',
                    help='Process data only from these GDC cases')
        cli.add_argument('--categories',nargs='+',metavar='category',
                help='Mirror data only from these GDC data categories. '
                'Note that many category names contain spaces, so use '
                'quotes to delimit (e.g. \'Copy Number Variation\')')
        cli.add_argument('-L', '--log-dir',
                    help='Directory where logfiles will be written')
        cli.add_argument('--programs', nargs='+', metavar='program',
                    help='Process data only from these GDC programs')
        cli.add_argument('--projects', nargs='+', metavar='project',
                    help='Process data only from these GDC projects')
        cli.add_argument('--workflow',
                help='Process data only from this GDC workflow type')

    def execute(self):
        self.options = self.cli.parse_args()
        if not self.configureAble:
            return
        self.parse_config()
        self.reconcile_config()

        # Get today's datestamp, the default value
        datestamp = time.strftime('%Y_%m_%d', time.localtime())

        if self.options.datestamp:
            # We are using an explicit datestamp, so it must match one from
            # the datestamps file, or be the string "latest"
            datestamp = self.options.datestamp
            existing_stamps = self.datestamps()

            if datestamp == "latest":
                if len(existing_stamps) == 0:
                    raise ValueError("No existing datestamps,"
                                     "cannot use 'latest' datestamp option ")
                # already sorted, so last one is latest
                datestamp = existing_stamps[-1]
            elif datestamp not in existing_stamps:
                # Timestamp not recognized, but print a combined message later
                raise ValueError("Given datestamp not present in "
                                 + self.config.datestamps + "\n"
                                 + "Existing datestamps: " + repr(existing_stamps))

        self.datestamp = datestamp
        self.init_logging()

    def get_config_values_as_list(self, values):
        if values:
            if type(values) is list:
                return values
            return [ v.strip() for v in values.split(',') ]
        else:
            return [ ]

    def parse_config(self):
        '''
        Read initial configuration state from one or more config files; store
        this state within .config member, a nested dict whose keys may also be
        referenced as attributes (safely, with a default value of None if unset)
        '''

        self.config = attrdict(default=attrdict())      # initially empty
        if not self.options.config:                     # list of file objects
            # No config file specified, use default
            cfg_default = resource_filename(__name__, "default.cfg")
            self.options.config = [open(cfg_default,"r")]

        cfgparser = configparser.SafeConfigParser()
        # The argparse module turns CLI config file args into file handles,
        # but config parser expects file names, so convert them here
        cfgparser.read([f.name for f in self.options.config])
        config = self.config

        # [DEFAULT] defines common variables for interpolation/substitution in
        # other sections, and are stored at the root level of the config object
        for keyval in cfgparser.items('DEFAULT'):
            config[keyval[0]] = keyval[1]

        for section in cfgparser.sections():
            config[section] = attrdict()
            for option in cfgparser.options(section):
                # DEFAULT vars ALSO behave as though they were defined in every
                # section, but we purposely skip them here so that each section
                # reflects only the options explicitly defined in that section
                if not config[option]:
                    config[section][option] = cfgparser.get(section, option)

        # FIXME: should this check for more config variables?
        self.validate_config(["root_dir"], UnsetValue={})
        if not config.datestamps:
            config.datestamps = os.path.join(config.root_dir, "datestamps.txt")

        if not config.missing_file_value:
            config.missing_file_value = "__DELETE__"

        # Ensure programs,projects,cases,data_categories config state are lists
        config.programs = self.get_config_values_as_list(config.programs)
        config.projects = self.get_config_values_as_list(config.projects)
        config.cases    = self.get_config_values_as_list(config.cases)

        # Ensure that aggregate cohort names (if present) are in uppercase
        # (necessary because ConfigParser returns option names in lowercase)
        # If no aggregates are defined, change None obj to empty dict, for
        # cleaner "if X in config.aggregates:" queries that will always work
        if config.aggregates:
            for key, val in config.aggregates.items():
                config.aggregates[key.upper()] = config.aggregates.pop(key)
        else:
            config.aggregates = {}

    def reconcile_config(self):
        # The runtime configuration of each GDCtool comes from several sources
        #   - built in defaults
        #   - configuration files
        #   - command line flags
        # in order of increasing precedence (i.e. cmd line flags are highest).
        # We enforce that precedence with this method, because it cannot be
        # done simply by parsing the CLI args after reading the config file,
        # as --config is also a cmd line flag.  So we have to give --config
        # CLI flag "a chance" to be utilized in parse_config(), then override
        # the config variables here if they were ALSO set at the command line

        opts = self.options
        config = self.config
        if opts.programs: config.programs = opts.programs
        if opts.projects: config.projects = opts.projects
        if opts.cases: config.cases = opts.cases
        if opts.log_dir : config.log_dir = opts.log_dir
        if opts.workflow : config.workflow = opts.workflow

        # If a list of individual cases has been specified then it completely
        # defines the projects & programs to be queried, and takes precedence
        # over any other configuration file settings or command line flags
        if config.cases:
            config.projects = api.get_project_from_cases(config.cases)
            config.programs = api.get_programs(config.projects)
        elif config.projects:
            # Simiarly, if projects is specified then the programs corresponding
            # to those projects takes precedence over config & CLI values
            config.programs = api.get_programs(config.projects)

        if opts.verbose:
            api.set_verbosity(opts.verbose)

    def validate_config(self, vars_to_examine, UnsetValue=None):
        '''
        Ensure that sufficient configuration state has been defined for tool to
        initiate its work; should only be called after CLI flags are parsed,
        because CLI has the highest precedence in setting configuration state
        '''
        for v in vars_to_examine:
            result = eval("self.config." + v)
            if result == UnsetValue:
                gabort(100, "Required config variable is unset: %s" % v)

    def datestamps(self):
        """ Returns a list of valid datestamps by reading the datestamps file """
        if not os.path.isfile(self.config.datestamps):
            return []
        else:
            raw = open(self.config.datestamps).read().strip()
            if not raw:
                return [] # Empty file
            else:
                # stamps are listed one per line, sorting is a sanity check
                return sorted(raw.split('\n'))

    def init_logging(self):

        if not self.config:
            return

        log_dir = self.config.log_dir
        datestamp = self.datestamp
        tool_name = self.__class__.__name__
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        log_formatter = logging.Formatter('%(asctime)s[%(levelname)s]: %(message)s')

        # Write logging data to file
        if log_dir and datestamp is not None:
            log_dir = os.path.join(log_dir, tool_name)
            if not os.path.isdir(log_dir):
                try:
                    os.makedirs(log_dir)
                except:
                    logging.info(" could not create logging dir: " + log_dir)
                    return

            logfile = os.path.join(log_dir, ".".join([tool_name, datestamp, "log"]))
            logfile = common.increment_file(logfile)

            file_handler = logging.FileHandler(logfile)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(log_formatter)
            root_logger.addHandler(file_handler)

            logging.info("Logfile:" + logfile)
            # For easier eyeballing & CLI tab-completion, symlink to latest.log
            latest = os.path.join(log_dir, "latest.log")
            common.silent_rm(latest)
            os.symlink(os.path.abspath(logfile), latest)

        # Send to console, too, if running at valid TTY (e.g. not cron job)
        if os.isatty(sys.stdin.fileno()):
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(log_formatter)
            root_logger.addHandler(console_handler)

    def status(self):
        # Emit system info (as header comments suitable for TSV, etc) ...
        gprint('#')  # @UndefinedVariable
        gprint('# %-22s = %s' % (self.__class__.__name__ + ' version ',  # @UndefinedVariable
                                 self.cli.version))
        gprint('#')  # @UndefinedVariable

if __name__ == "__main__":
    tool = GDCtool()
    tool.execute()
    tool.status()
