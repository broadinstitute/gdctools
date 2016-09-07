# Script to compare TCGA barcodes between GDC & DCC loadfiels
import csv
import os
import json

GDC_LOADFILE = "TCGA.2016_08_23__14_36_30.Sample.loadfile.txt"
GDC_FILTERED_SAMPLES = "TCGA.2016_08_23__14_36_30.filtered_samples.txt"
DCC_LOADFILE = "normalized.tcga_all_samples.2016_07_15__00_00_14.Sample.loadfile.txt"
DCC_FILTERED_SAMPLES = "filteredSamples.2016_07_15__00_00_14.txt"
GDC_RELEASE_NOTES = "release_notes.txt"

GDC_MISSING_FILE = "sample_based_GDC_missing.tsv"
GDC_CHANGED_FILE = "sample_based_GDC_changed.tsv"
GDC_NEW_FILE = "sample_based_GDC_new.tsv"

DCC_IGNORE_PLATFORMS = { 
    #'genome_wide_snp_6',     # GDC has these now
    'human1mduo',            # CN
    'humanhap550',
    'cgh_1x1m_g4447a', 'hg_cgh_244a',             # CNA
    'hg_cgh_415k_g4124a', 'illuminahiseq_dnaseqc',
    'illuminahiseq_dnaseqc',                      # LowP
    'humanmethylation27', 'humanmethylation450',  # Methylation
    'illuminadnamethylation_oma002_cpi',
    'illuminadnamethylation_oma003_cpi',
    'h_mirna_8x15k', 'h_mirna_8x15kv2',           # miR (array)
    'mda_rppa_core',                              # RPPA
    'agilentg4502a_07_1', 'agilentg4502a_07_2',   # mRNA (array)
    'agilentg4502a_07_3', 'ht_hg_u133a',
    'illuminaga_dnaseq', 'illuminaga_dnaseq_automated',   # MAF
    'solid_dna', 'solid_dna_automated',
    'huex_1_0_st_v2',                             # Exon
}
GDC_IGNORE_ANNOTS = {
    'SNV__mutect' # MAF
}

DCC_IGNORE_ANNOTS = {
    'snp__genome_wide_snp_6__broad_mit_edu__Level_2__birdseed_genotype__birdseed',
    'snp__genome_wide_snp_6__broad_mit_edu__Level_3__segmented_scna_minus_germline_cnv_hg18__seg',
    'snp__genome_wide_snp_6__broad_mit_edu__Level_3__segmented_scna_hg18__seg'
}



#'CNV__snp6', 'CNV_no_germline__snp6'} # GDC now has CN

