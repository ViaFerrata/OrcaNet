"""
Scripts for writing the logfiles.
"""

import numpy as np
import os
import keras as ks
from datetime import datetime
from shutil import move


class SummaryLogger:
    """
    For writing the summary logfile made during training.
    """
    def __init__(self, orga, model):
        """
        Init with the training files in orga, and metrics in the model.

        Parameters
        ----------
        orga : object Organizer
            Contains all the configurable options in the OrcaNet scripts.
        model : ks.model.Model or None
            Keras model containing the metrics to plot.

        """
        # Minimum width of the cells in characters.
        self.minimum_cell_width = 9
        # Precision to which floats are rounded if they appear in data.
        self.float_precision = 4

        self.logfile_name = orga.cfg.output_folder + 'summary.txt'
        self.temp_filepath = orga.cfg.output_folder + "/.temp_summary.txt"
        self.orga = orga

        self.metric_names = model.metrics_names
        self.column_names = self._get_column_names()

    def write_line(self, epoch_float, lr, history_train=None, history_val=None):
        """
        Write a line to the summary.txt file in every trained model folder.

        Parameters
        ----------
        epoch_float : float
            The current epoch and fileno as a float.
        lr : float
            The current learning rate of the model.
        history_train : dict
            Dict containing the history of the training, averaged over files.
            Keys: Metric names, e.g. "loss", "accuracy", ...
            Values: Value of the metric during validation as a float.
        history_val : dict or None
            Dict of validation losses for all the metrics, averaged over
            all validation files.
            Keys: Metric names, e.g. "loss", "accuracy", ...
            Values: Value of the metric during validation as a float.

        """
        if history_val is None and history_train is None:
            raise ValueError(
                "Can not summary log when both train and val history are None")

        widths = self._init_writing()

        # Format the content: (Epoch, LR, train_1, val_1, ...)
        data = [epoch_float, lr]
        for i, metric_name in enumerate(self.metric_names):
            if history_train is None:
                data.append("nan")
            else:
                data.append(history_train[metric_name])
            if history_val is None:
                data.append("nan")
            else:
                data.append(history_val[metric_name])

        # if the epoch is already in the file, its line will get updated
        update_line = False
        summary_data = self.orga.history.get_summary_data()
        if len(summary_data) > 0:
            last_line = summary_data[-1]
            if last_line["Epoch"] == data[0]:
                # merge arrays but ignore LR
                data = merge_arrays(data, last_line, exclude=1)
                update_line = True

        line = self._gen_line_str(data, widths)
        self._save_line(line, update_line)

    def _get_column_names(self):
        column_names = ["Epoch", "LR", ]
        for i, metric_name in enumerate(self.metric_names):
            column_names.append("train_" + str(metric_name))
            column_names.append("val_" + str(metric_name))
        column_names = tuple(column_names)

        if os.path.isfile(self.logfile_name):
            # if summary exists already, check if model metrics match
            file_column_names = self.orga.history.get_column_names()
            if not set(column_names) == set(file_column_names):
                raise NameError(
                    "Can not log to summary: column names differ (from model: "
                    "{}, from summary file: {}".format(column_names,
                                                       file_column_names))
            column_names = file_column_names

        return column_names

    def _save_line(self, line, update=False):
        """ Write a line in the summary file. If update, overwrite the last line.
        """
        if not update:
            with open(self.logfile_name, 'a+') as logfile:
                logfile.write(line + "\n")

        else:
            # replace last line by rewriting whole summary file :-(
            with open(self.logfile_name, "r") as old_file:
                lines = old_file.readlines()
            lines[-1] = line + "\n"

            # make new summary file as a temp
            with open(self.temp_filepath, 'w') as temp_file:
                for i, old_line in enumerate(lines):
                    temp_file.write(old_line)

            # Remove original file
            os.remove(self.logfile_name)
            # Move new file
            move(self.temp_filepath, self.logfile_name)

    def _init_writing(self):
        """
        Get the widths of the columns, and write the head if the file is new.

        The widths have the length of the metric names, but at least the
        self.minimum_cell_width.

        Returns
        -------
        widths : list
            The width of every cell in characters.

        """
        headline, widths = self._gen_line_str(self.column_names)
        if not os.path.isfile(self.logfile_name) or \
                os.stat(self.logfile_name).st_size == 0:

            vline = ["-" * width for width in widths]
            vertical_line = self._gen_line_str(vline, widths, seperator="-+-")
            with open(self.logfile_name, 'a+') as logfile:
                logfile.write(headline + "\n")
                logfile.write(vertical_line + "\n")

        return widths

    def _gen_line_str(self, data, widths=None, seperator=" | "):
        """
        Generate a line in the proper format for the summary plot,
        consisting of multiple spaced and seperated cells.

        Parameters
        ----------
        data : tuple
            Strings or floats of what is in each cell. It must be in the
            same order and have the same length as the column names.
        widths : List or None
            Optional: The width of every cell. If None, will set it
            automatically, depending on the data.
            If widths is given, but what is given in data is wider than
            the width, the cell will expand without notice. Must have the
            same length as the column names.
        seperator : str
            String that seperates two adjacent cells.

        Returns
        -------
        line : str
            The line.
        new_widths : List
            Optional: If the input widths were None: The widths of the cells .

        """
        if widths is None:
            new_widths = []

        assert len(data) == len(self.column_names)

        line = ""
        for i, entry in enumerate(data):
            # no seperator before the first entry
            if i == 0:
                sep = ""
            else:
                sep = seperator

            # If entry is a number, round to given precision and make it a string
            if not isinstance(entry, str):
                entry = format(float(entry), "."+str(self.float_precision)+"g")

            if widths is None:
                cell_width = max(self.minimum_cell_width, len(entry))
                new_widths.append(cell_width)
            else:
                cell_width = widths[i]

            cell_cont = format(entry, "<"+str(cell_width))

            line += "{seperator}{entry}".format(seperator=sep, entry=cell_cont,)

        if widths is None:
            return line, new_widths
        else:
            return line


