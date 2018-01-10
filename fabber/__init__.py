"""
Author: Martin Craig <martin.craig@eng.ox.ac.uk>
Copyright (c) 2016-2017 University of Oxford, Martin Craig
"""

# Fabber API and library is stored locally
import os

from .process import FabberProcess
from .widget import FabberWidget

QP_MANIFEST = {
    "widgets" : [FabberWidget],
    "processes" : [FabberProcess]
}
