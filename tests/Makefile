
include ../Makefile.inc

# ---------------------------- Macro definitions ---------------------------

SRC=../gdctools
PYTHON := set -o pipefail && env PYTHONPATH=.. $(PYTHON)
SORT=env LC_COLLATE=C sort
TEST_ROOT=$(ROOT)/tests/$(shell grep ROOT_DIR: $(CONFIG_FILE) | awk '{print $$NF}')
CONFIG_FILE=tcgaSmoketest.cfg
#VERBOSITY=-V
CONFIG=--config $(CONFIG_FILE) $(VERBOSITY)
PROJECT_SUBSET=--projects TCGA-ACC TCGA-SKCM TCGA-ESCA

# To improve readibility of targets definitions below, we define commands to
# encapsulate mirroring/dicing/file finding/loadfile parsing, etc operations
PERFORM_MIRROR=$(PYTHON) $(SRC)/gdc_mirror.py $(CONFIG)
FIND_MIRROR_FILES=cd $(TEST_ROOT)/mirror/TCGA && find TCGA-* \
							-name '*.gz' -o -name '*.xml' -o -name '*.txt'
PERFORM_DICE=$(PYTHON) $(SRC)/gdc_dice.py $(CONFIG) $(PROJECT_SUBSET)
FIND_DICE_FILES=cd $(TEST_ROOT)/dice/TCGA && find TCGA-* -name '*.txt'
FIND_LEGACY_FILES=cd legacy/mirror/TCGA && find TCGA-* -name '*.*' -a ! -name '*.json'
PERFORM_REPORT=$(PYTHON) $(SRC)/gdc_report.py $(CONFIG) $(PROJECT_SUBSET)
PERFORM_LOADF=$(PYTHON) $(SRC)/gdc_loadfile.py $(LOADFILE_FORMAT) $(CONFIG) $(PROJECT_SUBSET)
ifeq ($(LOADFILE_DESTINATION),google)
   # We generate Google-bucketized loadfiles with an additional config file
   CONFIG := --config $(CONFIG_FILE) ../config/google.cfg $(VERBOSITY)
   LOADFILE_SUBDIR=google/
   LOADFILE_MD5=load-md5sums-google.txt
   FILE_PREFIX=$(shell grep FILE_PREFIX: ../config/google.cfg | awk '{print $$NF}')
   # In this mode we also generate FireCloud-style loadfiles, including cases/participants
   CHECK_CASES_LOADFILE=diff -b baselines/TCGA-ACCSKCM.Participant.loadfile.txt $(LOADFILES_DIR)/.
else
   LOADFILE_SUBDIR=
   LOADFILE_MD5=load-md5sums.txt
   FILE_PREFIX=$(TEST_ROOT)
   LOADFILE_FORMAT=--format=firehose
endif
LOADFILES_DIR=$(TEST_ROOT)/loadfiles/$(LOADFILE_SUBDIR)TCGA/latest
# Note: Participant loadfiles are excluded b/c they are NOT generated for legacy/firehose format
FIND_LOAD_FILES=cd $(LOADFILES_DIR) && find . -name 'TCGA-*loadfile.txt' ! -name '*Participant*'
FILE_PREFIX_LENGTH=$(shell printf $(FILE_PREFIX) | wc -c | awk '{print $$NF}')
# The goal of VALIDATE_FILE_PREFIX is to ensure that data files listed within
# the loadfile have correct paths, either to local filesystem or cloud buckets
VALIDATE_FILE_PREFIX=cd $(LOADFILES_DIR) && \
	FILE_PATH=`sed -n '2,2p' TCGA-ACC.Sample.loadfile.txt | cut -f6` && \
	ACTUAL_PREFIX=`echo $$FILE_PATH | cut -c-$(FILE_PREFIX_LENGTH)` && \
	if [ $$ACTUAL_PREFIX != $(FILE_PREFIX) ] ; then \
		echo "File paths in loadfiles must begin with $(FILE_PREFIX)" ; \
		false ; \
	fi
ENSURE_FAILURE_EXIT_CODE=\
	if (($$Result)) ; then \
		echo "Pass: aborted with exit code $$Result" ; \
	else \
		echo "Fail: returned 0 exit code , but should've returned non-zero" ; \
		false ; \
	fi

