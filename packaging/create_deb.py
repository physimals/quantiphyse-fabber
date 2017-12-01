"""
Create a DEB package for Debian based systems (Ubuntu, Debian, etc)

This package contains the FROZEN python code, so it does not rely on dependencies
on the target system. This is not how Python packages 'ought' to be installed, so
it may be worthwhile producing a proper Python package which could be installed
via pip or similarly.
"""
import os, sys
import shutil
import subprocess

DEB_SUBDIR = "deb"
INSTALL_PREFIX = "usr/local"

# Template for the DEBIAN/control file
CONTROL_TEMPLATE = """
Package: %(name)
Architecture: %(arch)s
Maintainer: Martin Craig <martin.craig@eng.ox.ac.uk>
Depends: debconf (>= 0.5.00), quantiphyse
Priority: optional
Version: %(version_str)s
Description: %(name) plugin for Quantiphyse
"""

def create_deb(name, distdir, pkgdir, version_str, version_str_display=None):
    if version_str_display == None:
        version_str_display = version_str

    formatting_values = {
        "name" : name,
        "version_str" : version_str,
        "version_str_display" : version_str_display,
        "arch" : subprocess.check_output(['dpkg', '--print-architecture']).strip()
    }
    
    debdir = os.path.join(pkgdir, DEB_SUBDIR)
    # Existing files may be owned by root
    os.system("sudo rm -rf %s" % debdir)

    pkgname = "quantiphyse_%(version_str_display)s_%(arch)s" % formatting_values
    builddir = os.path.join(debdir, pkgname) 

    installdir = os.path.join(builddir, INSTALL_PREFIX, "quantiphyse", "packages", "plugins", name)
    shutil.copytree(os.path.join(distdir, name), installdir)
    
    metadir = os.path.join(builddir, "DEBIAN")
    os.makedirs(metadir)

    control_file = open(os.path.join(metadir, "control"), "w")
    control_file.write(CONTROL_TEMPLATE % formatting_values)
    control_file.close()

    # Need all files to be owned by root
    # No one-line way to do this in Python?
    os.system("sudo chown -R root:root %s" % builddir)

    # Build the actual deb
    os.system("dpkg-deb --build %s" % builddir)

    pkg = os.path.join(debdir, pkgname + ".deb")
    shutil.move(pkg, distdir)

if __name__ == "__main__":
    # Get absolute paths to the packaging dir and the root dir
    pkgdir = os.path.abspath(os.path.dirname(__file__))
    rootdir = os.path.abspath(os.path.join(pkgdir, os.pardir))
    sys.path.append(rootdir)
    #import update_version

    create_deb(os.path.join(qpdir, "dist"), pkgdir, "0.0.1")