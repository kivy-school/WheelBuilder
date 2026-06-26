import shutil
from pathlib import Path

from wheelbuilder import tools
from wheelbuilder.platforminfo import SDK
from wheelbuilder.platforms import Android_arm64, Android_x86_64
from wheelbuilder.protocols import CiWheelBase
from wheelbuilder.wheels.library.freetype import Freetype
from wheelbuilder.wheels.library.libjpeg_turbo import Jpeg


class Pillow(CiWheelBase):
    # Pinned to the version the textual setup.py edits below are tested against.
    version = "11.3.0"

    @classmethod
    def supported_platforms(cls):
        # Pillow publishes official iOS wheels upstream; we only build Android.
        return [Android_arm64(), Android_x86_64()]

    def dependencies_libraries(self):
        if self.platform.sdk != SDK.android:
            return []
        # Build order matters: builder.build_wheels iterates this list in order
        # and Freetype's CMake call needs Harfbuzz's outputs to already exist.
        # zlib is an NDK system library staged by _stage_ndk_zlib().
        # HarfBuzz is not needed: raqm=none disables the only Pillow consumer of
        # HarfBuzz, and FreeType is built without HarfBuzz to keep it standalone.
        return [Jpeg, Freetype]

    def _zlib_stage_path(self) -> Path:
        """Consistent path for the staged zlib prefix within the build root."""
        return self.root / "zlib_stage" / f"{self.platform.sdk}_{self.platform.arch}"

    def pre_build(self, target: Path) -> None:
        if self.platform.sdk != SDK.android:
            return
        self._neutralise_host_probes(target / "setup.py")
        self._stage_ndk_zlib()

    def _stage_ndk_zlib(self) -> None:
        """Copy zlib.h and libz.a from the NDK sysroot into a flat prefix.

        The NDK puts libz.a at usr/lib/<triple>/libz.a (no API-level subdir)
        while zlib.h is at usr/include/zlib.h.  Pillow's ZLIB_ROOT detection
        expects both at <prefix>/include/ and <prefix>/lib/ respectively, so
        we create a staging prefix that satisfies that layout.
        """
        ndk_sysroot = tools.get_sdk(SDK.android)
        triple = (
            "aarch64-linux-android"
            if self.platform.arch.value == "arm64"
            else "x86_64-linux-android"
        )
        stage = self._zlib_stage_path()
        (stage / "include").mkdir(parents=True, exist_ok=True)
        (stage / "lib").mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            ndk_sysroot / "usr/include/zlib.h",
            stage / "include/zlib.h",
        )
        shutil.copy2(
            ndk_sysroot / f"usr/lib/{triple}/libz.a",
            stage / "lib/libz.a",
        )

    @staticmethod
    def _neutralise_host_probes(setup_py: Path) -> None:
        """Strip Pillow's host-machine library probing.

        On a cross-build the upstream `setup.py` would (a) shell out to
        `ldconfig`, (b) call host `pkg-config`, and (c) add the host Python
        prefix's `lib`/`include` to the search paths — all of which pollute
        the Android build with macOS libraries. We make three small textual
        edits to disable those branches.
        """
        original = setup_py.read_text()
        replacements = [
            (
                "def _find_library_dirs_ldconfig() -> list[str]:\n"
                "    # Based on ctypes.util from Python 2",
                "def _find_library_dirs_ldconfig() -> list[str]:\n"
                "    return []\n"
                "    # Based on ctypes.util from Python 2",
            ),
            (
                'if _cmd_exists(os.environ.get("PKG_CONFIG", "pkg-config")):\n'
                "            pkg_config = _pkg_config",
                'if False and _cmd_exists(os.environ.get("PKG_CONFIG", "pkg-config")):\n'
                "            pkg_config = _pkg_config",
            ),
            (
                '_add_directory(library_dirs, os.path.join(sys.prefix, "lib"))\n'
                '        _add_directory(include_dirs, os.path.join(sys.prefix, "include"))',
                '# wheelbuilder: skip host Python prefix injection during cross-build\n'
                '        # _add_directory(library_dirs, os.path.join(sys.prefix, "lib"))\n'
                '        # _add_directory(include_dirs, os.path.join(sys.prefix, "include"))',
            ),
        ]
        patched = original
        for needle, replacement in replacements:
            if needle not in patched:
                raise RuntimeError(
                    "Pillow setup.py neutralisation failed — expected snippet not found: "
                    f"{needle[:60]!r}..."
                )
            patched = patched.replace(needle, replacement, 1)
        setup_py.write_text(patched)

    def env(self):
        env = self.base_env()
        if self.platform.sdk != SDK.android:
            return env

        # Each LibraryWheelBase installs into <root>/<sdk>_<arch> with
        # standard lib/ + include/ subdirs — exactly what Pillow's *_ROOT
        # env vars expect as a prefix.
        jpeg = Jpeg.new(version=None, platform=self.platform, root=self.root)
        freetype = Freetype.new(version=None, platform=self.platform, root=self.root)

        jpeg_prefix = jpeg.include_dir().parent
        freetype_prefix = freetype.include_dir().parent

        # Staged flat prefix so Pillow's ZLIB_ROOT detection finds both
        # include/zlib.h and lib/libz.a (created in pre_build/_stage_ndk_zlib).
        zlib_prefix = self._zlib_stage_path()

        cibw_env = " ".join(
            [
                f'JPEG_ROOT="{jpeg_prefix}"',
                f'FREETYPE_ROOT="{freetype_prefix}"',
                f'ZLIB_ROOT="{zlib_prefix}"',
                # Disable host pkg-config (defence-in-depth; the setup.py edit
                # above already short-circuits this branch).
                "PKG_CONFIG=/nonexistent/wheelbuilder-disabled",
                'LDFLAGS="$LDFLAGS -lc++_shared -lm"',
            ]
        )
        env["CIBW_ENVIRONMENT_ANDROID"] = cibw_env
        # raqm=none: vendored raqm needs hb-ft.h (HarfBuzz+FreeType integration),
        # which is only installed when HarfBuzz is built with FreeType support —
        # but that creates a circular build dependency.  Disabling raqm is the
        # pragmatic choice for Android; basic FreeType text rendering still works.
        # platform-guessing=disable: prevents Pillow's setup.py from probing host
        # macOS paths (/usr/local, /opt/homebrew) and detecting libtiff, xcb, etc.
        # that cannot be linked into an Android .so.
        env["CIBW_CONFIG_SETTINGS_ANDROID"] = "raqm=none platform-guessing=disable"
        # Pillow's pyproject.toml sets before_all to install system deps via
        # a shell script that only exists in the git repo, not in the sdist.
        # Override it to a no-op since we pre-built all deps ourselves.
        env["CIBW_BEFORE_ALL_ANDROID"] = ""
        # Skip tests — the test script also lives in the git repo only.
        env["CIBW_TEST_SKIP"] = "*"
        return env