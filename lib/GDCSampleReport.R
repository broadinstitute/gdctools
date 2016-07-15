#!/usr/bin/env Rscript

# William Mallard / Redactions Report / April 2012
# Dan DiCara / Updated to Samples Summary Report / January 2013
# Tim DeFreitas / Updated for GD + GDAN era / June 2016
GDAC_BIN        = "/xchip/tcga/Tools/gdac/bin"
HTML2PNG        = file.path(GDAC_BIN, "html2png")
REDACTIONS.HEAD = 'redactions'
FFPES.HEAD      = 'FFPEs'

DATA_TYPES = c("BCR", "Clinical", "CN", "LowP", "Methylation", "mRNA",
               "mRNASeq", "miR", "miRSeq", "RPPA", "MAF", "rawMAF")

LEVEL_3_DATA_TYPES = c("CN", "Methylation", "mRNASeq", "mRNA", "miR")

PLATFORM_TO_DATATYPE_MAP                             = list()
PLATFORM_TO_DATATYPE_MAP[["illuminahiseq_dnaseqc"]]  = "LowP"
PLATFORM_TO_DATATYPE_MAP[["humanmethylation27"]]     = "Methylation"
PLATFORM_TO_DATATYPE_MAP[["humanmethylation450"]]    = "Methylation"
PLATFORM_TO_DATATYPE_MAP[["h_mirna_8x15k"]]          = "miR"
PLATFORM_TO_DATATYPE_MAP[["h_mirna_8x15kv2"]]        = "miR"
PLATFORM_TO_DATATYPE_MAP[["illuminaga_mirnaseq"]]    = "miRSeq"
PLATFORM_TO_DATATYPE_MAP[["illuminahiseq_mirnaseq"]] = "miRSeq"
PLATFORM_TO_DATATYPE_MAP[["mda_rppa_core"]]          = "RPPA"
PLATFORM_TO_DATATYPE_MAP[["illuminaga_rnaseq"]]      = "mRNASeq"
PLATFORM_TO_DATATYPE_MAP[["illuminaga_rnaseqv2"]]    = "mRNASeq"
PLATFORM_TO_DATATYPE_MAP[["illuminahiseq_rnaseq"]]   = "mRNASeq"
PLATFORM_TO_DATATYPE_MAP[["illuminahiseq_rnaseqv2"]] = "mRNASeq"
PLATFORM_TO_DATATYPE_MAP[["genome_wide_snp_6"]]      = "CN"
PLATFORM_TO_DATATYPE_MAP[["agilentg4502a_07_1"]]     = "mRNA"
PLATFORM_TO_DATATYPE_MAP[["agilentg4502a_07_2"]]     = "mRNA"
PLATFORM_TO_DATATYPE_MAP[["agilentg4502a_07_3"]]     = "mRNA"
PLATFORM_TO_DATATYPE_MAP[["ht_hg_u133a"]]            = "mRNA"

SAMPLE_TYPES = c("TP", "TR", "TB", "TRBM", "TAP", "TM", "TAM", "THOC", "TBM",
                 "NB", "NT", "NBC", "NEBV", "NBM", "FFPE")


main <- function(...)
{
    startTime = Sys.time()
    ############################################################################
    # Parse inputs
    ############################################################################
    args = list(...)
    if (length(args) < 10 || length(args) > 11) {
        stop(
            paste(
                "Usage: RedactionsReport.R <redactionsDir> <sampleCountsPath>",
                "<timestamp> <filteredSamplesPath> <heatmapsDir>",
                "<blacklistPath> <sampleLoadfile> <refDir> <reportDir>",
                "<aggregatesPath> [sampleSet]"))
    }

    redacDir            = args[[1]]
    sampleCountsPath    = args[[2]]
    timestamp           = args[[3]]
    filteredSamplesPath = args[[4]]
    heatmapsPath        = args[[5]]
    blacklistPath       = args[[6]]
    sampleLoadfile      = args[[7]]
    refDir              = args[[8]]
    reportDir           = args[[9]]
    aggregatesPath      = args[[10]]

    sampleToSampleSetsMap = list()
    if (length(args) == 11) {
        sampleSetPath = args[[11]]
        sampleToSampleSetsMap = getSampleToSampleSetsMap(sampleSetPath)
    }

    ############################################################################
    # Initialization
    ############################################################################
    annotPaths = findAnnotationTSVs(redacDir, timestamp)
    redacFile  = annotPaths[[REDACTIONS.HEAD]]
    ffpeFile   = annotPaths[[FFPES.HEAD]]

    validateSymlink(sampleCountsPath, reportDir)

    maps            = getMaps(refDir)
    centerCodeMap   = maps[[1]]
    platformCodeMap = maps[[2]]
    diseaseStudyMap = maps[[3]]
    sampleTypeMap   = maps[[4]]

    result = getAggregates(aggregatesPath)
    tumorTypeToAggregateNamesMap = result[[1]]
    aggregateNameToTumorTypesMap = result[[2]]

    runDate = strsplit(timestamp, "__", TRUE)[[1]][1]
    runStmp = paste(runDate, "Data Snapshot")
    runName = paste0("stddata__", runDate)

    require("Nozzle.R1")

    title = sprintf("%s Samples Report", runName)
    report = newReport(title)

    ############################################################################
    # Introduction
    ############################################################################
    introduction = generateIntroduction()
    report       = addToIntroduction(report, introduction)

    ############################################################################
    # Summary
    ############################################################################
    annotResults <- sapply(annotPaths, generateAnnotationsTable)

    redactionsTable = NULL
    redactionsCount = NULL
    if (REDACTIONS.HEAD %in% colnames(annotResults)) {
        redactionsTable = annotResults[[1, REDACTIONS.HEAD]]
        redactionsCount = annotResults[[2, REDACTIONS.HEAD]]
    }
    if (is.null(redactionsCount)) {
        redactionsCount = 0
    }

    ffpeTable = NULL
    ffpeCount = NULL
    if (FFPES.HEAD %in% colnames(annotResults)) {
        ffpeTable = annotResults[[1, FFPES.HEAD]]
        ffpeCount = annotResults[[2, FFPES.HEAD]]
    }
    if (is.null(ffpeCount)) {
        ffpeCount = 0
    }

    result          = generateFilterTable(filteredSamplesPath, reportDir)
    filterTable     = result[[1]]
    filterCount     = result[[2]]

    result          = generateBlacklistTable(blacklistPath, reportDir)
    blacklistTable  = result[[1]]
    blacklistCount  = result[[2]]

    summaryParagraph = generateSummaryParagraph(redactionsCount, filterCount,
                                                blacklistCount, ffpeCount)
    report           = addToSummary(report, summaryParagraph)

    sampleCountsTableRaw = read.table(sampleCountsPath, header = TRUE,
                                      sep = "\t", stringsAsFactors=FALSE)

    if ("Tumor" %in% colnames(sampleCountsTableRaw)) {
        rownames(sampleCountsTableRaw) = sampleCountsTableRaw$Tumor
    } else if ("Cohort" %in% colnames(sampleCountsTableRaw)) {
        # Remove sample type rows (i.e. SKCM-TP, SKCM-NT, SKCM-FFPE, etc.)
        sampleCountsTableRaw = subset(sampleCountsTableRaw, !(grepl("-", sampleCountsTableRaw$Cohort)))
        rownames(sampleCountsTableRaw) = sampleCountsTableRaw$Cohort
    } else {
        stop("Neither Tumor or Cohort found in sample counts table header.")
    }

    ############################################################################
    # Heatmaps SubSection - generateHeatmapsSubSection() symlinks all the
    # heatmaps to the current working directory. This is where the ingested
    # samples section looks for them, so this must come first.
    ############################################################################
    heatmapsStart = Sys.time()
    heatmaps      = generateHeatmapsSubSection(heatmapsPath, timestamp,
                                               reportDir)
    report        = addToResults(report, heatmaps)
    print(sprintf("Heatmaps section generated in %s minutes.",
                  difftime(Sys.time(), heatmapsStart, units="min")))

    ############################################################################
    # Ingested Samples
    ############################################################################
    ingestSamplesStartTime = Sys.time()
    sampleCountsTable      =
        generateSampleCountsTable(
            sampleCountsPath, sampleCountsTableRaw, sampleLoadfile,
            heatmapsPath, timestamp, runStmp, reportDir, platformCodeMap,
            centerCodeMap, sampleTypeMap, annotPaths, filteredSamplesPath,
            blacklistPath, diseaseStudyMap, tumorTypeToAggregateNamesMap,
            aggregateNameToTumorTypesMap, sampleToSampleSetsMap)
    report                 = addToSummary(report, sampleCountsTable$tbl)
    createStandaloneTable(sampleCountsTable$df, "sample_counts", reportDir,
                          timestamp)
    print(sprintf("Created Ingested Samples section in %s minutes.",
                  difftime(Sys.time(), ingestSamplesStartTime, units="min")))

    ############################################################################
    # Filtered Samples SubSection
    ############################################################################
    filteredSamplesStart = Sys.time()
    validateSymlink(redacFile, reportDir)
    filteredSamplesSubSection = generateFilteredSamplesSubSection(reportDir,
            runStmp, redactionsTable, filterTable, blacklistTable)
    print(sprintf("Filtered samples section generated in %s minutes.",
                  difftime(Sys.time(), filteredSamplesStart, units="min")))
    report = addToResults(report, filteredSamplesSubSection)

    ############################################################################
    # FFPEs Subsection
    ############################################################################
    ffpeStart = Sys.time()
    ffpeSubSection = generateFFPEsSubSection(reportDir, ffpeTable, runStmp)
    print(sprintf("FFPE samples section generated in %s minutes.",
                  difftime(Sys.time(), ffpeStart, units="min")))
    report = addToResults(report, ffpeSubSection)

    ############################################################################
    # Annotations Subsection
    ############################################################################
    annotStart = Sys.time()
    annotSubSection = generateAnnotationsSubSection(reportDir, annotResults[1,],
                                                    runStmp)
    print(sprintf("Annotations section generated in %s minutes.",
                  difftime(Sys.time(), annotStart, units="min")))
    report = addToResults(report, annotSubSection)

    ############################################################################
    # Methods SubSection
    ############################################################################
    methodsStart = Sys.time()
    report       = addToMethodsSection(report)
    print(sprintf("Methods section generated in %s minutes.",
                  difftime(Sys.time(), methodsStart, units="min")))

    ############################################################################
    # Generate the report.
    ############################################################################
    reportFile = file.path(reportDir, "index", fsep = .Platform$file.sep)

    writeStart = Sys.time()
    writeReport(report, filename=reportFile)
    print(sprintf("Report written in %s minutes.",
                  difftime(Sys.time(), writeStart, units="min")))

    print(sprintf("Successfully completed report creation in %s minutes.",
                  difftime(Sys.time(), startTime, units="min")))
}

