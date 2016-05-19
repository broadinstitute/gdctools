# gdctools
Python and UNIX CLI utilities to simplify interaction with the NIH/NCI
Genomics Data Commons.

Corresponding Author: Michael S. Noble  (mnoble@broadinstitute.org)
Contributing Authors: Timothy DeFreitas (timdef@broadinstitute.org)
                      David Heiman      (dheiman@broadinstitute.org)

The Genomics Data Commons (GDC) is the next-generation storage warehouse for
genomic data.  It was inspired by lessons learned and technologies developed
during The Cancer Genome Atlas project (TCGA), in the hope of extending them
to a wide range of future genomics projects funded through the National Cancer
Institute (NCI) of the National Institutes of Health (NIH).

This GDCtools package is the offshoot of efforts at the Broad Institute to
connect the Firehose pipeline developed in TCGA to use the GDC as its primary
source of data.  The ultimate goal of this package, though, goes beyond simply
connecting Firehose to the GDC: we aim to provide a set of Python bindings and
UNIX cli wrappers to the GDC application programming interface (API) that are
vastly simpler to use for the majority of common operations.
