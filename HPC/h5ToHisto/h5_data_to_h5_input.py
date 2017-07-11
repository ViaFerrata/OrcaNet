#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""This main code takes raw simulated .hdf5 files as input in order to generate 2D/3D histograms ('images') that can be used for CNNs."""

import os
import sys
#from memory_profiler import profile # for memory profiling, call with @profile; myfunc()
import line_profiler # call with kernprof file.py args
from matplotlib.backends.backend_pdf import PdfPages

import glob
from file_to_hits import *
from histograms_to_files import *
from hits_to_histograms import *

__author__ = 'Michael Moser'
__license__ = 'AGPL'
__version__ = '1.0'
__email__ = 'michael.m.moser@fau.de'
__status__ = 'Prototype'
# Heavily based on code from sgeisselsoeder: https://github.com/sgeisselsoeder/km3netHdf5ToHistograms/


def calculate_bin_edges(n_bins, geo_limits):
    """
    Calculates the bin edges for the later np.histogramdd actions based on the number of specified bins. 
    This is performed in order to get the same bin size for each event regardless of the fact if all bins have a hit or not.
    :param list n_bins: contains the desired number of bins for each dimension. [n_bins_x, n_bins_y, n_bins_z]
    :param geo_limits: contains the min and max values of each geometry dimension. [[first_OM_id, xmin, ymin, zmin], [last_OM_id, xmax, ymax, zmax]]
    :return: ndarray(ndim=1) x_bin_edges, y_bin_edges, z_bin_edges: contains the resulting bin edges for each dimension.
    """
    x_bin_edges = np.linspace(geo_limits[0][1] -9.95, geo_limits[1][1]+9.95, num=n_bins[0] + 1) #try to get the lines in the bin center 9.95*2 = average x-separation of two lines
    y_bin_edges = np.linspace(geo_limits[0][2], geo_limits[1][2], num=n_bins[1] + 1) #+- 9.75
    z_bin_edges = np.linspace(geo_limits[0][3], geo_limits[1][3], num=n_bins[2] + 1)
    #TODO rethink bin centers due to new km3pipe geo
    return x_bin_edges, y_bin_edges, z_bin_edges


def main(n_bins, do2d=True, do2d_pdf=True, do3d=True, do_mc_hits=False):
    """
    Main code. Reads raw .hdf5 files and creates 2D/3D histogram projections that can be used for a CNN
    :param list n_bins: Declares the number of bins that should be used for each dimension (x,y,z,t).
    :param bool do2d: Declares if 2D histograms should be created.
    :param bool do2d_pdf: Declares if pdf visualizations of the 2D histograms should be created. Cannot be called if do2d=False.
    :param bool do3d: Declares if 3D histograms should be created.
    :param bool do_mc_hits: Declares if hits (False, mc_hits + BG) or mc_hits (True) should be processed
    """
    if len(sys.argv) < 2 or str(sys.argv[1]) == "-h":
        print "Usage: python " + str(sys.argv[0]) + " file.h5"
        sys.exit(1)

    if do2d==False and do2d_pdf==True:
        print 'The 2D pdf images cannot be created if do2d==False. Please try again.'
        sys.exit(1)

    if not os.path.isfile(str(sys.argv[1])):
        print 'The file -' + str(sys.argv[1]) + '- does not exist. Exiting.'
        sys.exit(1)

    filename_input = str(sys.argv[1])
    filename = os.path.basename(os.path.splitext(filename_input)[0])
    filename_output = filename.replace(".","_")
    filename_geometry = 'orca_115strings_av23min20mhorizontal_18OMs_alt9mvertical_v1.detx' # used for x/y/z calibration
    filename_geo_limits = 'ORCA_Geo_115lines.txt' # used for calculating the dimensions of the ORCA can #TODO not completely true anymore since single PMTs

    geo, geo_limits = get_geometry(filename_geometry, filename_geo_limits)

    x_bin_edges, y_bin_edges, z_bin_edges = calculate_bin_edges(n_bins, geo_limits)

    all_4d_to_2d_hists, all_4d_to_3d_hists = [], []
    mc_infos = []

    if do2d_pdf:
        glob.pdf_2d_plots = PdfPages('Results/4dTo2d/' + filename_output + '_plots.pdf')

    i=0
    # Initialize HDF5Pump of the input file
    event_pump = kp.io.hdf5.HDF5Pump(filename=filename_input)
    print "Generating histograms from the hits in XYZT format for files based on " + filename_input
    for event_blob in event_pump:
        if i % 10 == 0:
            print 'Event No. ' + str(i)
        i+=1
        # filter out all hit and track information belonging that to this event
        event_hits, event_track = get_event_data(event_blob, geo, do_mc_hits)

        # event_track: [event_id, particle_type, energy, isCC, bjorkeny, dir_x/y/z, time]
        mc_infos.append(event_track)

        if do2d:
            compute_4d_to_2d_histograms(event_hits, x_bin_edges, y_bin_edges, z_bin_edges, n_bins, all_4d_to_2d_hists, event_track, do2d_pdf)

        if do3d:
            compute_4d_to_3d_histograms(event_hits, x_bin_edges, y_bin_edges, z_bin_edges, n_bins, all_4d_to_3d_hists)

        #if i == 1:
           #  only for testing
         #   if do2d_pdf:
          #      glob.pdf_2d_plots.close()
         #   break
    #if do2d_pdf: # enabled if the if cause above (for testing) is commented out
     #   glob.pdf_2d_plots.close()

    if do2d:
        store_histograms_as_hdf5(np.stack([hist_tuple[0] for hist_tuple in all_4d_to_2d_hists]), np.array(mc_infos), 'Results/4dTo2d/h5/xy/' + filename_output + '_xy.h5')
        store_histograms_as_hdf5(np.stack([hist_tuple[1] for hist_tuple in all_4d_to_2d_hists]), np.array(mc_infos), 'Results/4dTo2d/h5/xz/' + filename_output + '_xz.h5')
        store_histograms_as_hdf5(np.stack([hist_tuple[2] for hist_tuple in all_4d_to_2d_hists]), np.array(mc_infos), 'Results/4dTo2d/h5/yz/' + filename_output + '_yz.h5')

    if do3d:
        store_histograms_as_hdf5(np.stack([hist_tuple[0] for hist_tuple in all_4d_to_3d_hists]), np.array(mc_infos), 'Results/4dTo3d/h5/xyz/' + filename_output + '_xyz.h5')
        store_histograms_as_hdf5(np.stack([hist_tuple[1] for hist_tuple in all_4d_to_3d_hists]), np.array(mc_infos), 'Results/4dTo3d/h5/xyt/' + filename_output + '_xyt.h5')
        store_histograms_as_hdf5(np.stack([hist_tuple[2] for hist_tuple in all_4d_to_3d_hists]), np.array(mc_infos), 'Results/4dTo3d/h5/xzt/' + filename_output + '_xzt.h5')
        store_histograms_as_hdf5(np.stack([hist_tuple[3] for hist_tuple in all_4d_to_3d_hists]), np.array(mc_infos), 'Results/4dTo3d/h5/yzt/' + filename_output + '_yzt.h5')
        store_histograms_as_hdf5(np.stack([hist_tuple[4] for hist_tuple in all_4d_to_3d_hists]), np.array(mc_infos), 'Results/4dTo3d/h5/rzt/' + filename_output + '_rzt.h5')


if __name__ == '__main__':
    main(n_bins=[11,13,18,50], do2d=False, do2d_pdf=False, do3d=True, do_mc_hits=False)