# --------------------------- Target definitions ---------------------------

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

test: test_smoke test_dice test_loadfiles test_legacy test_report echo_success
test_smoke: echo_ver test_invoke test_mirror test_redo_mirror test_badcfg \
			test_cases test_choose

test_invoke:
	@echo
	@echo Test runnability: invoke some tools to show nothing thrown to stderr
	@$(PYTHON) $(SRC)/GDCcore.py >/dev/null
	@$(PYTHON) $(SRC)/GDCtool.py >/dev/null
	@$(PYTHON) $(SRC)/gdc_mirror.py --help >/dev/null
	@$(PYTHON) $(SRC)/gdc_list.py --help >/dev/null

test_mirror:
	@echo
	@echo "Test mirror: download small set of data, compare to baselines"
	@$(PERFORM_MIRROR) 2>&1 | tee $@.log | egrep "GDC|Mirroring data|Mirroring start"
	$(ABORT_ON_ERROR) $@.log

	@# Now see that the named set of mirrored files matches what we expect
	$(FIND_MIRROR_FILES) | $(SORT) > $(TEST_ROOT)/mirror-files.txt
	diff -b baselines/mirror-files.txt $(TEST_ROOT)/.

	@# Verify integrity (but using our stored MD5s, not those just downloaded)
	$(FIND_MIRROR_FILES) -exec $(MD5) {} \; | $(SORT) > $(TEST_ROOT)/mirror-md5sums.txt
	diff -b baselines/mirror-md5sums.txt $(TEST_ROOT)/.

test_redo_mirror:
	@echo
	@echo Test retry of mirror: nothing should be re-downloaded
	@$(PERFORM_MIRROR) 2>&1 | grep -w new | grep -vl " [^0][0-9]* new " >/dev/null

test_badcfg:
	@echo
	@echo Test that attempting to use bad config file quickly aborts with error
	@touch bad.cfg
	@$(PYTHON) ../gdctools/gdc_mirror.py --config bad.cfg || Result=$$? ; \
	$(ENSURE_FAILURE_EXIT_CODE)
	@echo
	@echo Now test that given bad program/project names also quickly aborts
	@$(PYTHON) ../gdctools/gdc_mirror.py --programs DUMMY || Result=$$? ; \
	$(ENSURE_FAILURE_EXIT_CODE)
	@echo
	@$(PYTHON) ../gdctools/gdc_mirror.py --projects DUMMY || Result=$$? ; \
	$(ENSURE_FAILURE_EXIT_CODE)
	@echo
	@$(PERFORM_DICE) --programs DUMMY 2>&1 | grep -i error || Result=$$? ; \
	$(ENSURE_FAILURE_EXIT_CODE)
	@echo
	@$(PERFORM_LOADF) --projects DUMMY 2>&1 | grep -i error || Result=$$? ; \
	$(ENSURE_FAILURE_EXIT_CODE)
	@echo
	@echo Induce failure in gdc_list, by giving bad input
	@$(PYTHON) $(SRC)/gdc_list.py DUMMY 2>&1 || Result=$$? ; \
	$(ENSURE_FAILURE_EXIT_CODE)

test_choose:
	@echo
	@echo Test that replicate filter is choosing the appropriate aliquots
	@$(PYTHON) testchoose.py

test_dice:
	@echo
	@echo Test dice: on subset of cohorts, to show CLI args override config file
	$(PERFORM_DICE) 2>&1 | tee $@.log  | egrep "Dicing TCGA|date"
	$(ABORT_ON_ERROR) $@.log
	$(FIND_DICE_FILES) | $(SORT) > $(TEST_ROOT)/dice-files.txt
	diff -b baselines/dice-files.txt $(TEST_ROOT)/.

	@# Verify integrity (but using our stored MD5s, not those just downloaded)
	$(FIND_DICE_FILES) -exec $(MD5) {} \; | $(SORT) > $(TEST_ROOT)/dice-md5sums.txt
	diff -b baselines/dice-md5sums.txt $(TEST_ROOT)/.

test_loadfiles:
	# By default GDCtools generates firecloud-style loadfiles, so exercise other
	@$(EMAKE) test_loadfile
	@echo
	@$(EMAKE) test_loadfile LOADFILE_DESTINATION=google

