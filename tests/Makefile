
include ../Makefile.inc

SRC=../gdctools
TEST_ROOT=$(ROOT)/tests/$(shell grep ROOT_DIR: $(CONFIG_FILE) | awk '{print $$NF}')
CONFIG_FILE=tcgaSmoketest.cfg
CONFIG_FLAG=--config $(CONFIG_FILE)
DEFAULT_TESTS=test_smoke test_mirror
TCGA_DATA_DIR=$(TEST_ROOT)/mirror/TCGA 
FIND_TCGA_FILES=cd $(TCGA_DATA_DIR) && find TCGA-* -name '*.gz'
PERFORM_MIRROR=$(PYTHON) $(SRC)/gdc_mirror.py $(CONFIG_FLAG)

help:
	@echo
	@echo "Run various GDCtools tests.  Requires GNUmake 3.81 or later"
	@echo
	@echo "Targets:"
	@echo
	@echo  "1. test                     Exercise tests for this package"
	@echo  "2. install                  Install locally, using pip"
	@echo  "3. uninstall                Remove local install, using pip"
	@echo  "4. publish                  Submit to PyPI"
	@echo


test: $(DEFAULT_TESTS)

test_all: $(DEFAULT_TESTS) test_redo_mirror test_dice test_loadfile test_report

test_smoke:
	@# Basic smoketest in local directory: can anything even run?
	@ $(PYTHON) $(SRC)/GDCcli.py
	@echo
	$(PYTHON) $(SRC)/GDCtool.py

test_mirror:
	@# Mirror a very small amount of data (and filter most of the output)
	@$(PERFORM_MIRROR) 2>&1 | grep Mirror

	@# Now see that the named set of mirrored files matches what we expect
	$(FIND_TCGA_FILES) > $(TEST_ROOT)/mirrored-files.txt
	diff baselines/mirrored-files.txt $(TEST_ROOT)/.

	@# Verify integrity (but using our stored MD5s, not those just downloaded)
	$(FIND_TCGA_FILES) -exec $(MD5) {} \; > $(TEST_ROOT)/md5sums.txt
	diff baselines/md5sums.txt $(TEST_ROOT)/.

test_redo_mirror:
	@echo Test that redoing a mirror does not download files already mirrored
	@$(PERFORM_MIRROR) 2>&1 | grep -w new | grep -vl " [^0][0-9]* new " >/dev/null

test_dice:
	$(PYTHON) $(SRC)/gdc_dice.py $(CONFIG_FLAG)

test_loadfile:
	$(PYTHON) $(SRC)/create_loadfile.py $(CONFIG_FLAG)

test_report:
	$(PYTHON) $(SRC)/sample_report.py $(CONFIG_FLAG)

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

.PHONY: test clean

clean:
	rm -rf build dist *.egg-info *~ *mirror.log

rclean: clean
	\rm -rf sandbox GDCtool
