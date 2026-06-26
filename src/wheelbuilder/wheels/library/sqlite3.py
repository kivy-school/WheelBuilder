from pathlib import Path

from wheelbuilder import tools
from wheelbuilder.platforminfo import Arch, CFlagInclude, LDFlagLibrary, SDK
from wheelbuilder.protocols import BuildTarget, LibraryWheelBase

_DEFAULT_VERSION = "3.49.1"


def _version_int(v: str) -> str:
    parts = [int(p) for p in v.split(".") if p.isdigit()]
    major = parts[0] if len(parts) > 0 else 3
    minor = parts[1] if len(parts) > 1 else 49
    patch = parts[2] if len(parts) > 2 else 1
    return str(major * 1_000_000 + minor * 10_000 + patch * 100)


class Sqlite3(LibraryWheelBase):
    @property
    def build_target(self) -> BuildTarget:
        v = self.version or _DEFAULT_VERSION
        vi = _version_int(v)
        return BuildTarget.url(f"https://www.sqlite.org/2025/sqlite-autoconf-{vi}.tar.gz")

    def pre_build_library(self, working_dir: Path) -> None:
        if self.platform.sdk != SDK.android:
            return

        v = self.version or _DEFAULT_VERSION
        vi = _version_int(v)
        url = f"https://www.sqlite.org/2025/sqlite-autoconf-{vi}.tar.gz"

        tools.download_tar_file(url, working_dir)

        src_dir = working_dir / f"sqlite-autoconf-{vi}"

        ndk = tools.get_android_ndk()
        host = tools.android_ndk_host()
        api = tools.android_api_level()
        bin_dir = ndk / "toolchains/llvm/prebuilt" / host / "bin"

        triple = (
            f"aarch64-linux-android{api}"
            if self.platform.arch == Arch.arm64
            else f"x86_64-linux-android{api}"
        )

        clang = bin_dir / f"{triple}-clang"
        llvm_ar = bin_dir / "llvm-ar"

        obj_file = src_dir / "sqlite3.o"
        tools.run(
            [
                str(clang),
                "-O2",
                "-c",
                str(src_dir / "sqlite3.c"),
                "-o",
                str(obj_file),
                "-DSQLITE_THREADSAFE=1",
                "-DSQLITE_ENABLE_FTS5",
            ]
        )

        lib_file = src_dir / "libsqlite3.a"
        tools.run([str(llvm_ar), "rcs", str(lib_file), str(obj_file)])

        inc_dir = self.include_dir()
        lib_dir = self.lib_dir()
        inc_dir.mkdir(parents=True, exist_ok=True)
        lib_dir.mkdir(parents=True, exist_ok=True)

        import shutil

        shutil.copy2(src_dir / "sqlite3.h", inc_dir / "sqlite3.h")
        shutil.copy2(lib_file, lib_dir / "libsqlite3.a")

    def build_library_platform(self, working_dir: Path) -> None:
        return None

    def post_build_library(self, working_dir: Path) -> None:
        return None

    def cflag_includes(self):
        if self.platform.sdk != SDK.android:
            return []
        return [CFlagInclude(self.include_dir())]

    def ldflag_libraries(self):
        if self.platform.sdk != SDK.android:
            return []
        return [LDFlagLibrary(self.lib_dir())]
