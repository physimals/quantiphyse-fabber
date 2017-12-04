"""
Author: Martin Craig <martin.craig@eng.ox.ac.uk>
Copyright (c) 2016-2017 University of Oxford, Martin Craig
"""

# Fabber API and library is stored locally
import os
os.environ["FSLDIR"] = os.path.abspath(os.path.dirname(__file__))

from .process import FabberProcess
from .widget import FabberWidget

QP_MANIFEST = {
    "widgets" : [FabberWidget],
    "processes" : [FabberProcess]
}
