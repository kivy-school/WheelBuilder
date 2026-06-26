from pathlib import Path

from wheelbuilder.platforminfo import SDK
from wheelbuilder.protocols import CiWheelBase


class Netifaces(CiWheelBase):
    def pre_build(self, target: Path) -> None:
        if self.platform.sdk != SDK.android:
            return
        setup = target / "setup.py"
        if not setup.exists():
            return
        contents = setup.read_text()
        contents = contents.replace(
            "def test_build(self, contents, link=True, execute=False,",
            "def test_build(self, contents, link=False, execute=False,",
        )
        setup.write_text(contents)
