# gdctools
Python and UNIX CLI utilities to simplify interaction with the [NIH/NCI Genomics Data Commons](https://gdc.cancer.gov/)

Corresponding Author: Michael S. Noble  (mnoble@broadinstitute.org)  
Contributing Authors: Timothy DeFreitas (timdef@broadinstitute.org)
                      David Heiman      (dheiman@broadinstitute.org)

To get started from a Unix command line, simply clone the repo, test, then install:
```
    %  git clone https://github.com/broadinstitute/gdctools`
    %  make test
    %  make install
```
At this point you should be able to easily [mirror](https://github.com/broadinstitute/gdctools/wiki/GDC-Mirror) GDC data directly from the command line, and perform many other operations such as seeing which NIH/NCI programs have exposed data for download
```
%  gdc_ls programs
[
  "TCGA", 
  "TARGET"
]
```
or see what programs have submitted data (that may not be exposed yet)
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
For more information and examples see the [overview](https://docs.google.com/viewer?url=https://github.com/broadinstitute/gdctools/files/818713/GDCtools-overview.pdf) and [Wiki pages](https://github.com/broadinstitute/gdctools/wiki).
