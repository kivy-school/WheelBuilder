from __future__ import annotations

import copy
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from wheelbuilder import tools
from wheelbuilder.platforminfo import (
    CFlagInclude,
    CFlags,
    LDFlagLibrary,
    LDFlags,
    SDK,
)
from wheelbuilder.platforms import (
    Android_arm64,
    Android_x86_64,
    Iphoneos,
    IphoneSimulator_arm64,
    IphoneSimulator_x86_64,
    PlatformBase,
)


# -------------------------------------------------------------- BuildTarget


@dataclass
class BuildTarget:
    """Tagged enum mirroring Swift `BuildTarget`."""

    kind: str  # "pypi" | "local" | "url"
    value: str  # the pypi name, local path, or url

    @classmethod
    def pypi(cls, name: str) -> "BuildTarget":
        return cls("pypi", name)

    @classmethod
    def local(cls, path: str | Path) -> "BuildTarget":
        return cls("local", str(path))

    @classmethod
    def url(cls, url: str) -> "BuildTarget":
        return cls("url", url)

    def __str__(self) -> str:
        return self.value


# -------------------------------------------------------------- merge env


def _merge_env(extra: dict[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    env.update(extra)
    return env


# -------------------------------------------------------------- WheelBase


class WheelBase:
    """Replaces Swift `WheelProtocol`.

    Subclasses set class attributes `name` (defaults to lowercased class name)
    and optionally `build_target` (defaults to `BuildTarget.pypi(name)`).
    Override methods to customize per-wheel behavior.
    """

    # populated by __init_subclass__
    name: ClassVar[str] = ""

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Auto-derive name if subclass didn't set one.
        if "name" not in cls.__dict__ or not cls.__dict__.get("name"):
            cls.name = cls.__name__.lower()

    @property
    def build_target(self) -> BuildTarget:
        """Default: pypi target using self.name.  Subclasses override with a
        class-level attribute or a @property for instance-dependent targets."""
        return BuildTarget.pypi(self.name)

    def __init__(
        self,
        version: str | None,
        platform: PlatformBase,
        root: Path,
    ) -> None:
        self.version = version
        self.platform = platform
        self.root = root

    # --- overridable hooks ---

    def urls(self) -> list[str]:
        return []

    def patches(self) -> list[str]:
        return []

    def pre_build(self, target: Path) -> None:
        return None

    def _build_wheel(self, output: Path) -> bool:
        return False

    def dependencies_libraries(self) -> list[type["LibraryWheelBase"]]:
        return []

    def env(self) -> dict[str, str]:
        return self.base_env()

    def get_cflags(self) -> CFlags:
        # CFlags is mutable — copy so we don't mutate the platform's instance.
        flags = copy.deepcopy(self.platform.cflags)
        for dep in self.dependencies_libraries():
            lib = dep.new(version=None, platform=self.platform, root=self.root)
            flags.extend(lib.cflag_includes())
        return flags

    def get_ldflags(self) -> LDFlags:
        flags = copy.deepcopy(self.platform.ldflags)
        for dep in self.dependencies_libraries():
            lib = dep.new(version=None, platform=self.platform, root=self.root)
            flags.extend(lib.ldflag_libraries())
        return flags

    def base_env(self) -> dict[str, str]:
        extra = {
            "CFLAGS": str(self.get_cflags()),
            "LDFLAGS": str(self.get_ldflags()),
            "ANDROID_API_LEVEL": tools.android_api_level(),
        }
        if self.platform.sdk == SDK.android:
            home = tools.android_home()
            if home:
                extra["ANDROID_HOME"] = home
        return _merge_env(extra)

    def apply_patches(self, target: Path, working_dir: Path) -> None:
        for url in self.patches():
            patch_path = tools.download_url(url, working_dir)
            tools.patch_file(patch_path, target)

    @classmethod
    def source_version(cls) -> str | None:
        """Return a pinned version string for packages not sourced from PyPI.
        If None, compare_versions falls back to fetching the PyPI latest."""
        return None

    @classmethod
    def r2_name(cls) -> str:
        """Package name used to look up wheels in the R2 index.
        Defaults to cls.name; override when the wheel name differs from the
        registry key (e.g. 'ffmpeg' registry key but 'libffmpeg' wheel name)."""
        return cls.name

    @classmethod
    def supported_platforms(cls) -> list[PlatformBase]:
        return [
            Iphoneos(),
            IphoneSimulator_arm64(),
            IphoneSimulator_x86_64(),
            Android_arm64(),
            Android_x86_64(),
        ]

    @classmethod
    def new(cls, version: str | None, platform: PlatformBase, root: Path):
        return cls(version=version, platform=platform, root=root)


# -------------------------------------------------------------- CiWheelBase


class CiWheelBase(WheelBase):
    """Replaces Swift `CiWheelProtocol`.

    Default `build_wheel` dispatches on `build_target` kind and invokes
    cibuildwheel. Subclasses typically override `env()` and optionally
    `pre_build`/`patches`.
    """

    def build_wheel(
        self,
        working_dir: Path,
        version: str | None,
        wheels_dir: Path,
    ) -> None:
        self._wheels_dir = wheels_dir
        if self._build_wheel(working_dir):
            return
        bt = self.build_target
        if bt.kind == "local":
            target = Path(bt.value)
            self.pre_build(target)
            tools.cibuildwheel(
                target=target,
                ci_platform=self.platform.ci_platform,
                ci_archs=self.platform.ci_archs,
                env=self.env(),
                output=wheels_dir,
            )
            return
        if bt.kind == "pypi":
            folder = tools.pip_download(bt.value, version, working_dir)
            if folder is None:
                return
            self.pre_build(folder)
            self.apply_patches(folder, working_dir)
            tools.cibuildwheel(
                target=folder,
                ci_platform=self.platform.ci_platform,
                ci_archs=self.platform.ci_archs,
                env=self.env(),
                output=wheels_dir,
            )
            shutil.rmtree(folder, ignore_errors=True)
            return
        if bt.kind == "url":
            name = bt.value.rsplit("/", 1)[-1]
            folder = tools.url_download(bt.value, name, wheels_dir)
            if folder is None:
                return
            self.pre_build(folder)
            self.apply_patches(folder, working_dir)
            print(type(self).__name__, "cibuildwheel", folder)
            tools.cibuildwheel(
                target=folder,
                ci_platform=self.platform.ci_platform,
                ci_archs=self.platform.ci_archs,
                env=self.env(),
                output=wheels_dir,
            )
            shutil.rmtree(folder, ignore_errors=True)
            return


# -------------------------------------------------------------- LibraryWheelBase


class LibraryWheelBase(WheelBase):
    """Replaces Swift `LibraryWheelProtocol`.

    Subclass `new()` (here via metaclass-less classmethod) places `root`
    inside `<root>/<name>` to mirror Swift behavior.
    """

    @classmethod
    def new(cls, version: str | None, platform: PlatformBase, root: Path):
        return cls(version=version, platform=platform, root=root / cls.name)

    def pre_build_library(self, working_dir: Path) -> None:
        return None

    def build_library_platform(self, working_dir: Path) -> None:
        # mirrors Swift default which calls pre_build(target: working_dir)
        self.pre_build(working_dir)

    def post_build_library(self, working_dir: Path) -> None:
        return None

    def include_dir(self) -> Path:
        return self.root / f"{self.platform.sdk}_{self.platform.arch}" / "include"

    def lib_dir(self) -> Path:
        return self.root / f"{self.platform.sdk}_{self.platform.arch}" / "lib"

    def cflag_includes(self) -> list:
        return [CFlagInclude(self.include_dir())]

    def ldflag_libraries(self) -> list:
        return [LDFlagLibrary(self.lib_dir())]

    # Library wheels keep cflags/ldflags equal to the platform's (no dep recursion).
    def get_cflags(self) -> CFlags:
        return copy.deepcopy(self.platform.cflags)

    def get_ldflags(self) -> LDFlags:
        return copy.deepcopy(self.platform.ldflags)

    def base_env(self) -> dict[str, str]:
        return _merge_env(
            {
                "CFLAGS": str(self.get_cflags()),
                "LDFLAGS": str(self.get_ldflags()),
            }
        )


# -------------------------------------------------------------- MaturinWheelBase


class MaturinWheelBase(CiWheelBase):
    """Replaces Swift `MaturinWheelProtocol`."""

    def maturin_env(self) -> dict[str, str]:
        env = self.base_env()
        home = os.environ.get("HOME")
        if home:
            env["CARGO"] = f"{home}/.cargo/bin/cargo"
            env["RUSTC"] = f"{home}/.cargo/bin/rustc"
            current_path = env.get("PATH", "")
            env["PATH"] = f"{home}/.cargo/bin:{current_path}"

        if self.platform.sdk == SDK.android:
            env["SDKROOT"] = str(tools.get_macos_sdk())
            env["CIBW_XBUILD_TOOLS_ANDROID"] = "rustc cargo maturin"
        else:
            ios_sdkroot = self.platform.sdk_root()
            macos_sdkroot = tools.get_macos_sdk()

            env["CIBW_XBUILD_TOOLS_IOS"] = "cmake rustc cargo maturin"

            cargo_target_flags = [
                "-C", f"link-arg=-isysroot",
                "-C", f"link-arg={ios_sdkroot}",
                "-C", "link-arg=-arch",
                "-C", f"link-arg={self.platform.arch}",
                "-C", "link-arg=-undefined",
                "-C", "link-arg=dynamic_lookup",
            ]
            # Match Swift quoting: items were joined by " " — we mirror exactly.
            cargo_target = " ".join(
                [
                    "-C link-arg=-isysroot",
                    f"-C link-arg={ios_sdkroot}",
                    "-C link-arg=-arch",
                    f"-C link-arg={self.platform.arch}",
                    "-C link-arg=-undefined",
                    "-C link-arg=dynamic_lookup",
                ]
            )

            env["OSX_SDKROOT"] = str(macos_sdkroot)
            env["IOS_SDKROOT"] = str(ios_sdkroot)
            env["SDKROOT"] = str(macos_sdkroot)
            env[self.platform.cargo_target_key] = cargo_target
            env["MATURIN_PEP517_ARGS"] = f"--target {self.platform.maturin_target}"
            env["CIBW_ENVIRONMENT_IOS"] = " ".join(
                [
                    "PYO3_CROSS=1",
                    f'IOS_SDKROOT="{ios_sdkroot}"',
                    'PYO3_CROSS_PYTHON_VERSION=$(python3 -c \'import sys; v=sys.version_info; print(f"{v.major}.{v.minor}")\')',
                    'PYO3_CROSS_LIB_DIR=$(python3 -c \'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))\')',
                ]
            )
            env["CIBW_BUILD_FRONTEND"] = "build"
        return env

    def env(self) -> dict[str, str]:
        return self.maturin_env()


# -------------------------------------------------------------- MesonWheelBase


class MesonWheelBase(CiWheelBase):
    """Replaces Swift `MesonWheelProtocol`."""

    @property
    def meson_cross_file_path(self) -> str:
        return f"/tmp/{self.name}-android-meson-cross.ini"

    def meson_extra_ini_sections(self) -> str:
        return ""

    def write_meson_cross_file(self) -> None:
        if self.platform.sdk != SDK.android:
            return
        ndk = str(tools.get_android_ndk())
        api = tools.android_api_level()
        host = tools.android_ndk_host()
        if self.platform.arch.value == "arm64":
            triple, cpu = "aarch64-linux-android", "aarch64"
        else:
            triple, cpu = "x86_64-linux-android", "x86_64"
        bin_dir = f"{ndk}/toolchains/llvm/prebuilt/{host}/bin"
        content = (
            "[binaries]\n"
            f"c = '{bin_dir}/{triple}{api}-clang'\n"
            f"cpp = '{bin_dir}/{triple}{api}-clang++'\n"
            f"ar = '{bin_dir}/llvm-ar'\n"
            f"strip = '{bin_dir}/llvm-strip'\n"
            "\n"
            "[host_machine]\n"
            "system = 'android'\n"
            f"cpu_family = '{cpu}'\n"
            f"cpu = '{cpu}'\n"
            "endian = 'little'"
        )
        extra = self.meson_extra_ini_sections()
        if extra:
            content += "\n\n" + extra
        Path(self.meson_cross_file_path).write_text(content)

    def pre_build(self, target: Path) -> None:
        self.write_meson_cross_file()

    def meson_env(self) -> dict[str, str]:
        env = self.base_env()
        env["CIBW_XBUILD_TOOLS_IOS"] = "cmake ninja"
        env["CIBW_TEST_SKIP"] = "*"
        if self.platform.sdk == SDK.android:
            env["CIBW_CONFIG_SETTINGS_ANDROID"] = (
                f"setup-args=--cross-file={self.meson_cross_file_path}"
            )
            env["CIBW_BEFORE_BUILD_ANDROID"] = (
                'PYPREFIX=$(dirname "$CMAKE_TOOLCHAIN_FILE")/python/prefix; '
                'for f in "$PYPREFIX/lib/pkgconfig/python-"*.pc; do '
                '[ -f "$f" ] && ! [ -L "$f" ] || continue; '
                "VER=$(basename \"$f\" | sed 's/python-//;s/\\.pc//'); "
                "sed -i '' \"s/\\$(BLDLIBRARY)/-lpython${VER}/g\" \"$f\"; "
                "done"
            )
            env["CIBW_ENVIRONMENT_ANDROID"] = 'PKG_CONFIG_PATH=""'
        return env

    def env(self) -> dict[str, str]:
        return self.meson_env()
