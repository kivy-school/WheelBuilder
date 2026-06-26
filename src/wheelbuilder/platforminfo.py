from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class SDK(str, Enum):
    iphoneos = "iphoneos"
    iphonesimulator = "iphonesimulator"
    macos = "macos"
    android = "android"

    def __str__(self) -> str:
        return self.value


class Arch(str, Enum):
    arm64 = "arm64"
    x86_64 = "x86_64"

    def __str__(self) -> str:
        return self.value


@dataclass
class CFlagInclude:
    path: Path

    def __str__(self) -> str:
        return f"-I{self.path}"


@dataclass
class LDFlagArch:
    arch: Arch

    def __str__(self) -> str:
        return f"-arch {self.arch}"


@dataclass
class LDFlagFramework:
    name: str

    def __str__(self) -> str:
        return f"-framework {self.name}"


@dataclass
class LDFlagLibrary:
    path: Path

    def __str__(self) -> str:
        return f"-L{self.path}"


@dataclass
class LDFlagFrameworkPath:
    path: Path

    def __str__(self) -> str:
        return f"-F{self.path}"


class CFlags:
    def __init__(self, elements: list | None = None, sdk_root: Path | None = None) -> None:
        if sdk_root is not None:
            self.elements: list = [CFlagInclude(sdk_root / "usr/include")]
        else:
            self.elements = list(elements) if elements else []

    def append(self, value) -> None:
        self.elements.append(value)

    def extend(self, values) -> None:
        self.elements.extend(values)

    def __str__(self) -> str:
        return " ".join(str(e) for e in self.elements)


class LDFlags:
    def __init__(self, elements: list | None = None, arch: Arch | None = None) -> None:
        if arch is not None:
            self.elements: list = [LDFlagArch(arch)]
        else:
            self.elements = list(elements) if elements else []

    def append(self, value) -> None:
        self.elements.append(value)

    def extend(self, values) -> None:
        self.elements.extend(values)

    def __str__(self) -> str:
        return " ".join(str(e) for e in self.elements)
