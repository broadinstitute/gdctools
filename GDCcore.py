
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
import __builtin__

from GDCversion import GDCT_VERSION
__interactive__ = os.isatty(sys.stdout.fileno())

# Silence SSL warnings on older systems: should check Unix kernel
requests.packages.urllib3.disable_warnings()

GDC_ROOT_URI = "https://gdc-api.nci.nih.gov"

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

def gabort(errCode=1, *args, **kwargs):
    gprint(*args, **kwargs)
    sys.exit(errCode)

class attrdict(dict):
    """ dict where members can be accessed as attributes, and default value
    returned for non-existent attributes is None.
    """
    def __init__(self, srcdict=None, default=None):
        if srcdict is None:
            srcdict = {}
        dict.__init__(self, srcdict)

    def __getattr__(self, item):
        try:
            return self.__getitem__(item)
        except KeyError:
            return None

    def __setattr__(self, item, value):
        if self.__dict__.has_key(item):
            dict.__setattr__(self, item, value)
        else:
            self.__setitem__(item, value)

# --- Below is code borrowed from fbget (FireBrowse client bindings) ---
# --- Needs more scrubbing/pruning -------------------------------------

__builtinHelp = __builtin__.help

def __autohelp(obj):
    # Intercept help calls so that autohelp-decorated funcs always show correct
    # name, docstring, and signature.  For our purpose (of allowing funcs to
    # be called with zero args, even when they have required args), this works
    # better than functools.wraps & decorator module, and is smaller/simpler
    wrapped = getattr(obj, "__autohelp__", None)
    if wrapped:
        __builtinHelp(wrapped)
    else:
        __builtinHelp(obj)

__builtin__.help = __autohelp

def __annotate_wrapper(wrapper, func):
    setattr(wrapper, "__autohelp__", func)
    setattr(wrapper, "__name__", func.__name__)
    setattr(wrapper, "__doc__", func.__doc__)

def autohelp(hasSemiRequiredArgs):
    def helpWrapper(func):
        # Funcs called with zero args will helpfully emit docstring giving
        # complete usage info, instead of less-helpfully raising TypeError

        spec = inspect.getargspec(func)
        nargs_reqd = len(spec.args) + hasSemiRequiredArgs
        nargs_reqd -= len(spec.defaults) if spec.defaults else 0

        def check_args(*args, **kwargs):
            nargs_given = len(args) + len(kwargs)
            nkeywords = len(kwargs)
            if nargs_reqd and (nargs_given < nargs_reqd):
                return __builtinHelp(func)
            return func(*args, **kwargs)

        __annotate_wrapper(check_args, func)
        return check_args
    return helpWrapper

def __has_enough_args(func, mapping, *args, **kwargs):
    defaults = inspect.getargspec(func).defaults
    reqArgs = mapping['params']["required"]
    semiReq = mapping['params']["semiReq"]
    # First see if we have all mandatory positional arguments
    num_positional = len(args)
    num_required = len(reqArgs)
    enoughArgs = num_positional >= num_required
    # If so then ALSO ensure we have at least 1 of any semi-required arg
    if enoughArgs and semiReq and num_positional == num_required:
        # No semiReq positional params, so check keywords & value !=None
        enoughArgs = False
        for i in range(len(semiReq)):
            param = semiReq[i]
            value = kwargs[param] if param in kwargs else defaults[i]
            if value:
                enoughArgs = True
                break

    if enoughArgs:
        return ""

    errMsg = ""
    if reqArgs:
        errMsg += "%s() call " % func.__name__
        errMsg += "missing required arg(s):: "+", ".join(reqArgs)
    if semiReq:
        if errMsg:
            errMsg += " AND at least one of: "
        else:
            errMsg += "%s() call " % func.__name__
            errMsg += "has missing/None arg value(s), need at least one of"
        errMsg += ": " + " OR ".join(semiReq)
    return errMsg

def hlwrap(lowLevelFuncName):
    def hlWrapper(func):
        # fbHLMap cannot be referenced directly, b/c closures are determined at
        # compile time, so instead we peek at namespace of the decorated func
        # We use fbHLMap instead of simply calling inspect.getargspec(func), b/c
        # from the latter we can't distinguish between required & semi-required
        # (short of declaring as <semiReqArg>=<obscure_sentinel_value_not_None>)

        hlmap = func.func_globals["fbHLMap"]
        mapping = hlmap.get(lowLevelFuncName, None)
        if mapping == None:
            raise KeyError("hlwrap cannot be applied to: %s" % lowLevelFuncName)

        # Attach low level docstring
        llfunc = eval("__"+lowLevelFuncName, func.func_globals)
        func.__doc__ += llfunc.__doc__.replace('\n    ', '\n')

        def check_args(*args, **kwargs):
            error = __has_enough_args(func, mapping, *args, **kwargs)
            if not error:
                return func(*args, **kwargs)
            # Too few args passed: so print err msg, then high & low level docs
            print(error)
            __builtinHelp(func)

        __annotate_wrapper(check_args, func)

        # Add to list of functions that can be called directly from CLI
        hlmap[func.__name__] = check_args
        return check_args
    return hlWrapper