################################################################################
#                                    METHODS                                   #
################################################################################

################################################################################
# Write a new report that contains descriptions at the top and a table in the
# body.
################################################################################
writeSectionReport <- function(reportDir, table, name, runStmp, descFun,
        noSamplesMsg, disease=NULL) {
    report = newCustomReport(name)
    report = setReportSubTitle(report, runStmp)

    if (! is.null(descFun)) {
        descriptions = descFun()

        for (i in 1:length(descriptions)) {
            report = addTo(report, descriptions[[i]])
        }
    }

    report = addTable(report, table, noSamplesMsg)

    filenamePrefix = gsub(" ", "_",name)
    if (! is.null(disease)) {
        filenamePrefix = sprintf("%s_%s", disease, filenamePrefix)
    }
    reportPath = file.path(reportDir, filenamePrefix, fsep = .Platform$file.sep)
    writeReport(report, filename=reportPath)

    return(newParagraph(asLink(sprintf("%s.html", filenamePrefix), name)))
}

addTable <- function(container, table, nullMsg) {
    if (is.null(table)) {
        container = addTo(container, newParagraph(nullMsg))
    } else {
        container = addTo(container, table)
    }
    return(container)
}

################################################################################
# Validate existance of a symlink, create it if it doesn't exist
################################################################################
validateSymlink <- function(sourceFile, destDir) {
    symlinkPath = file.path(destDir, basename(sourceFile))
    if ((! file.exists(symlinkPath)) && is.na(Sys.readlink(symlinkPath))) {
        file.symlink(sourceFile, destDir)
    }
}

################################################################################
# Discover Annotation Tables
################################################################################
findAnnotationTSVs <- function(redactionsDir, timestamp) {
    tsvSuffix = paste0('_', timestamp, '.tsv')
    annotationGlob = file.path(redactionsDir, paste0('*', tsvSuffix))
    annotationTSVs = list()
    for (filename in Sys.glob(annotationGlob)) {
        annotationTSVs[sub(paste0(tsvSuffix, '$'), '', basename(filename))] =
            filename
    }
    return(annotationTSVs)
}

getSampleToSampleSetsMap <- function(sampleSetPath) {
    sampleToSampleSetsMap = list()

    if (file.exists(sampleSetPath)) {
        sampleSetTable =
            read.table(
                sampleSetPath, sep="\t", header=TRUE, comment.char="", quote="",
                stringsAsFactors=FALSE)
        for (i in 1:nrow(sampleSetTable)) {
            sampleSet = sampleSetTable$sample_set_id[i]
            sample    = sampleSetTable$sample_id[i]

            if (! (sample %in% names(sampleToSampleSetsMap))) {
                sampleToSampleSetsMap[[sample]] = c()
            }
            sampleToSampleSetsMap[[sample]] =
                c(sampleToSampleSetsMap[[sample]], sampleSet)
        }
    }
    return(sampleToSampleSetsMap)
}

