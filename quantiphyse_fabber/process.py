"""
Quantiphyse: Process implementations for Fabber plugin

Copyright (c) 2016-2017 University of Oxford, Martin Craig
"""

import sys
import os
import re
import logging
import math

import numpy as np

from quantiphyse.data import DataGrid
from quantiphyse.processes import Process
from quantiphyse.utils import get_plugins, QpException

LOG = logging.getLogger(__name__)

def _make_fabber_progress_cb(worker_id, queue):
    """ 
    Closure which can be used as a progress callback for the C API. Puts the 
    number of voxels processed onto the queue
    """
    def _progress_cb(voxel, nvoxels):
        percent = int(100*float(voxel)/nvoxels)
        if percent != _progress_cb.last_percent:
            _progress_cb.last_percent = percent
            queue.put((worker_id, voxel, nvoxels))

    _progress_cb.last_percent = 0
    return _progress_cb

def _run_fabber(worker_id, queue, options, main_data, roi, *add_data):
    """
    Function to run Fabber in a multiprocessing environment
    """
    from fabber import FabberRun
    try:
        indir = options.pop("indir")
        if indir:
            os.chdir(indir)

        if np.count_nonzero(roi) == 0:
            # Ignore runs with no voxel. Return placeholder object
            LOG.debug("No voxels")
            return worker_id, True, FabberRun({}, "")
    
        options["data"] = main_data
        options["mask"] = roi
        if len(add_data) % 2 != 0:
            raise Exception("Additional data has odd-numbered length %i - should be sequence of key then value" % len(add_data))
        n = 0
        while n < len(add_data):
            options[add_data[n]] = add_data[n+1]
            n += 2
            
        api = FabberProcess.api(options.pop("model-group", None))
        run = api.run(options, progress_cb=_make_fabber_progress_cb(worker_id, queue))
        return worker_id, True, run
    except:
        import traceback
        traceback.print_exc()
        return worker_id, False, sys.exc_info()[1]