test_loadfile:
	@echo
	@echo "Test $(LOADFILE_DESTINATION) loadfile generation ..."
	$(PERFORM_LOADF) 2>&1 | tee $@.log | egrep "Generating|date"
	$(ABORT_ON_ERROR) $@.log
	# First, ensure that data files are prefixed with appropriate path
	$(VALIDATE_FILE_PREFIX)
	# Now compare names of files
	$(FIND_LOAD_FILES) | $(SORT) > $(TEST_ROOT)/load-files.txt
	diff -b baselines/load-files.txt $(TEST_ROOT)/.
	# Now ensure that replicate etc filter worked
	diff -b baselines/TCGA.filtered_samples.txt $(LOADFILES_DIR)/.
	# And check that case/participants loadfile is OK, if relevant
	$(CHECK_CASES_LOADFILE)
	# Lastly, MD5 compare content after removing local path prefix to files
	$(FIND_LOAD_FILES) -exec sed 's|$(FILE_PREFIX)/||g' {} \; \
						| $(SORT) > $(TEST_ROOT)/load-munged.txt
	$(MD5) $(TEST_ROOT)/load-munged.txt | sed 's|$(TEST_ROOT)/||g' \
						> $(TEST_ROOT)/$(LOADFILE_MD5)
	diff -b baselines/$(LOADFILE_MD5) $(TEST_ROOT)/.

Rscript=$(shell type -P Rscript 2>/dev/null)
test_report:
	@echo
	@if [ -z "$(Rscript)" ] ; then \
		echo "R / Rscript not installed on your system, skipping test_report" ;\
	else \
		echo "Test sample report generation ..." ; \
		$(PERFORM_REPORT) 2>&1 | tee $@.log | egrep "Generating|date" ; \
		$(ABORT_ON_ERROR) $@.log ; \
		(cd $(TEST_ROOT)/reports/latest && find . -name '*.html' | \
									$(SORT) > $(TEST_ROOT)/report-files.txt) ; \
		diff -b baselines/report-files.txt $(TEST_ROOT)/. ; \
	fi

test_cases:
	@echo
	@echo "Test fine-grained retrieval of 1 case (and 1 data category)"
	@$(PYTHON) $(SRC)/gdc_mirror.py --config onlycases.cfg 2>&1 \
					--categories Biospecimen | tee $@.log | \
					egrep "GDC|Mirroring data|Mirroring start|categorie"
	$(ABORT_ON_ERROR) $@.log
	@cd onlycases/mirror/TCGA && find TCGA-* \
					-name '*.*' -a ! -name '*.json' | \
					$(SORT) > ../../onlycases-files.txt
	diff -b baselines/onlycases-files.txt onlycases/.

test_legacy:
	@echo
	@echo "Test legacy data download (for 1 case and 3 data categories)"
	@$(PYTHON) ../gdctools/gdc_mirror.py --config legacy.cfg  2>&1 | \
					tee $@.log | \
					egrep "GDC|Mirroring data|Mirroring start"
	$(ABORT_ON_ERROR) $@.log
	$(FIND_LEGACY_FILES) | $(SORT) > ../../legacy-files.txt
	diff -b baselines/legacy-files.txt legacy/.
	$(FIND_LEGACY_FILES) -exec $(MD5) {} \; | $(SORT) > ../../legacy-md5sums.txt
	diff -b baselines/legacy-md5sums.txt legacy/.

test3:
	$(MAKE) -e PYTHON_VER=3 test

VERTEST="import gdctools as g; print('Version: ' + g.GDCcore.GDCT_VERSION)"
testl:
	@# Test the package locally, as if it were installed
	@$(PYTHON) -c  $(VERTEST)

testi:
	@# Test the installed package
	@(cd /tmp ; $(PYTHON) -c $(VERTEST))

.PHONY: test clean echo_success test_mirror test_dice test_redo_mirror

echo_success:
	@echo
	@echo Success!

echo_ver:
	@echo Using $(PYTHON_HOME)/bin/$(PYTHON_EXE) ...

clean:
	rm -rf build dist *.egg-info *~ test_*.log bad.cfg

rclean: clean
	\rm -rf sandbox GDCtool gdctools_tmp onlycases legacy
