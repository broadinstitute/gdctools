


# Pull Request Template
Describe your changes here.


## Style Checklist
Please ensure that your pull request meets the following standards for quality.
Code should not be merged into the master branch until all of these criteria have been satisfied.

### Comments
- [ ] Each source file includes comments at the top describing its purpose
- [ ] Each function includes a comment/docstring describing inputs and outputs, and any assumptions it makes
- [ ] Variable and function names have semantic meaning, and are not reused with a different meaning within the same scope
- [ ] “Magic” numbers, such index of a particular column name, have a comment describing their value, or are declared as a global constant with a semantic name (e.g. TCGA_ID_COL = 16)
- [ ] Commented-out code is removed

### Style/Execution
- [ ] Code contains no hard-coded paths
- [ ] Code contains appropriate logging & or debugging
- [ ] If possible, input data is validated early in the execution. If not, errors are sufficiently detailed to aid debugging.
- [ ] Code uses a library (e.g. optparse, argparse) for command-line parsing