getMaps <- function(refDir) {

    centerCodeMap    = list()
    platformCodeMap  = list()
    diseaseStudyMap  = list()
    sampleTypeMap    = list()

    if (! file.exists(refDir)) {
        return(list(centerCodeMap, platformCodeMap, diseaseStudyMap,
                    sampleTypeMap))
    }

    centerCodePath = file.path(refDir, "centerCode.txt")
    if (file.exists(centerCodePath)) {
        centerCodeTable =
            read.table(centerCodePath, sep="\t", header=TRUE, comment.char="",
                       quote="", stringsAsFactors=FALSE)
        for (i in 1:nrow(centerCodeTable)) {
            centerName = gsub("\\.", "_",centerCodeTable$Center.Name[i])
            centerName = gsub("-", "_",centerName)
            # Ignore duplicates (i.e. Broad listed twice, once for GSC and once
            # for GDAC)
            if (! (centerName %in% centerCodeMap)) {
                centerCodeMap[[centerName]] = centerCodeTable$Display.Name[i]
            }
        }
    }

    platformCodePath = file.path(refDir, "platformCode.txt")
    if (file.exists(platformCodePath)) {
        platformCodeTable =
            read.table(platformCodePath, sep="\t", header=TRUE, comment.char="",
                       quote="", stringsAsFactors=FALSE)
        for (i in 1:nrow(platformCodeTable)) {
            platformCode = tolower(platformCodeTable$Platform.Code[i])
            platformCode = gsub("-", "_", platformCode)
            platformName = platformCodeTable$Platform.Name[i]
            platformCodeMap[[platformCode]] = platformName
        }
        platformCodeMap[[platformCode]] = platformName
    }

    diseaseStudyPath = file.path(refDir, "diseaseStudy.txt")
    if (file.exists(diseaseStudyPath)) {
        diseaseStudyTable =
            read.table(diseaseStudyPath, sep="\t", header=TRUE, comment.char="",
                       quote="", stringsAsFactors=FALSE)
        for (i in 1:nrow(diseaseStudyTable)) {
            studyAbbreviation = diseaseStudyTable$Study.Abbreviation[i]
            studyName         = diseaseStudyTable$Study.Name[i]
            diseaseStudyMap[[studyAbbreviation]] = studyName
        }
    }

    sampleTypePath = file.path(refDir, "sampleType.txt")
    if (file.exists(sampleTypePath)) {
        sampleTypeTable =
            read.table(sampleTypePath, sep="\t", header=TRUE, comment.char="",
                       quote="", stringsAsFactors=FALSE)
        for (i in 1:nrow(sampleTypeTable)) {
            shortLetterCode = sampleTypeTable$Short.Letter.Code[i]
            sampleType      = sampleTypeTable$Definition[i]
            sampleTypeMap[[shortLetterCode]] = sampleType
        }
    }

    return(list(centerCodeMap, platformCodeMap, diseaseStudyMap, sampleTypeMap))
}

getAggregates <- function(aggregatesPath) {
    tumorTypeToAggregateNamesMap  = list()
    aggregateNameToTumorTypesMap  = list()

    if (file.exists(aggregatesPath)) {
        aggregatesTable =
            read.table(aggregatesPath, sep="\t", header=TRUE, comment.char="",
                       quote="", stringsAsFactors=FALSE)
        if (nrow(aggregatesTable) > 0) {
            for (i in 1:nrow(aggregatesTable)) {
                aggregateName  = aggregatesTable$Aggregate.Name[i]
                tumorTypes     = aggregatesTable$Tumor.Types[i]
                tumorTypes     = strsplit(tumorTypes, ",")[[1]]
                aggregateNameToTumorTypesMap[[aggregateName]] = tumorTypes
                for (tumorType in tumorTypes) {
                    if (!(tumorType %in% names(tumorTypeToAggregateNamesMap))) {
                        tumorTypeToAggregateNamesMap[[tumorType]] = c()
                    }
                    tumorTypeToAggregateNamesMap[[tumorType]] =
                        c(tumorTypeToAggregateNamesMap[[tumorType]],
                          aggregateName)
                }
            }
        }
    }
    return(list(tumorTypeToAggregateNamesMap, aggregateNameToTumorTypesMap))
}

parseLoadfile <- function(samplesLoadfile, heatmapsDir, timestamp, destDir,
                         platformCodeMap, centerCodeMap,
                         tumorTypeToAggregateNamesMap, sampleToSampleSetsMap) {

    loadfile = read.table(samplesLoadfile, header = TRUE, sep = "\t")

    # Header begins with sample_id, individual_id, sample_type, and
    # tcga_sample_id.
    # BLCA-BL-A0C8-NB::BLCA-BL-A0C8::NB::TCGA-BL-A0C8-10
    annotations = names(loadfile)

    annotationsMap   = list()
    ignoredPlatforms = c()
    data_types       = c()
    centers          = c()

    if (length(annotations) > 4) {
        for (i in 5:length(annotations)) {
            annotation = annotations[i]
            # <data_type>__<     platform    >__< center  >__<level>__<           protocol            >__<  >
            # methylation__humanmethylation450__jhu_usc_edu__Level_3__within_bioassay_data_set_function__data
            fields = strsplit(annotation, "__")[[1]]
            numFieldsExpected = 6
            if (length(fields) != numFieldsExpected) {
                print(
                    sprintf(
                        "Annotation doesn't have %d fields (has %d), skipping.",
                        numFieldsExpected, length(fields)))
                next
            }
            type     = fields[1]
            platform = fields[2]
            center   = fields[3]
            level    = fields[4]
            protocol = fields[5]

            dataType = getDataType(platform, protocol)

            # Skip outdated data types for now
            if (is.null(dataType)) {
                if (!(platform %in% ignoredPlatforms)) {
                    ignoredPlatforms = c(ignoredPlatforms, platform)
                }
                next
            }

            if (dataType %in% LEVEL_3_DATA_TYPES && level != "Level_3") {
                next
            }

            # Improve the platform and center names for clarity
            if ((! is.null(names(platformCodeMap))) &&
                platform %in% names(platformCodeMap)) {
                platform = platformCodeMap[[platform]]
            } else {
                print(sprintf("Unknown platform: %s", platform))
            }

            if ((! is.null(names(centerCodeMap))) &&
                center %in% names(centerCodeMap)) {
                center = centerCodeMap[[center]]
            } else {
                print(sprintf("Unknown Center: %s", center))
            }

            level = gsub("^Level_", "", level, ignore.case = TRUE)

            fieldsMap               = list()
            fieldsMap[["type"]]     = type
            fieldsMap[["platform"]] = platform
            fieldsMap[["center"]]   = center
            fieldsMap[["level"]]    = level
            fieldsMap[["protocol"]] = protocol
            fieldsMap[["datatype"]] = dataType

            if (! (dataType %in% data_types)) {
                data_types = c(data_types, dataType)
            }

            annotationsMap[[annotation]] = fieldsMap
        }
    }

    #tumorTypeToSampleTypesMap
    #    [tumorType][sampleType][dataType][sampleId][annotationName]
    tumorTypeToSampleTypesMap = list()
    sampleTypes               = c()
    for (i in 1:length(loadfile[[annotations[1]]])) {
        sampleId   = paste(loadfile[i, annotations[1]])
        tumorType  = strsplit(sampleId, "-")[[1]][1]
        sampleType = paste(loadfile[i, annotations[3]])
        if (grepl("^.*FFPE$",tumorType) == TRUE) {
            tumorType  = gsub("FFPE","", tumorType)
            sampleType = "FFPE"
        }

        diseaseTypes = c(tumorType)
        if (tumorType %in% names(tumorTypeToAggregateNamesMap)) {
            diseaseTypes =
                c(diseaseTypes, tumorTypeToAggregateNamesMap[[tumorType]])
        }

        for (disease in diseaseTypes) {
            if (! (disease %in% names(tumorTypeToSampleTypesMap))) {
                tumorTypeToSampleTypesMap[[disease]] = list()
            }

            if (! (sampleType %in%
                   names(tumorTypeToSampleTypesMap[[disease]]))) {
                tumorTypeToSampleTypesMap[[disease]][[sampleType]] = list()
            }

            if (! (sampleType %in% sampleTypes)) {
                sampleTypes = c(sampleTypes, sampleType)
            }

            types = c(sampleType)

            if (sampleId %in% names(sampleToSampleSetsMap)) {
                sampleSets = sampleToSampleSetsMap[[sampleId]]
                for (sampleSet in sampleSets) {
                    sampleSetSplit  = strsplit(sampleSet, "-")
                    subtype = sampleSetSplit[[1]][2]
                    if (sampleSet != tumorType && !(subtype %in% SAMPLE_TYPES)) {
                        types = c(types, sampleSet)
                        if (! (sampleSet %in%
                                    names(tumorTypeToSampleTypesMap[[disease]]))) {
                            tumorTypeToSampleTypesMap[[disease]][[sampleSet]] =
                                    list()
                        }
                    }
                }
            }

            annotationsMapNames = names(annotationsMap)
            for (annotationName in annotationsMapNames) {
                annotation = paste(loadfile[i, annotationName])
                if (annotation != "__DELETE__") {
                    filename = basename(annotation)
                    tcgaId   = strsplit(filename, ".", fixed=TRUE)[[1]][1]
                    dataType =
                        paste(annotationsMap[[annotationName]][["datatype"]])

                    for (type in types) {

                        if (! (dataType %in%
                               names(
                                   tumorTypeToSampleTypesMap[[disease]][[type]]))) {
                            tumorTypeToSampleTypesMap[[disease]][[type]][[dataType]] =
                                list()
                        }

                        if (! (sampleId %in%
                               names(
                                   tumorTypeToSampleTypesMap[[disease]][[type]][[dataType]]))) {
                            tumorTypeToSampleTypesMap[[disease]][[type]][[dataType]][[sampleId]] =
                                list()
                        }

                        annotationsMap[[annotationName]][["tcgaId"]] = tcgaId
                        tumorTypeToSampleTypesMap[[disease]][[type]][[dataType]][[sampleId]][[annotationName]] =
                            annotationsMap[[annotationName]]
                    }
                }
            }
        }
    }

    return(list(tumorTypeToSampleTypesMap, sampleTypes, ignoredPlatforms))
}

