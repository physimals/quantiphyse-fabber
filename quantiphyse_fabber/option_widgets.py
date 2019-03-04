"""
Widgets for controlling different types of Fabber options

Copyright (c) 2016-2018 University of Oxford, Martin Craig
"""

import os
import logging

from PySide import QtCore, QtGui

from quantiphyse.gui.widgets import OverlayCombo
from quantiphyse.gui.options import NumberListOption

LOG = logging.getLogger(__name__)

def get_label(text="", size=None, bold=False, italic=False):
    """
    :return: QtGui.QLabel with specified text and attributes
    """
    label = QtGui.QLabel(text)
    font = label.font()
    font.setBold(bold)
    font.setItalic(italic)
    label.setFont(font)
    if size: label.setStyleSheet("QLabel{ font: %ipx }" % size)
    return label

class OptionWidget(QtCore.QObject):
    """
    Widget which allows a Fabber option to be controlled
    """
    def __init__(self, opt, **kwargs):
        super(OptionWidget, self).__init__()
        self.key = opt["name"]
        self.dtype = opt["type"]
        self.req = not opt["optional"]
        self.default = opt["default"]
        self.desc = opt["description"]

        self.options = kwargs.get("options", {})
        self.ivm = kwargs.get("ivm", None)
        self.desc_first = kwargs.get("desc_first", False)
        self.dependents = []
        self.widgets = []

        # Basic label
        self.label = get_label(opt["name"])
        self.widgets.append(self.label)

        # Description label
        self.desclabel = get_label(opt["description"])
        self.desclabel.setToolTip("--%s" % self.key)
        self.desclabel.resize(400, self.desclabel.height())
        self.desclabel.setWordWrap(True)
        self.widgets.append(self.desclabel)

        # For non-mandatory options, provide a checkbox to enable them
        if self.req:
            self.enable_cb = None
            self.checked = True
        else:
            self.enable_cb = QtGui.QCheckBox()
            self.enable_cb.stateChanged.connect(self._checkbox_toggled)
            self.widgets.append(self.enable_cb)
            self.checked = False

    def update(self, options):
        """
        Update the displayed option value from an options dictionary
        """
        val = options.get(self.key, None)
        if val is not None:
            self.set_value(val)
            if self.enable_cb is not None:
                self.enable_cb.setChecked(True)
        else:
            self.set_value(self.default)
            if self.enable_cb is not None:
                self.enable_cb.setChecked(False)
        # Make sure visibility is updated even if state is unchanged
        if self.enable_cb is not None: 
            self._checkbox_toggled()

    def update_options(self):
        """
        Update the options dictionary from the current displayed value
        """
        if self.checked:
            self.options[self.key] = self.get_value()
        elif self.key in self.options:
            del self.options[self.key]
        LOG.debug(self.options)

    def set_value(self, value):
        """ Set the displayed option value """
        pass
    
    def get_value(self):
        """ Get the displayed option value """
        return ""

    def set_visible(self, visible=True):
        """ Set the visibility of the option widget """
        for widget in self.widgets:
            widget.setVisible(visible)

    def set_enabled(self, enabled=True):
        """ Set the enabled (greyed out) status of the option widget """
        for widget in self.widgets:
            widget.setEnabled(enabled)
        # Checkbox is always enabled!
        if self.enable_cb is not None: 
            self.enable_cb.setEnabled(True)

    def add(self, grid, row):
        """ 
        Add the option widget to a grid layout
        
        This base method adds the label/description and checkbox if required.
        Subclasses should call this method first and then add their own specific
        widget to column 1 of the grid

        :param grid: QtGui.QGridLayout 
        :param row: Row index number
        """
        if self.desc_first:
            label = self.desclabel
        else:
            label = self.label
            grid.addWidget(self.desclabel, row, 2)

        if self.req:
            grid.addWidget(label, row, 0)
        else:
            hbox = QtGui.QHBoxLayout()
            hbox.addWidget(self.enable_cb)
            hbox.addWidget(label, row)
            grid.addLayout(hbox, row, 0)

    def add_dependent(self, dep):
        """
        Add another OptionWidget as a dependent

        Dependent widgets are only visible when the parent widget is enabled/checked
        """
        if not self.enable_cb: return
        self.dependents.append(dep)
        dep.set_visible(self.checked)
        if not self.checked: dep.enable_cb.setChecked(False)

    def _checkbox_toggled(self):
        # This function is only called if we have a checkbox
        self.checked = self.enable_cb.checkState() == QtCore.Qt.CheckState.Checked
        self.set_enabled(self.checked)
        
        for dep in self.dependents:
            dep.set_visible(self.checked)
            if not self.checked: dep.enable_cb.setChecked(False)

        self.update_options()
        
