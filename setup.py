#===============================================================================
# The Broad Institute
# SOFTWARE COPYRIGHT NOTICE AGREEMENT
# This software and its documentation are copyright 2016-2017 by the
# Broad Institute/Massachusetts Institute of Technology. All rights reserved.
#
# This software is supplied without any warranty or guaranteed support whatsoever.
# Neither the Broad Institute nor MIT can be responsible for its use, misuse, or
# functionality.
#===============================================================================

import os
from setuptools import setup, find_packages

#===============================================================================
# Setup
#===============================================================================

README = open('README.md').read()
README = README.replace("&nbsp;","")
README = README.replace("**","")
version = open('VERSION').read().strip()

setup(
	name         = 'gdctools',
    version      = version,
    author       = 'Michael S. Noble, Timothy DeFreitas, David Heiman',
    author_email = 'gdac@broadinstitute.org',
    url          = 'https://github.com/broadinstitute/gdctools',
    packages     = find_packages(),
    description  = (
		"GDCtools: Python and UNIX CLI utils to simplify interaction with the NIH/NCI Genomics Data Commons."
	),
    long_description = README,
    entry_points     = {
		'console_scripts': [
			# FIXME: this list s/b generated from $(TOOLS) macro in Makefile
			'gdc_dice = gdctools.gdc_dice:main',
			'gdc_list = gdctools.gdc_list:main',
			'gdc_mirror = gdctools.gdc_mirror:main',
    		'gdc_loadfile = gdctools.gdc_loadfile:main',
    		'gdc_report = gdctools.gdc_report:main'
		]
	},
    # Put cfg files in bin, but better may be to look in pkg_data config subdir
    data_files = [('bin', ['gdctools/config/tcga.cfg','gdctools/config/google.cfg' ])],
    package_data = {'gdctools': [
                        'config/*.cfg',
                        'lib/annot*.tsv',
                        'lib/GDCSampleReport.R',
                        'reference/*',
                        'default.cfg'
                    ],
                    },
    test_suite   = 'nose.collector',
    install_requires = [
        'requests',
        'fasteners',
        'matplotlib==2.1.1', # v2.1.1 avoids hardcoded dependency on bz2 module
        'future',
        'configparser',
    ],
)
