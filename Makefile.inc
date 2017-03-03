
# Makefile.inc: common definitions for use throughout the set of Makefiles in
# the GDCtools build system.  GNU make 3.81 or later is required by GDCtools.

SHELL=/bin/bash
__FILE__=$(lastword $(MAKEFILE_LIST))
__PATH__=$(abspath $(dir $(__FILE__)))
ROOT=$(__PATH__)

EMAKE=$(MAKE) -e
TIMESTAMP = $(shell date +"%F %T")
REPO_HASH=$(shell $(GIT) log -n 1 --pretty=%H | cut -c 1-24)
VERSION = $(shell cat $(ROOT)/VERSION)
LONGVERSION=$(VERSION) ($(TIMESTAMP) $(REPO_HASH))

PYTHON_HOME=$(shell $(ROOT)/util/findPython.sh)
MD5=$(ROOT)/util/checkMD5.sh
DEST=$(PYTHON_HOME)
BIN_DIR=$(DEST)/bin					# Python virtual environment here
PYTHON=$(DEST)/bin/python
PIP=$(DEST)/bin/pip
