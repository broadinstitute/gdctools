
include Makefile.inc

help:
	@echo
	@echo "Build, test and install GDCtools.  Requires GNUmake 3.81 or later"
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

rclean: clean
	(cd tests && $(MAKE) rclean)

test:
	cd tests && $(MAKE) test

.PHONY: help test install release publish clean
