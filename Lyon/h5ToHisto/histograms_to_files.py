#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""This utility code contains functions that save the histograms (generated by hits_to_histograms) to .h5 files"""

import h5py

def store_histograms_as_hdf5(hists, tracks, filepath_output, projection='None'):
    """
    Takes numpy histograms ('images') for a certain projection as well as the mc_info ('tracks') and saves them to a h5 file. 
    :param ndarray(ndim=2) hists: array that contains all histograms for a certain projection.
    :param ndarray(ndim=2) tracks: 2D array containing important MC information for each event_id. [event_id, particle_type, energy, isCC]
    :param str filepath_output: complete filepath of the created h5 file.
    :param str projection: specifies the projection type in order to get a named label for the created histogram dataset.
    """
    h5f = h5py.File(filepath_output, 'w')
    dset_tracks = h5f.create_dataset('tracks', data=tracks)
    dset_hists = h5f.create_dataset(projection, data=hists, dtype='uint8')

    h5f.close()


# def store_2d_histograms_as_hdf5(hists, tracks, filepath_output, projection='None'):
#
#     h5f = h5py.File(filepath_output, 'w')
#     dset_tracks = h5f.create_dataset('tracks', data=tracks)
#     dset_hists = h5f.create_dataset(projection, data=hists, dtype='uint8')
#
#     h5f.close()
#
#
# def store_3d_histograms_as_hdf5(hists, tracks, filename_output, projection='None'):
#     """
#     Takes the 3D np histograms ('images') as well as the mc_info ('tracks') and saves them to a h5 file.
#     :param list all_4d_to_3d_hists: contains all 3D np histograms (ndarrays(ndim=2))
#     :param ndarray(ndim=2) tracks: 2D array containing important MC information for each event_id. [event_id, particle_type, energy, isCC]
#     :param filename_output: placeholder filename till production
#     """
#
#     hists_3d_xyz = np.array(all_4d_to_3d_hists)[:, 0]
#
#     h5f = h5py.File('Results/4dTo3d/h5/' + filename_output + '_xyz.h5', 'w')
#     dset_tracks = h5f.create_dataset('tracks', data=tracks)
#     dset_xyz = h5f.create_dataset('xyz', data=hists_3d_xyz, dtype='uint8')
#
#     h5f.close()
