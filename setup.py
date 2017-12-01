#!/usr/bin/env python
"""
Build Quantiphyse plugin for fabber
"""

import numpy
import os
import sys
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py

desc = "Quantiphyse package for Fabber"
version = "0.0.1"

SHLIB_DIR = "lib"
SHLIB_TEMPLATE = "lib%s.so"

class build_plugin(build_py):
    def run(self):
        build_py.run(self)
        fsldir = os.environ.get("FSLDEVDIR", os.environ.get("FSLDIR", ""))
        print("Coping Fabber libraries from %s" % fsldir)
        rootdir = os.path.abspath(os.path.dirname(__file__))
        distdir = os.path.join(rootdir, "dist")
        plugindir = os.path.join(distdir, "plugin")
        shutil.rmtree(plugindir)
        os.makedirs(plugindir)

        pkgdir = os.path.join(plugindir, "qp_fabber")
        shutil.copytree(os.path.join(rootdir, "fabber_qp"), pkgdir)
        LIB = os.path.join(fsldir, SHLIB_DIR, SHLIB_TEMPLATE % "fabbercore_shared")
        shutil.copy(LIB, pkgdir)
        PYAPI = os.path.join(fsldir, "lib", "python", "fabber.py")
        shutil.copy(PYAPI, os.path.join(pkgdir, "fabber_api.py"))
        
# setup parameters
setup(name='fabber_qp',
      cmdclass={"build_plugin" : build_plugin},
      version=version,
      description=desc,
      long_description=desc,
      author='Michael Chappell, Martin Craig',
      author_email='martin.craig@eng.ox.ac.uk',
      packages=['fabber_qp'],
      include_package_data=True,
      data_files=[],
      setup_requires=[],
      install_requires=[],
      classifiers=["Programming Language :: Python :: 2.7",
                   "Development Status:: 3 - Alpha",
                   'Programming Language :: Python',
                   'Operating System :: MacOS :: MacOS X',
                   'Operating System :: Microsoft :: Windows',
                   'Operating System :: POSIX',
                   "Intended Audience :: Education",
                   "Intended Audience :: Science/Research",
                   "Intended Audience :: End Users/Desktop",
                   "Topic :: Scientific/Engineering :: Bio-Informatics",],
)

