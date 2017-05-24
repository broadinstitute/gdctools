
# Regression test to ensure that our aliquot selector algorithm is working
# properly; it is needed when a case contains multiple aliquots for a given
# datatype, and presently operates only for TCGA data.

import sys
from gdctools.gdc_loadfile import choose_file

dummy_files = [
# Should choose file2 (H > R)
['TCGA-A6-5656-01A-21R-2338-13', 'TCGA-A6-5656-01A-21H-1838-13'],
# Should choose file2 (higher plate)
['TCGA-A6-5656-01A-21H-1838-13', 'TCGA-A6-5656-01A-21H-1900-13'],
# Should choose file1 (H > T)
['TCGA-A6-5656-01A-21H-1838-13', 'TCGA-A6-5656-01A-21T-3900-13'],
# Should choose file1 (D > W, unless W has higher plate)
['TCGA-43-2581-01A-01D-1522-08', 'TCGA-43-2581-01A-01W-0877-08'],
# Should choose file1 (D > G, unless G has higher plate)
['TCGA-06-0122-10A-01D-0914-01', 'TCGA-06-0122-10A-01G-0289-01'],
# Should choose file2 (D > X, unless X has higher plate)
['TCGA-06-0122-10A-01X-0289-01', 'TCGA-06-0122-10A-01D-0914-01'],
# Should choose file2 (D > W, unless W has higher plate)
['TCGA-43-2581-01A-01D-0000-08', 'TCGA-43-2581-01A-01W-0877-08'],
# Should choose file2 (D > G, unless W has higher plate)
['TCGA-06-0122-10A-01D-0000-01', 'TCGA-06-0122-10A-01G-0289-01'],
# Should choose file1 (D > X, unless W has higher plate)
['TCGA-06-0122-10A-01X-0289-01', 'TCGA-06-0122-10A-01D-0000-01'],
# Should choose file2 (same analyte, but higher plate)
['TCGA-37-4130-01A-01D-1097-01', 'TCGA-37-4130-01A-01D-1969-01'],

]
choices = []
for group in dummy_files:
    chosen, ignored = choose_file(group)
    choices.append(chosen)

correct = [
'TCGA-A6-5656-01A-21H-1838-13',
'TCGA-A6-5656-01A-21H-1900-13',
'TCGA-A6-5656-01A-21H-1838-13', 
'TCGA-43-2581-01A-01D-1522-08',
'TCGA-06-0122-10A-01D-0914-01',
'TCGA-06-0122-10A-01D-0914-01',
'TCGA-43-2581-01A-01W-0877-08',
'TCGA-06-0122-10A-01G-0289-01',
'TCGA-06-0122-10A-01X-0289-01',
'TCGA-37-4130-01A-01D-1969-01',
]

if not choices == correct:
    print("ERROR: replicate filter did not choose proper aliquots\n")
    sys.exit(1)
else:
    print("GOOD: replicate filter chose aliquots properly\n")
    sys.exit(0)
