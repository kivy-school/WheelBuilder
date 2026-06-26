from wheelbuilder.platforminfo import SDK, Arch
from wheelbuilder.protocols import MesonWheelBase


class Numpy(MesonWheelBase):
    def meson_extra_ini_sections(self) -> str:
        longdouble = (
            "IEEE_QUAD_LE" if self.platform.arch == Arch.arm64 else "INTEL_EXTENDED_16_BYTES_LE"
        )
        return f"[properties]\nlongdouble_format = '{longdouble}'"

    def env(self):
        env = self.meson_env()
        env["CIBW_BEFORE_BUILD"] = ""
        if self.platform.sdk == SDK.android:
            env["CIBW_ENVIRONMENT_ANDROID"] = 'NPY_DISABLE_SVML=1 PKG_CONFIG_PATH=""'
            env["CIBW_CONFIG_SETTINGS_ANDROID"] = (
                f"setup-args=--cross-file={self.meson_cross_file_path} "
                f"setup-args=-Dblas=none setup-args=-Dlapack=none"
            )
            cross = self.meson_cross_file_path
            env["CIBW_BEFORE_BUILD_ANDROID"] = (
                'PYPREFIX=$(dirname "$CMAKE_TOOLCHAIN_FILE")/python/prefix; '
                'PYLIBDIR="$PYPREFIX/lib"; '
                'PCDIR="$PYLIBDIR/pkgconfig"; '
                'PC=$(ls "$PCDIR/python-3."*"-embed.pc" 2>/dev/null | head -1); '
                'if [ -n "$PC" ]; then '
                "VER=$(basename \"$PC\" | sed 's/python-//;s/-embed\\.pc//'); "
                'BROKEN="$PCDIR/python-${VER}.pc"; '
                '[ -f "$BROKEN" ] && cp "$PC" "$BROKEN"; '
                f"sed -i '' '/^\\[built-in options\\]/,$d' {cross}; "
                "{ echo ''; echo '[built-in options]'; "
                "echo \"c_link_args = ['-L${PYLIBDIR}', '-lpython${VER}']\"; "
                "echo \"cpp_link_args = ['-L${PYLIBDIR}', '-lpython${VER}']\"; "
                f"}} >> {cross}; fi"
            )
        return env

    def patches(self):
        return [
            "https://raw.githubusercontent.com/Py-Swift/LibraryPatches/refs/heads/master/numpy.patch",
        ]
