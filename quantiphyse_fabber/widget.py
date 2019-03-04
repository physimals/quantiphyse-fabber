"""
Quantiphyse: Widgets for Fabber plugin

Author: Martin Craig <martin.craig@eng.ox.ac.uk>
Copyright (c) 2016-2017 University of Oxford, Martin Craig
"""

from __future__ import division, unicode_literals, absolute_import, print_function

import numpy as np

from PySide import QtGui

from quantiphyse.gui.options import OptionBox, DataOption, ChoiceOption, VectorOption, NumberListOption, NumericOption, OutputNameOption, BoolOption
from quantiphyse.gui.widgets import QpWidget, Citation, TitleWidget, RunBox, WarningBox
from quantiphyse.utils import QpException

from .process import FabberProcess, FabberTestDataProcess
from .dialogs import OptionsDialog, PriorsDialog
from ._version import __version__

FAB_CITE_TITLE = "Variational Bayesian inference for a non-linear forward model"
FAB_CITE_AUTHOR = "Chappell MA, Groves AR, Whitcher B, Woolrich MW."
FAB_CITE_JOURNAL = "IEEE Transactions on Signal Processing 57(1):223-236, 2009."

class FabberWidget(QpWidget):
    """
    Widget for running Fabber model fitting
    """
    def __init__(self, **kwargs):
        QpWidget.__init__(self, **kwargs)
        self._fabber_options = {
            "degree" : 2,
            "noise" : "white",
            "save-mean" : True,
            "save-model-fit" : True,
            "save-model-extras" : True,
        }
        self._fabber_params = []

    def init_ui(self):
        self.vbox = QtGui.QVBoxLayout()
        self.setLayout(self.vbox)

        title = TitleWidget(self, subtitle="Plugin %s" % __version__, help="fabber")
        self.vbox.addWidget(title)
        
        cite = Citation(FAB_CITE_TITLE, FAB_CITE_AUTHOR, FAB_CITE_JOURNAL)
        self.vbox.addWidget(cite)

        self.options = OptionBox("Options")
        self.options.sig_changed.connect(self._options_changed)
        self.vbox.addWidget(self.options)

        self.warn_box = WarningBox("")
        self.warn_box.setVisible(False)
        self.vbox.addWidget(self.warn_box)

    def _model_group_changed(self):
        models = FabberProcess.api().get_models(model_group=self._fabber_options.get("model-group", None))
        self.debug("Models: %s", models)
        self.options.option("model").setChoices(models)
      
    def _options_changed(self):
        self._fabber_options.update(self.options.values())
        if self._fabber_options.get("model-group", None) == "ALL":
           self._fabber_options["model-group"] = None

        self.debug("Options changed:\n%s", self._fabber_options)
        self._update_params()

    def _fix_data_params(self, api):
        """
        Given a set of Fabber options, replace those that should be data items with a Numpy array
        """
        options = dict(self._fabber_options)
        known_options = api.get_options(generic=True, model=options.get("model", None), method=options.get("method", None))[0]
        for key in options:
            if api.is_data_option(key, known_options):
                # Just provide a placeholder
                options[key] = np.zeros((1, 1, 1))
        return options

    def _update_params(self):
        from fabber import FabberException
        try:
            api = FabberProcess.api()
            options = self._fix_data_params(api)
            self._fabber_params = api.get_model_params(options)
            self.warn_box.setVisible(False)
        except FabberException as exc:
            self._fabber_params = []
            self.warn_box.text.setText("Invalid model options:\n\n%s" % str(exc))
            self.warn_box.setVisible(True)

    def _show_model_options(self):
        model = self._fabber_options["model"]
        dlg = OptionsDialog(self, ivm=self.ivm, rundata=self._fabber_options, desc_first=True)
        opts, desc = FabberProcess.api().get_options(model=model)
        self.debug("Model options: %s", opts)
        dlg.set_title("Forward Model: %s" % model, desc)
        dlg.set_options(opts)
        dlg.exec_()
        self._update_params()

    def _show_method_options(self):
        method = self._fabber_options["method"]
        dlg = OptionsDialog(self, ivm=self.ivm, rundata=self._fabber_options, desc_first=True)
        opts, desc = FabberProcess.api().get_options(method=method)
        # Ignore prior options which have their own dialog
        opts = [o for o in opts if "PSP_byname" not in o["name"] and o["name"] != "param-spatial-priors"]
        dlg.set_title("Inference method: %s" % method, desc)
        self.debug("Method options: %s", opts)
        dlg.set_options(opts)
        dlg.fit_width()
        dlg.exec_()
        
    def _show_general_options(self):
        dlg = OptionsDialog(self, ivm=self.ivm, rundata=self._fabber_options, desc_first=True)
        dlg.ignore("model", "method", "output", "data", "mask", "data<n>", "overwrite", "help",
                   "listmodels", "listmethods", "link-to-latest", "data-order", "dump-param-names",
                   "loadmodels")
        opts, _ = FabberProcess.api().get_options()
        dlg.set_options(opts)
        dlg.fit_width()
        dlg.exec_()
        
    def _show_prior_options(self):
        dlg = PriorsDialog(self, ivm=self.ivm, rundata=self._fabber_options)
        try:
            api = FabberProcess.api()
            options = self._fix_data_params(api)
            params = api.get_model_params(options)
        except Exception as exc:
            raise QpException("Unable to get list of model parameters\n\n%s\n\nModel options must be set before parameters can be listed" % str(exc))
        dlg.set_params(params)
        dlg.fit_width()
        dlg.exec_()

    def get_options(self):
        """ Return a copy of current Fabber options """
        return dict(self._fabber_options)

    def get_process(self):
        return FabberProcess(self.ivm)

    def batch_options(self):
        return "Fabber", self.get_options()
   
