from pathlib import Path

from wheelbuilder import tools
from wheelbuilder.platforminfo import SDK
from wheelbuilder.protocols import BuildTarget, LibraryWheelBase

_DEFAULT_VERSION = "3.0.4"


class Jpeg(LibraryWheelBase):
    @property
    def build_target(self) -> BuildTarget:
        v = self.version or _DEFAULT_VERSION
        return BuildTarget.url(
            f"https://github.com/libjpeg-turbo/libjpeg-turbo/releases/download/{v}/libjpeg-turbo-{v}.tar.gz"
        )

    def pre_build_library(self, working_dir: Path) -> None:
        if self.platform.sdk != SDK.android:
            return
        v = self.version or _DEFAULT_VERSION
        tools.download_tar_file(self.build_target.value, working_dir)
        src = working_dir / f"libjpeg-turbo-{v}"
        prefix = self.include_dir().parent
        tools.ndk_cmake_build(
            source_dir=src,
            install_prefix=prefix,
            arch=str(self.platform.arch),
            extra_args=[
                "-DENABLE_SHARED=OFF",
                "-DENABLE_STATIC=ON",
                "-DWITH_TURBOJPEG=OFF",
                "-DWITH_JPEG8=ON",
            ],
        )

    def build_library_platform(self, working_dir: Path) -> None:
        return None

    def post_build_library(self, working_dir: Path) -> None:
        return None

    def _build_wheel(self, output: Path) -> bool:
        return True
