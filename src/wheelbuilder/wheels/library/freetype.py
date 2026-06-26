from pathlib import Path

from wheelbuilder import tools
from wheelbuilder.platforminfo import CFlagInclude, SDK
from wheelbuilder.protocols import BuildTarget, LibraryWheelBase

_DEFAULT_VERSION = "2.13.3"


class Freetype(LibraryWheelBase):
    @property
    def build_target(self) -> BuildTarget:
        v = self.version or _DEFAULT_VERSION
        return BuildTarget.url(
            f"https://download.savannah.gnu.org/releases/freetype/freetype-{v}.tar.xz"
        )

    def pre_build_library(self, working_dir: Path) -> None:
        if self.platform.sdk != SDK.android:
            return
        v = self.version or _DEFAULT_VERSION
        tools.download_tar_file(self.build_target.value, working_dir)
        src = working_dir / f"freetype-{v}"
        prefix = self.include_dir().parent

        # Build FreeType without HarfBuzz and without zlib so that libfreetype.a
        # is self-contained.  Pillow links _imagingft.so with only -lfreetype;
        # adding transitive deps (harfbuzz, zlib) would require patching Pillow's
        # setup.py further.  Gzip-compressed font loading and HarfBuzz-assisted
        # glyph shaping are acceptable losses for Android cross-builds.
        tools.ndk_cmake_build(
            source_dir=src,
            install_prefix=prefix,
            arch=str(self.platform.arch),
            extra_args=[
                "-DFT_DISABLE_BZIP2=ON",
                "-DFT_DISABLE_BROTLI=ON",
                "-DFT_DISABLE_PNG=ON",
                "-DFT_DISABLE_ZLIB=ON",
                "-DFT_DISABLE_HARFBUZZ=ON",
            ],
        )

    def build_library_platform(self, working_dir: Path) -> None:
        return None

    def post_build_library(self, working_dir: Path) -> None:
        return None

    def _build_wheel(self, output: Path) -> bool:
        return True

    def cflag_includes(self):
        if self.platform.sdk != SDK.android:
            return []
        # Pillow's setup.py expects to find `ft2build.h` either directly in
        # an include dir or under `<dir>/freetype2/`. CMake installs freetype
        # headers to `<prefix>/include/freetype2/`. Expose both to be safe.
        return [
            CFlagInclude(self.include_dir()),
            CFlagInclude(self.include_dir() / "freetype2"),
        ]
