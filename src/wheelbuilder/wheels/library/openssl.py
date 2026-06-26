import shutil
from pathlib import Path

from wheelbuilder import tools
from wheelbuilder.platforminfo import Arch, CFlagInclude, SDK
from wheelbuilder.protocols import BuildTarget, LibraryWheelBase

_DEFAULT_VERSION = "3.0.17-1"
_ANDROID_DEFAULT_VERSION = "3.5.5-0"


class Openssl(LibraryWheelBase):
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
                f"https://github.com/beeware/cpython-android-source-deps/releases/download/openssl-{v}/openssl-{v}-{arch_triple}.tar.gz"
            )
        v = self.version or _DEFAULT_VERSION
        return BuildTarget.url(
            f"https://github.com/beeware/cpython-apple-source-deps/releases/download/OpenSSL-{v}/openssl-{v}-{self.platform.sdk}.{self.platform.arch}.tar.gz"
        )

    def pre_build_library(self, working_dir: Path) -> None:
        bt = self.build_target
        if bt.kind != "url":
            return
        tools.download_tar_file(bt.value, working_dir)

        openssl_folder = working_dir / "openssl"
        lib_platform = openssl_folder / f"{self.platform.sdk}_{self.platform.arch}"
        lib_platform.mkdir(parents=True, exist_ok=True)

        include = working_dir / "include"
        lib = working_dir / "lib"

        include_target = self.include_dir()
        include_target.mkdir(parents=True, exist_ok=True)

        shutil.copytree(include / "openssl", include_target / "openssl", dirs_exist_ok=True)
        lib.rename(self.lib_dir())

    def build_library_platform(self, working_dir: Path) -> None:
        return None

    def post_build_library(self, working_dir: Path) -> None:
        return None

    # Note: the Swift source returns include_dir + "ffi" here, which appears to be a
    # bug (should be openssl). Port verbatim — user explicitly asked not to change
    # Swift source semantics.
    def cflag_includes(self):
        return [CFlagInclude(self.include_dir() / "ffi")]
