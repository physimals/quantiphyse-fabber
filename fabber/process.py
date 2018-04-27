import sys
import os
import warnings
import traceback
import re

import numpy as np

from quantiphyse.processes import Process
from quantiphyse.utils import debug, warn, get_plugins, get_local_shlib, QpException

# The Fabber API is bundled with the plugin under a different name
from .fabber_api import find_fabber, Fabber, FabberRun

def _make_fabber_progress_cb(id, queue):
    """ 
    Closure which can be used as a progress callback for the C API. Puts the 
    number of voxels processed onto the queue
    """
    def progress_cb(voxel, nvoxels):
        if (voxel % 100 == 0) or (voxel == nvoxels):
            queue.put((id, voxel, nvoxels))
    return progress_cb

def _run_fabber(id, queue, rundata, main_data, roi, *add_data):
    """
    Function to run Fabber in a multiprocessing environment
    """
    try:
        indir = rundata.pop("indir")
        if indir:
            os.chdir(indir)

        if np.count_nonzero(roi) == 0:
            # Ignore runs with no voxel. Return placeholder object
            debug("No voxels")
            return id, True, FabberRun({}, "")
    
        data = {"data" : main_data}
        n = 0
        if len(add_data) % 2 != 0:
            raise Exception("Additional data has length %i - should be key then value" % len(add_data))
        while n < len(add_data):
            data[add_data[n]] = add_data[n+1]
            n += 2
            
        api = Fabber(lib=FabberProcess.get_core_lib(), rundata=rundata, auto_load_models=False)
        run = api.run_with_data(rundata, data, roi, progress_cb=_make_fabber_progress_cb(id, queue))
        
        return id, True, run
    except:
        return id, False, sys.exc_info()[1]

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
    def get_core_lib():
        """ Get path to core shared library """
        return get_local_shlib("fabbercore_shared", __file__)
    
    @staticmethod
    def get_model_group_name(lib):
        """ Get the model group name from a library name"""
        match = re.match(".*fabber_models_(.+)\..+", lib, re.I)
        if match:
            return match.group(1).lower()
        else:
            return lib.lower()

    @staticmethod
    def get_model_group_lib(name):
        """ Get the model group library path from the model group name"""
        for lib in get_plugins(key="fabber-libs"):
            libname = os.path.basename(lib)
            if FabberProcess.get_model_group_name(libname) == name.lower():
                return lib
        return None

    @staticmethod
    def api(options={}):
        options = dict(options) # Don't modify
        return Fabber(lib=FabberProcess.get_core_lib(), rundata=FabberProcess.get_rundata(options), auto_load_models=False)
    
    @staticmethod
    def get_rundata(options={}):
        """ 
        Get rundata which is nearly a copy of options with a few changes 
        Note default argument is safe because never modified if empty
        """
        # FIXME rundata requires all arguments to be strings!
        rundata = {}
        for key in options.keys():
            value = options.pop(key)
            if value is not None: rundata[key] = str(value)
            else: rundata[key] = ""

        # Make sure we have minimal defaults to run
        if "model" not in rundata: 
            rundata["model"] = "poly"
            rundata["degree"] = 2
        rundata["method"] = rundata.get("method", "vb")
        rundata["noise"] = rundata.get("noise", "white")
    
        # Look up the actual library which provides a model group
        lib = FabberProcess.get_model_group_lib(rundata.pop("model-group", ""))
        if lib is not None:
            rundata["loadmodels"] = lib

        return rundata

    def run(self, options):
        data = self.get_data(options, multi=True)
        self.grid = data.grid
        roi = self.get_roi(options, self.grid)
        
        self.output_rename = options.pop("output-rename", {})
        rundata = self.get_rundata(options)

        # Pass our input directory
        rundata["indir"] = self.indir

        # Pass in input data. To enable the multiprocessing module to split our volumes
        # up automatically we have to pass the arguments as a single list. This consists of
        # rundata, main data, roi and then each of the used additional data items, name followed by data
        input_args = [rundata, data.raw(), roi.raw()]

        # This is not perfect - we just grab all data matching an option value
        for key, value in rundata.items():
            if value in self.ivm.data:
                input_args.append(value)
                input_args.append(self.ivm.data[value].resample(data.grid).raw())
        
        if rundata["method"] == "spatialvb":
            # Spatial VB will not work properly in parallel
            n = 1
        else:
            # Run one worker for each slice
            n = self.grid.shape[0]

        self.voxels_todo = np.count_nonzero(roi.raw())
        self.voxels_done = [0, ] * n
        self.start_bg(input_args, n_workers=n)

    def timeout(self):
        """
        Check the queue and emit sig_progress
        """
        if self.queue.empty(): return
        while not self.queue.empty():
            id, v, nv = self.queue.get()
            self.voxels_done[id] = v
        cv = sum(self.voxels_done)
        if self.voxels_todo > 0: complete = float(cv)/self.voxels_todo
        else: complete = 1
        self.sig_progress.emit(complete)

    def finished(self):
        """ 
        Add output data to the IVM and set the log 
        """
        self.log = ""
        
        if self.status == Process.SUCCEEDED:
            # Only include log from first process to avoid multiple repetitions
            for o in self.worker_output:
                if o is not None and  hasattr(o, "log") and len(o.log) > 0:
                    self.log = o.log
                    break
            first = True
            data_keys = []
            self.data_items = []
            for o in self.worker_output:
                if len(o.data) > 0: data_keys = o.data.keys()
            for key in data_keys:
                debug(key)
                recombined_item = self.recombine_data([o.data.get(key, None) for o in self.worker_output])
                debug("recombined")
                name = self.output_rename.get(key, key)
                self.data_items.append(name)
                self.ivm.add_data(recombined_item, grid=self.grid, name=name, make_current=first)
                first = False
        else:
            # Include the log of the first failed process
            for o in self.worker_output:
                if o is not None and isinstance(o, Exception) and hasattr(o, "log") and len(o.log) > 0:
                    self.log = o.log
                    break

    def output_data_items(self):
        return self.data_items
