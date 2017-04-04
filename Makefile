
include Makefile.inc

help:
	@echo
	@echo "Build, test and install GDCtools.  Requires GNUmake 3.81 or later"
	@echo
	@echo "Targets:"
	@echo
	@echo  "1. test | test3             Exercise tests for this package"
	@echo  "2. install                  Install locally, using pip"
	@echo  "3. uninstall                Remove local install, using pip"
	@echo  "4. publish                  Submit to PyPI"
	@echo

install:
	$(PIP) install --upgrade .

reinstall:
	$(MAKE) uninstall
	$(MAKE) install

uninstall:
	$(PIP) uninstall -y gdctools

publish:
	$(PYTHON) setup.py sdist upload && \
	rm -rf build dist *.egg-info

clean:
	rm -rf build dist *.egg-info *~

rclean: clean
	(cd tests && $(MAKE) rclean)
	(cd gdctools && $(MAKE) rclean)

test:
	cd tests && $(MAKE) test

test3:
	cd tests && $(MAKE) -e PYTHON_VER=3 test

.PHONY: help test install release publish clean