class IntegerOptionWidget(OptionWidget):
    """
    Option which allows an integer to be chosen using a spin box
    """
    def __init__(self, opt, **kwargs):
        OptionWidget.__init__(self, opt, **kwargs)
        self.spin = QtGui.QSpinBox()
        self.spin.valueChanged.connect(self.update_options)
        self.widgets.append(self.spin)
    
    def get_value(self):
        return str(self.spin.value())
        
    def set_value(self, value):
        if value == "":
            try:
                self.spin.setValue(int(self.default))
            except ValueError:
                self.spin.setValue(0)
        else:
            self.spin.setValue(int(value))

    def add(self, grid, row):
        OptionWidget.add(self, grid, row)
        grid.addWidget(self.spin, row, 1)

class StringOptionWidget(OptionWidget):
    """
    OptionWidget allowing a text string to be entered
    """
    def __init__(self, opt, **kwargs):
        OptionWidget.__init__(self, opt, **kwargs)
        self.edit = QtGui.QLineEdit()
        self.edit.editingFinished.connect(self.update_options)
        self.widgets.append(self.edit)
            
    def get_value(self):
        return self.edit.text()
        
    def set_value(self, value):
        self.edit.setText(value)

    def add(self, grid, row):
        OptionWidget.add(self, grid, row)
        grid.addWidget(self.edit, row, 1)

class FileOptionWidget(StringOptionWidget):
    """
    OptionWidget allowing a file name to be chosen using a standard file selector
    """
    def __init__(self, opt, **kwargs):
        StringOptionWidget.__init__(self, opt, **kwargs)
        self.hbox = QtGui.QHBoxLayout()
        self.hbox.addWidget(self.edit)
        self.btn = QtGui.QPushButton("Choose")
        self.hbox.addWidget(self.btn)
        self.widgets.append(self.btn)
        self.btn.clicked.connect(self._choose_file)
    
    def _choose_file(self):
        dialog = QtGui.QFileDialog()
        dialog.setFileMode(QtGui.QFileDialog.AnyFile)
        if dialog.exec_():
            fname = dialog.selectedFiles()[0]
            self.edit.setText(fname)
            self.update_options()

    def add(self, grid, row):
        OptionWidget.add(self, grid, row)
        grid.addLayout(self.hbox, row, 1)

class VestParseError(Exception):
    """ Failure to parse a VEST matrix file """
    pass

