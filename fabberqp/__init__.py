"""
Author: Martin Craig <martin.craig@eng.ox.ac.uk>
Copyright (c) 2016-2017 University of Oxford, Martin Craig
"""
from quantiphyse.utils import get_local_shlib

from .process import FabberProcess
from .widget import FabberModellingWidget, SimData
from .tests import FabberWidgetTest

QP_MANIFEST = {
    "widgets" : [FabberModellingWidget, SimData],
    "widget-tests" : [FabberWidgetTest],
    "processes" : [FabberProcess],
    "fabber-corelib" : [get_local_shlib("fabbercore_shared", __file__)],
    "module-dirs" : ["deps",],
}