DCC_TO_GDC = {
   'snp__genome_wide_snp_6__broad_mit_edu__Level_3__segmented_scna_hg19__seg':['CNV__snp6'],
   'snp__genome_wide_snp_6__broad_mit_edu__Level_3__segmented_scna_minus_germline_cnv_hg19__seg':['CNV_no_germline__snp6'],
   'clin__bio__genome_wustl_edu__Level_1__biospecimen__clin':['clinical__biospecimen'],
   'clin__bio__genome_wustl_edu__Level_1__clinical__clin':['clinical__primary'],
   'clin__bio__nationwidechildrens_org__Level_1__biospecimen__clin':['clinical__biospecimen'],
   'clin__bio__intgen_org__Level_1__biospecimen__clin':['clinical__biospecimen'],
   'clin__bio__nationwidechildrens_org__Level_1__clinical__clin':['clinical__primary'],
   'clin__bio__intgen_org__Level_1__clinical__clin':['clinical__primary'],
   'rnaseq__illuminaga_rnaseq__bcgsc_ca__Level_3__gene_expression__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseq__illuminahiseq_rnaseq__bcgsc_ca__Level_3__gene_expression__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'], 
   'rnaseqv2__illuminaga_rnaseqv2__unc_edu__Level_3__RSEM_genes__data' : ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseqv2__illuminahiseq_rnaseqv2__unc_edu__Level_3__RSEM_genes__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseq__illuminaga_rnaseq__unc_edu__Level_3__exon_expression__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseq__illuminaga_rnaseq__unc_edu__Level_3__gene_expression__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseq__illuminaga_rnaseq__unc_edu__Level_3__splice_junction_expression__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseq__illuminahiseq_rnaseq__unc_edu__Level_3__exon_expression__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseq__illuminahiseq_rnaseq__unc_edu__Level_3__gene_expression__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseq__illuminahiseq_rnaseq__unc_edu__Level_3__splice_junction_expression__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseqv2__illuminahiseq_rnaseqv2__unc_edu__Level_3__RSEM_genes_normalized__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseqv2__illuminaga_rnaseqv2__unc_edu__Level_3__RSEM_genes__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseqv2__illuminahiseq_rnaseqv2__unc_edu__Level_3__RSEM_isoforms__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseqv2__illuminahiseq_rnaseqv2__unc_edu__Level_3__RSEM_isoforms_normalized__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseqv2__illuminahiseq_rnaseqv2__unc_edu__Level_3__exon_quantification__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseqv2__illuminahiseq_rnaseqv2__unc_edu__Level_3__junction_quantification__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseqv2__illuminahiseq_rnaseqv2__unc_edu__Level_3__RSEM_genes__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseqv2__illuminahiseq_rnaseqv2__unc_edu__Level_3__RSEM_genes_normalized__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseqv2__illuminahiseq_rnaseqv2__unc_edu__Level_3__RSEM_isoforms__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseq__illuminahiseq_rnaseq__bcgsc_ca__Level_3__exon_expression__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseq__illuminaga_rnaseq__bcgsc_ca__Level_3__splice_junction_expression__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseq__illuminahiseq_rnaseq__bcgsc_ca__Level_3__splice_junction_expression__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseqv2__illuminaga_rnaseqv2__unc_edu__Level_3__RSEM_genes_normalized__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseqv2__illuminaga_rnaseqv2__unc_edu__Level_3__RSEM_isoforms__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseqv2__illuminaga_rnaseqv2__unc_edu__Level_3__RSEM_isoforms_normalized__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseqv2__illuminaga_rnaseqv2__unc_edu__Level_3__exon_quantification__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseqv2__illuminaga_rnaseqv2__unc_edu__Level_3__junction_quantification__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseq__illuminaga_rnaseq__bcgsc_ca__Level_3__exon_expression__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'rnaseq__illuminaga_rnaseq__unc_edu__Level_3__coverage__data': ['mRNA__counts__FPKM', 'mRNA__geneExpNormed__FPKM', 'mRNA__geneExp__FPKM'],
   'mirnaseq__illuminahiseq_mirnaseq__bcgsc_ca__Level_3__miR_gene_expression__data': ['miR__geneExp'],
   'mirnaseq__illuminaga_mirnaseq__bcgsc_ca__Level_3__miR_gene_expression__data': ['miR__geneExp'],
   'mirnaseq__illuminahiseq_mirnaseq__bcgsc_ca__Level_3__miR_gene_expression__data': ['miR__geneExp'],
   'mirnaseq__illuminaga_mirnaseq__bcgsc_ca__Level_3__miR_isoform_expression__data': ['miR__isoformExp'],
   'mirnaseq__illuminahiseq_mirnaseq__bcgsc_ca__Level_3__miR_isoform_expression__data': ['miR__isoformExp'],
   'mirnaseq__illuminahiseq_mirnaseq__bcgsc_ca__Level_3__miR_isoform_expression__data': ['miR__isoformExp'],
   'mirnaseq__illuminaga_mirnaseq__bcgsc_ca__Level_3__miR_isoform_expression__data': ['miR__isoformExp'],
}


# Build dictionary lookup for each loadfile

