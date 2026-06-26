from pathlib import Path

from wheelbuilder.platforminfo import SDK
from wheelbuilder.protocols import MesonWheelBase


class Matplotlib(MesonWheelBase):
    def env(self):
        env = self.meson_env()
        if self.platform.sdk == SDK.android:
            env["CIBW_ENVIRONMENT_ANDROID"] = (
                'CXXFLAGS="$CXXFLAGS -Wno-c++11-narrowing" PKG_CONFIG_PATH=""'
            )
        return env

    def pre_build(self, target: Path) -> None:
        pyproject = target / "pyproject.toml"
        contents = pyproject.read_text()
        contents = contents.replace(
            "meson-python>=0.13.1,<0.17.0",
            "meson-python>=0.13.1",
        )
        pyproject.write_text(contents)
        self.write_meson_cross_file()

    def patches(self):
        return []