class FabberModellingWidget(FabberWidget):
    """
    Widget for running Fabber model fitting
    """

    def __init__(self, **kwargs):
        super(FabberModellingWidget, self).__init__(name="Fabber", icon="fabber", group="Fabber",
                                                    desc="Fabber Bayesian model fitting", **kwargs)

    def init_ui(self):
        FabberWidget.init_ui(self)

        self.run_box = RunBox(self.get_process, self.get_options, title="Run Fabber", save_option=True)
        self.vbox.addWidget(self.run_box)
        self.vbox.addStretch(1)

        model_opts_btn = QtGui.QPushButton('Model Options')
        method_opts_btn = QtGui.QPushButton('Method Options')
        edit_priors_btn = QtGui.QPushButton('Edit Priors')
        options_btn = QtGui.QPushButton('Edit')

        self.options.add("Main input data", DataOption(self.ivm), key="data")
        self.options.add("Model group", ChoiceOption(), key="model-group")
        self.options.add("Model", ChoiceOption(), model_opts_btn, key="model")
        self.options.add("Parameter priors", edit_priors_btn)
        self.options.add("Inference method", ChoiceOption(), method_opts_btn, key="method")
        self.options.add("General options", options_btn)

        self.options.option("model-group").sig_changed.connect(self._model_group_changed)
        method_opts_btn.clicked.connect(self._show_method_options)
        model_opts_btn.clicked.connect(self._show_model_options)
        edit_priors_btn.clicked.connect(self._show_prior_options)
        options_btn.clicked.connect(self._show_general_options)
        
        model_groups = ["ALL"]
        for group in FabberProcess.api().get_model_groups():
            model_groups.append(group.upper())
        self.options.option("model-group").setChoices(model_groups)
        self.options.option("model-group").value = "ALL"
        self._model_group_changed()

        self.options.option("model").value = "poly"
        self.options.option("method").setChoices(FabberProcess.api().get_methods())
        self.options.option("method").value = "vb"
        self._options_changed()

class SimData(FabberWidget):
    """
    Widget which uses Fabber models to generate simulated data
    """
    def __init__(self, **kwargs):
        super(SimData, self).__init__(name="Simulated Fabber Data", icon="fabber", 
                                      desc="Generate test data sets from Fabber models", 
                                      group="Simulation", **kwargs)
        self._param_test_values = {}

    def init_ui(self):
        FabberWidget.init_ui(self)
        
        self.param_values_box = OptionBox("Parameter values")
        self.param_values_box.sig_changed.connect(self._param_values_changed)
        self.vbox.addWidget(self.param_values_box)

        run_btn = QtGui.QPushButton('Generate test data', self)
        run_btn.clicked.connect(self._run)
        self.vbox.addWidget(run_btn)
        
        self.vbox.addStretch(1)

        model_opts_btn = QtGui.QPushButton('Model Options')
        model_opts_btn.clicked.connect(self._show_model_options)

        self.options.add("Model group", ChoiceOption(), key="model-group")
        self.options.add("Model", ChoiceOption(), model_opts_btn, key="model")
        self.options.add("Number of volumes (time points)", NumericOption(intonly=True, minval=1, maxval=100, default=10), key="num-vols")
        self.options.add("Voxels per patch (approx)", NumericOption(intonly=True, minval=1, maxval=10000, default=1000), key="num-voxels")
        self.options.add("Noise (Gaussian std.dev)", NumericOption(intonly=True, minval=0, maxval=1000, default=0), key="noise")
        self.options.add("Output data name", OutputNameOption(initial="fabber_test_data"), key="output-name")
        self.options.add("Output noise-free data", BoolOption(), key="save-clean")
        self.options.add("Output parameter ROIs", BoolOption(), key="save-rois")
        self.options.option("model-group").sig_changed.connect(self._model_group_changed)

        model_groups = ["ALL"]
        for group in FabberProcess.api().get_model_groups():
            model_groups.append(group.upper())
        self.options.option("model-group").setChoices(model_groups)
        self.options.option("model-group").value = "ALL"
        self._model_group_changed()

        self.options.option("model").value = "poly"
        self._options_changed()

        # Start with something sensible for the polynomial model
        self._param_test_values = {"c0" : [-100, 0, 100], "c1" : [-10, 0, 10], "c2" : [-1, 0, 1]}
        self._update_params()
 
    def _update_params(self):
        FabberWidget._update_params(self)
        self.param_values_box.clear()
        for param in self._fabber_params:
            current_values = self._param_test_values.get(param, [1.0])
            self.param_values_box.add(param, NumberListOption(initial=current_values))
            self._param_test_values[param] = current_values

        # Remove references to parameters which no longer exist
        for param in list(self._param_test_values.keys()):
            if param not in self._fabber_params:
                del self._param_test_values[param]

    def _param_values_changed(self):
        self._param_test_values = self.param_values_box.values()
        num_variable = len([1 for v in self._param_test_values.values() if len(v) > 1])
        if num_variable > 3:
            self.warn("Cannot have more than 3 varying parameters")
        
    def get_options(self):
        """ Return a copy of current Fabber options and parameter test values """
        options = dict(self._fabber_options)
        options["param-test-values"] = self._param_test_values
        return options
        
    def _run(self):
        process = self.get_process()
        options = self.get_options()
        process.run(options)
        
    def get_process(self):
        return FabberTestDataProcess(self.ivm)
  
    def batch_options(self):
        return "FabberTestData", self.get_options()
