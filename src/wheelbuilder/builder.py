from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from enum import Enum
from pathlib import Path

from wheelbuilder import tools
from wheelbuilder.platforms import (
    Android_arm64,
    Android_x86_64,
    Iphoneos,
    IphoneSimulator_arm64,
    IphoneSimulator_x86_64,
    PlatformBase,
)
from wheelbuilder.protocols import CiWheelBase, LibraryWheelBase, WheelBase


class BuildPlatform(str, Enum):
    ios = "ios"
    android = "android"

    def __str__(self) -> str:
        return self.value


def resolve_platforms(
    filter_: BuildPlatform | None, wheel_cls: type[WheelBase] | None
) -> list[PlatformBase]:
    if filter_ == BuildPlatform.ios:
        filtered: list[PlatformBase] = [Iphoneos(), IphoneSimulator_arm64(), IphoneSimulator_x86_64()]
    elif filter_ == BuildPlatform.android:
        filtered = [Android_arm64(), Android_x86_64()]
    else:
        return wheel_cls.supported_platforms() if wheel_cls is not None else [
            Iphoneos(),
            IphoneSimulator_arm64(),
            IphoneSimulator_x86_64(),
            Android_arm64(),
            Android_x86_64(),
        ]
    if wheel_cls is not None:
        supported_types = {type(p) for p in wheel_cls.supported_platforms()}
        filtered = [p for p in filtered if type(p) in supported_types]
    return filtered


def build_wheels(
    wheel_cls: type[WheelBase],
    version: str | None,
    platform_filter: BuildPlatform | None,
    wheel_output: Path,
) -> list[str]:
    """Build wheels for all platforms. Returns a list of failure strings (empty = all OK)."""
    failures: list[str] = []
    with tools.with_temp() as working_dir:
        platforms = resolve_platforms(platform_filter, wheel_cls)
        for platform in platforms:
            wheel = wheel_cls.new(version=version, platform=platform, root=working_dir)

            # Library-only wheels: build the library, no cibuildwheel step.
            if isinstance(wheel, LibraryWheelBase) and not isinstance(wheel, CiWheelBase):
                wheel.pre_build_library(working_dir)
                wheel.build_library_platform(working_dir)
                wheel.post_build_library(working_dir)
                continue

            for lib_cls in wheel.dependencies_libraries():
                lib = lib_cls.new(version=None, platform=platform, root=working_dir)
                lib.pre_build_library(working_dir)
                lib.build_library_platform(working_dir)
                lib.post_build_library(working_dir)

            if isinstance(wheel, CiWheelBase):
                try:
                    wheel.build_wheel(working_dir, version, wheel_output)
                except Exception as exc:
                    label = f"{wheel_cls.name} [{platform.ci_platform}/{platform.ci_archs}]"
                    print(f"[FAILED] {label}: {exc}")
                    failures.append(label)
    return failures


def compare_versions(name: str, wheel_cls: type[WheelBase] | None = None) -> list[BuildPlatform]:
    """Return platforms whose latest R2-published wheel lags the source version.

    For packages with a pinned source_version() that is not from PyPI, that
    version is compared directly against R2.  For all others, the latest PyPI
    version is fetched.  If any lookup fails the function returns all build
    platforms (safe default).  When wheel_cls is given, only checks platforms
    that the wheel supports.
    """
    if wheel_cls is not None and wheel_cls.source_version() is not None:
        source_version = wheel_cls.source_version()
    else:
        source_version = _fetch_pypi_version(name)
    if source_version is None:
        return list(BuildPlatform)
    r2_key = wheel_cls.r2_name() if wheel_cls is not None else name
    files = _fetch_r2_files(r2_key)
    if files is None:
        return list(BuildPlatform)
    ios_versions = [f["version"] for f in files if _is_ios(f["basename"])]
    android_versions = [f["version"] for f in files if "android" in f["basename"]]
    ios_latest = max(ios_versions) if ios_versions else None
    android_latest = max(android_versions) if android_versions else None
    if wheel_cls is not None:
        sp = wheel_cls.supported_platforms()
        check_ios = any(isinstance(p, (Iphoneos, IphoneSimulator_arm64, IphoneSimulator_x86_64)) for p in sp)
        check_android = any(isinstance(p, (Android_arm64, Android_x86_64)) for p in sp)
    else:
        check_ios = True
        check_android = True
    needed: list[BuildPlatform] = []
    if check_ios and (ios_latest is None or source_version > ios_latest):
        needed.append(BuildPlatform.ios)
    if check_android and (android_latest is None or source_version > android_latest):
        needed.append(BuildPlatform.android)
    if needed:
        print(f"\n############# {name} #############")
        print(f"source version:  {source_version}")
        print(f"ios latest:      {ios_latest or 'missing'}")
        print(f"android latest:  {android_latest or 'missing'}")
        print(f"needs build:     {', '.join(p.value for p in needed)}")
        print("##########################################\n")
    return needed


def _is_ios(basename: str) -> bool:
    return "iphoneos" in basename or "iphonesimulator" in basename


def _fetch_pypi_version(name: str) -> str | None:
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json") as resp:
            data = json.load(resp)
    except (urllib.error.URLError, json.JSONDecodeError):
        return None
    info = data.get("info") or {}
    version = info.get("version")
    return version if isinstance(version, str) else None


R2_INDEX = "https://pypi-index.psychowaspx.workers.dev/simple"


def _fetch_r2_files(name: str) -> list[dict] | None:
    """Return [{basename, version}, ...] for all wheels in the R2 index for name."""
    import re
    normalized = re.sub(r"[-_.]+", "-", name).lower()
    url = f"{R2_INDEX}/{normalized}/"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "WheelBuilder/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode()
    except (urllib.error.URLError, OSError):
        return None
    files = []
    for href in re.findall(r'href="([^"]+\.whl)(?:#[^"]*)?"', html):
        basename = href.split("/")[-1].split("#")[0]
        parts = basename.split("-")
        if len(parts) >= 2:
            files.append({"basename": basename, "version": parts[1]})
    return files



