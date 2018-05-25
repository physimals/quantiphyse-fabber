"""
Author: Martin Craig <martin.craig@eng.ox.ac.uk>
Copyright (c) 2016-2017 University of Oxford, Martin Craig
"""
from quantiphyse.utils import get_local_shlib

from .process import FabberProcess

QP_MANIFEST = {
    "processes" : [FabberProcess],
    "fabber-libs" : [get_local_shlib("fabber_models_t1", __file__)],
}
