import os, sys
import platform
import shutil

def get_lib_template(platform):
    if platform == "win32":
        return "bin", "%s.dll"
    elif platform == "osx":
        return "lib", "lib%s.dylib"
    else:
        return "lib", "lib%s.so"

def build_plugin(rootdir, distdir, platform):
    fsldir = os.environ.get("FSLDEVDIR", os.environ.get("FSLDIR", ""))
    print("Coping Fabber libraries from %s" % fsldir)
    print("Root dir is %s" % rootdir)
    os.makedirs(distdir)

    packagedir = os.path.join(distdir, "fabber_qp")
    shutil.copytree(os.path.join(rootdir, "fabber_qp"), packagedir)
    
    # Copy Fabber shared lib and API
    shlib_dir, shlib_template = get_lib_template(platform)
    LIB = os.path.join(fsldir, shlib_dir, shlib_template % "fabbercore_shared")
    print("%s -> %s" % (LIB, packagedir))
    shutil.copy(LIB, packagedir)
    PYAPI = os.path.join(fsldir, "lib", "python", "fabber.py")
    shutil.copy(PYAPI, os.path.join(pkgdir, "fabber_api.py"))

pkgdir = os.path.abspath(os.path.dirname(__file__))
rootdir = os.path.abspath(os.path.join(pkgdir, os.pardir))
distdir = os.path.join(rootdir, "dist", "plugin")
version_str = "0.0.1-1"
version_str_display = "0.0.1-1"

sys.path.append(rootdir)

if sys.platform.startswith("win"):
    platform="win32"
    import create_msi
    build_platform_package = create_msi.create_msi
elif sys.platform.startswith("linux"):
    platform="linux"
    import create_deb
    build_platform_package = create_deb.create_deb
elif sys.platform.startswith("darwin"):
    platform="osx"

os.system("rm -rf %s/dist" % rootdir)
#os.system("python %s/update_version.py" % pkgdir)
print("Building plugin")
build_plugin(rootdir, distdir, platform)
build_platform_package("fabber_qp", distdir, pkgdir, version_str, version_str_display)
