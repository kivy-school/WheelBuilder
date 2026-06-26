from __future__ import annotations

from itertools import groupby
from pathlib import Path


class RepoFolder:
    """Generates a PEP 503 simple-index HTML repo from a folder of wheels.

    Mirrors Swift `PipRepo.RepoFolder` 1:1.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        wheels = sorted(p for p in root.iterdir() if _whl_or_gz(p))
        groups: list[WheelFolder] = []
        for key, items in groupby(wheels, key=_whl_name):
            paths = list(items)
            print((key, paths))
            groups.append(WheelFolder(name=key, wheels=paths))
        self.folders = groups

    def _html_elements(self) -> str:
        return "\n".join(f.html_element() for f in self.folders)

    def html(self) -> str:
        return f"<!DOCTYPE html><html><body>\n{self._html_elements()}\n</body></html>"

    def generate_simple(self, output: Path) -> None:
        simple = output / "simple"
        simple.mkdir(parents=True, exist_ok=True)
        (simple / "index.html").write_text(self.html())
        for wheel in self.folders:
            wheel.generate_index(simple)


class WheelFolder:
    def __init__(self, name: str, wheels: list[Path]) -> None:
        self.name = name
        self.wheels = wheels

    def html_element(self) -> str:
        return f'<a href="{self.name}/">{self.name}</a></br>'

    def _html_elements(self) -> str:
        return "\n".join(_html_whl_element(w) for w in self.wheels)

    def html(self) -> str:
        return f"<!DOCTYPE html><html><body>\n{self._html_elements()}\n</body></html>"

    def generate_index(self, output: Path) -> None:
        root = output / self.name
        root.mkdir(parents=True, exist_ok=True)
        (root / "index.html").write_text(self.html())


def _whl_or_gz(p: Path) -> bool:
    return p.suffix in (".whl", ".gz")


def _whl_name(p: Path) -> str:
    return p.name.split("-", 1)[0].lower()


def _html_whl_element(p: Path) -> str:
    return f'<a href="../../{p.name}">{p.name}</a></br>'