getDataType <- function(platform, protocol) {
    if (platform %in% names(PLATFORM_TO_DATATYPE_MAP)) {
        return(paste(PLATFORM_TO_DATATYPE_MAP[platform]))
    }

    if (platform == "bio") {
        if (protocol == "clinical") {
            return("Clinical")
        } else if (protocol == "biospecimen") {
            return("BCR")
        } else {
            return(protocol)
        }
    } else if (platform == "illuminaga_dnaseq" || platform == "solid_dna") {
        if (protocol == "Coverage_Calculation") {
            return("WIG")
        } else if (protocol == "Mutation_Calling") {
            return("MAF")
        } else {
            return(NULL)
        }
    } else if (platform == "illuminaga_dnaseq_automated" || platform == "solid_dna_automated") {
        if (protocol == "Coverage_Calculation") {
            return("rawWIG")
        } else if (protocol == "Mutation_Calling") {
            return("rawMAF")
        } else {
            return(NULL)
        }
    }
    return(NULL)
}

generateSamplesSubsection <- function(tumorType, sampleType, dataType,
                                     samplesToDataMap, sampleTypeMap) {
    samples   = c()
    platforms = c()
    centers   = c()
    levels    = c()
    protocols = c()
    for (sample in names(samplesToDataMap)) {
        dataMap = samplesToDataMap[[sample]]

        for (sampleInfo in dataMap) {
            samples   = c(samples, sampleInfo[["tcgaId"]])
            platforms = c(platforms, sampleInfo[["platform"]])
            centers   = c(centers, sampleInfo[["center"]])
            levels    = c(levels, sampleInfo[["level"]])
            protocols = c(protocols, sampleInfo[["protocol"]])
        }
    }
    df = data.frame(samples, platforms, centers, levels, protocols)
    colnames(df) =
        cbind("TCGA Barcode", "Platform", "Center", "Data Level", "Protocol")
    table = newTable(df)

    if ((! is.null(names(sampleTypeMap))) &&
        sampleType %in% names(sampleTypeMap)) {
        sampleType = sampleTypeMap[[sampleType]]
    }

    subsection =
        newSubSection(sprintf("%s %s %s Data", tumorType, sampleType, dataType))
    subsection = addTo(subsection, table)
    return(subsection)
}

generateHeatmapFigure <- function(heatmapsDir, tumorType, timestamp, destDir) {
    heatmapFilename    =
        sprintf("%s.%s.low_res.heatmap.png", tumorType, timestamp)
    lowResHeatmapPath  =
        file.path(heatmapsDir,
                  sprintf("%s.%s.low_res.heatmap.png", tumorType, timestamp))
    highResHeatmapPath =
        file.path(heatmapsDir,
                  sprintf("%s.%s.high_res.heatmap.png", tumorType, timestamp))

    figure = NULL
    if (file.exists(lowResHeatmapPath)) {
        if (file.exists(highResHeatmapPath)) {
            figure = newFigure(
                basename(lowResHeatmapPath),
                paste("This figure depicts the distribution of available",
                      "data on a per participant basis."),
                fileHighRes=basename(highResHeatmapPath))
        } else {
            figure = newFigure(
                basename(lowResHeatmapPath),
                paste("This figure depicts the distribution of available",
                      "data on a per participant basis."),
                fileHighRes=basename(lowResHeatmapPath))
        }
    }
    return(figure)
}

generateIntroduction <- function() {
    introduction = newParagraph(
        "The Broad GDAC mirrors data from the DCC on a daily basis. Although ",
        "all data is mirrored, not every sample is ingested into Firehose. ",
        "There are three main mechanisms that filter samples to ensure that ",
        "only the most scientifically relevant samples make it into our ",
        "standard data and analyses runs. These three mechanisms are ",
        "redactions, replicate filtering, and blacklisting. This report ",
        "summarizes the data that is ingested into Firehose, describes the ",
        "three filtering mechanisms, lists those samples that are removed, ",
        "and gives all available annotations from the DCC's Annotation Manager."
    )
    return(introduction)
}

generateSummaryParagraph <- function(redactionsCount, filterCount,
                                    blacklistCount, ffpeCount) {
    summaryParagraph = newParagraph(
        "There were ", redactionsCount, " redactions, ", filterCount,
        " replicate aliquots, ", blacklistCount, " blacklisted aliquots, and ",
        ffpeCount, " FFPE aliquots. The table below represents the sample ",
        "counts for those samples that were ingested into firehose after ",
        "filtering out redactions, replicates, and blacklisted data, and ",
        "segregating FFPEs."
    )
    return(summaryParagraph)
}

generateAnnotationsTable <- function(annotFile, tumorType = NULL,
                                    aggregateNameToTumorTypesMap = NULL) {
    annotTableRaw =
        read.table(annotFile, sep="\t", header=TRUE, comment.char="", quote="",
                   stringsAsFactors=FALSE)
    if (! is.null(tumorType)) {
        if (tumorType %in% names(aggregateNameToTumorTypesMap)) {
            annotTableRaw =
                subset(
                    annotTableRaw,
                    annotTableRaw$Type %in% aggregateNameToTumorTypesMap[[tumorType]])
        } else {
            annotTableRaw =
                subset(annotTableRaw, annotTableRaw$Type == tumorType)
        }
    }

    if (nrow(annotTableRaw) == 0) {
        return(list(NULL, 0))
    }

    annotTable = newTable(annotTableRaw, file=basename(annotFile))
    return(list(annotTable, nrow(annotTableRaw)))
}

