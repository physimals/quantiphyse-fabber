import os, sys
import platform

pkgdir = os.path.abspath(os.path.dirname(__file__))
rootdir = os.path.abspath(os.path.join(pkgdir, os.pardir))
distdir = os.path.join(rootdir, "dist", "plugin")
version_str = "0.0.1-1"
version_str_display = "0.0.1-1"

sys.path.append(rootdir)

if sys.platform.startswith("win"):
    sysname="win32"
    import create_msi
    build_platform_package = create_msi.create_msi
elif sys.platform.startswith("linux"):
    sysname=platform.linux_distribution()[0].split()[0].lower()
    import create_deb
    build_platform_package = create_deb.create_deb
elif sys.platform.startswith("darwin"):
    sysname="osx"

os.system("rm -rf %s/dist" % rootdir)
#os.system("python %s/update_version.py" % pkgdir)
print("Building plugin")
os.system("python %s/setup.py build_plugin" % rootdir)

build_platform_package("fabber_qp", distdir, pkgdir, version_str, version_str_display)