class MatrixFileOptionWidget(FileOptionWidget):
    """
    Option which allows the user to choose a file containing a matrix
    """
    def __init__(self, opt, **kwargs):
        FileOptionWidget.__init__(self, opt, **kwargs)
        edit_btn = QtGui.QPushButton("Edit")
        self.hbox.addWidget(edit_btn)
        self.widgets.append(edit_btn)
        edit_btn.clicked.connect(self._edit_file)
    
    def _read_vest(self, fname):
        f = None
        in_matrix = False
        mat = []
        try:
            f = open(fname, "r")
            lines = f.readlines()
            nx, ny = 0, 0
            for line in lines:
                if in_matrix:
                    nums = [float(num) for num in line.split()]
                    if len(nums) != nx: raise VestParseError("Incorrect number of x values")
                    mat.append(nums)
                elif line.startswith("/Matrix"):
                    if nx == 0 or ny == 0: raise VestParseError("Missing /NumWaves or /NumPoints")
                    in_matrix = True
                elif line.startswith("/NumWaves"):
                    parts = line.split()
                    if len(parts) == 1: raise VestParseError("No number following /NumWaves")
                    nx = int(parts[1])
                elif line.startswith("/NumPoints") or line.startswith("/NumContrasts"):
                    parts = line.split()
                    if len(parts) == 1: raise VestParseError("No number following /NumPoints")
                    ny = int(parts[1])
            if len(mat) != ny:
                raise VestParseError("Incorrect number of y values")      
        finally:
            if f is not None: f.close()

        if not in_matrix: 
            raise VestParseError("File '%s' does not seem to contain a VEST matrix" % fname)
        else:
            return mat, ""

    def _read_ascii(self, fname):
        f = None
        in_matrix = False
        mat = []
        desc = ""
        try:
            f = open(fname, "r")
            lines = f.readlines()
            nx = 0
            for line in lines:
                if line.strip().startswith("#"):
                    desc += line.lstrip("#")
                else:
                    row = [float(n) for n in line.split()]
                    if not in_matrix:
                        nx = len(row)
                        in_matrix = True
                    elif len(row) != nx:
                        raise Exception("Incorrect number of x values: %s" % line)
                    mat.append(row)
        finally:
            if f is not None: f.close()

        return mat, desc

    def _write_vest(self, fname, matrix):
        f = None
        try:
            f = open(fname, "w")
            nx, ny = len(matrix), len(matrix[0])
            f.write("/NumWaves %i\n" % nx)
            f.write("/NumPoints %i\n" % ny)
            f.write("/Matrix\n")
            for row in matrix:
                for item in row:
                    f.write("%f " % item)
                f.write("\n")
        finally:
            if f is not None: f.close()

    def _write_ascii(self, fname, matrix, desc=""):
        f = None
        try:
            f = open(fname, "w")
            for line in desc.splitlines():
                f.write("#%s\n" % line)
            for row in matrix:
                f.write(" ".join([str(v) for v in row]))
                f.write("\n")
        finally:
            if f is not None: f.close()

    def _edit_file(self):
        fname = self.edit.text()
        if fname.strip() == "":
            msg_box = QtGui.QMessageBox()
            msg_box.setText("Enter a filename")
            msg_box.setStandardButtons(QtGui.QMessageBox.Ok)
            msg_box.exec_()
            return
        elif not os.path.exists(fname):
            msg_box = QtGui.QMessageBox()
            msg_box.setText("File does not exist - create?")
            msg_box.setStandardButtons(QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel)
            msg_box.setDefaultButton(QtGui.QMessageBox.Ok)
            ret = msg_box.exec_()
            if ret != QtGui.QMessageBox.Ok:
                return
            open(fname, "a").close()

        try:
            mat, desc = self._read_vest(fname)
            ascii = False
        except VestParseError:
            mat, desc = self._read_ascii(fname)
            ascii = True
        self.mat_dialog.set_matrix(mat, desc)
        if self.mat_dialog.exec_():
            mat, desc = self.mat_dialog.get_matrix()
            if ascii:
                self._write_ascii(fname, mat, desc)
            else:
                self._write_vest(fname, mat)

class ImageOptionWidget(OptionWidget):
    """
    OptionWidget subclass which allows image options to be chosen
    from the current list of overlays
    """
    def __init__(self, opt, **kwargs):
        OptionWidget.__init__(self, opt, **kwargs)
        self.combo = OverlayCombo(self.ivm, static_only=True)
        self.widgets.append(self.combo)

    def get_value(self):
        return self.combo.currentText()

    def set_value(self, value):
        idx = self.combo.findText(value)
        self.combo.setCurrentIndex(idx)

    def add(self, grid, row):
        OptionWidget.add(self, grid, row)
        grid.addWidget(self.combo, row, 1)

class ListOptionWidget(OptionWidget):
    """
    OptionWidget subclass for a list of values
    """
    def __init__(self, opt, **kwargs):
        OptionWidget.__init__(self, opt, **kwargs)
        self.edit = NumberListOption(intonly=opt["type"] == "INT")
        self.edit.sig_changed.connect(self.update_options)
        self.widgets.append(self.edit)

    def get_value(self):
        return self.edit.value
        
    def set_value(self, value):
        self.edit.value = value

    def add(self, grid, row):
        OptionWidget.add(self, grid, row)
        grid.addWidget(self.edit, row, 1)

    def update_options(self):
        """
        Update the options dictionary from the current displayed value
        """
        if self.checked:
            values = self.get_value()
            for idx, value in enumerate(values):
                key = self.key.replace("<n>", str(idx+1))
                self.options[key] = value
        else:
            idx = 1
            while 1:
                key = self.key.replace("<n>", str(idx))
                if key not in self.options:
                    break
                del self.options[key]
        LOG.debug(self.options)

OPT_VIEW = {
    "INT" : IntegerOptionWidget,
    "BOOL": OptionWidget,
    "FILE": FileOptionWidget,
    "IMAGE": ImageOptionWidget,
    "TIMESERIES" : ImageOptionWidget,
    "MVN": FileOptionWidget,
    "MATRIX": MatrixFileOptionWidget,
}

def get_option_widget(opt, **kwargs):
    """
    Get an option widget for a Fabber option

    :param opt: Option as a dictionary, as returned by Fabber.get_options
    """

    if opt["name"].find("<n>") >= 0:
        return ListOptionWidget(opt, **kwargs)
    else:
        return OPT_VIEW.get(opt["type"], StringOptionWidget)(opt, **kwargs)
   