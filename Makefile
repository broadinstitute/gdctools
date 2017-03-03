SHELL=/bin/bash
__FILE__=$(lastword $(MAKEFILE_LIST))
__PATH__=$(abspath $(dir $(__FILE__)))

EMAKE=$(MAKE) -e
TIMESTAMP = $(shell date +"%F %T")
REPO_HASH=$(shell $(GIT) log -n 1 --pretty=%H | cut -c 1-24)
VERSION = $(shell cat $(__PATH__)/VERSION)
LONGVERSION=$(VERSION) ($(TIMESTAMP) $(REPO_HASH))

PYTHON_HOME=$(shell gdctools/config/findPython.sh)
DEST=$(PYTHON_HOME)
BIN_DIR=$(DEST)/bin					# Python virtual environment here
PYTHON=$(DEST)/bin/python
PIP=$(DEST)/bin/pip


help:
	@echo
	@echo "Build, test and install the GDCtools package"
	@echo
	@echo "Targets:"
	@echo
	@echo  "1. test                     Exercise tests for this package"
	@echo  "2. install                  Install locally, using pip"
	@echo  "3. uninstall                Remove local install, using pip"
	@echo  "4. publish                  Submit to PyPI"
	@echo


install:
	pip install --upgrade .

reinstall:
	$(MAKE) uninstall
	$(MAKE) install

uninstall:
	pip uninstall -y gdctools

publish:
	python setup.py sdist upload && \
	rm -rf build dist *.egg-info

clean:
	rm -rf build dist *.egg-info *~

TEST_CONFIG=--config tests/tcgaSmoketest.cfg

test: test_all

test_all: test_smoke test_mirror test_dice test_loadfile test_report

test_smoke:
	@# Basic smoketest in local directory
	@ $(PYTHON) gdctools/GDCcli.py
	@echo
	$(PYTHON) gdctools/GDCtool.py

test_mirror:
	$(PYTHON) gdctools/gdc_mirror.py $(TEST_CONFIG) #> $@.log

test_dice:
	$(PYTHON) gdctools/gdc_dice.py $(TEST_CONFIG)

test_loadfile:
	$(PYTHON) gdctools/create_loadfile.py $(TEST_CONFIG)

test_report:
	$(PYTHON) gdctools/sample_report.py $(TEST_CONFIG)

USE=/broad/tools/scripts/useuse
test3: default
	@# Python 3 compatibility
	if [ -d $(USE) ] ; then \
		. $(USE) && \
		reuse -q Python-3.4 && \
		$(MAKE) -e test ; \
	fi

VERTEST="import gdctools as g; print('Version: ' + g.GDCcore.GDCT_VERSION)"
testl: default
	@# Test the package locally, as if it were installed
	@$(PYTHON) -c  $(VERTEST)

testi:
	@# Test the installed package
	@(cd /tmp ; $(PYTHON) -c $(VERTEST))


.PHONY: help test install release publish clean