generateBlacklistTable <- function(blacklistPath, destDir, tumorType = NULL,
                                  aggregateNameToTumorTypesMap = NULL) {
    if ((! is.null(blacklistPath)) && file.exists(blacklistPath)) {
        validateSymlink(blacklistPath, destDir)
        blacklistTableRaw =
            read.table(blacklistPath, header = TRUE, sep = "\t",
                       stringsAsFactors=FALSE, blank.lines.skip=TRUE)

        if (! is.null(tumorType)) {

            if (tumorType %in% names(aggregateNameToTumorTypesMap)) {
                blacklistTableRaw =
                    subset(
                        blacklistTableRaw,
                        blacklistTableRaw$Tumor.Type %in% aggregateNameToTumorTypesMap[[tumorType]])
                if (nrow(blacklistTableRaw) == 0) {
                    return(list(NULL, 0))
                }
            } else {
                if (! (tumorType %in% blacklistTableRaw$Tumor.Type)) {
                    return(list(NULL, 0))
                }
                blacklistTableRaw =
                    subset(blacklistTableRaw,
                           blacklistTableRaw$Tumor.Type == tumorType)
            }
        }

        blacklistTable =
            newTable(blacklistTableRaw, file=basename(blacklistPath),
                     "These samples were blacklisted and removed from the run.")
        return(list(blacklistTable, nrow(blacklistTableRaw)))
    }
    return(list(NULL, 0))
}

generateFilterTable <- function(filteredSamplesPath, destDir, tumorType = NULL,
                               aggregateNameToTumorTypesMap = NULL) {
    if ((! is.null(filteredSamplesPath)) && file.exists(filteredSamplesPath)) {
        validateSymlink(filteredSamplesPath, destDir)
        filterTableRaw = read.table(filteredSamplesPath, header = TRUE,
                                    sep = "\t", stringsAsFactors=FALSE)

        # If no filtered samples are reported, then return NULL
        if (nrow(filterTableRaw) == 0) {
            print(sprintf("no filtered for %s", tumorType))
            return(list(NULL, 0))
        }

        if (! is.null(tumorType)) {
            if (tumorType %in% names(aggregateNameToTumorTypesMap)) {
                filterTableRaw =
                    subset(
                        filterTableRaw,
                        filterTableRaw$Tumor.Type %in% aggregateNameToTumorTypesMap[[tumorType]])
                if (nrow(filterTableRaw) == 0) {
                    return(list(NULL, 0))
                }
            } else {
                if (! (tumorType %in% filterTableRaw$Tumor.Type)) {
                    return(list(NULL, 0))
                }
                filterTableRaw = subset(filterTableRaw,
                                        filterTableRaw$Tumor.Type == tumorType)
            }
        }

        tumorDataFrameWithCounts =
            as.data.frame(table(filterTableRaw$Tumor.Type))
        colnames(tumorDataFrameWithCounts) =
            cbind("Tumor Type", "Filtered Samples Count")

        tumorTableWithCounts =
            newTable(tumorDataFrameWithCounts,
                     file=basename(filteredSamplesPath),
                     paste("Click on any filtered samples count to display a",
                           "table detailing the filtered samples for the",
                           "associated tumor type."))
        for (i in 1:nrow(tumorDataFrameWithCounts)) {
            tumorType = tumorDataFrameWithCounts[i,1]
            tumorSubSection = generateFilterSubsection(tumorType,
                                                       filterTableRaw)
            result = addTo(newResult(""), tumorSubSection)
            tumorTableWithCounts =
                addTo(tumorTableWithCounts, result, row=i, column=2)
        }
        return(list(tumorTableWithCounts, nrow(filterTableRaw)))
    }
    return(list(NULL, 0))
}

generateFilterSubsection <- function(tumorType, filterTableRaw) {
    subsection = newSubSection(tumorType)
    tumorTypeDataFrame = subset(filterTableRaw, Tumor.Type == tumorType)
    tumorTypeDataFrameRed =
        cbind(tumorTypeDataFrame[,1],
              tumorTypeDataFrame[,3:ncol(tumorTypeDataFrame)])
    colnames(tumorTypeDataFrameRed) =
        cbind("Participant Id",
              "DataType__Platform__Center__DataLevel__ProtocolName_Extension",
              "Filter Reason", "Removed Sample(s)", "Chosen Sample")
    tumorTypeTable = newTable(tumorTypeDataFrameRed)
    subsection = addTo(subsection, tumorTypeTable)
    return(subsection)
}

generateHeatmapsSubSection <- function(heatmapsDir, timestamp, destDir) {
    heatmapsFilePattern =
        sprintf("^[0-9A-Za-z]+.%s.low_res.heatmap.png", timestamp)
    heatmaps = list.files(heatmapsDir, pattern=heatmapsFilePattern)
    heatmapsSubSection = newSubSection("Sample Heatmaps")
    for (heatmap in heatmaps) {
        splitResult = strsplit(heatmap, ".", fixed=TRUE)
        splitArray  = splitResult[[length(splitResult)]]
        tumorType = splitArray[[1]]
        lowResHeatmapPath = file.path(heatmapsDir, heatmap)
        highResHeatmapPath =
            file.path(heatmapsDir, sub("low_res","high_res", heatmap))
        heatmapSubSubSection =
            generateHeatmapSubSubSection(tumorType, lowResHeatmapPath,
                                         highResHeatmapPath, destDir)
        if (! is.null(heatmapSubSubSection)) {
            heatmapsSubSection = addTo(heatmapsSubSection, heatmapSubSubSection)
        }
    }
    return(heatmapsSubSection)
}

generateHeatmapSubSubSection <- function(tumorType, lowResHeatmapPath,
                                        highResHeatmapPath, destDir) {
    if (file.exists(lowResHeatmapPath)) {
        validateSymlink(lowResHeatmapPath, destDir)
        figure = NULL
        if (file.exists(highResHeatmapPath)) {
            validateSymlink(highResHeatmapPath, destDir)
            figure =
                newFigure(basename(lowResHeatmapPath),
                          paste("This figure depicts the distribution of",
                                "available data on a per participant basis."),
                          fileHighRes=basename(highResHeatmapPath))
        } else {
            figure =
                newFigure(basename(lowResHeatmapPath),
                          paste("This figure depicts the distribution of",
                                "available data on a per participant basis."),
                          fileHighRes=basename(lowResHeatmapPath))
        }
        subsection = newSubSubSection(tumorType)
        subsection = addTo(subsection, figure)
        return(subsection)
    }
    return(NULL)
}

