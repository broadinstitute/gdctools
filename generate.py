
# Experimental code, to explore how to best automate wrapper generation

import GDCcore as core
from pprint import pprint

core.set_codec(core.CODEC_DJSON)
Endpoints=["projects", "cases", "files", "annotations"]
#Endpoints = ["files"]

fields = {}

for ep in Endpoints:
    mapping = ep + "/_mapping"
    core.set_debug(True)
    mapping = core.get(mapping)
    continue
    print("\n\n%s/_mapping contains: %s" % (ep, str(mapping.keys())))
    print(ep + " endpoint supports the query fields: ")
    for field in mapping["fields"]:
        print("\t" + field)
        terms = field.split(".")
        terms.reverse()
        fields.setdefault(terms[0], []).extend(terms[1:])

    pprint(fields)
