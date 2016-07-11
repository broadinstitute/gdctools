from __future__ import print_function

import xml.etree.ElementTree as ET
import sys
import codecs

def path_iter(elem, prefix=""):
    '''Iterates over nodes in an Element Tree with full node paths'''

    #Some fields may be repeated by specifying a sequence number 
    # Use this dictionary to keep track of the last sequence number assigned to each unique path
    path_sequences = dict()

    for child in elem:
        tag = child.tag.split("}")[1] # Split off the xmlns info  --> ${xmlns:abc}tag_name
        child_path = (prefix + "." + tag) if prefix != "" else tag

        #If this is a member of a sequence, append the sequence number. "1" is omitted
        if child_path in path_sequences:
            seq = str(path_sequences[child_path] + 1)
            path_sequences[child_path] += 1
        else:
            seq = child.attrib.get("sequence", "1")
            path_sequences[child_path] = int(seq)

        if seq != "1": child_path += "-" + seq

        if len(list(child)) == 0:
            yield child_path.lower(), parse_element_value(child.text)
        for nested_nodes in path_iter(child, child_path):
            yield nested_nodes

def parse_element_value(s):
    '''Converts a element node's text value into valid data.
    None/whitespace --> NA
    String --> stripped string, in lowercase
    '''
    return "NA" if s == None or s.strip() == '' else s.lower()

def parse_clinical_xml(xmlfile, outtsv):
    """Parses the clinical xml file and outputs node values in two column tsv file."""
    tree = ET.parse(xmlfile)
    root = tree.getroot()
    with codecs.open(outtsv, 'w', 'utf-8') as f:
        f.write("node_name\tnode_value\n")
        for tup in path_iter(root):
            f.write("\t".join(tup) + "\n")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: clin_xml_parser <input_xml> <output_tsv>")
        sys.exit(1)
    parse_clinical_xml(sys.argv[1], sys.argv[2])