################################################################################
# Generate Sample Counts Table
################################################################################
generateSampleCountsTable <- function(sampleCountsPath, sampleCountsTableRaw,
                                     sampleLoadfile, heatmapsPath, timestamp,
                                     runStmp, reportDir, platformCodeMap,
                                     centerCodeMap, sampleTypeMap, annotPaths,
                                     filteredSamplesPath, blacklistPath,
                                     diseaseStudyMap,
                                     tumorTypeToAggregateNamesMap,
                                     aggregateNameToTumorTypesMap,
                                     sampleToSampleSetsMap) {
    results = parseLoadfile(sampleLoadfile, heatmapsPath, timestamp, reportDir,
                            platformCodeMap, centerCodeMap,
                            tumorTypeToAggregateNamesMap, sampleToSampleSetsMap)

    tumorTypeToSampleTypesMap = results[[1]]
    sampleTypes               = results[[2]]
    ignoredPlatforms          = results[[3]]

    ignoredPlatformsDescription =
        newParagraph("The following platforms are outdated and are not ",
                     "included in the counts depicted in the table above.")
    ignoredPlatformsList = NULL
    if (length(ignoredPlatforms) > 0) {
        for (ignoredPlatform in ignoredPlatforms) {
            if ((! is.null(names(platformCodeMap))) &&
                ignoredPlatform %in% names(platformCodeMap)) {
                if (is.null(ignoredPlatformsList)) {
                    ignoredPlatformsList = newList(isNumbered=FALSE)
                }
                ignoredPlatformsList =
                    addTo(ignoredPlatformsList,
                          newParagraph(platformCodeMap[[ignoredPlatform]]))
            }
        }
    }

    sampleTypeDescription =
        newParagraph("The sample type short letter codes in the table above ",
                     "are defined in the following list.")
    sampleTypeList = NULL
    for (sampleType in names(sampleTypeMap)) {
        if (sampleType %in% sampleTypes) {
            if (is.null(sampleTypeList)) {
                sampleTypeList = newList(isNumbered=FALSE)
            }
            sampleTypeList =
                addTo(sampleTypeList,
                      newParagraph(
                          sprintf("%s: %s", sampleType,
                                  sampleTypeMap[[sampleType]])))
        }
    }

    for (tumorType in names(tumorTypeToSampleTypesMap)) {
        sampleTypesToDataTypesMap = tumorTypeToSampleTypesMap[[tumorType]]

        # Generate the tumor specific heatmap and sample counts table broken
        # down by sample type.
        sampleCountsTable =
            generateTumorTypeSampleCountsTable(
                tumorType, sampleTypesToDataTypesMap, sampleTypeMap,
                sampleCountsTableRaw)

        heatmap =
            generateHeatmapFigure(heatmapsPath, tumorType, timestamp, reportDir)

        fullName = tumorType
        if ((! is.null(names(diseaseStudyMap))) &&
            tumorType %in% names(diseaseStudyMap)) {
            fullName = diseaseStudyMap[[tumorType]]
        }
        url =
            createTumorSamplesReport(
                tumorType, fullName, runStmp, annotPaths, reportDir,
                filteredSamplesPath, blacklistPath, sampleCountsTable,
                ignoredPlatformsDescription, ignoredPlatformsList,
                sampleTypeDescription, sampleTypeList, heatmap,
                aggregateNameToTumorTypesMap, timestamp)

        if ("Tumor" %in% colnames(sampleCountsTableRaw)) {
            row = which(sampleCountsTableRaw$Tumor == tumorType)
        } else if ("Cohort" %in%  colnames(sampleCountsTableRaw)) {
            row = which(sampleCountsTableRaw$Cohort == tumorType)
        }

        sampleCountsTableRaw[row,1] = asLink(url, tumorType)
    }

    # Add links to sample counts summary table
    sampleCountsTable =
            newTable(
                    sampleCountsTableRaw, file=basename(sampleCountsPath),
                    paste("Summary of TCGA Tumor Data. Click on a tumor type to",
                            "display a tumor type specific Samples Report."))
    return(list("tbl" = sampleCountsTable, "df" = sampleCountsTableRaw))
}

################################################################################
# Generate Tumor Specific Sample Counts Table
################################################################################
generateTumorTypeSampleCountsTable <- function(tumorType,
    sampleTypesToDataTypesMap, sampleTypeMap, sampleCountsTableRaw) {
    columns = list()
    columns[["Sample Type"]] = c()
    for (dataType in DATA_TYPES) {
        columns[[dataType]] = c()
    }

    for (sampleType in names(sampleTypesToDataTypesMap)) {
        columns[["Sample Type"]] = c(columns[["Sample Type"]], sampleType)
        dataTypesToSamplesMap = sampleTypesToDataTypesMap[[sampleType]]

        for (dataType in DATA_TYPES) {
            if (dataType %in% names(dataTypesToSamplesMap)) {
                columns[[dataType]] =
                    c(columns[[dataType]],
                      length(dataTypesToSamplesMap[[dataType]]))
            } else {
                columns[[dataType]] = c(columns[[dataType]], 0)
            }
        }
    }

    # Add Totals row
    if (tumorType %in% row.names(sampleCountsTableRaw)) {
        columns[["Sample Type"]] = c(columns[["Sample Type"]], "Totals")
        for (dataType in DATA_TYPES) {
            if (dataType %in% names(sampleCountsTableRaw)) {
                columns[[dataType]] =
                    c(columns[[dataType]],
                      sampleCountsTableRaw[tumorType, dataType])
            } else {
                print(sprintf("Unrecognized data type: %s", dataType))
                columns[[dataType]] = c(columns[[dataType]], 0)
            }
        }
    }

    df = NULL
    for (column in columns) {
        if (is.null(df)) {
            df = data.frame(column)
        } else {
            df = data.frame(df, column)
        }
    }

    rownames(df) = df[,1]
    colnames(df) = cbind(names(columns))

    orderedRowNames = c()
    for (sampleType in names(sampleTypeMap)) {
        if (sampleType %in% row.names(df)) {
            orderedRowNames = c(orderedRowNames, sampleType)
        }
    }

    for (type in row.names(df)) {
        if (type != "Totals" && ! (type %in% names(sampleTypeMap))) {
            orderedRowNames = c(orderedRowNames, type)
        }
    }

    if ("Totals" %in% row.names(df)) {
        orderedRowNames = c(orderedRowNames, "Totals")
    }
    df = df[orderedRowNames,]

    table = newTable(df,
        paste("This table provides a breakdown of sample counts on a per",
              "sample type and, if applicable, per subtype basis. Each count",
              "is a link to a table containing a list of the samples that",
              "comprise that count and details pertaining to each individual",
              "sample (e.g. platform, sequencing center, etc.). Please note,",
              "there are usually multiple protocols per data type, so there",
              "are typically many more rows than the count implies."))

    for (r in 1:nrow(df)) {
        sampleType = rownames(df)[r]
        for (c in 2:ncol(df)) {
            dataType   = colnames(df)[c]
            if (dataType %in% names(sampleTypesToDataTypesMap[[sampleType]])) {
                samplesToDataMap =
                    sampleTypesToDataTypesMap[[sampleType]][[dataType]]

                samplesSubsection =
                    generateSamplesSubsection(tumorType, sampleType, dataType,
                                              samplesToDataMap, sampleTypeMap)

                result = addTo(newResult(""), samplesSubsection)
                table  = addTo(table, result, row=r, column=c)
            }
        }
    }
    return(list("tbl" = table, "df" = df))
}

################################################################################
# Create a standalone table file
################################################################################
createStandaloneTable <- function(dataFrame, tableName, reportDir, timestamp,
                                  del = FALSE) {
    tableReport <- newCustomReport("")
    tableReport <- addTo(tableReport, newTable(dataFrame))
    tableName <- file.path(reportDir, paste(tableName, timestamp, sep = "."))
    writeReport(tableReport, filename = tableName, output = c(HTML.REPORT),
                credits = FALSE)
    if (del) {
        write.table(dataFrame, paste0(tableName, ".tsv"), row.names=FALSE,
                    quote=FALSE, sep="\t")
    }
    tableName <- paste0(tableName, ".html")
    cleanStandaloneTable(tableName)
    html2png(tableName, del = del)
}

################################################################################
# Remove menus and background from standalone table
################################################################################
cleanStandaloneTable <- function(tableHtmlFile) {
    oldTable <- paste0(tableHtmlFile, ".old")
    file.rename(tableHtmlFile, oldTable)
    cmd =
        paste("awk '/<p>/, /<\\/p>/ {next} /<\\/?div/ {next} {print}'",
              oldTable, "| sed 's/color:\\#eee/color:\\#fff/g' >",
              tableHtmlFile)
    system(cmd)
    unlink(oldTable)
}

################################################################################
# Convert an html file to an image
################################################################################
html2png <- function(htmlFile, del = FALSE) {
    system(paste(HTML2PNG, htmlFile))
    if(del) unlink(htmlFile)
}

