from wheelbuilder.platforminfo import SDK
from wheelbuilder.protocols import MaturinWheelBase
from wheelbuilder.wheels.library.openssl import Openssl


class Cryptography(MaturinWheelBase):
    def env(self):
        env = self.maturin_env()
        env["OPENSSL_DIR"] = str(self.root / f"openssl/{self.platform.sdk_arch}")
        if self.platform.sdk != SDK.android:
            before_build = " && ".join(
                [
                    "pip install maturin setuptools pycparser",
                    "pip download cffi --platform macosx_14_0_arm64 --python-version 313 --only-binary :all: -d /tmp/cffi_wheels",
                    "python -c 'import sys, zipfile, glob; sp = next(p for p in sys.path if \"site-packages\" in p); whl = glob.glob(\"/tmp/cffi_wheels/cffi*.whl\")[0]; zipfile.ZipFile(whl).extractall(sp)'",
                    "python3 -c \"import sysconfig, os; libdir=sysconfig.get_config_var('LIBDIR'); vars=sysconfig.get_config_vars(); open(os.path.join(libdir,'_sysconfigdata__ios.py'),'w').write('build_time_vars='+repr(vars))\"",
                ]
            )
            env["CIBW_BEFORE_BUILD"] = before_build
            env["CIBW_BUILD_FRONTEND"] = "build;args: --no-isolation --skip-dependency-check"
        return env

    def dependencies_libraries(self):
        return [Openssl]
