from pathlib import Path

from wheelbuilder.protocols import CiWheelBase


class Atom(CiWheelBase):
    def pre_build(self, target: Path) -> None:
        pyproject = target / "pyproject.toml"
        if not pyproject.exists():
            return
        contents = pyproject.read_text()
        if 'packages = ["atom"]' in contents:
            return
        contents = contents.replace(
            '  package-data = { atom = ["py.typed", "*.pyi"] }',
            '  package-data = { atom = ["py.typed", "*.pyi"] }\n  packages = ["atom"]',
        )
        pyproject.write_text(contents)