################################################################################
# Generate Tumor Specific Samples Report
################################################################################
createTumorSamplesReport <- function(disease, fullName, runStmp, annotPaths,
    reportDir, filteredSamplesPath, blacklistPath, sampleCountsTable,
    ignoredPlatformsDescription, ignoredPlatformsList, sampleTypeDescription,
    sampleTypeList, heatmap, aggregateNameToTumorTypesMap, timestamp) {
    reportStartTime = Sys.time()
    print(sprintf("Generating sample report for %s...", disease))

    if (disease == fullName) {
        reportName = sprintf("%s", disease)
    } else {
        reportName = sprintf("%s (%s)", fullName, disease)
    }

    reportName = paste(reportName, " Samples Report")

    diseaseReport = newReport(reportName)
    diseaseReport = setReportSubTitle(diseaseReport, runStmp)

    annotResults <- sapply(annotPaths, generateAnnotationsTable, disease,
                           aggregateNameToTumorTypesMap)

    redactionsTable = NULL
    redactionsCount = NULL
    if (REDACTIONS.HEAD %in% colnames(annotResults)) {
        redactionsTable = annotResults[[1, REDACTIONS.HEAD]]
        redactionsCount = annotResults[[2, REDACTIONS.HEAD]]
    }
    if (is.null(redactionsCount)) {
        redactionsCount = 0
    }

    ffpeTable = NULL
    ffpeCount = NULL
    if (FFPES.HEAD %in% colnames(annotResults)) {
        ffpeTable = annotResults[[1, FFPES.HEAD]]
        ffpeCount = annotResults[[2, FFPES.HEAD]]
    }
    if (is.null(ffpeCount)) {
        ffpeCount = 0
    }

    result         = generateFilterTable(filteredSamplesPath, reportDir,
                                         disease, aggregateNameToTumorTypesMap)
    filterTable    = result[[1]]
    filterCount    = result[[2]]

    result         = generateBlacklistTable(blacklistPath, reportDir, disease,
                                             aggregateNameToTumorTypesMap)
    blacklistTable = result[[1]]
    blacklistCount = result[[2]]

    summaryParagraph          = generateSummaryParagraph(redactionsCount,
                                                         filterCount,
                                                         blacklistCount,
                                                         ffpeCount)

    filteredSamplesSubSection = generateFilteredSamplesSubSection(reportDir,
            runStmp, redactionsTable, filterTable, blacklistTable, disease)
    ffpeSubSection            = generateFFPEsSubSection(reportDir, ffpeTable,
                                                        runStmp, disease)
    annotSubSection           = generateAnnotationsSubSection(reportDir,
                                                              annotResults[1,],
                                                              runStmp,
                                                              disease)

    diseaseReport = addToIntroduction(diseaseReport, generateIntroduction())
    diseaseReport = addToSummary(
        diseaseReport, summaryParagraph, sampleCountsTable$tbl)
    if (! is.null(sampleTypeList)) {
        diseaseReport = addToSummary(diseaseReport,
                                     sampleTypeDescription, sampleTypeList)
    }
    if (! is.null(ignoredPlatformsList)) {
        diseaseReport = addToSummary(
            diseaseReport, ignoredPlatformsDescription, ignoredPlatformsList)
    }
    diseaseReport = addToSummary(diseaseReport, heatmap)
    diseaseReport = addToResults(diseaseReport, filteredSamplesSubSection,
                                 ffpeSubSection, annotSubSection)
    diseaseReport = addToMethodsSection(diseaseReport)

    reportPath = file.path(reportDir, disease, fsep = .Platform$file.sep)

    createStandaloneTable(sampleCountsTable$df,
                          paste(disease, "sample_counts", sep = "."), reportDir,
                          timestamp, del = TRUE)
    writeReport(diseaseReport, filename=reportPath)
    print(sprintf("Finished generating sample report for %s in %s minutes",
                  disease,  difftime(Sys.time(), reportStartTime, units="min")))
    return(sprintf("%s.html", disease))
}

################################################################################
# Generate Filtered Samples SubSection
################################################################################
generateFilteredSamplesSubSection <- function(reportDir, runStmp,
        redactionsTable, filterTable, blacklistTable, disease=NULL) {

    redactionsReportLink = writeSectionReport(reportDir, redactionsTable,
            "Redactions", runStmp, getRedactionsDescriptions,
            "There were no redactions.", disease)
    replicateFilterLink = writeSectionReport(reportDir, filterTable,
            "Replicate Samples", runStmp, getReplicateFilterDescriptions,
            "There were no replicate samples.", disease)
    blacklistLink  = writeSectionReport(reportDir, blacklistTable,
            "Blacklisted Samples", runStmp, getBlacklistDescription,
            "There were no blacklisted samples.", disease)

    filteredSamplesSubSection = newSubSection("Filtered Samples")
    filteredSamplesSubSection = addTo(filteredSamplesSubSection,
                                      redactionsReportLink)
    filteredSamplesSubSection = addTo(filteredSamplesSubSection,
                                      replicateFilterLink)
    filteredSamplesSubSection = addTo(filteredSamplesSubSection,
                                      blacklistLink)

    return(filteredSamplesSubSection)
}

getRedactionsDescriptions <- function() {
    redactionsDescription1 = newParagraph(
            "For TCGA data, redaction is the removal of cases from the data ",
            "prior to publication or release. Redacted cases are generally rare, ",
            "but cases must be redacted when the TSS/BCR subject link is ",
            "incorrect (\"unknown patient identity\"), or in the case of genotype ",
            "mismatch, completely wrong cancer, or completely wrong organ/tissue. ",
            "Redaction occurs regardless of a case's analyte characterization or ",
            "DCC data deposition status."
    )

    redactionsDescription2 = newParagraph(
            "Rescission is the removal of samples from the list of redactions. ",
            "This happens if the reason for redaction is eventually cleared up. ",
            "For clarity, rescinded redactions do not appear in this report."
    )

    return(list(redactionsDescription1, redactionsDescription2))
}

getReplicateFilterDescriptions <- function() {
    filterDescription = newParagraph(
            "In many instances there is more than one aliquot for a given ",
            "combination of individual, platform, and data type. However, only ",
            "one aliquot may be ingested into Firehose. Therefore, a set of ",
            "precedence rules are applied to select the most scientifically ",
            "advantageous one among them. Two filters are applied to achieve this ",
            "aim: an Analyte Replicate Filter and a Sort Replicate Filter."
    )

    analyteFilterSubSubSection = newSubSubSection("Analyte Replicate Filter")
    analyteFilterDescription = newParagraph(
            "The following precedence rules are applied when the aliquots have ",
            "differing analytes. For RNA aliquots, T analytes are dropped in ",
            "preference to H and R analytes, since T is the inferior extraction ",
            "protocol. If H and R are encountered, H is the chosen analyte. This ",
            "is somewhat arbitrary and subject to change, since it is not clear ",
            "at present whether H or R is the better protocol. If there are ",
            "multiple aliquots associated with the chosen RNA analyte, the ",
            "aliquot with the later plate number is chosen. For DNA aliquots, D ",
            "analytes (native DNA) are preferred over G, W, or X (whole-genome ",
            "amplified) analytes, unless the G, W, or X analyte sample has a ",
            "higher plate number."
    )
    analyteFilterSubSubSection = addTo(analyteFilterSubSubSection,
            analyteFilterDescription)

    sortFilterSubSubSection = newSubSubSection("Sort Replicate Filter")
    sortFilterDescription = newParagraph(
            "The following precedence rules are applied when the analyte filter ",
            "still produces more than one sample. The sort filter chooses the ",
            "aliquot with the highest lexicographical sort value, to ensure that ",
            "the barcode with the highest portion and/or plate number is selected ",
            "when all other barcode fields are identical."
    )
    sortFilterSubSubSection = addTo(sortFilterSubSubSection,
            sortFilterDescription)

    return(list(filterDescription, analyteFilterSubSubSection,
                    sortFilterSubSubSection))
}

