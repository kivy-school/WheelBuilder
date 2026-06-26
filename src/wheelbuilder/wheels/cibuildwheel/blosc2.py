from pathlib import Path

from wheelbuilder import tools
from wheelbuilder.protocols import CiWheelBase


class Blosc2(CiWheelBase):
    def env(self):
        env = self.base_env()
        env["CIBW_XBUILD_TOOLS_IOS"] = "cmake ninja git"
        env["CIBW_BEFORE_BUILD_IOS"] = """\
pip install --only-binary=numpy 'scikit-build-core>=0.11.0' 'cython>=3' 'numpy>=2.1'
python3 - << 'PYEOF'
import sys, sysconfig, os, subprocess
sp = sysconfig.get_path('purelib')
ni = next((os.path.join(sp, d) for d in ('numpy/_core/include', 'numpy/core/include') if os.path.isdir(os.path.join(sp, d))), sp + '/numpy/_core/include')
cc = os.environ.get('CC', '')
sdk = 'iphonesimulator' if 'simulator' in cc else 'iphoneos'
r = subprocess.run(['xcrun', '--sdk', sdk, '--show-sdk-path'], capture_output=True, text=True)
sysroot = r.stdout.strip() if r.returncode == 0 else sdk
with open('/tmp/blosc2_cmake_init.cmake', 'w') as f:
    f.write('set(Python_EXECUTABLE "' + sys.executable + '" CACHE FILEPATH "" FORCE)\n')
    f.write('set(Python_NumPy_INCLUDE_DIRS "' + ni + '" CACHE PATH "" FORCE)\n')
    f.write('set(CMAKE_OSX_SYSROOT "' + sysroot + '" CACHE STRING "" FORCE)\n')
PYEOF
MINIEXPR_SRC=/tmp/blosc2_ios_miniexpr
rm -rf $MINIEXPR_SRC
git clone --depth 1 https://github.com/Blosc/miniexpr.git $MINIEXPR_SRC
cd $MINIEXPR_SRC && git fetch --depth 1 origin f2faef741c4c507bf6a03167c72ce7f92c6f0ae8 && git checkout f2faef741c4c507bf6a03167c72ce7f92c6f0ae8
sed -i '' 's/int rc = system(cmd);/int rc = -1; (void)cmd;/' $MINIEXPR_SRC/src/*.c
CBLOSC2_SRC=/tmp/blosc2_ios_cblosc2
rm -rf $CBLOSC2_SRC
git clone --depth 1 --branch v3.0.3 https://github.com/Blosc/c-blosc2.git $CBLOSC2_SRC
sed -i '' 's/STREQUAL "Darwin")/STREQUAL "Darwin" OR SYSTEM_NAME STREQUAL "iOS")/' $CBLOSC2_SRC/cmake/merge_static_libs.cmake"""
        env["CIBW_ENVIRONMENT_IOS"] = " ".join(
            [
                'PIP_EXTRA_INDEX_URL="https://pypi-index.psychowaspx.workers.dev/simple/"',
                'SKBUILD_CMAKE_ARGS="-DFETCHCONTENT_SOURCE_DIR_MINIEXPR=/tmp/blosc2_ios_miniexpr;-DFETCHCONTENT_SOURCE_DIR_BLOSC2=/tmp/blosc2_ios_cblosc2;-C;/tmp/blosc2_cmake_init.cmake"',
            ]
        )
        env["CIBW_BUILD_FRONTEND"] = "build; args: --no-isolation"
        # Android: scikit-build-core calls get_numpy_include_dir() which does
        # `import numpy` — numpy's ctypes tries dlopen(libpython3.13.so) which
        # doesn't exist on macOS. Provide Python_NumPy_INCLUDE_DIRS via a cmake
        # init file using importlib.util.find_spec (no import, just path lookup).
        env["CIBW_BEFORE_BUILD_ANDROID"] = """\
pip install 'scikit-build-core>=0.11.0' 'cython>=3' 'numpy>=2.1'
python3 - << 'SCPATCH'
import pathlib, importlib.util as _il
spec = _il.find_spec('scikit_build_core')
if spec and spec.submodule_search_locations:
    sc_dir = pathlib.Path(list(spec.submodule_search_locations)[0])
    sysc = sc_dir / 'builder' / 'sysconfig.py'
    if sysc.exists():
        t = sysc.read_text()
        old = '''def get_numpy_include_dir() -> Path | None:
    try:
        import numpy as np
    except ImportError:
        return None

    return Path(np.get_include())'''
        new = '''def get_numpy_include_dir() -> Path | None:
    import importlib.util as _iu
    spec = _iu.find_spec("numpy")
    if spec is None or spec.origin is None:
        return None
    np_dir = Path(spec.origin).parent
    for subdir in ("_core/include", "core/include"):
        candidate = np_dir / subdir
        if candidate.is_dir():
            return candidate
    return np_dir / "_core" / "include"'''
        if old in t:
            sysc.write_text(t.replace(old, new))
SCPATCH
python3 - << 'PYEOF'
import sys, os, importlib.util
spec = importlib.util.find_spec('numpy')
np_dir = os.path.dirname(spec.origin) if spec and spec.origin else ''
ni = next((os.path.join(np_dir, d) for d in ('_core/include', 'core/include') if os.path.isdir(os.path.join(np_dir, d))), np_dir + '/_core/include')
with open('/tmp/blosc2_android_cmake_init.cmake', 'w') as f:
    f.write('set(Python_EXECUTABLE "' + sys.executable + '" CACHE FILEPATH "" FORCE)\\n')
    f.write('set(Python_NumPy_INCLUDE_DIRS "' + ni + '" CACHE PATH "" FORCE)\\n')
    f.write('set(ANDROID_PLATFORM_LEVEL 24 CACHE STRING "" FORCE)\\n')
    # Android Bionic has no separate librt; clock/timer functions are in libc.
    # Prevent find_library(LIB_RT rt) from succeeding so blosc2/zfp cmake
    # don't add -lrt to target_link_libraries.
    f.write('set(LIB_RT "" CACHE FILEPATH "rt library" FORCE)\\n')
    f.write('set(RT_LIBRARY "" CACHE FILEPATH "rt library" FORCE)\\n')
    # Also scrub it from standard library lists just in case
    f.write('set(CMAKE_C_STANDARD_LIBRARIES "" CACHE STRING "" FORCE)\\n')
    f.write('set(CMAKE_CXX_STANDARD_LIBRARIES "" CACHE STRING "" FORCE)\\n')
PYEOF
MINIEXPR_SRC=/tmp/blosc2_android_miniexpr
rm -rf $MINIEXPR_SRC
git clone --depth 1 https://github.com/Blosc/miniexpr.git $MINIEXPR_SRC
cd $MINIEXPR_SRC && git fetch --depth 1 origin f2faef741c4c507bf6a03167c72ce7f92c6f0ae8 && git checkout f2faef741c4c507bf6a03167c72ce7f92c6f0ae8
sed -i '' 's/int rc = system(cmd);/int rc = -1; (void)cmd;/' $MINIEXPR_SRC/src/*.c
python3 - << 'MINIEXPRPATCH'
import pathlib
f = pathlib.Path('/tmp/blosc2_android_miniexpr/src/functions.c')
t = f.read_text()
old = '#define me_cpowf cpowf\\n#define me_cpow cpow\\n#define me_csqrtf csqrtf\\n#define me_csqrt csqrt\\n#define me_cexpf cexpf\\n#define me_cexp cexp\\n#define me_clogf clogf\\n#define me_clog clog'
new = (
    'static inline float _Complex me_clogf_android(float _Complex a)'
    ' { return __builtin_complex(logf(cabsf(a)), cargf(a)); }\\n'
    'static inline double _Complex me_clog_android(double _Complex a)'
    ' { return __builtin_complex(log(cabs(a)), carg(a)); }\\n'
    'static inline float _Complex me_cpowf_android(float _Complex a, float _Complex b)'
    ' { return cexpf(b * me_clogf_android(a)); }\\n'
    'static inline double _Complex me_cpow_android(double _Complex a, double _Complex b)'
    ' { return cexp(b * me_clog_android(a)); }\\n'
    '#define me_cpowf me_cpowf_android\\n'
    '#define me_cpow me_cpow_android\\n'
    '#define me_csqrtf csqrtf\\n'
    '#define me_csqrt csqrt\\n'
    '#define me_cexpf cexpf\\n'
    '#define me_cexp cexp\\n'
    '#define me_clogf me_clogf_android\\n'
    '#define me_clog me_clog_android'
)
if old in t:
    f.write_text(t.replace(old, new))
    print('Patched me_cpowf/me_cpow in miniexpr functions.c')
else:
    print('WARNING: cpowf/cpow pattern not found in functions.c')
MINIEXPRPATCH
CBLOSC2_SRC=/tmp/blosc2_android_cblosc2
rm -rf $CBLOSC2_SRC
git clone --depth 1 --branch v3.0.3 https://github.com/Blosc/c-blosc2.git $CBLOSC2_SRC
# Remove hardcoded -lrt: Android Bionic has no separate librt
sed -i '' '/set(LIBS \\${LIBS} "rt")/d' $CBLOSC2_SRC/blosc/CMakeLists.txt"""
        env["CIBW_ENVIRONMENT_ANDROID"] = " ".join(
            [
                'PIP_EXTRA_INDEX_URL="https://pypi-index.psychowaspx.workers.dev/simple/"',
                'SKBUILD_CMAKE_ARGS="-DFETCHCONTENT_SOURCE_DIR_MINIEXPR=/tmp/blosc2_android_miniexpr;-DFETCHCONTENT_SOURCE_DIR_BLOSC2=/tmp/blosc2_android_cblosc2;-C;/tmp/blosc2_android_cmake_init.cmake"',
            ]
        )
        # Android: numexpr (blosc2 runtime dep) has no Android wheels so tests
        # can't be installed; and we can't execute Android binaries on macOS anyway
        env["CIBW_TEST_SKIP"] = "*-android*"
        return env

    def patches(self):
        return [
            "https://raw.githubusercontent.com/Py-Swift/LibraryPatches/refs/heads/master/blosc2-ios.patch",
        ]

    def apply_patches(self, target: Path, working_dir: Path) -> None:
        for url in self.patches():
            patch_file = tools.download_url(url, working_dir)
            tools.git_apply(patch_file, target)
