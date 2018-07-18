
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

# Root dir for test data is NOT within dev tree, so as to save time & disk space
# during pip install (because pip copies entire dev tree during packaging)
TEST_CONFIG_FILE=$(ROOT)/tests/tcgaSmoketest.cfg
TEST_ROOT=$(abspath $(ROOT)/tests/$(shell grep ROOT_DIR: $(TEST_CONFIG_FILE) | awk '{print $$NF}'))

# Simple way to use Python3, e.g. for install, tests etc:
#               make -e PYTHON_VER=3 install test
# This will automatically adjust pip to Python3, too

PYTHON_VER=
PYTHON_EXE=python$(PYTHON_VER)
PYTHON_HOME=$(shell $(ROOT)/util/findPython.sh $(PYTHON_EXE))
ifeq ($(PYTHON_HOME),)
$(error Unable to continue, no $(PYTHON_EXE) found)
endif
MD5=$(ROOT)/util/checkMD5.sh
DEST=$(PYTHON_HOME)
BIN_DIR=$(DEST)/bin					# Python virtual environment here
PYTHON=$(DEST)/bin/$(PYTHON_EXE)
PIP=$(DEST)/bin/pip$(PYTHON_VER)

ABORT_ON_ERROR=$(ROOT)/util/checkError.sh
