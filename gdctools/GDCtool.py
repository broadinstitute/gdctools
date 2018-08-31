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
    def __init__(self, version="", description=None, datestamp_required=True):
        self.version = version + " (GDCtools: " + GDCT_VERSION + ")"
        self.cli = argparse.ArgumentParser( description=description,
                    formatter_class=argparse.RawDescriptionHelpFormatter)

        self.datestamp_required = datestamp_required
        self.config_add_args()
        self.cli.add_argument('--version', action='version', version=self.version)
        self.cli.add_argument('-V', '--verbose', dest='verbose',
                action='count', help=\
                'Each time specified, increment verbosity level [%(default)s]')

        # Derived classes should add custom options & behavior in their
        # respective __init__/config_customize/execute implementations

    def execute(self):
        self.options = self.cli.parse_args()
        api.set_verbosity(self.options.verbose)

        if not self.config_supported():
            return

        self.config_initialize()
        self.config_customize()
        self.config_finalize()

        if self.datestamp_required:
            datestamp = self.options.datestamp
            if not datestamp:
                datestamp = 'latest'

            existing_dates = self.datestamps()         # ascending sort order
            if len(existing_dates) == 0:
                raise ValueError("No datestamps found, use upstream tool first")

            if datestamp == 'latest':
                datestamp = existing_dates[-1]
            elif datestamp not in existing_dates:
                raise ValueError("Requested datestamp not present in "
                             + self.config.datestamps + "\n"
                             + "Existing datestamps: " + repr(existing_dates))
        else:
            datestamp = time.strftime('%Y_%m_%d', time.localtime())

        self.datestamp = datestamp
        self.init_logging()

    def get_values_as_list(self, values):
        if values:
            if type(values) is list:
                return values
            return [ v.strip() for v in values.split(',') ]
        else:
            return [ ]

    def config_supported(self):
        return True

    def config_add_args(self):
        ''' If tool supports config file (i.e. a named [TOOL] section), then
        reflect config file vars that are common across all tools as CLI args,
        too.  Note that args with nargs=+ will be instantiated as lists.'''
        if not self.config_supported():
            return
        cli = self.cli
        cli.add_argument('--config', nargs='+', type=argparse.FileType('r'),
                            help='One or more configuration files')

        if self.datestamp_required:
            cli.add_argument('--date', nargs='?', dest='datestamp',
                help='Use data from a given dated version (snapshot) of '
                'GDC data, specified in YYYY_MM_DD form.  If omitted, '
                'the latest available snapshot will be used.')
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

    def config_initialize(self):
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
            # Note that tool-specific sections should be named to match the
            # tool name, i.e. [toolname] for each gdc_<toolname> tool
            config[section] = attrdict()
            for option in cfgparser.options(section):
                # DEFAULT vars ALSO behave as though they were defined in every
                # section, but we purposely skip them here so that each section
                # reflects only the options explicitly defined in that section
                if not config[option]:
                    config[section][option] = cfgparser.get(section, option)

        self.validate_config(["root_dir"], UnsetValue={})
        if not config.datestamps:
            config.datestamps = os.path.join(config.root_dir, "datestamps.txt")

        if not config.missing_file_value:
            config.missing_file_value = "__DELETE__"

        # Ensure that aggregate cohort names (if present) are in uppercase
        # (necessary because ConfigParser returns option names in lowercase)
        # If no aggregates are defined, change None obj to empty dict, for
        # cleaner "if X in config.aggregates:" queries that will always work
        if config.aggregates:
            for key, val in config.aggregates.items():
                config.aggregates[key.upper()] = config.aggregates.pop(key)
        else:
            config.aggregates = {}

        for var in ["cases", "categories", "projects", "programs"]:
            config[var] = self.get_values_as_list(config[var])

    def config_customize(self):
        pass

    def config_finalize(self):
        # Here we define & enforce precedence in runtime/configuration state:
        #   1) amongst the SCOPES (sources) from which that state is gathered
        #   2) then using intersection to decide what needs to be processed
        #
        # The runtime configuration of each GDCtool comes from several SCOPES
        #   - built in defaults
        #   - configuration files
        #   - command line flags
        # in order of increasing precedence (CLI flags highest). For example,
        # setting --cases <something> at the command line will override a
        # CASES: entry in a configuration file.  Note we need to enforce this
        # precedence explicitly here because of an unavoidable chicken/egg
        # problem: namely that precdence can't be enforced simply by waiting
        # to parse the CLI args UNTIL AFTER reading the config file, because
        # --config is ALSO a CLI arg.  So we have to give the --config CLI flag
        # a chance to be used in config_initialize(), then override the config
        # file variables (as given in named sections) here if they were ALSO
        # set as CLI flags.
        #
        # After scoping the values of each configuration variable, we then
        # intersect the cases/projects/programs values to ultimately decide
        # what to process (i.e. what samples to mirror/download, dice, etc)

        def enforce_scope(From, To):
            if From.log_dir:    To.log_dir    = From.log_dir
            if From.workflow:   To.workflow   = From.workflow
            if From.categories: To.categories = From.categories
            if From.programs:   To.programs   = From.programs
            if From.projects:   To.projects   = From.projects
            if From.cases:      To.cases      = From.cases

        config = self.config
        toolname = self.__class__.__name__.split('gdc_')[-1]
        enforce_scope(config[toolname], config)
        enforce_scope(self.options, config)

        # Determine what to ultimately process, noting that
        #
        #  - explicitly specified cases implicitly constrain projects & programs
        #  - explicitly specified projects implicitly constrains programs
        #
        # and using intersection here to adjudicate.  Also note that specifying
        #
        #  - only a program selects all projects & cases within that program
        #  - only a project selects all cases for that project (w/in 1 program)
        #
        # but effect of the latter two is achieved downstream (not here), when
        # the invoked tool is performing its function. Finally, nearly all
        # GDCtools utilities need at least 1 case, project or program to be
        # specified as a prerequisite to nominal operation.

        projs = set(api.get_project_from_cases(config.cases))
        if not projs:
            projs = set(config.projects)
        elif config.projects:
            projs &= set(config.projects)
            # If this results in an empty set of projects, reset to CLI value
            # as warning sign (by trying to induce downstream failure/exception)
            if not projs:
                projs = config.projects

        progs = set(api.get_programs(projs))
        if not progs:
            progs = set(config.programs)
        elif config.programs:
            progs &= set(config.programs)
            # If this results in an empty set of programs, reset to CLI value
            # as warning sign (by trying to induce downstream failure/exception)
            if not progs:
                progs = config.programs

        config.projects = list(projs)
        config.programs = list(progs)
        for var in ["cases", "categories", "projects", "programs"]:
            config[var] = self.get_values_as_list(config[var])

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
                                 self.version))
        gprint('#')  # @UndefinedVariable

if __name__ == "__main__":

    class ToolExample(GDCtool):
        def config_supported (self):
            return False

    tool = ToolExample()
    tool.execute()
    tool.status()
