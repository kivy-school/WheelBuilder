from __future__ import annotations

from wheelbuilder import tools
from wheelbuilder.platforminfo import (
    Arch,
    CFlagInclude,
    CFlags,
    LDFlagLibrary,
    LDFlags,
    SDK,
)


class PlatformBase:
    sdk: SDK
    arch: Arch

    def __init__(self) -> None:
        self.cflags: CFlags
        self.ldflags: LDFlags

    # --- shared computed props (mirror Swift PlatformProtocol extension) ---

    @property
    def ci_archs(self) -> str:
        if self.sdk == SDK.android:
            return "arm64_v8a" if self.arch == Arch.arm64 else "x86_64"
        return f"{self.arch}_{self.sdk}"

    @property
    def ci_platform(self) -> str:
        if self.sdk in (SDK.iphoneos, SDK.iphonesimulator):
            return "ios"
        if self.sdk == SDK.android:
            return "android"
        raise RuntimeError(f"no support for sdk {self.sdk}")

    @property
    def sdk_arch(self) -> str:
        return f"{self.sdk}_{self.arch}"

    @property
    def arch_sdk(self) -> str:
        return f"{self.arch}_{self.sdk}"

    @property
    def wheel_file_platform(self) -> str:
        if self.sdk == SDK.android:
            abi = "arm64_v8a" if self.arch == Arch.arm64 else "x86_64"
            return f"android_{tools.android_api_level()}_{abi}"
        return f"ios_13_0_{self.arch}_{self.sdk}"

    @property
    def cargo_target_key(self) -> str:
        if self.sdk == SDK.iphoneos:
            return "CARGO_TARGET_AARCH64_APPLE_IOS_RUSTFLAGS"
        if self.sdk == SDK.iphonesimulator:
            return (
                "CARGO_TARGET_AARCH64_APPLE_IOS_SIM_RUSTFLAGS"
                if self.arch == Arch.arm64
                else "CARGO_TARGET_X86_64_APPLE_IOS_RUSTFLAGS"
            )
        if self.sdk == SDK.android:
            return (
                "CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER"
                if self.arch == Arch.arm64
                else "CARGO_TARGET_X86_64_LINUX_ANDROID_LINKER"
            )
        raise RuntimeError("no macos support")

    @property
    def maturin_target(self) -> str:
        if self.sdk == SDK.iphoneos:
            return "aarch64-apple-ios"
        if self.sdk == SDK.iphonesimulator:
            return "aarch64-apple-ios-sim" if self.arch == Arch.arm64 else "x86_64-apple-ios"
        if self.sdk == SDK.android:
            return "aarch64-linux-android" if self.arch == Arch.arm64 else "x86_64-linux-android"
        raise RuntimeError("no macos support")

    def sdk_root(self):
        return tools.get_sdk(self.sdk)


class Iphoneos(PlatformBase):
    sdk = SDK.iphoneos
    arch = Arch.arm64

    def __init__(self) -> None:
        sdk_root = tools.get_sdk(self.sdk)
        self.cflags = CFlags(sdk_root=sdk_root)
        self.ldflags = LDFlags(arch=self.arch)


class IphoneSimulator_arm64(PlatformBase):
    sdk = SDK.iphonesimulator
    arch = Arch.arm64

    def __init__(self) -> None:
        sdk_root = tools.get_sdk(self.sdk)
        self.cflags = CFlags(sdk_root=sdk_root)
        self.ldflags = LDFlags(arch=self.arch)


class IphoneSimulator_x86_64(PlatformBase):
    sdk = SDK.iphonesimulator
    arch = Arch.x86_64

    def __init__(self) -> None:
        sdk_root = tools.get_sdk(self.sdk)
        self.cflags = CFlags(sdk_root=sdk_root)
        self.ldflags = LDFlags(arch=self.arch)


class Android_arm64(PlatformBase):
    sdk = SDK.android
    arch = Arch.arm64

    def __init__(self) -> None:
        sysroot = tools.get_sdk(self.sdk)
        api = tools.android_api_level()
        self.cflags = CFlags(
            elements=[
                CFlagInclude(sysroot / "usr/include"),
                CFlagInclude(sysroot / "usr/include/aarch64-linux-android"),
            ]
        )
        self.ldflags = LDFlags(
            elements=[LDFlagLibrary(sysroot / f"usr/lib/aarch64-linux-android/{api}")]
        )


class Android_x86_64(PlatformBase):
    sdk = SDK.android
    arch = Arch.x86_64

    def __init__(self) -> None:
        sysroot = tools.get_sdk(self.sdk)
        api = tools.android_api_level()
        self.cflags = CFlags(
            elements=[
                CFlagInclude(sysroot / "usr/include"),
                CFlagInclude(sysroot / "usr/include/x86_64-linux-android"),
            ]
        )
        self.ldflags = LDFlags(
            elements=[LDFlagLibrary(sysroot / f"usr/lib/x86_64-linux-android/{api}")]
        )
