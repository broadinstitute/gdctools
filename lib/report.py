#!/usr/bin/env python
# encoding: utf-8

# Front Matter {{{
'''
Copyright (c) 2016 The Broad Institute, Inc.  All rights are reserved.

report.py: Functions for creating reports of Mirrored/Diced Data

@author: Timothy DeFreitas
@date:  2016_06_06
'''

# }}}
import os
import numpy
import subprocess
import logging

from matplotlib.figure import Figure, Rectangle
from matplotlib.colors import ListedColormap, NoNorm
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib import font_manager

NOZZLE_PATH = "/xchip/tcga/Tools/gdac/bin/nozzle"
_SUMMARY_REPORT_R = ""

def draw_heatmaps(rownames, matrix, cohort, timestamp, outputDir):
    if not len(matrix) > 0:
        raise ValueError('input matrix must have nonzero length')
    if not len(matrix) == len(rownames):
        raise ValueError('Number of row names does not match input matrix')

    #Sort heatmaps rows by row count
    sorted_rownames, sorted_matrix = __sort_rows(rownames, matrix)

    green = '#338855'
    white = '#FFFFFF'
    cmap = ListedColormap([white, green])
    fig = Figure(figsize=(24,12))
    ax = fig.add_subplot(111)
    ax.set_title("%s: Data Type Breakdown by Participant" % cohort, weight="black")
    ax.set_ylabel("Data Type (Total Sample Count)", weight="black")
    ax.set_xlabel("Participant", weight="black")
    ax.set_xlim(0, len(sorted_matrix[0]))
    ax.set_yticks([0.5 + x for x in range(len(sorted_matrix))])

    counts = [sum(row) for row in sorted_matrix]
    ax.set_yticklabels(["%s (%s)" % (data_type, count) for data_type, count in zip(sorted_rownames, counts)])
    ax.pcolor(numpy.array(sorted_matrix), cmap=cmap, norm=NoNorm(), edgecolor="k")
    missing = Rectangle((0, 0), 1, 1, fc=white)
    present = Rectangle((0, 0), 1, 1, fc=green)
    ax.legend([present, missing], ["Present", "Absent"], loc=1)

    fig.set_size_inches(24,12)
    ax.title.set_size("xx-large")
    ax.xaxis.label.set_size("xx-large")
    ax.yaxis.label.set_size("xx-large")
    ax.tick_params(axis="both", labelsize="x-large")
    canvas = FigureCanvasAgg(fig)
    high_res_filepath = os.path.join(outputDir, ".".join([cohort, timestamp,"high_res.heatmap.png"]))
    fig.tight_layout()
    canvas.print_figure(high_res_filepath)

    fig.set_size_inches(12,6)
    ax.title.set_size("medium")
    ax.xaxis.label.set_size("small")
    ax.yaxis.label.set_size("small")
    ax.tick_params(axis="both", labelsize="x-small")
    fontProp = font_manager.FontProperties(size=9)
    ax.legend([present, missing], ["Present", "Absent"], loc=1, prop=fontProp)
    canvas = FigureCanvasAgg(fig)
    low_res_filepath = os.path.join(outputDir, ".".join([cohort, timestamp, "low_res.heatmap.png"]))
    fig.tight_layout()
    canvas.print_figure(low_res_filepath)

def __sort_rows(rownames, matrix):
    '''Sort the rows in matrix by the number of values in the row, in ascending order'''

    row_dict = {rownames[i]:matrix[i] for i in range(len(rownames))}
    sorted_rows = sorted(row_dict.keys(), key=lambda k: sum(row_dict[k]))

    sorted_mat = [row_dict[row] for row in sorted_rows]

    return sorted_rows, sorted_mat

def generate_report(timestamp, blacklist, refdir, redactionsdir, samplestamp,
                    samplecounts, samplesets, heatmap, outdir, aggregates,
                    filteredSamplesPath):
    pass
