# gdctools
Python and UNIX CLI utilities to simplify search and retrieval of open-access data from the [NIH/NCI Genomics Data Commons](https://gdc.cancer.gov/), and automate tasks that are common to most data-driven science projects.   For more information and examples see the [pictorial overview](https://docs.google.com/viewer?url=https://github.com/broadinstitute/gdctools/files/825892/GDCtools-overview.pdf), [Wiki pages](https://github.com/broadinstitute/gdctools/wiki) or [tests/Makefile](tests/Makefile).  To get started from a Unix command line, simply `pip install gdctools` or clone the repo and install:
```
    %  git clone https://github.com/broadinstitute/gdctools
    %  cd gdctools
    %  make install
```
This should take only a minute or two, and may install [requests](http://docs.python-requests.org/en/master/), [fasteners](https://github.com/harlowja/fasteners) or [matplotlib](http://matplotlib.org/) dependencies.  *Note that if you are installing to a protected location you may need to preface the `make install` command with `sudo.`  After this you should be able to easily [mirror](https://github.com/broadinstitute/gdctools/wiki/GDC-Mirror) either [harmonized](https://gdc.cancer.gov/about-data/gdc-data-harmonization) or [legacy](https://gdc-portal.nci.nih.gov/legacy-archive) data directly from the command line 
```
    gdc_mirror --config tests/tcgaSmoketest.cfg
```
(this is what the `make test` target does), even for a single patient case
```
    gdc_mirror --cases TCGA-EE-A3J8
```
or just one category of data for that patient
```
    gdc_mirror --cases TCGA-EE-A3J8 --categories "Copy Number Variation"
```
or perform other operations such as seeing which NIH/NCI programs have exposed data for download
```
    %  gdc_list programs
    [
      "TCGA", 
      "TARGET"
    ]
```
or what programs have submitted data (that may not be exposed yet)
```
    %  gdc_list submission
    [
      "CCLE", 
      "REBC", 
      "TCGA", 
      "TARGET", 
      "CGCI", 
      "CDDP", 
      "ALCHEMIST", 
      "GDC", 
      "Exceptional_Responders", 
      "UAT08", 
      "TRIO", 
      "CPTAC"
    ]
```
After mirroring you may run [gdc_dice](https://github.com/broadinstitute/gdctools/wiki/GDC-Dicer) on the mirror tree, followed by [gdc_loadfile](https://github.com/broadinstitute/gdctools/wiki/Create-Loadfile) to generate a sample "freeze" list which identifies the data for loading into pipeline execution systems like Firehose or FireCloud.  Finally, if you have *matplotlib* and *R* installed you may also run the [gdc_report](https://github.com/broadinstitute/gdctools/wiki/Sample-reports) tool to generate an HTML samples report ([similar to this](http://gdac.broadinstitute.org/runs/sampleReports/latest/)) that provides an annotated description of the processed data; note that this tool will attempt to automatically install [Nozzle](https://confluence.broadinstitute.org/display/GDAC/Nozzle) if it is not detected within the R installation. As noted earlier, the [tests/Makefile](tests/Makefile) provides examples of using the dice, loadfile and report tools.  GDCtools has been verified to function properly with multiple Python2 and Python3 versions, and we are [grateful for the community contributions](https://github.com/broadinstitute/gdctools/commit/53be8ee4d720b502c2dbb1e110e7c20754331e3e) in support of this goal.
