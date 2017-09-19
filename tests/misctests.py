
from __future__ import print_function
import gdctools.lib.api as api

print('All projects in TCGA program:{0}'.format(api.get_projects('TCGA')))
