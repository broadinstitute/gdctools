# gdctools
Python and UNIX CLI utilities to simplify interaction with the [NIH/NCI Genomics Data Commons](https://gdc.cancer.gov/), and automate tasks that are common to most data-driven science projects.   For more information and examples see the [overview](https://docs.google.com/viewer?url=https://github.com/broadinstitute/gdctools/files/825892/GDCtools-overview.pdf) and [Wiki pages](https://github.com/broadinstitute/gdctools/wiki).

To get started from a Unix command line, simply clone the repo and install:
```
    %  git clone https://github.com/broadinstitute/gdctools
    %  cd gdctools
    %  make install
```
This should take only a minute or two, and may install [requests](http://docs.python-requests.org/en/master/), [fasteners](https://github.com/harlowja/fasteners) or [matplotlib](http://matplotlib.org/) dependencies.  *Note that if you are installing to a protected location you may need to preface the `make install` command with `sudo `*.  After this you should be able to easily [mirror](https://github.com/broadinstitute/gdctools/wiki/GDC-Mirror) GDC data directly from the command line
```
    gdc_mirror --config tests/tcgaSmoketest.cfg
```
(this is what the `make test` target does) or perform other operations such as seeing which NIH/NCI programs have exposed data for download
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
If *matplotlib* is installed you may also run [gdc_dice](https://github.com/broadinstitute/gdctools/wiki/GDC-Dicer) on the mirror tree, followed by [gdc_loadfile](https://github.com/broadinstitute/gdctools/wiki/Create-Loadfile) to generate a sample "freeze" list which identifies the data for loading into pipeline execution systems like Firehose or FireCloud.  Finally, if you have R installed you may also run the *gdc_report* tool to generate an HTML samples report ([similar to this](http://gdac.broadinstitute.org/runs/sampleReports/latest/)) that provides an annotated description of the processed data; note that this tool will attempt to automatically install [Nozzle](https://confluence.broadinstitute.org/display/GDAC/Nozzle) if it is not detected within the R installation.
