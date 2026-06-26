from wheelbuilder.platforminfo import SDK
from wheelbuilder.protocols import CiWheelBase

_SODIUM_PREFIX = "/tmp/pynacl_sodium"
_PYPI_INDEX = "https://pypi-index.psychowaspx.workers.dev/simple/"


class Pynacl(CiWheelBase):
    def env(self):
        env = self.base_env()

        if self.platform.sdk == SDK.android:
            # Android: let pynacl build its own bundled libsodium.
            # cibuildwheel Android always uses --no-isolation; cffi is pre-installed
            # by cibuildwheel into the macOS build_env (so _cffi_backend is the
            # macOS-native  loadable at build time).binary 
            # We patch setup.py to skip `make check` (cross-compiled android
            # binaries can't run on macOS) and to pass --host=$CIBW_HOST_TRIPLET
            # (set in android_env during the BUILD step) to ./configure so
            # libsodium cross-compiles for the correct android ABI.
            env["CIBW_ENVIRONMENT_ANDROID"] = " ".join([
                'PYNACL_SODIUM_STATIC="1"',
                f'PIP_EXTRA_INDEX_URL="{_PYPI_INDEX}"',
                # LDSHARED in _sysconfigdata has the wrong NDK path (from BeeWare's
                # build machine, /Users/msmith/...). We can't use $CC in
                # CIBW_ENVIRONMENT because it's expanded before android_env sets CC.
                # Instead, point LDSHARED to a wrapper script that resolves $CC at
                # link execution time (when android_env has CC set correctly).
                'LDSHARED="/tmp/pynacl_ldshared.sh"',
            ])
            env["CIBW_BEFORE_BUILD_ANDROID"] = """\
python3 - << 'PATCH'
import pathlib
f = pathlib.Path('{package}/setup.py')
t = f.read_text()
old_check = '        subprocess.check_call(["make", "check"] + make_args, cwd=build_temp)'
new_check = '        pass  # make check skipped for cross-compilation'
old_cfg = '''        subprocess.check_call(
            [configure]
            + configure_flags
            + ["--prefix", os.path.abspath(self.build_clib)],'''
new_cfg = '''        if os.environ.get("CIBW_HOST_TRIPLET"):
            configure_flags.append("--host=" + os.environ["CIBW_HOST_TRIPLET"])
''' + old_cfg
assert old_check in t, 'PATCH FAILED: make check pattern not found'
assert old_cfg in t, 'PATCH FAILED: configure pattern not found'
t = t.replace(old_check, new_check, 1)
t = t.replace(old_cfg, new_cfg, 1)
f.write_text(t)
print('Patched setup.py: skipped make check + added --host')
PATCH
cat > /tmp/pynacl_ldshared.sh << 'WRAPEOF'
#!/bin/sh
exec "$CC" -shared "$@"
WRAPEOF
chmod +x /tmp/pynacl_ldshared.sh"""

        else:
            # iOS: pre-build libsodium with xcrun (SODIUM_INSTALL=system).
            # --no-isolation skips build dep auto-installation, so we manually
            # install cffi. The ios-targeted cffi wheel from the custom index
            # installs an ios _cffi_backend.so that the macOS Python can't load.
            # Fix: download the macOS arm64 cffi wheel from PyPI and extract its
            # _cffi_backend.cpython-3xx-darwin.so into site-packages so
            # `import _cffi_backend` succeeds at build time. cffi then compiles
            # _sodium.c using the ios sysconfig CC (xcrun clang targeting ios).
            env["CIBW_BUILD_FRONTEND"] = "build; args: --no-isolation"
            env["CIBW_ENVIRONMENT_IOS"] = " ".join([
                'SODIUM_INSTALL="system"',
                'PYNACL_SODIUM_STATIC="1"',
                f'CFLAGS="$CFLAGS -I{_SODIUM_PREFIX}/include"',
                f'LDFLAGS="$LDFLAGS -L{_SODIUM_PREFIX}/lib"',
                f'PIP_EXTRA_INDEX_URL="{_PYPI_INDEX}"',
            ])
            env["CIBW_BEFORE_BUILD_IOS"] = (
                "pip install 'cffi>=2.0.0' 'setuptools>=40.8.0' wheel\n"
                "python3 - << 'CFFI_FIX'\n"
                "import subprocess, sys, site, zipfile, pathlib, glob, shutil\n"
                "ver = str(sys.version_info.major) + str(sys.version_info.minor)\n"
                "shutil.rmtree('/tmp/_cffi_macos_dl', ignore_errors=True)\n"
                "r = subprocess.run(\n"
                "    [sys.executable, '-m', 'pip', 'download', 'cffi==2.0.0',\n"
                "     '--platform', 'macosx_11_0_arm64', '--only-binary=:all:',\n"
                "     '--python-version', ver, '--no-deps',\n"
                "     '--dest', '/tmp/_cffi_macos_dl'],\n"
                "    capture_output=True, text=True)\n"
                "print(r.stdout[-500:] + r.stderr[-500:])\n"
                "wheels = glob.glob('/tmp/_cffi_macos_dl/cffi*.whl')\n"
                "assert wheels, 'ERROR: no macOS arm64 cffi wheel downloaded'\n"
                "sp = pathlib.Path(next(iter(site.getsitepackages())))\n"
                "with zipfile.ZipFile(wheels[0]) as z:\n"
                "    for name in z.namelist():\n"
                "        if '_cffi_backend' in name and name.endswith('.so'):\n"
                "            dest = sp / pathlib.Path(name).name\n"
                "            dest.write_bytes(z.read(name))\n"
                "            print('cffi backend installed:', dest)\n"
                "            break\n"
                "CFFI_FIX\n"
                f"bash ${{GITHUB_WORKSPACE}}/src/wheelbuilder/scripts/libsodium.sh"
                f' "{{package}}/src/libsodium" "{_SODIUM_PREFIX}"'
            )

        return env