def get_failed_aliquots(manifest_file):
    """Build a set of aliquots that failed harmonization"""
    failed_aliquots = set()
    with open(manifest_file) as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            failed_wxs = row['WXS (aliquots that failed harmonization, QC, or pending analysis)']
            if failed_wxs:
                failed_aliquots.update(failed_wxs.strip('"').split(','))
            failed_rna = row['RNA-Seq (aliquot that failed harmonization, QC, or pending analysis)']
            if failed_rna:
                failed_aliquots.update(failed_rna.strip('"').split(','))
    return failed_aliquots

def should_use_dcc(a):
    """Return true if this DCC annotation should be used in the diff"""
    if a in DCC_IGNORE_ANNOTS:
        return False
    fields = a.split('__')
    platform = fields[1]
    #Ignore certain platforms
    if platform in DCC_IGNORE_PLATFORMS:
        return False
    # Also ignore wustl clinical
    center = fields[2]
    type = fields[0]
    if type == 'clin' and platform == 'bio':
        #if center == 'genome_wustl_edu':
        #    return False
         # And ignore clinical ssf
        t = fields[4]
        if t == 'ssf' or t == 'auxiliary' or t == 'omf':
            return False
    return True

# TODO: break down barcodes by sample type
def compare_barcodes(gdc_barcodes, gdc_cohort_lookup, dcc_barcodes, dcc_cohort_lookup, failed_aliquots):
    new_gdc = []
    changed_gdc = []
    missing_gdc = []

    # Loop through DCC annotations, looking for missing or changed
    # entries in gdc_barcodes
    for tcga_id, dcc_annots in dcc_barcodes.iteritems():
        cohort = dcc_cohort_lookup[tcga_id]
        for dcc_annot in dcc_annots:
            # If the annotation is in the DCC loadfile,
            # but not in the GDC loadfile, then these files
            # count as missing
            barcode_list = dcc_barcodes[tcga_id][dcc_annot]
            if tcga_id not in gdc_barcodes or dcc_annot not in gdc_barcodes[tcga_id]:
                barcode_str = ",".join(sorted(barcode_list))
                missing_entry = [tcga_id, cohort, dcc_annot, barcode_str, ""]
                missing_gdc.append(missing_entry)
            else:
            # Otherwise, we have to compare the two sets of barcodes, to see if there was a change
                dcc_barcode_set = dcc_barcodes[tcga_id][dcc_annot]
                gdc_barcode_set = gdc_barcodes[tcga_id][dcc_annot]
                if dcc_barcode_set != gdc_barcode_set:
                    # The set of barcodes has changed
                    dcc_barcode_str = ",".join(sorted(dcc_barcode_set))
                    gdc_barcode_str = ",".join(sorted(gdc_barcode_set))
                    change_entry = [tcga_id, cohort, dcc_annot, dcc_barcode_str, gdc_barcode_str]
                    changed_gdc.append(change_entry)

    # Now do the same for GDC annotations
    for tcga_id, gdc_annots in gdc_barcodes.iteritems():
        for gdc_annot in gdc_annots:
            # If the annotation is in the GDC loadfile,
            # but not in the DCC loadfile, then these files
            # count as new
            cohort = gdc_cohort_lookup[tcga_id]
            barcode_list = gdc_barcodes[tcga_id][gdc_annot]
            if tcga_id not in dcc_barcodes or gdc_annot not in dcc_barcodes[tcga_id]:
                barcode_str = ",".join(barcode_list)
                new_entry = [tcga_id, cohort, dcc_annot, "", barcode_str]
                new_gdc.append(new_entry)
            else:
            # Otherwise, we have to compare the two sets of barcodes, to see if there was a change
                dcc_barcode_set = set(dcc_barcodes[tcga_id][gdc_annot])
                gdc_barcode_set = set(gdc_barcodes[tcga_id][gdc_annot])
                if dcc_barcode_set != gdc_barcode_set:
                    # The set of barcodes has changed
                    dcc_barcode_str = ",".join(sorted(dcc_barcode_set))
                    gdc_barcode_str = ",".join(sorted(gdc_barcode_set))
                    change_entry = [tcga_id, cohort, dcc_annot, dcc_barcode_str, gdc_barcode_str]
                    changed_gdc.append(change_entry)

    # Now filter out any rows in missing where the aliquot failed harmonization
    missing_gdc = [l for l in missing_gdc if l[3] not in failed_aliquots]

    return new_gdc, changed_gdc, missing_gdc