def merge_arrays(base, supp, exclude=None):
    """
    Fill nans in a list with values from another list.

    Parameters
    ----------
    base : List
    supp : List
    exclude : List or int
        Which indices to ignore.

    Returns
    -------
    np.array

    """
    try:
        iter(exclude)
    except TypeError:
        exclude = [exclude]

    for i in range(len(base)):
        if exclude is not None and i in exclude:
            continue

        if base[i] == supp[i]:
            continue

        elif base[i] == "nan" or np.isnan(base[i]):
            base[i] = supp[i]

        elif supp[i] == "nan" or np.isnan(supp[i]):
            continue

        else:
            raise ValueError(
                "Cannot merge arrays at index {}: Base {}, supplement {}"
                .format(i, base[i], supp[i]))
    return base


class BatchLogger(ks.callbacks.Callback):
    """
    Write logfiles during training.

    Averages the losses of the model over some number of batches,
    and then writes that in a line in the logfile.
    The Batch_float entry in the logfiles gives the absolute position
    of the batch in the epoch (i.e. taking all files into account).
    This class is intended to be used only for one epoch = one file.

    """
    def __init__(self, orga, epoch):
        """

        Parameters
        ----------
        orga : object Organizer
            Contains all the configurable options in the OrcaNet scripts.
        epoch : tuple
            Epoch and file number.

        """
        ks.callbacks.Callback.__init__(self)

        self.epoch_number = epoch[0]
        self.f_number = epoch[1]

        # settings (read from orga)
        self.display = orga.cfg.train_logger_display
        self.flush = orga.cfg.train_logger_flush
        self.logfile_name = '{}/log_epoch_{}_file_{}.txt'.format(
            orga.io.get_subfolder("train_log", create=True),
            self.epoch_number, self.f_number)
        self.batchsize = orga.cfg.batchsize
        self.file_sizes = np.array(orga.io.get_file_sizes("train"))

        # get the total no of batches over all files (not just the current one)
        # This is for calculating the batch_float number in the logs
        file_batches = np.ceil(self.file_sizes / self.batchsize)
        self.total_batches = np.sum(file_batches)
        # no of batches seen in previous files
        if self.f_number == 1:
            self.previous_batches = 0.
        elif self.f_number > 1:
            self.previous_batches = np.cumsum(file_batches)[self.f_number - 2]
        else:
            raise AssertionError("f_number not >= 1 ({})".format(self.f_number))

        self.seen = None
        self.lines = None
        self.cum_metrics = None
        self.file = None
        self._stored_metrics = False

    def on_epoch_begin(self, epoch, logs=None):
        # no of seen batches in this epoch
        self.seen = 0
        # list of stored lines, so that multiple can be written at once
        self.lines = []
        # store the various metrices to be able to average over multiple batches
        self.cum_metrics = {}
        for metric in self.model.metrics_names:
            self.cum_metrics[metric] = 0
        self.file = open(self.logfile_name, "w")
        self._write_head()

    def on_batch_end(self, batch, logs=None):
        # self.params:
        #   {'epochs': 1, 'steps': 50, 'verbose': 1, 'do_validation': False,
        #    'metrics': ['loss', 'dx_loss', 'dx_err_loss',
        #    'val_loss', 'val_dx_loss', 'val_dx_err_loss']}
        # logs:
        #   {'batch': 7, 'size': 5, 'loss': 2.06344,
        #    'dx_loss': 0.19809794, 'dx_err_loss': 0.08246058}
        logs = logs or {}

        self.seen += 1
        for metric in self.model.metrics_names:
            self.cum_metrics[metric] += logs.get(metric)
        if not self._stored_metrics:
            self._stored_metrics = True

        if self.seen % self.display == 0:
            self._write_line()

        if self.flush != -1 and self.display % self.flush == 0:
            self._flush_file()

    def on_epoch_end(self, batch, logs=None):
        # on epoch end here means that this is called after one fit_generator
        # loop in Keras is finished, so after one file in our case.
        if self._stored_metrics:
            self._write_line()
        self.file.close()

    def _write_line(self):
        """ Write a line with the metrics for current status and reset metrics.
        """
        # The fraction is shifted by self.display / 2., so that it is in
        # the middle of the samples
        batch_frctn = self.epoch_number - 1 + (
                self.previous_batches + self.seen
                - self.display / 2.) / self.total_batches

        line = '{0}\t{1}'.format(int(self.seen), batch_frctn)
        for metric in self.model.metrics_names:
            line += '\t' + str(self.cum_metrics[metric] / self.display)
            self.cum_metrics[metric] = 0
        line += "\n"
        self.file.write(line)
        self._stored_metrics = False

    def _flush_file(self):
        self.file.flush()
        os.fsync(self.file.fileno())

    def _write_head(self):
        """ write column names for all losses / metrics """
        line = 'Batch\tBatch_float'
        for i, metric in enumerate(self.model.metrics_names):
            line += "\t" + str(metric)
        line += "\n"
        self.file.write(line)