CODEC_DJSON = "djson"       # See documentation in set_codec()
CODEC_JSON  = "json"
CODEC_TSV   = "tsv"
CODEC_CSV   = "csv"
PAGES_ALL   = -1            # retrieve all N pages of a given RESTful call

__host = os.uname()[1].split('.')[0]
__gdc_config = attrdict({
    'codec'     : CODEC_JSON,
    'host'      : 'gdc-api.nci.nih.gov',
    'debug'     : False,
    'page_size' : 1000      # 4X the RESTful api default, for performance
})

def __jcat(src, chunk):
    chunk = chunk.json()
    if not src:
        return chunk
    # For single-key JSON/dict objects, concatenate json[key] onto src[key]: a
    # simple dict.update() will not work b/c it will replace the value of the
    # key field in src with that of chunk, but our goal is increase the length
    # of the field in src (which should be list) with the value of the same
    # field in chunk.  AGAIN, THIS ONLY WORKS (MAKES SENSE) FOR SINGLE-KEY JSON
    k = chunk.keys()
    if len(k) > 1:
        raise TypeError("multi-page JSON can only be combined if single-key")
    k = k[0]
    src.setdefault(k,[]).extend(chunk[k])
    return src

__Decoders = {
    CODEC_DJSON : ({}, __jcat),
    CODEC_JSON  : ('', lambda x,y : x + y.text),
    CODEC_TSV   : ('', lambda x,y : x + y.text),
    CODEC_CSV   : ('', lambda x,y : x + y.text),
}

@autohelp(False)
def set_codec(codec):
    ''' Set the default decoding for HTTP responses.  By default FireBrowse
    will return JSON or TSV verbatim (as plain text); but if you want JSON
    to be automatically decoded to a Python dict, then specify CODEC_DJSON.
    A similar effect may be achieved by specifying format=CODEC_DJSON to
    individual wrapper function calls (e.g. Samples.mRNASeq); but in that
    case the effect applies only to results of that specific call, while
    using this function ensures the effect persists for multiple calls.  The
    following codecs are supported:

        CODEC_JSON      verbatim JSON (returns unicode text)
        CODEC_DJSON     decoded JSON  (returns Python dict)
        CODEC_TSV       verbatim TSV  (returns unicode text)
        CODEC_CSV       verbatim CSV  (returns unicode text)

    Attempts to set the codec to an unsupported value will be silently ignored.
    '''
    if __Decoders.get(codec, None):
        __gdc_config.codec = codec 

def get_codec():
    ''' Return the current default codec.  See set_codec() for more details '''
    return __gdc_config.codec

def get_host():
    ''' Return current setting of the remote server hosting the GDC api'''
    return __gdc_config.host

@autohelp(False)
def set_host(host):
    '''Set name of remote host to which FireBrowse api calls will be routed'''
    if host.startswith('http://'):
        url=host
        host=host[7:]
    else:
        url = 'http://' + host
    try:
        response = requests.get(url)
    except Exception as e:
        raise RuntimeError("set_host FAILED: could not reach remote host "+url)
        #raise
    __gdc_config.host = host

@autohelp(False)
def set_debug(toggle):
    ''' Toggle debugging on / off for selected FireBrowse api calls '''
    prev = __gdc_config.debug
    __gdc_config.debug = True if toggle else False
    return prev

@autohelp(False)
def set_page_size(value):
    ''' Customize the default page size '''
    prev = __gdc_config.page_size
    if value:
        __gdc_config.page_size = value
    return prev

def get_page_size():
    ''' Return setting of the page size to be requested by client '''
    return __gdc_config.page_size

def get(url, codec=None, verify=False, stream=True, pages=1):
    '''
    Invoke GDC REST api call via given URL.  This is for internal use;
    external users should employ the low level bindings or high level wrappers
    '''

    if not codec:
        codec = __gdc_config.codec

    result, cat = __Decoders.get(codec, (None, None))
    if result == None:
        raise KeyError('unsupported codec : %s' % str(codec))

    pages = pages if pages > 0 else sys.maxint

    if not url.startswith("http"):
        url = "http://%s/%s" % (__gdc_config.host, url)

    while True:
        if __gdc_config.debug:
            gprint("GDCcore GET:  " + url)

        chunk = requests.get(url, verify=verify, stream=stream)
        if not chunk.ok:
            eprint("\nGDCcore ERROR calling: url="+url)
            eprint("GDCcore ERROR response="+chunk.text)
            raise chunk.raise_for_status()
        pages -= 1
        result = cat(result, chunk)
        if pages > 0 and 'next' in chunk.links:
            url = (chunk.links['next']['url'])
        else:
            break
        
    return result
