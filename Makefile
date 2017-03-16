
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

install: README
	pip install --upgrade .

reinstall:
	$(MAKE) uninstall
	$(MAKE) install

uninstall:
	pip uninstall -y gdctools

publish: README
	$(PYTHON) setup.py sdist upload && \
	rm -rf build dist *.egg-info

# sdist seems to automatically bundle README into tarball for PyPI, so
# we fake it by creating a soft-link to README.md (which GitHub likes)
README: README.md
	\rm -f README
	ln -s README.md README

clean:
	rm -rf build dist *.egg-info *~ README

rclean: clean
	(cd tests && $(MAKE) rclean)
	(cd gdctools && $(MAKE) rclean)

test:
	cd tests && $(MAKE) test

.PHONY: help test install release publish clean
