
# Copyright (c) 2016, Broad Institute, Inc. {{{
# All rights reserved.
#
# This file is part of GDCtools: Python and UNIX commandn line wrappers
# for the Genomics Data Commons api.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name Broad Institute, Inc. nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE
# }}}

from __future__ import print_function
import os
import re
import sys
import inspect
import requests
import builtins
import logging
from pkg_resources import get_distribution, DistributionNotFound

__interactive__ = os.isatty(sys.stdout.fileno())

# Silence SSL warnings on older systems: should check Unix kernel
requests.packages.urllib3.disable_warnings()

GDC_ROOT_URI = "https://gdc-api.nci.nih.gov"
try:
    GDCT_VERSION = get_distribution('gdctools').version
except DistributionNotFound as dnf:
    GDCT_VERSION = 'TESTING'

def eprint(*args, **kwargs):
    # If not interactive (e.g. writing to log), show user from whence msg came
    if not __interactive__:
        print('gdctools Error: ', file=sys.stderr, end='')
    print(*args, file=sys.stderr, **kwargs)

def gprint(*args, **kwargs):
    # If not interactive (e.g. writing to log), show user from whence msg came
    if not __interactive__:
        print('gdctools: ', file=sys.stdout, end='')
    print(*args, file=sys.stdout, **kwargs)

def gabort(errCode, *args, **kwargs):
    gprint(*args, **kwargs)
    # This purpose of this method is to abort with a short, easily comprehended
    # message; so, disable logging to stop it from printing exception stacktrace
    logging.disable(logging.CRITICAL)
    sys.exit(errCode)

class attrdict(dict):
    """ dict whose members can be accessed as attributes, and default value is
    transparently returned for undefined keys; this yields more natural syntax
    dict[key]/dict.key for all use cases, instead of dict.get(key, <default>)
    """

    def __init__(self, srcdict=None, default=None):
        if srcdict is None:
            srcdict = {}
        dict.__init__(self, srcdict)
        self.__dict__["__default__"] = default

    def __getitem__(self, item):
        try:
            return dict.__getitem__(self, item)
        except KeyError:
            return self.__dict__["__default__"]

    def __getattr__(self, item):
        return self.__getitem__(item)

    def __setattr__(self, item, value):
        if item in self.__dict__:
            dict.__setattr__(self, item, value)
        else:
            self.__setitem__(item, value)
