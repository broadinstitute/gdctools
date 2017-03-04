# gdctools
Python and UNIX CLI utilities to simplify interaction with the [NIH/NCI Genomics Data Commons](https://gdc.cancer.gov/)

Corresponding Author: Michael S. Noble  (mnoble@broadinstitute.org)  
Contributing Authors: Timothy DeFreitas (timdef@broadinstitute.org)
                      David Heiman      (dheiman@broadinstitute.org)

To get started from a Unix command line, simply clone the repo and install:
```
    %  git clone https://github.com/broadinstitute/gdctools
    %  make install
```
This should take only a minute or two, at which point you should be able to easily [mirror](https://github.com/broadinstitute/gdctools/wiki/GDC-Mirror) GDC data directly from the command line
```
    gdc_mirror --config tests/tcgaSmoketest.cfg
```
(this is what the `make test` target does) or perform other operations such as seeing which NIH/NCI programs have exposed data for download
```
    %  gdc_ls programs
    [
      "TCGA", 
      "TARGET"
    ]
```
or what programs have submitted data (that may not be exposed yet)
```
    %  gdc_ls submission
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
For more information and examples see the [overview](https://docs.google.com/viewer?url=https://github.com/broadinstitute/gdctools/files/818725/GDCtools-overview.pdf) and [Wiki pages](https://github.com/broadinstitute/gdctools/wiki).
