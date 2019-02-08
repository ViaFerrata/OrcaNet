#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Scripts for making specific models.
"""

import keras as ks
import toml

from orcanet.model_archs.short_cnn_models import create_vgg_like_model_multi_input_from_single_nns, create_vgg_like_model
from orcanet.model_archs.wide_resnet import create_wide_residual_network
from orcanet.utilities.losses import get_all_loss_functions
from orcanet_contrib.contrib import orca_label_modifiers, orca_sample_modifiers


class OrcaModel:
    """
    Class for building models.

    Attributes
    ----------
    compile_opt : dict
        Dict of loss functions and optionally weights & metrics that should be used for each nn output.
        Format: { layer_name : { loss_function:, weight:, metrics: } }
        The loss_function is a string or a function, the weight is a float and metrics is a list of functions/strings.
        Typically read in from a .toml file.
    optimizer : str
        Specifies, if "Adam" or "SGD" should be used as optimizer.

    """

    def __init__(self, model_file):
        """
        Read out parameters for creating models with OrcaNet from a toml file.

        Parameters
        ----------
        model_file : str
            Path to the model toml file.

        """
        file_content = toml.load(model_file)['model']

        self.nn_arch = file_content.pop('nn_arch')
        self.compile_opt = file_content.pop('compile_opt')
        self.class_type = ''
        self.str_ident = ''
        self.swap_4d_channels = None
        self.optimizer = "adam"
        self.custom_objects = get_all_loss_functions()

        if 'class_type' in file_content:
            self.class_type = file_content.pop('class_type')
        if 'str_ident' in file_content:
            self.str_ident = file_content.pop('str_ident')
        if 'swap_4d_channels' in file_content:
            self.swap_4d_channels = file_content.pop('swap_4d_channels')

        self.kwargs = file_content

    def build(self, orca, parallelized=False):
        """
        Function that builds a Keras nn model with a specific type of architecture.

        Will adapt to the data given in the orca object, and load in the necessary modifiers.
        Can also parallelize to multiple GPUs.

        Parameters
        ----------
        orca : Object OrcaHandler
            Contains all the configurable options in the OrcaNet scripts.
        parallelized : bool
            If true, will parallelize the model to the n_gpus given in the cfg.

        Returns
        -------
        model : ks.models.Model
            A Keras nn instance.

        """
        n_bins = orca.io.get_n_bins()
        n_gpu = orca.cfg.n_gpu
        batchsize = orca.cfg.batchsize

        if self.nn_arch == 'WRN':
            model = create_wide_residual_network(n_bins[0], n=1, k=1, dropout=0.2, k_size=3, swap_4d_channels=self.swap_4d_channels)

        elif self.nn_arch == 'VGG':
            if 'multi_input_single_train' in self.str_ident:
                dropout = (0, 0.1)
                model = create_vgg_like_model_multi_input_from_single_nns(n_bins, self.str_ident,
                                                                          dropout=dropout, swap_4d_channels=self.swap_4d_channels)
            else:
                dropout = self.kwargs["dropout"]
                n_filters = self.kwargs["n_filters"]
                model = create_vgg_like_model(n_bins, self.class_type, dropout=dropout,
                                              n_filters=n_filters, swap_col=self.swap_4d_channels)  # 2 more layers
        else:
            raise ValueError('Currently, only "WRN" or "VGG" are available as nn_arch')

        if parallelized:
            model, orca.cfg.batchsize = parallelize_model_to_n_gpus(model, n_gpu, batchsize)
        self._compile_model(model)

        return model

    def update_orca(self, orca):
        """ Update the orca object for using the model.
        """
        assert orca.cfg.sample_modifier is None, "Can not set sample modifier: " \
                                                 "Has already been set: {}".format(orca.cfg.sample_modifier)
        assert orca.cfg.label_modifier is None, "Can not set label modifier: " \
                                                "Has already been set: {}".format(orca.cfg.label_modifier)
        assert orca.cfg.custom_objects is None, "Can not set custom objects: " \
                                                "Have already been set: {}".format(orca.cfg.custom_objects)

        if self.swap_4d_channels is not None:
            orca.cfg.sample_modifier = orca_sample_modifiers(self.swap_4d_channels, self.str_ident)
        orca.cfg.label_modifier = orca_label_modifiers(self.class_type)
        orca.cfg.custom_objects = self.custom_objects

    def _compile_model(self, model):
        """
        Compile a model with the loss optimizer settings given in the model toml file.

        Returns
        -------
        model : ks.model
            A compile keras model.

        """
        if self.optimizer == 'adam':
            optimizer = ks.optimizers.Adam(beta_1=0.9, beta_2=0.999, epsilon=0.1,
                                           decay=0.0)  # epsilon=1 for deep networks
        elif self.optimizer == 'sgd':
            optimizer = ks.optimizers.SGD(momentum=0.9, decay=0, nesterov=True)
        else:
            raise NameError('Unknown optimizer name ({})'.format(self.optimizer))

        loss_functions, loss_weights, loss_metrics = {}, {}, {}
        for layer_name, layer_info in self.compile_opt.items():
            # Replace the str function name with the actual function if it is custom
            loss_function = layer_info['function']
            if loss_function in self.custom_objects:
                loss_function = self.custom_objects[loss_function]
            loss_functions[layer_name] = loss_function

            # Use given weight, else use default weight of 1
            if 'weight' in layer_info:
                weight = layer_info['weight']
            else:
                weight = 1.0
            loss_weights[layer_name] = weight

            # Use given metrics, else use no metrics
            if 'metrics' in layer_info:
                metrics = layer_info['metrics']
            else:
                metrics = []
            loss_metrics[layer_name] = metrics

        model.compile(loss=loss_functions, optimizer=optimizer, metrics=loss_metrics, loss_weights=loss_weights)
        return model


def parallelize_model_to_n_gpus(model, n_gpu, batchsize):
    """
    Parallelizes the nn-model to multiple gpu's.

    Currently, up to 4 GPU's at Tiny-GPU are supported.

    Parameters
    ----------
    model : ks.model.Model
        Keras model of a neural network.
    n_gpu : tuple(int, str)
        Number of gpu's that the model should be parallelized to [0] and the multi-gpu mode (e.g. 'avolkov') [1].
    batchsize : int
        Batchsize that is used for the training / inferencing of the cnn.

    Returns
    -------
    model : ks.models.Model
        The parallelized Keras nn instance (multi_gpu_model).
    batchsize : int
        The new batchsize scaled by the number of used gpu's.

    """
    if n_gpu[1] == 'avolkov':
        if n_gpu[0] == 1:
            return model, batchsize
        else:
            assert n_gpu[0] > 1 and isinstance(n_gpu[0],
                                               int), 'You probably made a typo: n_gpu must be an int with n_gpu >= 1!'

            from utilities.multi_gpu.multi_gpu import get_available_gpus, make_parallel, print_mgpu_modelsummary

            gpus_list = get_available_gpus(n_gpu[0])
            ngpus = len(gpus_list)
            print('Using GPUs: {}'.format(', '.join(gpus_list)))
            batchsize = batchsize * ngpus

            # Data-Parallelize the model via function
            model = make_parallel(model, gpus_list, usenccl=False, initsync=True, syncopt=False, enqueue=False)
            print_mgpu_modelsummary(model)

            return model, batchsize

    else:
        raise ValueError('Currently, no multi_gpu mode other than "avolkov" is available.')
