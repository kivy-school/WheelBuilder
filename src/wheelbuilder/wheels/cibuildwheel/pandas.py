import os
import stat
from pathlib import Path

from wheelbuilder import tools
from wheelbuilder.platforminfo import SDK
from wheelbuilder.protocols import MesonWheelBase


class Pandas(MesonWheelBase):
    def env(self):
        env = self.meson_env()
        env["CIBW_BEFORE_BUILD_IOS"] = (
            "env -u SDKROOT -u IPHONEOS_DEPLOYMENT_TARGET pip install meson-python meson Cython"
            " && env -u SDKROOT -u IPHONEOS_DEPLOYMENT_TARGET"
            " pip install numpy --only-binary :all:"
        )
        env["CIBW_CONFIG_SETTINGS_IOS"] = (
            "setup-args=--cross-file=/tmp/pandas-ios-meson-cross.ini "
            "setup-args=--native-file=/tmp/pandas-ios-meson-native.ini"
        )
        wheels_dir = getattr(self, "_wheels_dir", None)
        env["CIBW_ENVIRONMENT_IOS"] = " ".join(
            [
                'PIP_EXTRA_INDEX_URL="https://pypi-index.psychowaspx.workers.dev/simple/"',
                'PIP_PREFER_BINARY="1"',
                'CFLAGS="-g0"',
                'LDFLAGS=""',
            ]
            + (
                [f'PIP_FIND_LINKS="{wheels_dir}"']
                if wheels_dir and wheels_dir.exists()
                else []
            )
        )
        if self.platform.sdk == SDK.android:
            env["CIBW_ENVIRONMENT_ANDROID"] = (
                'LDFLAGS="$LDFLAGS -landroid -lc++_shared" PKG_CONFIG_PATH=""'
            )
        return env

    def patches(self):
        return [
            "https://raw.githubusercontent.com/Py-Swift/LibraryPatches/refs/heads/master/pandas/pandas-ios.patch",
        ]

    def apply_patches(self, target: Path, working_dir: Path) -> None:
        for url in self.patches():
            patch_file = tools.download_url(url, working_dir)
            tools.git_apply(patch_file, target)
        for name in (
            "ios-meson-cross.ini",
            "ios-meson-native.ini",
            "ios-native-cc.sh",
            "ios-native-cxx.sh",
        ):
            try:
                (target / name).unlink(missing_ok=True)
            except OSError:
                pass

    def pre_build(self, target: Path) -> None:
        self.write_meson_cross_file()
        if self.platform.sdk == SDK.android:
            return

        cross_ini = (
            "; Supplementary meson cross-file for iOS builds.\n"
            "; Tells meson that cross-compiled binaries cannot run on the build host,\n"
            "; preventing it from trying to execute sanity-check programs that would\n"
            "; hang on macOS (since iOS arm64 Mach-O binaries can't run on the host).\n"
            "\n"
            "[properties]\n"
            "needs_exe_wrapper = true\n"
            "\n"
            "[binaries]\n"
            "exe_wrapper = ['/usr/bin/true']"
        )
        native_ini = (
            "; Native (build-machine) meson file for iOS cross-builds.\n"
            "; Uses wrapper scripts that unset SDKROOT and IPHONEOS_DEPLOYMENT_TARGET\n"
            "; so the build-machine compiler targets macOS, not iOS.\n"
            "\n"
            "[binaries]\n"
            "c = '/tmp/pandas-ios-native-cc.sh'\n"
            "cpp = '/tmp/pandas-ios-native-cxx.sh'\n"
            "objc = '/tmp/pandas-ios-native-cc.sh'\n"
            "objcpp = '/tmp/pandas-ios-native-cxx.sh'\n"
            "ar = '/usr/bin/ar'\n"
            "strip = '/usr/bin/strip'"
        )
        native_cc = (
            "#!/bin/bash\n"
            "unset SDKROOT\n"
            "unset IPHONEOS_DEPLOYMENT_TARGET\n"
            'exec /usr/bin/cc "$@"'
        )
        native_cxx = (
            "#!/bin/bash\n"
            "unset SDKROOT\n"
            "unset IPHONEOS_DEPLOYMENT_TARGET\n"
            'exec /usr/bin/c++ "$@"'
        )

        # Supplement meson cross-file used when pip builds numpy from source.
        # iOS arm64 uses 8-byte IEEE 754 double for long double.
        Path("/tmp/pandas-ios-meson-cross.ini").write_text(cross_ini)
        Path("/tmp/pandas-ios-meson-native.ini").write_text(native_ini)
        for path, content in (
            ("/tmp/pandas-ios-native-cc.sh", native_cc),
            ("/tmp/pandas-ios-native-cxx.sh", native_cxx),
        ):
            Path(path).write_text(content)
            os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
