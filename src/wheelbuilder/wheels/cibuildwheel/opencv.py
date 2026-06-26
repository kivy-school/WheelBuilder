from pathlib import Path

from wheelbuilder import tools
from wheelbuilder.platforminfo import SDK
from wheelbuilder.protocols import BuildTarget, CiWheelBase


class Opencv(CiWheelBase):
    build_target = BuildTarget.url(
        "https://github.com/opencv/opencv-python/archive/refs/tags/92.tar.gz"
    )

    def env(self):
        env = self.base_env()
        env["CIBW_ENVIRONMENT_IOS"] = " ".join(
            [
                'PIP_EXTRA_INDEX_URL="https://pypi-index.psychowaspx.workers.dev/simple/"',
                'CI_BUILD="1"',
                'OPENCV_PYTHON_SKIP_GIT_COMMANDS="1"',
                f'CMAKE_ARGS="-DCMAKE_OSX_SYSROOT=$(xcrun --sdk {self.platform.sdk} --show-sdk-path)"',
            ]
        )
        env["CIBW_XBUILD_TOOLS_IOS"] = "cmake ninja"
        if self.platform.sdk == SDK.android:
            env["CIBW_ENVIRONMENT_ANDROID"] = " ".join(
                [
                    'OPENCV_PYTHON_SKIP_GIT_COMMANDS="1"',
                    'CI_BUILD="1"',
                    'PKG_CONFIG_PATH=""',
                ]
            )
            env["CIBW_BEFORE_BUILD_ANDROID"] = r"""
                set -e
                OCV="${GITHUB_WORKSPACE}/output/wheels/opencv-python-92"
                PYVER=$(python -c "import sys; v=sys.version_info; print(f'{v.major}.{v.minor}')")
                PBS_LIB=$(python -c "import sys,os; print(os.path.join(os.path.dirname(sys.prefix), 'pbs', 'python', 'lib'))")
                mkdir -p "$PBS_LIB"
                printf 'void _dummy(void){}' | cc -x c - -dynamiclib -o "$PBS_LIB/libpython${PYVER}.so" 2>/dev/null || true
                rm -rf "${OCV}/_skbuild" 2>/dev/null || true
                cat > /tmp/wb_android_patch.py << 'PYEOF'
                import sys, os
                f = os.environ["GITHUB_WORKSPACE"] + "/output/wheels/opencv-python-92/setup.py"
                src = open(f).read()
                _cm = os.environ["GITHUB_WORKSPACE"] + "/output/wheels/opencv-python-92/opencv/modules/python/CMakeLists.txt"
                if os.path.exists(_cm):
                    _s = open(_cm).read()
                    _o = "if(ANDROID OR APPLE_FRAMEWORK OR WINRT)"
                    _n = "if((ANDROID AND NOT BUILD_opencv_python3) OR APPLE_FRAMEWORK OR WINRT)"
                    if _o in _s:
                        open(_cm, "w").write(_s.replace(_o, _n, 1))
                        print("[WheelBuilder] patched modules/python/CMakeLists.txt for Android python3")
                    elif _n in _s:
                        print("[WheelBuilder] modules/python/CMakeLists.txt already patched")
                    else:
                        print("[WheelBuilder] WARNING: modules/python/CMakeLists.txt android check not found")
                if "is_android" in src:
                    print("[WheelBuilder] setup.py already patched for Android")
                    sys.exit(0)
                src = src.replace(
                    '    is_ios = "ios" in target_platform',
                    '    is_ios = "ios" in target_platform\n    is_android = "android" in target_platform')
                block = (
                    "\n    if is_android:\n"
                    "        _inc = __import__('sysconfig').get_path('include')\n"
                    "        cmake_args.append('-DPYTHON3INTERP_FOUND=ON')\n"
                    "        cmake_args.append('-DPYTHON3_INCLUDE_PATH=%s' % _inc)\n"
                    "        cmake_args.append('-DPYTHON3_VERSION_STRING=%d.%d' % (sys.version_info.major, sys.version_info.minor))\n"
                    "        cmake_args.append('-DPYTHON3_VERSION_MAJOR=%d' % sys.version_info.major)\n"
                    "        cmake_args.append('-DPYTHON3_VERSION_MINOR=%d' % sys.version_info.minor)\n"
                    "        cmake_args.append('-DPYTHON3_PACKAGES_PATH=python')\n"
                    "        cmake_args.append('-DPYTHON_DEFAULT_AVAILABLE=TRUE')\n"
                    "        cmake_args.append('-DPYTHON3_PACKAGES_PATH=python')\n"
                    "        cmake_args.append('-DOPENCV_OTHER_INSTALL_PATH=share/opencv4')\n"
                    "        try:\n"
                    "            import numpy as _n; cmake_args.append('-DPYTHON3_NUMPY_INCLUDE_DIRS=%s' % _n.get_include())\n"
                    "        except: pass\n"
                )
                src = src.replace("    if build_headless:", block + "    if build_headless:")
                open(f, "w").write(src)
                print("[WheelBuilder] patched setup.py for Android cmake args")
                PYEOF
                python /tmp/wb_android_patch.py
                sed -i.bak '/add_subdirectory.*android/d' "${OCV}/opencv/samples/CMakeLists.txt" 2>/dev/null || true
                """
        return env

    def patches(self):
        return [
            "https://raw.githubusercontent.com/Py-Swift/LibraryPatches/refs/heads/master/opencv/opencv-python-ios-92.patch",
        ]

    def apply_patches(self, target: Path, working_dir: Path) -> None:
        for url in self.patches():
            patch_file = tools.download_url(url, working_dir)
            tools.git_apply(patch_file, target)

    def build_wheel(self, working_dir: Path, version, wheels_dir: Path) -> None:
        tag = version or "92"
        clone_dir = wheels_dir / f"opencv-python-{tag}"
        tools.run(
            [
                "git",
                "clone",
                "--recursive",
                "--branch",
                tag,
                "--depth",
                "1",
                "https://github.com/opencv/opencv-python.git",
                str(clone_dir),
            ]
        )
        if not clone_dir.exists():
            return
        self.apply_patches(clone_dir, working_dir)
        pyproject = clone_dir / "pyproject.toml"
        text = pyproject.read_text()
        patched = text.replace("numpy==2.3.2", "numpy>=2.3.2")
        if patched != text:
            pyproject.write_text(patched)
            print("[WheelBuilder] relaxed numpy==2.3.2 -> >=2.3.2 in pyproject.toml")
        else:
            print("[WheelBuilder] numpy==2.3.2 not found in pyproject.toml, skipping pin relax")
        print(type(self).__name__, "cibuildwheel", clone_dir)
        tools.cibuildwheel(
            target=clone_dir,
            ci_platform=self.platform.ci_platform,
            ci_archs=self.platform.ci_archs,
            env=self.env(),
            output=wheels_dir,
        )
        import shutil

        shutil.rmtree(clone_dir, ignore_errors=True)