getBlacklistDescription <- function() {
    blacklistDescription = newParagraph(
            "In certain circumstances, replicate filtering may choose the less ",
            "favorable among two or more aliquots. For instance, an analyst may ",
            "manually review two aliquots for a given individual and determine ",
            "that one is superior. If the replicate filtering would choose the ",
            "inferior sample, then the inferior sample can be added to this ",
            "blacklist. This would result in the desired sample being chosen. ",
            "This table lists those blacklisted samples and a reason for their ",
            "being blacklisted."
    )
    return(list(blacklistDescription))
}

################################################################################
# Generate FFPEs SubSection
################################################################################
generateFFPEsSubSection <- function(reportDir, ffpeTable, runStmp, disease=NULL) {
    title = "FFPE Cases"
    ffpeSubSection = newSubSection(title)
    ffpeLink = writeSectionReport(reportDir, ffpeTable, title, runStmp,
            getFfpeDescriptions, "There were no FFPE cases.", disease)
    ffpeSubSection = addTo(ffpeSubSection, ffpeLink)
    return(ffpeSubSection)
}

getFfpeDescriptions <- function() {
    ffpeTcgaDescription = newSubSubSection(
        "FFPE description from ",
        asLink("http://cancergenome.nih.gov/cancersselected/biospeccriteria",
               "TCGA Tissue Sample Requirements"), " (2013)"
    )

    ffpeDescription = newParagraph(
            "FFPE (formalin fixed paraffin embedded) samples are not suitable ",
            "for molecular analysis because the RNA and DNA are trapped in ",
            "the nucleic acid-protein cross linking from the fixation process."
    )

    ffpeTcgaDescription = addTo(ffpeTcgaDescription, ffpeDescription)

    return(list(ffpeTcgaDescription))
}

################################################################################
# Generates Annotations SubSection
################################################################################
generateAnnotationsSubSection <- function(reportDir, annotTables, runStmp,
        disease=NULL){
    annotationsSubsection <- newSubSection(
        "Additional Annotations from the DCC's ",
        asLink("https://tcga-data.nci.nih.gov/annotations",
               "Annotations Manager")
        )

    for (classification in names(annotTables)) {
        if ((! (classification %in% c(REDACTIONS.HEAD, FFPES.HEAD))) &&
            (! is.null(annotTables[[classification]]))) {
            annotationLink = writeSectionReport(reportDir,
                                                annotTables[[classification]],
                                                classification, runStmp, NULL,
                                                sprintf("There were no %s", classification),
                                                disease)
            annotationsSubsection = addTo(annotationsSubsection, annotationLink)
        }
    }
    return(annotationsSubsection)
}

################################################################################
# Add to the Methods section in the provided report
################################################################################
addToMethodsSection <- function(report) {
    methodsP1 = newParagraph(
        "Annotation data was taken from the",
        asLink(url="https://tcga-data.nci.nih.gov/tcga/", "TCGA Data Portal"),
        "using the query string:"
    )
    methodsP2 = newParagraph(
        asFilename(paste0("https://tcga-data.nci.nih.gov/annotations/resources",
                          "/searchannotations/json?item=TCGA"))
    )
    methodsP3 = newParagraph("Redaction information was generated by ",
        'filtering for the annotationClassificationName "Redaction"')
    methodsP4 = newParagraph("FFPE information was generated by ",
        'filtering for "FFPE" in annotation note text')
    methodsP5 = newParagraph("Additional FFPEs were garnered from clinical ",
        "data")
    methodsP6 = newParagraph("Remaining annotations were sorted into sections ",
        "by annotationClassificationName")

    redactionsSubSection = newSubSection("Redactions and Other Annotations")
    redactionsSubSection = addTo(redactionsSubSection, methodsP1)
    redactionsSubSection = addTo(redactionsSubSection, methodsP2)
    redactionsSubSection = addTo(redactionsSubSection, methodsP3)
    redactionsSubSection = addTo(redactionsSubSection, methodsP4)
    redactionsSubSection = addTo(redactionsSubSection, methodsP5)
    redactionsSubSection = addTo(redactionsSubSection, methodsP6)

    mRNAPreprocessor = newParagraph(
        "The mRNA preprocess median module chooses the matrix for the ",
        "platform(Affymetrix HG U133, Affymetrix Exon Array and Agilent Gene ",
        "Expression) with the largest number of samples."
    )
    mRNAPreprocessorSubSubSection = newSubSubSection("mRNA Preprocessor")
    mRNAPreprocessorSubSubSection = addTo(mRNAPreprocessorSubSubSection,
                                          mRNAPreprocessor)

    mRNAseqPreprocessor = newParagraph(
        "The mRNAseq preprocessor picks the \"scaled_estimate\" (RSEM) value ",
        "from Illumina HiSeq/GA2 mRNAseq level_3 (v2) data set and makes the ",
        "mRNAseq matrix with log2 transformed for the downstream analysis. If ",
        "there are overlap samples between two different platforms, samples ",
        "from illumina hiseq will be selected. The pipeline also creates the ",
        "matrix with RPKM and log2 transform from HiSeq/GA2 mRNAseq level 3 ",
        "(v1) data set."
    )
    mRNAseqPreprocessorSubSubSection = newSubSubSection("mRNAseq Preprocessor")
    mRNAseqPreprocessorSubSubSection = addTo(mRNAseqPreprocessorSubSubSection,
                                             mRNAseqPreprocessor)

    miRseqPreprocessor = newParagraph(
        "The miRseq preprocessor picks the \"RPM\" (reads per million miRNA ",
        "precursor reads) from the Illumina HiSeq/GA miRseq Level_3 data set ",
        "and makes the matrix with log2 transformed values."
    )
    miRseqPreprocessorSubSubSection = newSubSubSection("miRseq Preprocessor")
    miRseqPreprocessorSubSubSection = addTo(miRseqPreprocessorSubSubSection,
                                            miRseqPreprocessor)

    methylationPreprocessor = newParagraph(
        "The methylation preprocessor filters methylation data for use in ",
        "downstream pipelines. To learn more about this preprocessor, please ",
        "visit the ",
        paste0(asLink(paste0("https://confluence.broadinstitute.org/display/",
                             "GDAC/Methylation+Preprocessor"),"documentation"),
               ".")
    )
    methylationPreprocessorSubSubSection =
        newSubSubSection("Methylation Preprocessor")
    methylationPreprocessorSubSubSection =
        addTo(methylationPreprocessorSubSubSection, methylationPreprocessor)

    preprocessorsSubSection = newSubSection("Preprocessors")
    preprocessorsSubSection = addTo(preprocessorsSubSection,
                                    mRNAPreprocessorSubSubSection)
    preprocessorsSubSection = addTo(preprocessorsSubSection,
                                    mRNAseqPreprocessorSubSubSection)
    preprocessorsSubSection = addTo(preprocessorsSubSection,
                                    miRseqPreprocessorSubSubSection)
    preprocessorsSubSection = addTo(preprocessorsSubSection,
                                    methylationPreprocessorSubSubSection)

    report = addToMethods(report, redactionsSubSection)
    report = addToMethods(report, preprocessorsSubSection)
    return(report)
}

#===============================================================================
# Call main(args)
#===============================================================================
main(commandArgs(trailingOnly = TRUE))
