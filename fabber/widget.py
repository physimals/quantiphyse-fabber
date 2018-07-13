"""
Quantiphyse: Widgets for Fabber plugin

Author: Martin Craig <martin.craig@eng.ox.ac.uk>
Copyright (c) 2016-2017 University of Oxford, Martin Craig
"""

from __future__ import division, unicode_literals, absolute_import, print_function

from PySide import QtGui

from quantiphyse.gui.widgets import QpWidget, Citation, TitleWidget, RunBox
from quantiphyse.utils import get_plugins, QpException

from .process import FabberProcess
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
        QpWidget.__init__(self, name="Fabber", icon="fabber", group="Fabber",
                          desc="Fabber Bayesian model fitting", **kwargs)

    def init_ui(self):
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        self.rundata = {}
        self.rundata["model"] = "poly"
        self.rundata["degree"] = "2"
        self.rundata["method"] = "vb"
        self.rundata["save-mean"] = ""
        self.rundata["save-model-fit"] = ""
        #self.rundata["save-model-extras"] = ""

        title = TitleWidget(self, title="Fabber Bayesian Model Fitting", subtitle="Plugin %s" % __version__, help="fabber")
        vbox.addWidget(title)
        
        cite = Citation(FAB_CITE_TITLE, FAB_CITE_AUTHOR, FAB_CITE_JOURNAL)
        vbox.addWidget(cite)

        # Options box
        opts_box = QtGui.QGroupBox()
        opts_box.setTitle('Options')
        opts_box.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.MinimumExpanding)
        grid = QtGui.QGridLayout()
        opts_box.setLayout(grid)

        grid.addWidget(QtGui.QLabel("Model group"), 0, 0)
        self.model_group_combo = QtGui.QComboBox(self)
        self.model_group_combo.addItem("GENERIC", "")
        for lib in get_plugins(key="fabber-libs"):
            self.model_group_combo.addItem(FabberProcess.get_model_group_name(lib).upper())
        self.model_group_combo.currentIndexChanged.connect(self._model_group_changed)
        self.model_group_combo.setCurrentIndex(0)
        grid.addWidget(self.model_group_combo, 0, 1)
        
        grid.addWidget(QtGui.QLabel("Model"), 1, 0)
        self.model_combo = QtGui.QComboBox(self)
        self.model_combo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.model_combo.currentIndexChanged.connect(self._model_changed)
        grid.addWidget(self.model_combo, 1, 1)
        self.model_opts_btn = QtGui.QPushButton('Model Options', self)
        self.model_opts_btn.clicked.connect(self._show_model_options)
        grid.addWidget(self.model_opts_btn, 1, 2)
        
        grid.addWidget(QtGui.QLabel("Inference method"), 4, 0)
        self.method_combo = QtGui.QComboBox(self)
        self.method_combo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        methods = self._api().get_methods()
        for method in methods:
            self.method_combo.addItem(method)
        self.method_combo.setCurrentIndex(self.method_combo.findText(self.rundata["method"]))
          
        self.method_combo.currentIndexChanged.connect(self._method_changed)
        grid.addWidget(self.method_combo, 4, 1)
        self.method_opts_btn = QtGui.QPushButton('Inference Options', self)
        self.method_opts_btn.clicked.connect(self._show_method_options)
        grid.addWidget(self.method_opts_btn, 4, 2)
        
        grid.addWidget(QtGui.QLabel("Parameter priors"), 5, 0)
        self.priors_btn = QtGui.QPushButton('Edit', self)
        self.priors_btn.clicked.connect(self._show_prior_options)
        grid.addWidget(self.priors_btn, 5, 2)
        
        grid.addWidget(QtGui.QLabel("General Options"), 6, 0)
        self.general_opts_btn = QtGui.QPushButton('Edit', self)
        self.general_opts_btn.clicked.connect(self._show_general_options)
        grid.addWidget(self.general_opts_btn, 6, 2)
        
        vbox.addWidget(opts_box)

        # Run box
        self.run_box = RunBox(self.get_process, self.get_options, title="Run Fabber", save_option=True)
        vbox.addWidget(self.run_box)

        vbox.addStretch(1)

        self._model_group_changed()
        self._method_changed()

    def _model_group_changed(self):
        idx = self.model_group_combo.currentIndex()
        if idx >= 0:
            self.rundata["model-group"] = self.model_group_combo.currentText()
        else:
            self.rundata.pop("model-group", None)

        # Update the list of models
        models = self._api().get_models()
        self.model_combo.blockSignals(True)
        try:
            self.model_combo.clear()
            for model in models:
                self.model_combo.addItem(model)
        finally:
            self.model_combo.blockSignals(False)
            if self.rundata.get("model", "") in models:
                self.model_combo.setCurrentIndex(self.model_combo.findText(self.rundata["model"]))
            else:
                self.model_combo.setCurrentIndex(0)
      
    def _model_changed(self):
        model = self.model_combo.currentText()
        self.rundata["model"] = model

    def _method_changed(self):
        method = self.method_combo.currentText()
        self.rundata["method"] = method

    def _show_model_options(self):
        model = self.rundata["model"]
        dlg = OptionsDialog(self, ivm=self.ivm, rundata=self.rundata, desc_first=True)
        opts, desc = self._api().get_options(model=model)
        dlg.set_title("Forward Model: %s" % model, desc)
        dlg.set_options(opts)
        if dlg.exec_():
            pass

    def _show_method_options(self):
        method = self.rundata["method"]
        dlg = OptionsDialog(self, ivm=self.ivm, rundata=self.rundata, desc_first=True)
        opts, desc = self._api().get_options(method=method)
        # Ignore prior options which have their own dialog
        opts = [o for o in opts if "PSP_byname" not in o["name"] and o["name"] != "param-spatial-priors"]
        dlg.set_title("Inference method: %s" % method, desc)
        dlg.set_options(opts)
        dlg.fit_width()
        dlg.exec_()
        
    def _show_general_options(self):
        dlg = OptionsDialog(self, ivm=self.ivm, rundata=self.rundata, desc_first=True)
        dlg.ignore("model", "method", "output", "data", "mask", "data<n>", "overwrite", "help",
                   "listmodels", "listmethods", "link-to-latest", "data-order", "dump-param-names",
                   "loadmodels")
        opts, _ = self._api().get_options()
        dlg.set_options(opts)
        dlg.fit_width()
        dlg.exec_()
        
    def _show_prior_options(self):
        dlg = PriorsDialog(self, ivm=self.ivm, rundata=self.rundata)
        try:
            params = self._api().get_model_params(self.rundata)
        except Exception, exc:
            raise QpException("Unable to get list of model parameters\n\n%s\n\nModel options must be set before parameters can be listed" % str(exc))
        dlg.set_params(params)
        dlg.fit_width()
        dlg.exec_()
        
    def _api(self):
        """
        :return: Fabber API object with the current model group selected
        """
        return FabberProcess.api(self.rundata.get("model-group", None))

    def get_process(self):
        process = FabberProcess(self.ivm)
        return process

    def get_options(self):
        # Must return a copy as process may modify
        return dict(self.rundata)

    def batch_options(self):
        return "Fabber", self.get_options()
