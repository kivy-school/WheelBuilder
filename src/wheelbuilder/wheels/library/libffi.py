from pathlib import Path

from wheelbuilder import tools
from wheelbuilder.platforminfo import Arch, CFlagInclude, SDK
from wheelbuilder.protocols import BuildTarget, LibraryWheelBase

_DEFAULT_VERSION = "3.4.7-2"
_ANDROID_DEFAULT_VERSION = "3.4.4-3"


class Libffi(LibraryWheelBase):
    @property
    def build_target(self) -> BuildTarget:
        if self.platform.sdk == SDK.android:
            v = self.version or _ANDROID_DEFAULT_VERSION
            arch_triple = (
                "aarch64-linux-android"
                if self.platform.arch == Arch.arm64
                else "x86_64-linux-android"
            )
            return BuildTarget.url(
                f"https://github.com/beeware/cpython-android-source-deps/releases/download/libffi-{v}/libffi-{v}-{arch_triple}.tar.gz"
            )
        v = self.version or _DEFAULT_VERSION
        return BuildTarget.url(
            f"https://github.com/beeware/cpython-apple-source-deps/releases/download/libFFI-{v}/libffi-{v}-{self.platform.sdk}.{self.platform.arch}.tar.gz"
        )

    def cflag_includes(self):
        return [CFlagInclude(self.include_dir() / "ffi")]

    def pre_build_library(self, working_dir: Path) -> None:
        bt = self.build_target
        if bt.kind != "url":
            return
        tools.download_tar_file(bt.value, working_dir)

        for child in working_dir.iterdir():
            print(type(self).__name__, "found", child)

        libmain_folder = working_dir / "libffi"
        lib_platform = libmain_folder / f"{self.platform.sdk}_{self.platform.arch}"
        lib_platform.mkdir(parents=True, exist_ok=True)

        include = working_dir / "include"
        lib = working_dir / "lib"

        include_target = self.include_dir()
        include_target.mkdir(parents=True, exist_ok=True)

        include.rename(include_target / "ffi")
        lib.rename(self.lib_dir())

    def build_library_platform(self, working_dir: Path) -> None:
        return None

    def post_build_library(self, working_dir: Path) -> None:
        return None

    def _build_wheel(self, output: Path) -> bool:
        return True
