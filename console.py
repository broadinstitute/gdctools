
# Simple func for each mdbtool to be used from the CLI: infer the tool name at
# runtime, instantiate an object of that class, then call its execute() method

def console():
    import os
    import sys
    import mdbtools
    tool = os.path.basename(sys.argv[0])
    klass = getattr(mdbtools, tool)
    klass().execute()
