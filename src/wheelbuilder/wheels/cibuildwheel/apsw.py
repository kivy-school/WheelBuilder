from pathlib import Path

from wheelbuilder.platforminfo import SDK
from wheelbuilder.protocols import CiWheelBase
from wheelbuilder.wheels.library.sqlite3 import Sqlite3


class Apsw(CiWheelBase):
    def dependencies_libraries(self):
        return [Sqlite3]

    def pre_build(self, target: Path) -> None:
        if self.platform.sdk != SDK.android:
            return
        setup_py = target / "setup.py"
        if not setup_py.exists():
            return
        src = setup_py.read_text()

        old = (
            '            if sys.platform != "win32":\n'
            '                write("    Running configure to work out SQLite compilation flags")\n'
            "                env = os.environ.copy()\n"
            '                for v in "CC", "CFLAGS", "LDFLAGS":\n'
            "                    val = sysconfig.get_config_var(v)\n"
            "                    if val:\n"
            "                        env[v] = val\n"
            '                subprocess.check_call(["./configure"], cwd="sqlite3", env=env)'
        )
        new = (
            '            if sys.platform != "win32" and "CMAKE_TOOLCHAIN_FILE" not in os.environ:\n'
            '                write("    Running configure to work out SQLite compilation flags")\n'
            "                env = os.environ.copy()\n"
            '                for v in "CC", "CFLAGS", "LDFLAGS":\n'
            "                    val = sysconfig.get_config_var(v)\n"
            "                    if val:\n"
            "                        env[v] = val\n"
            '                subprocess.check_call(["./configure"], cwd="sqlite3", env=env)'
        )
        if old not in src:
            print("Apsw.pre_build: configure block not found in setup.py — skipping patch")
            return
        setup_py.write_text(src.replace(old, new))

    def env(self):
        env = self.base_env()
        env["CIBW_TEST_SKIP"] = "*"
        return env
