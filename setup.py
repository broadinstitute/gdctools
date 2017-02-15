import os
from setuptools import setup, find_packages

# Setup information
setup(
    name = 'gdctools',
    version = "0.1.0",
    description = 'Firecloud API bindings and FISS CLI',
    author = 'Mike Noble, Tim DeFreitas, David Heiman',
    author_email = 'mnoble@broadinstitute.org',
    packages = find_packages(),
    entry_points = {
        'console_scripts': [
            'gdc_mirror = gdctools.gdc_mirror:main',
            'gdc_dice = gdctools.gdc_dice:main',
            'create_loadfile = gdctools.create_loadfile:main',
            'sample_report = gdctools.sample_report:main',
            'gdc_ls = gdctools.gdc_ls:main' 
        ]
    },
    package_data={'gdctools':['config/*.tsv', 'config/*.cfg', 'lib/GDCSampleReport.R' ]
                },
    install_requires = [
        'requests',
        'fasteners'
    ],

)