def log_start_training(orga):
    """
    Whenever the orga.train function is run, this logs all the input parameters
    in the full log file.

    Parameters
    ----------
    orga : object Organizer
        Contains all the configurable options in the OrcaNet scripts.

    """
    lines = []
    log = lines.append

    log('-'*60)
    time = datetime.now().strftime('%Y-%m-%d  %H:%M:%S')
    log('-'*19 + " {} ".format(time) + '-'*19)
    log("New training run started with the following configuration:\n")

    log("Output folder:\t" + orga.cfg.output_folder)
    log("List file path:\t" + orga.cfg.get_list_file() + "\n")

    log("Given trainfiles in the .list file:")
    for input_name, input_files in orga.cfg.get_files("train").items():
        log(" " + input_name + ":")
        [log("\t" + input_file) for input_file in input_files]

    log("\nGiven validation files in the .list file:")
    for input_name, input_files in orga.cfg.get_files("val").items():
        log(" " + input_name + ":")
        [log("\t" + input_file) for input_file in input_files]

    log("\nNon-default settings used:")
    for key, value in vars(orga.cfg).items():
        defaults = orga.cfg.get_defaults()
        if key == "output_folder" or key.startswith("_") \
                or value == defaults.get(key):
            continue
        log("   {}:\t{}".format(key, value))

    """
    log("\nDefault settings used:")
    for key, value in vars(orga.cfg).items():
        defaults = orga.cfg.get_defaults()
        if value == defaults.get(key):
            log("   {}:\t{}".format(key, value))
    """

    log("")
    orga.io.print_log(lines)


def log_start_validation(orga):
    """ Log filenames used for validation. """
    line = "Validation"
    orga.io.print_log(line)
    orga.io.print_log("-" * len(line))
    lines = ['Inputs and files:', ]
    for input_name, input_files in orga.io.get_local_files("val").items():
        line = "   " + input_name + ":\t"
        for i, input_file in enumerate(input_files):
            if i != 0:
                line += ", "
            line += os.path.basename(input_file)
        lines.append(line)
    orga.io.print_log(lines)


# class TensorBoardWrapper(ks.callbacks.TensorBoard):
#     """Up to now (05.10.17), Keras doesn't accept TensorBoard callbacks with validation data that is fed by a generator.
#      Supplying the validation data is needed for the histogram_freq > 1 argument in the TB callback.
#      Without a workaround, only scalar values (e.g. loss, accuracy) and the computational graph of the model can be saved.
#
#      This class acts as a Wrapper for the ks.callbacks.TensorBoard class in such a way,
#      that the whole validation data is put into a single array by using the generator.
#      Then, the single array is used in the validation steps. This workaround is experimental!"""
#     def __init__(self, batch_gen, nb_steps, **kwargs):
#         super(TensorBoardWrapper, self).__init__(**kwargs)
#         self.batch_gen = batch_gen # The generator.
#         self.nb_steps = nb_steps   # Number of times to call next() on the generator.
#
#     def on_epoch_end(self, epoch, logs):
#         # Fill in the `validation_data` property.
#         # After it's filled in, the regular on_epoch_end method has access to the validation_data.
#         imgs, tags = None, None
#         for s in range(self.nb_steps):
#             ib, tb = next(self.batch_gen)
#             if imgs is None and tags is None:
#                 imgs = np.zeros(((self.nb_steps * ib.shape[0],) + ib.shape[1:]), dtype=np.float32)
#                 tags = np.zeros(((self.nb_steps * tb.shape[0],) + tb.shape[1:]), dtype=np.uint8)
#             imgs[s * ib.shape[0]:(s + 1) * ib.shape[0]] = ib
#             tags[s * tb.shape[0]:(s + 1) * tb.shape[0]] = tb
#         self.validation_data = [imgs, tags, np.ones(imgs.shape[0]), 0.0]
#         return super(TensorBoardWrapper, self).on_epoch_end(epoch, logs)