"""
Quantiphyse: Process implementations for Fabber plugin

Author: Martin Craig <martin.craig@eng.ox.ac.uk>
Copyright (c) 2016-2017 University of Oxford, Martin Craig
"""

import sys
import os
import re
import logging

import six
import numpy as np

from quantiphyse.processes import Process
from quantiphyse.utils import get_plugins, get_local_shlib, QpException

# The Fabber API is bundled with the plugin
from .fabber import Fabber, FabberRun

LOG = logging.getLogger(__name__)

def _make_fabber_progress_cb(worker_id, queue):
    """ 
    Closure which can be used as a progress callback for the C API. Puts the 
    number of voxels processed onto the queue
    """
    def _progress_cb(voxel, nvoxels):
        if (voxel % 100 == 0) or (voxel == nvoxels):
            queue.put((worker_id, voxel, nvoxels))
    return _progress_cb

def _run_fabber(worker_id, queue, options, main_data, roi, *add_data):
    """
    Function to run Fabber in a multiprocessing environment
    """
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
            raise Exception("Additional data has length %i - should be key then value" % len(add_data))
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
        core_lib = get_local_shlib("fabbercore_shared", __file__)
        model_libs = []
        if model_group:
            for lib in get_plugins(key="fabber-libs"):
                libname = os.path.basename(lib)
                if FabberProcess.get_model_group_name(libname) == model_group.lower():
                    model_libs.append(lib)

        return Fabber(core_lib=core_lib, model_libs=model_libs)

    def run(self, options):
        """
        Run the Fabber process
        """
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
                
        # Pass our input directory
        options["indir"] = self.indir

        # Use smallest sub-array of the data which contains all unmasked voxels
        self.bb_slices = roi.get_bounding_box()
        data_bb = data.raw()[self.bb_slices]
        mask_bb = roi.raw()[self.bb_slices]

        # Pass in input data. To enable the multiprocessing module to split our volumes
        # up automatically we have to pass the arguments as a single list. This consists of
        # options, main data, roi and then each of the used additional data items, name followed by data
        input_args = [options, data_bb, mask_bb]

        # This is not perfect - we just grab all data matching an option value
        for key in options.keys():
            value = options[key]
            if isinstance(value, six.string_types) and value in self.ivm.data:
                extra_data = self.ivm.data[value].resample(data.grid).raw()[self.bb_slices]
                input_args.append(key)
                input_args.append(extra_data)
                options.pop(key)
        
        if options["method"] == "spatialvb":
            # Spatial VB will not work properly in parallel
            n = 1
        else:
            # Run one worker for each slice
            n = data_bb.shape[0]

        self.debug(options)

        self.voxels_todo = np.count_nonzero(mask_bb)
        self.voxels_done = [0, ] * n
        self.start_bg(input_args, n_workers=n)

    def timeout(self):
        """
        Check the queue and emit sig_progress
        """
        if self.queue.empty(): return
        while not self.queue.empty():
            worker_id, voxels_done, _ = self.queue.get()
            if worker_id < len(self.voxels_done):
                self.voxels_done[worker_id] = voxels_done
            else:
                self.warn("Fabber: Id=%i in timeout (max %i)" % (worker_id, len(self.voxels_done)))
        voxels_done_total = sum(self.voxels_done)
        if self.voxels_todo > 0: complete = float(voxels_done_total)/self.voxels_todo
        else: complete = 1
        self.sig_progress.emit(complete)

    def finished(self):
        """ 
        Add output data to the IVM and set the log 
        """
        self.log = ""
        
        if self.status == Process.SUCCEEDED:
            # Only include log from first process to avoid multiple repetitions
            for out in self.worker_output:
                if out and  hasattr(out, "log") and len(out.log) > 0:
                    self.log = out.log
                    break
            first = True
            data_keys = []
            self.data_items = []
            for out in self.worker_output:
                if out.data: data_keys = out.data.keys()
            for key in data_keys:
                self.debug(key)
                recombined_data = self.recombine_data([o.data.get(key, None) for o in self.worker_output])
                name = self.output_rename.get(key, key)
                if key is not None:
                    self.data_items.append(name)
                    if recombined_data.ndim == 4:
                        full_data = np.zeros(list(self.grid.shape) + [recombined_data.shape[3],])
                    else:
                        full_data = np.zeros(self.grid.shape)
                    full_data[self.bb_slices] = recombined_data
                    self.ivm.add_data(full_data, grid=self.grid, name=name, make_current=first)
                    first = False
        else:
            # Include the log of the first failed process
            for out in self.worker_output:
                if out and isinstance(out, Exception) and hasattr(out, "log") and len(out.log) > 0:
                    self.log = out.log
                    break

    def output_data_items(self):
        """ :return: List of names of data items Fabber is expecting to produce """
        return self.data_items