def loadfile_iter(loadfile):
    with open(loadfile) as lf:
        rdr = csv.DictReader(lf, delimiter='\t')
        annots = rdr.fieldnames[4:]
        for row in rdr:
            tcga_samp_id = row['tcga_sample_id']
            cohort = row['sample_id'].split('-')[0]
            for a in annots:
                filename = row[a]
                if filename != '__DELETE__':
                    barcode = os.path.basename(filename).split('.')[0]
                    yield tcga_samp_id, cohort, a, barcode

def barcode_lookup(loadfile, isGDC):
    '''Build a nested dictionary where lookup[tcga_sample_id][annotation] = barcode'''
    sample_lookup = dict()
    sample_cohort_lookup = dict()
    for tcga_id, cohort, annot, barcode in loadfile_iter(loadfile):

        if len(barcode) == 12:
            # Case level, use the barcode as the tcga_id
            tcga_id = barcode

        if cohort == "FPPP" or cohort == "FPPPFFPE":
            continue # Skip this, not a real cohort
        sample_lookup[tcga_id] = sample_lookup.get(tcga_id, dict())
        sample_cohort_lookup[tcga_id] = cohort
        if isGDC:
            if annot not in GDC_IGNORE_ANNOTS:
                if 'clinical' in annot:
                    # only one barcode possible for clinical types 
                    sample_lookup[tcga_id][annot] = set([barcode])
                else:
                    sample_lookup[tcga_id][annot] = sample_lookup[tcga_id].get(annot, set())
                    sample_lookup[tcga_id][annot].add(barcode)
        elif should_use_dcc(annot):
            # Replace the annot with the DCC equivalent
            new_annots = DCC_TO_GDC[annot]
            for a in new_annots:
                if 'clinical' in a:
                    tcga_id = tcga_id[:12] # Case level tcga id
                    # only one barcode possible for clinical types 
                    sample_lookup[tcga_id][a] = set([barcode])
                else:
                    sample_lookup[tcga_id][a] = sample_lookup[tcga_id].get(a, set())
                    sample_lookup[tcga_id][a].add(barcode)
    return sample_lookup, sample_cohort_lookup

def write_changes(change_list, to_file):
    with open(to_file, 'w') as f:
        f.write("tcga_sample_id\tcohort\tannot\tDCC Barcode(s)\tGDC Barcode(s)\n")
        # Sort change list by combination of cohort + tcga_sample_id
        change_list = sorted(change_list, key=lambda l: l[1]+l[0])
        for change in change_list:
            line = "\t".join(change) + "\n"
            f.write(line)

# Main starts here

gdc_barcodes, gdc_cohort_lookup = barcode_lookup(GDC_LOADFILE, True)
dcc_barcodes, dcc_cohort_lookup = barcode_lookup(DCC_LOADFILE, False)


FAILED_ALIQUOTS = get_failed_aliquots(GDC_RELEASE_NOTES)
NEW_GDC, CHANGED_GDC, MISSING_GDC = compare_barcodes(gdc_barcodes, gdc_cohort_lookup, dcc_barcodes, dcc_cohort_lookup, FAILED_ALIQUOTS)
write_changes(NEW_GDC, GDC_NEW_FILE)
write_changes(CHANGED_GDC, GDC_CHANGED_FILE)
write_changes(MISSING_GDC, GDC_MISSING_FILE)