class FabberProcess(Process):
    """
    Asynchronous background process to run Fabber

    Note the static methods - these are so they can be called by other plugins which
    can obtain a reference to the FabberProcess class only 
    """

    PROCESS_NAME = "Fabber"

    def __init__(self, ivm, **kwargs):
        Process.__init__(self, ivm, worker_fn=_run_fabber, **kwargs)
        self.grid = None
        self.data_items = []
    
    @staticmethod
    def get_model_group_name(lib):
        """ Get the model group name from a library name"""
        match = re.match(r".*fabber_models_(.+)\..+", lib, re.I)
        if match:
            return match.group(1).lower()
        else:
            return lib.lower()

    @staticmethod
    def api(model_group=None):
        """
        Return a Fabber API object
        """
        from fabber import Fabber
        search_dirs = get_plugins(key="fabber-dirs")
        return Fabber(*search_dirs)

    def run(self, options):
        """
        Run the Fabber process

        FIXME need to be able to pass matrix options as actual matrices
        """
        # Take a copy of the options dict and then clean it out to avoid
        # warnings in batch mode. Fabber logfile will warn about unusued
        # options itself
        new_options = options.copy()
        for key in list(options.keys()):
            options.pop(key)
        options = new_options
        
        data = self.get_data(options, multi=True)
        self.grid = data.grid
        roi = self.get_roi(options, self.grid)

        self.output_rename = options.pop("output-rename", {})

        # Set some defaults
        options["method"] = options.get("method", "vb")
        options["noise"] = options.get("noise", "white")

        # None is returned for blank YAML options - treat this as 'option set'
        for key in options.keys():
            if options[key] is None:
                options[key] = True

        # Pass our input directory - this is used as the working directory so file names
        # can be passed relative to it
        options["indir"] = self.indir

        # Use smallest sub-array of the data which contains all unmasked voxels
        self.bb_slices = roi.get_bounding_box()
        data_bb = data.raw()[self.bb_slices]
        mask_bb = roi.raw()[self.bb_slices]

        # Pass in input data. To enable the multiprocessing module to split our volumes
        # up automatically we have to pass the arguments as a single list. This consists of
        # options, main data, roi and then each of the used additional data items, name followed by data
        input_args = [options, data_bb, mask_bb]

        # Determine which of the options should be treated as data sets and add them to the input args
        api = self.api(options.get("model-group", None))
        known_options = api.get_options(generic=True, model=options.get("model", None), method=options.get("method", None))[0]
        for key in list(options.keys()):
            if api.is_data_option(key, known_options):
                data_option = self.ivm.data.get(options[key], None)
                if data_option is not None:
                    extra_data = data_option.resample(data.grid).raw()[self.bb_slices]
                    input_args.append(key)
                    input_args.append(extra_data)
                    options.pop(key)
                else:
                    raise QpException("Fabber option '%s' expected data item but data set '%s' not found" % (key, options[key]))
    
        if options["method"] == "spatialvb":
            # Spatial VB will not work properly in parallel
            n_workers = 1
        else:
            # Run one worker for each slice
            n_workers = data_bb.shape[0]

        self.voxels_todo = np.count_nonzero(mask_bb)
        self.voxels_done = [0, ] * n_workers
        self.start_bg(input_args, n_workers=n_workers)

    def timeout(self, queue):
        """
        Check the queue and emit sig_progress
        """
        if queue.empty(): return
        while not queue.empty():
            worker_id, done, todo = queue.get()
            if worker_id < len(self.voxels_done):
                self.voxels_done[worker_id] = float(done) / todo
            else:
                self.warn("Fabber: Id=%i in timeout (max %i)" % (worker_id, len(self.voxels_done)))
        complete = sum(self.voxels_done) / len(self.voxels_done)
        self.sig_progress.emit(complete)

    def finished(self, worker_output):
        """ 
        Add output data to the IVM and set the log 
        """
        if self.status == Process.SUCCEEDED:
            # Only include log from first process to avoid multiple repetitions
            for out in worker_output:
                if out and  hasattr(out, "log") and len(out.log) > 0:
                    self.log(out.log)
                    break
            first = True
            data_keys = []
            self.data_items = []
            for out in worker_output:
                if out.data: data_keys = out.data.keys()
            for key in data_keys:
                self.debug(key)
                recombined_data = self.recombine_data([o.data.get(key, None) for o in worker_output])
                name = self.output_rename.get(key, key)
                if key is not None:
                    self.data_items.append(name)
                    if recombined_data.ndim == 4:
                        full_data = np.zeros(list(self.grid.shape) + [recombined_data.shape[3],])
                    else:
                        full_data = np.zeros(self.grid.shape)
                    full_data[self.bb_slices] = recombined_data
                    self.ivm.add(full_data, grid=self.grid, name=name, make_current=first)
                    first = False
        else:
            # Include the log of the first failed process
            for out in worker_output:
                if out and isinstance(out, Exception) and hasattr(out, "log") and len(out.log) > 0:
                    self.log(out.log)
                    break

    def output_data_items(self):
        """ :return: List of names of data items Fabber is expecting to produce """
        return self.data_items

class FabberTestDataProcess(Process):
    """
    Process which generates test data by evaluating a Fabber model on specified parameter values
    with optional noise
    """

    PROCESS_NAME = "FabberTestData"

    def __init__(self, ivm, **kwargs):
        Process.__init__(self, ivm, **kwargs)

    def run(self, options):
        """ Generate test data from Fabber model """
        kwargs = {
            "patchsize" : int(math.floor(options.pop("num-voxels", 1000) ** (1. / 3) + 0.5)),
            "nt" : options.pop("num-vols", 10),
            "noise" : options.pop("noise", 0),
            "param_rois" : options.pop("save-rois", False),
        }
        param_test_values = options.pop("param-test-values", None)
        output_name = options.pop("output-name", "fabber_test_data")
        grid_data_name = options.pop("grid", None)

        if not param_test_values:
            raise QpException("No test values given for model parameters")

        api = FabberProcess.api(options.pop("model-group", None))
        from fabber import generate_test_data
        test_data = generate_test_data(api, options, param_test_values, **kwargs)
        
        data = test_data["data"]
        self.debug("Data shape: %s", data.shape)

        if grid_data_name is None:
            grid = DataGrid(data.shape[:3], np.identity(4))
        else:
            grid_data = self.ivm.data.get(grid_data_name, None)
            if grid_data is None:
                raise QpException("Data not found for output grid: %s" % grid_data_name)
            grid = grid_data.grid

        self.ivm.add(data, name=output_name, grid=grid, make_current=True)

        clean_data = test_data.get("clean", None)
        if clean_data is not None:
            self.ivm.add(clean_data, name="%s_clean" % output_name, grid=grid, make_current=False)

        for param, param_roi in test_data.get("param-rois", {}).items():
            self.ivm.add(param_roi, name="%s_roi_%s" % (output_name, param), grid=grid)
