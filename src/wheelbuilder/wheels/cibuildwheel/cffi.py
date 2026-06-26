from pathlib import Path

from wheelbuilder.platforminfo import SDK
from wheelbuilder.protocols import CiWheelBase
from wheelbuilder.wheels.library.libffi import Libffi


class Cffi(CiWheelBase):
    def pre_build(self, target: Path) -> None:
        if self.platform.sdk != SDK.android:
            return
        libffi = Libffi.new(version=None, platform=self.platform, root=self.root)
        ffi_inc = str(libffi.include_dir() / "ffi")
        ffi_lib = str(libffi.lib_dir())
        setup = target / "setup.py"
        if not setup.exists():
            return
        contents = setup.read_text()
        contents = contents.replace(
            "include_dirs = ['/usr/include/ffi',\n                '/usr/include/libffi']    # may be changed by pkg-config",
            f"include_dirs = ['{ffi_inc}']",
        )
        contents = contents.replace("library_dirs = []", f"library_dirs = ['{ffi_lib}']")
        contents = contents.replace("else:\n    use_pkg_config()", "else:\n    pass")
        setup.write_text(contents)

    def dependencies_libraries(self):
        return [Libffi]

    # Swift extension overrides build_wheel to a no-op — preserve that behavior.
    def build_wheel(self, working_dir: Path, version, wheels_dir: Path) -> None:
        return None
