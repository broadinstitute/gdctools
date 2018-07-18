
from __future__ import print_function
import gdctools.lib.api as api
import json

projects = [ json.dumps(s) for s in api.get_projects('TCGA')]
print('All projects in TCGA program:{}'.format(projects))
