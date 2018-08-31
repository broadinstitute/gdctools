#!/usr/bin/env Rscript

# William Mallard / Redactions Report / April 2012
# Dan DiCara / Updated to Samples Summary Report / January 2013
# Tim DeFreitas / Updated for GDC + GDAN era / June 2016
# Michael S. Noble / More GDC + GDAN updates / March 2017

if(!require(Nozzle.R1)){
    install.packages("Nozzle.R1", repos='https://cloud.r-project.org/')
}

library(Nozzle.R1)
options(error = function() traceback(2))

SAMPLE_TYPES = c("TP", "TR", "TB", "TRBM", "TAP", "TM", "TAM", "THOC", "TBM",
                 "NB", "NT", "NBC", "NEBV", "NBM", "FFPE")

main <- function(...) {
  startTime = Sys.time()
  ############################################################################
  # Parse inputs
  ############################################################################
  # Why is this necessary?
  args <- unlist(list(...))
### TODO: Fix input arguments and make abbreviated list
  if (length(args)  != 4) {
    stop(
      paste(
            "Usage: RedactionsReport.R <datestamp> <reportDir> <refDir>",
            "<blacklist>"))
    }
  datestamp           = args[[1]]
  reportDir           = args[[2]]
  refDir              = args[[3]]
  blacklistPath       = args[[4]]
  ############################################################################
  # Initialization
  ############################################################################

  aggregatesPath = file.path(reportDir, "aggregates.txt")
  result = getAggregates(aggregatesPath)
  tumorTypeToAggregateNamesMap = result[[1]]
  aggregateNameToTumorTypesMap = result[[2]]

  runDate = datestamp
  runStmp = paste(runDate, "Data Snapshot")
  runName = paste0("stddata__", runDate)

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
  #  FIXME: nrow() the raw data, not the Nozzle table?
  redactionsTable  <- getRedactionsTable(reportDir, datestamp)
  redactionsCount  <- 0 # nrow(redactionsTable)

  ffpeTable        <- getFFPETable(reportDir, datestamp)
  ffpeCount        <- 0 # nrow(ffpeTable)

  filterTableList  <- getFilterTable(reportDir, datestamp, aggregateNametoTumorTypesMap)
  filterTable      <- filterTableList[[1]]
  filterCount      <- filterTableList[[2]]

  blacklistTable   <- getBlacklistTable(blacklistPath)
  blacklistCount   <- 0 # nrow(blacklistTable)

  summaryParagraph <- generateSummaryParagraph(redactionsCount, filterCount,
                                              blacklistCount, ffpeCount)
  report           <- addToSummary(report, summaryParagraph)

  ############################################################################
  # Heatmaps SubSection
  ############################################################################
  heatmapsStart   <- Sys.time()
  heatmaps        <- generateHeatmapsSubSection(datestamp, reportDir)
  report          <- addToResults(report, heatmaps)
  print(sprintf("Heatmaps section generated in %s minutes.",
                difftime(Sys.time(), heatmapsStart, units="min")))


  ############################################################################
  # Ingested Samples
  ############################################################################
  ingestSamplesStartTime <- Sys.time()
  sampleCountsPath <- paste("sample_counts", datestamp, "tsv", sep=".")
  sampleCountsPath <- file.path(reportDir, sampleCountsPath)
  sampleCountsTableRaw <- read.table(sampleCountsPath, header = TRUE,
                                    sep = "\t", stringsAsFactors=FALSE)

  # Remove sample type rows (i.e. SKCM-TP, SKCM-NT, SKCM-FFPE, etc.)
  sampleCountsTableRaw <- subset(sampleCountsTableRaw,
                                  !(grepl("-[[:upper:]]*-",
                                        sampleCountsTableRaw$Cohort)))
  rownames(sampleCountsTableRaw) <- sampleCountsTableRaw$Cohort

  sampleCountsTable <- generateSampleCountsTable(sampleCountsPath,
                                     sampleCountsTableRaw,
                                     refDir, datestamp, reportDir,
                                     blacklistPath, aggregateNameToTumorTypesMap)
  report  <- addToSummary(report, sampleCountsTable$tbl)
#    createStandaloneTable(sampleCountsTable$df, "sample_counts", reportDir,
#                          datestamp)
  print(sprintf("Created Ingested Samples section in %s minutes.",
                 difftime(Sys.time(), ingestSamplesStartTime, units="min")))

  ############################################################################
  # Filtered Samples SubSection
  ############################################################################
  filteredSamplesStart = Sys.time()
  filteredSamplesSubSection = generateFilteredSamplesSubSection(reportDir,
         runStmp, redactionsTable, filterTable, blacklistTable)
  print(sprintf("Filtered samples section generated in %s minutes.",
                 difftime(Sys.time(), filteredSamplesStart, units="min")))
  report = addToResults(report, filteredSamplesSubSection)

  ############################################################################
  # FFPEs Subsection
  ############################################################################
  #ffpeStart = Sys.time()
  #ffpeSubSection = generateFFPEsSubSection(reportDir, ffpeTable, runStmp)
  #print(sprintf("FFPE samples section generated in %s minutes.",
  #              difftime(Sys.time(), ffpeStart, units="min")))
  #report = addToResults(report, ffpeSubSection)

  ############################################################################
  # Annotations Subsection
  ############################################################################
  #annotStart = Sys.time()
  #annotSubSection = generateAnnotationsSubSection(reportDir, NULL,
  #                                                runStmp)
  #print(sprintf("Annotations section generated in %s minutes.",
  #              difftime(Sys.time(), annotStart, units="min")))
  #report = addToResults(report, annotSubSection)

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

### Return a map of sample type codes to full names.
### e.g. "TP" -> "Tumor Primary"
getSampleTypeMap <- function(refDir) {
  sampleTypePath <- file.path(refDir, "sampleType.txt")
  sampleTypeMap <- list()
  if (file.exists(sampleTypePath)) {
      sampleTypeTable =
          read.table(sampleTypePath, sep="\t", header=TRUE, comment.char="",
                     quote="", stringsAsFactors=FALSE)
      for (i in 1:nrow(sampleTypeTable)) {
          shortLetterCode = sampleTypeTable$Short.Letter.Code[i]
          sampleType      = sampleTypeTable$Definition[i]
          sampleTypeMap[[shortLetterCode]] = sampleType
      }
  } else {
      stop(sprintf("Could not find sample type table: %s", sampleTypePath))
  }

  return(sampleTypeMap)
}
### Return a map of cohort abbreviations to full names.
### e.g. "ACC" -> "Adrenocortical Carcinoma"
getDiseaseStudyMap <- function(refDir) {
  diseaseStudyPath <- file.path(refDir, "diseaseStudy.txt")
  diseaseStudyMap <- list()
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
  return(diseaseStudyMap)
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

generateSamplesSubsection <- function(tumorType, sampleType, dataType,
                                     tumorMeta.df) {

    # Filter matching report type
    dataType.df <- tumorMeta.df[tumorMeta.df$report_type == dataType, ]
    # Filter by correct sample type
    # TODO: sample_types are slightly different between GDC and TCGA
    # There should be a better way to verify that the expected values are the same
    #FIXME: Hack for FFPE's should be rearchitected
    if (!(dataType %in% c("BCR", "Clinical"))) {
      if (sampleType != "FFPE") {
        dataType.df <- dataType.df[dataType.df$sample_type == sampleType, ]
        dataType.df <- dataType.df[dataType.df$is_ffpe == "False", ]
      } else {
        dataType.df <- dataType.df[dataType.df$is_ffpe == "True", ]
      }
    } else {
    # We need to search tumorMeta.df to figure out which cases have the right
    # tumorType
      if (sampleType != "FFPE") {
       cases.df <- tumorMeta.df[tumorMeta.df$sample_type == sampleType, ]
      } else {
       cases.df <- tumorMeta.df[tumorMeta.df$is_ffpe =="True", ]
      }
      dataType.df <- dataType.df[dataType.df$case_id %in% cases.df$case_id, ]
    }
    columns <- c("tcga_barcode", "platform", "center", "annotation")
    dataType.df <- dataType.df[,columns]
    names(dataType.df) <- c("TCGA Barcode", "Platform", "Center", "Annotation")
    dataType.df <- dataType.df[order(dataType.df[,1]), ]
    table <- newTable(dataType.df)

    subsection <-
        newSubSection(sprintf("%s %s %s Data", tumorType, sampleType, dataType))
    subsection <- addTo(subsection, table)
    return(subsection)
}

generateHeatmapFigure <- function(heatmapsDir, tumorType, datestamp) {
    heatmapFilename    =
        sprintf("%s.%s.low_res.heatmap.png", tumorType, datestamp)
    lowResHeatmapPath  =
        file.path(heatmapsDir,
                  sprintf("%s.%s.low_res.heatmap.png", tumorType, datestamp))
    highResHeatmapPath =
        file.path(heatmapsDir,
                  sprintf("%s.%s.high_res.heatmap.png", tumorType, datestamp))

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
        "This is a summary of data mirrored from the Genomic Data Commons ",
        "(GDC) and processed by the GDCtools package.  Note that some ",
        "sample data will be filtered as unsuitable for downstream ",
        "pipelines, through one of three mechanisms: redactions, replicate ",
        "filtering, and blacklisting. The report lists the counts and types ",
        "of the sample data, in both hyperlinked tables and heatmap images; ",
        "describes the three filtering mechanisms; lists the samples removed ",
        "by filtering, why they were ",
        "removed; and (eventually will) catalog how the data have been ",
        "annotated by the respective projects that submitted them to the GDC."
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

generateHeatmapsSubSection <- function(datestamp, reportDir) {
    heatmapsFilePattern =
        sprintf("^[-0-9A-Za-z]+.%s.low_res.heatmap.png", datestamp)
    heatmaps = list.files(reportDir, pattern=heatmapsFilePattern)
    heatmapsSubSection = newSubSection("Sample Heatmaps")
    for (heatmap in heatmaps) {
        splitResult = strsplit(heatmap, ".", fixed=TRUE)
        splitArray  = splitResult[[length(splitResult)]]
        tumorType = splitArray[[1]]
        lowResHeatmapPath = file.path(reportDir, heatmap)
        highResHeatmapPath =
            file.path(reportDir, sub("low_res","high_res", heatmap))
        heatmapSubSubSection =
            generateHeatmapSubSubSection(tumorType, lowResHeatmapPath,
                                         highResHeatmapPath, reportDir)
        if (! is.null(heatmapSubSubSection)) {
            heatmapsSubSection = addTo(heatmapsSubSection, heatmapSubSubSection)
        }
    }
    return(heatmapsSubSection)
}

generateHeatmapSubSubSection <- function(tumorType, lowResHeatmapPath,
                                        highResHeatmapPath, destDir) {
    if (file.exists(lowResHeatmapPath)) {
        ### All heatmaps are already in the reportDir, no need to symlink
        figure = NULL
        if (file.exists(highResHeatmapPath)) {
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
                                   refDir, datestamp, reportDir,
                                   blacklistPath, aggregateNameToTumorTypesMap) {
  ### Create a list of sample types and their abbreviations
  sampleTypeMap <- getSampleTypeMap(refDir)
  sampleTypeDescription =
      newParagraph("The sample type short letter codes in the table above ",
                   "are defined in the following list.")
  sampleTypeList = newList(isNumbered=FALSE)
  for (sampleType in names(sampleTypeMap)) {
     sampleTypeList <-
       addTo(sampleTypeList,
         newParagraph(
                   sprintf("%s: %s", sampleType, sampleTypeMap[[sampleType]])))
  }
  countsPattern <- paste("", datestamp, "sample_counts.tsv", sep='.')
  cohortCountsFiles <- list.files(reportDir, pattern=countsPattern)
  cohorts <- lapply(cohortCountsFiles, function(fn) {
    unlist(strsplit(fn, "\\."))[1]
  })
  ### Get full names of cohorts
  diseaseStudyMap <- getDiseaseStudyMap(refDir)

  ### TODO: Vectorize w/lapply
  for (tumorType in cohorts){
    # Create the tumor specific heatmap and sample counts table
    # TODO: These steps should be moved to createTumorSamplesReport
    tumorCountsPath <- paste0(tumorType, ".", datestamp, ".sample_counts.tsv")
    tumorCountsPath <- file.path(reportDir, tumorCountsPath)
    tumorDicedMetaPath <- paste0(tumorType, ".", datestamp, ".diced_metadata.tsv")
    tumorDicedMetaPath <- file.path(reportDir, tumorDicedMetaPath)
    sampleCountsTable <-
        generateTumorTypeSampleCountsTable(tumorType, tumorCountsPath,
                                           tumorDicedMetaPath, sampleTypeMap)
    heatmap <-
        generateHeatmapFigure(reportDir, tumorType, datestamp)

    fullName <- tumorType
    if ((! is.null(names(diseaseStudyMap))) &&
        tumorType %in% names(diseaseStudyMap)) {
        fullName = diseaseStudyMap[[tumorType]]
    }

    ### Create the tumor specific report
    url <-
      createTumorSamplesReport(tumorType, fullName,
        reportDir, sampleCountsTable, sampleTypeDescription,
        sampleTypeList, heatmap, datestamp, aggregateNameToTumorTypesMap)

    # Update row for this cohort  with link to cohort report
    # FIXME: TCGA-Hard coded here
    row = which(sampleCountsTableRaw$Cohort == tumorType)
    sampleCountsTableRaw[row,1] = asLink(url, tumorType)
  }

###    # Add links to sample counts summary table

  sampleCountsTable <-
            newTable(sampleCountsTableRaw, file=basename(sampleCountsPath),
                     paste("Summary of TCGA Tumor Data. Click on a tumor type to",
                           "display a tumor type specific Samples Report."))
  return(list("tbl" = sampleCountsTable, "df" = sampleCountsTableRaw))
}

################################################################################
# Generate Tumor Specific Sample Counts Table
################################################################################
generateTumorTypeSampleCountsTable <- function(tumorType, tumorCountsPath, tumorDicedMetaPath, sampleTypeMap) {

### FIXME: Only works for TCGA samples...
  tumorTable.df <- read.table(tumorCountsPath, header=TRUE,
                              sep="\t", stringsAsFactors=FALSE)

  tumorMeta.df <- read.table(tumorDicedMetaPath, header=TRUE,
                              sep="\t", stringsAsFactors=FALSE)

  table <-  newTable(tumorTable.df,
        paste("This table provides a breakdown of sample counts on a per",
              "sample type and, if applicable, per subtype basis. Each count",
              "is a link to a table containing a list of the samples that",
              "comprise that count and details pertaining to each individual",
              "sample (e.g. platform, sequencing center, etc.). Please note,",
              "there are usually multiple protocols per data type, so there",
              "are typically many more rows than the count implies."))


###  For each table entry, append the sample subsection for the relevant samples
### Note -1 to skip Totals row, which does not need this.
  last <- nrow(tumorTable.df) - 1
  for (r in 1:last) {
    sampleType <- tumorTable.df[r,1]
	if (length(sampleType) < 1) {
		print("Skipping zero-sized sampleType: is sample counts table empty?")
		next
	}
    sampleTypeLong <- sampleTypeMap[[sampleType]]
    #FIXME:  Hack for FFPE's, must be a better way to write this...
    if (sampleType == "FFPE") {
      sampleTypeLong <- "FFPE"
    }
    for (c in 2:ncol(tumorTable.df)) {
          dataType   = colnames(tumorTable.df)[c]
          if (tumorTable.df[r,c] > 0 ) {
          # Set sampleType to the full name
              samplesSubsection <-
                  generateSamplesSubsection(tumorType, sampleTypeLong, dataType,
                                            tumorMeta.df)

              result = addTo(newResult(""), samplesSubsection)
              table  = addTo(table, result, row=r, column=c)
          }
      }
  }
  return(list("tbl" = table, "df" = tumorTable.df))
}

################################################################################
# Create a standalone table file
################################################################################
createStandaloneTable <- function(dataFrame, tableName, reportDir, datestamp,
                                  del = FALSE) {
    tableReport <- newCustomReport("")
    tableReport <- addTo(tableReport, newTable(dataFrame))
    tableName <- file.path(reportDir, paste(tableName, datestamp, sep = "."))
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
createTumorSamplesReport <- function(disease, fullName,
  reportDir, sampleCountsTable, sampleTypeDescription,
  sampleTypeList, heatmap, datestamp, aggregateNameToTumorTypesMap) {

  reportStartTime <- Sys.time()
  print(sprintf("Generating sample report for %s...", disease))

  if (disease == fullName) {
      reportName <- sprintf("%s", disease)
  } else {
      reportName <- sprintf("%s (%s)", fullName, disease)
  }

  reportName <- paste(reportName, " Samples Report")

  runDate <- datestamp
  runStmp <- paste(runDate, "Data Snapshot")

  diseaseReport <- newReport(reportName)
  diseaseReport <- setReportSubTitle(diseaseReport, runStmp)
### TODO: re-insert redactions, filtered samples, etc..
###     annotResults <- sapply(annotPaths, generateAnnotationsTable, disease,
###                            aggregateNameToTumorTypesMap)
  redactionsTable <- NULL
  redactionsCount <- 0
###     if (REDACTIONS.HEAD %in% colnames(annotResults)) {
###         redactionsTable = annotResults[[1, REDACTIONS.HEAD]]
###         redactionsCount = annotResults[[2, REDACTIONS.HEAD]]
###     }
###     #if (is.null(redactionsCount)) {
###     #    redactionsCount = 0
###     #}
###
  ffpeTable <- NULL
  ffpeCount <- 0
###     if (FFPES.HEAD %in% colnames(annotResults)) {
###         ffpeTable = annotResults[[1, FFPES.HEAD]]
###         ffpeCount = annotResults[[2, FFPES.HEAD]]
###     }
###     if (is.null(ffpeCount)) {
###         ffpeCount = 0
###     }
###
  filterTableList         <- getFilterTable(reportDir, datestamp,
                                            aggregateNameToTumorTypesMap, disease)
  filterTable    <- filterTableList[[1]]
  filterCount    <- filterTableList[[2]]
###
###     result         = generateBlacklistTable(blacklistPath, reportDir, disease,
###                                              aggregateNameToTumorTypesMap)
###     blacklistTable = result[[1]]
###     blacklistCount = result[[2]]
  blacklistTable <- NULL
  blacklistCount <- 0

  summaryParagraph          = generateSummaryParagraph(redactionsCount,
                                                       filterCount,
                                                       blacklistCount,
                                                       ffpeCount)

  filteredSamplesSubSection = generateFilteredSamplesSubSection(reportDir,
          runStmp, redactionsTable, filterTable, blacklistTable, disease)
###   ffpeSubSection            = generateFFPEsSubSection(reportDir, ffpeTable,
###                                                       runStmp, disease)
###   annotSubSection           = generateAnnotationsSubSection(reportDir,
###                                                             annotResults[1,],
###                                                             runStmp,
###                                                             disease)
###
    diseaseReport = addToIntroduction(diseaseReport, generateIntroduction())
    diseaseReport = addToSummary(
        diseaseReport, summaryParagraph, sampleCountsTable$tbl)
    if (! is.null(sampleTypeList)) {
        diseaseReport = addToSummary(diseaseReport,
                                     sampleTypeDescription, sampleTypeList)
    }
###     if (! is.null(ignoredPlatformsList)) {
###         diseaseReport = addToSummary(
###             diseaseReport, ignoredPlatformsDescription, ignoredPlatformsList)
###     }
    diseaseReport <-  addToSummary(diseaseReport, heatmap)
    diseaseReport <- addToResults(diseaseReport, filteredSamplesSubSection)
###     diseaseReport = addToResults(diseaseReport, filteredSamplesSubSection,
###                                  ffpeSubSection, annotSubSection)
###     diseaseReport = addToMethodsSection(diseaseReport)

    reportPath = file.path(reportDir, disease)

###     createStandaloneTable(sampleCountsTable$df,
###                           paste(disease, "sample_counts", sep = "."), reportDir,
###                           datestamp, del = TRUE)

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
### TODO: fix not yet implemented messages
    redactionsReportLink = writeSectionReport(reportDir, redactionsTable,
            "Redactions", runStmp, getRedactionsDescriptions,
            "NOT YET IMPLEMENTED", disease)
    replicateFilterLink = writeSectionReport(reportDir, filterTable,
            "Replicate Samples", runStmp, getReplicateFilterDescriptions,
            "There were no replicate samples.", disease)
    blacklistLink  = writeSectionReport(reportDir, blacklistTable,
            "Blacklisted Samples", runStmp, getBlacklistDescription,
            "NOT YET IMPLEMENTED", disease)

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
    # TODO: Fix not yet implemented message
    title = "FFPE Cases"
    ffpeSubSection = newSubSection(title)
    ffpeLink = writeSectionReport(reportDir, ffpeTable, title, runStmp,
            getFfpeDescriptions, "NOT YET IMPLEMENTED", disease)
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
        "[NOT YET IMPLEMENTED] Additional Annotations from the DCC's ",
        asLink("https://tcga-data.nci.nih.gov/annotations",
               "Annotations Manager")
        )

###     for (classification in names(annotTables)) {
###         if ((! (classification %in% c(REDACTIONS.HEAD, FFPES.HEAD))) &&
###             (! is.null(annotTables[[classification]]))) {
###             annotationLink = writeSectionReport(reportDir,
###                                                 annotTables[[classification]],
###                                                 classification, runStmp, NULL,
###                                                 sprintf("There were no %s", classification),
###                                                 disease)
###             annotationsSubsection = addTo(annotationsSubsection, annotationLink)
###         }
###     }
    return(annotationsSubsection)
}

################################################################################
# Add to the Methods section in the provided report
################################################################################
addToMethodsSection <- function(report) {

    redactionsSubSection = newSubSection("Redactions and Other Annotations")

    methodsP1 = newParagraph(
        "NOT IMPLEMENTED YET: redactions are not yet exposed at the GDC. For ",
        "examples of the annotation-based filtering performed in the past by ",
        "the Broad GDAC Firehose pipeline, explore this ",
        asLink(url="http://gdac.broadinstitute.org/runs/stddata__2016_01_28/samples_report",
        "legacy GDAC Firehose sample report"))

    redactionsSubSection = addTo(redactionsSubSection, methodsP1)

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
#TODO: Fully implement these functions
getRedactionsTable <- function(reportDir, datestamp){
  return(NULL)
}
getFFPETable <- function (reportDir, datestamp){
  return(NULL)
}
getFilterTable <- function (reportDir, datestamp, aggregateNameToTumorTypesMap=NULL,tumor.type=NULL){
  filtered.file <- "*.filtered_samples.txt"
  filtered_samples_files <- Sys.glob( file.path(reportDir, filtered.file))
  if (length(filtered_samples_files) != 1)
		print("Warning: more than 1 filtered_samples.txt file, choosing first")
  filtered.file <- filtered_samples_files[1]
  filterTableRaw <- read.table(filtered.file, sep="\t", header=TRUE, stringsAsFactors=FALSE)
  if (!is.null(tumor.type)){
    # Split
    if (substr(tumor.type, 1, 5) == "TCGA-"){
       tumor.type <- substr(tumor.type, 6, nchar(tumor.type))
    }
    # Filter by tumor.type
    if (tumor.type %in% names(aggregateNameToTumorTypesMap)){
    # Aggregate, filter to members of the aggregate
      filterTableRaw <- subset(filterTableRaw,
                               filterTableRaw$Tumor.Type %in% aggregateNameToTumorTypesMap[[tumor.type]])
    } else {
    # Singleton, filter to this tumor type
      filterTableRaw <- subset(filterTableRaw, filterTableRaw$Tumor.Type == tumor.type)
    }
  }

  filterTable <- NULL
  filterTableCount <- nrow(filterTableRaw)
  if (filterTableCount != 0){
    filterTable <- newTable(filterTableRaw, file=basename(filtered.file))
  }
  return(list(filterTable, filterTableCount))

}
getBlacklistTable <- function(blacklistPath){
  return(NULL)
}
#===============================================================================
# Call main(args)
#===============================================================================
main(commandArgs(trailingOnly = TRUE))
