"""
Author: Martin Craig <martin.craig@eng.ox.ac.uk>
Copyright (c) 2016-2017 University of Oxford, Martin Craig
"""

from .process import FabberProcess
from .widget import FabberModellingWidget, SimData
from .tests import FabberWidgetTest

QP_MANIFEST = {
    "widgets" : [FabberModellingWidget, SimData],
    "widget-tests" : [FabberWidgetTest],
    "processes" : [FabberProcess],
    "module-dirs" : ["deps",],
}
