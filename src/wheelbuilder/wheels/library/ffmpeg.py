import os
import shutil
from pathlib import Path

from wheelbuilder import tools
from wheelbuilder.patches import ffmpeg_android15_patch, ffmpeg_configure_patch
from wheelbuilder.platforminfo import Arch, SDK
from wheelbuilder.protocols import BuildTarget, CiWheelBase

_DEFAULT_VERSION = "8.0.1"


class Ffmpeg(CiWheelBase):
    @classmethod
    def source_version(cls) -> str:
        return _DEFAULT_VERSION

    @classmethod
    def r2_name(cls) -> str:
        return "libffmpeg"

    @property
    def build_target(self) -> BuildTarget:
        v = self.version or _DEFAULT_VERSION
        return BuildTarget.url(f"https://www.ffmpeg.org/releases/ffmpeg-{v}.tar.xz")

    def build_wheel(self, working_dir: Path, version, wheels_dir: Path) -> None:
        v = version or _DEFAULT_VERSION
        sdk = self.platform.sdk
        if sdk == SDK.android:
            self._build_android(working_dir, v, wheels_dir)
        elif sdk in (SDK.iphoneos, SDK.iphonesimulator):
            self._build_ios(working_dir, v, wheels_dir)

    # ------------------------------------------------------------------- Android

    def _build_android(self, working_dir: Path, version: str, wheels_dir: Path) -> None:
        url = f"https://www.ffmpeg.org/releases/ffmpeg-{version}.tar.xz"

        ndk = tools.get_android_ndk()
        host = tools.android_ndk_host()
        api = tools.android_api_level()
        bin_dir = ndk / "toolchains/llvm/prebuilt" / host / "bin"
        sysroot = ndk / "toolchains/llvm/prebuilt" / host / "sysroot"

        if self.platform.arch == Arch.arm64:
            triple = "aarch64-linux-android"
            arch_flag = "aarch64"
            extra: list[str] = []
        else:
            triple = "x86_64-linux-android"
            arch_flag = "x86"
            extra = ["--disable-asm"]

        clang_triple = f"{triple}{api}"
        cross_prefix = str(bin_dir / f"{clang_triple}-")

        arch_work_dir = working_dir / arch_flag
        arch_work_dir.mkdir(parents=True, exist_ok=True)
        tools.download_tar_file(url, arch_work_dir)
        src_dir = arch_work_dir / f"ffmpeg-{version}"

        tools.patch_content(ffmpeg_configure_patch, "configure", src_dir)

        if not (src_dir / "compat/android/binder.c").exists():
            with tools.with_temp() as tmp:
                patch_file = tmp / "android15.patch"
                patch_file.write_text(ffmpeg_android15_patch)
                tools.git_apply(patch_file, src_dir)

        env = {
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "CC": str(bin_dir / f"{clang_triple}-clang"),
            "CXX": str(bin_dir / f"{clang_triple}-clang++"),
            "AR": str(bin_dir / "llvm-ar"),
            "RANLIB": str(bin_dir / "llvm-ranlib"),
            "NM": str(bin_dir / "llvm-nm"),
            "STRIP": str(bin_dir / "llvm-strip"),
        }

        configure_args = [
            "--enable-jni",
            "--enable-mediacodec",
            "--disable-symver",
            "--disable-doc",
            "--enable-filter=aresample,resample,crop,adelay,volume,scale",
            "--enable-protocol=file,http,hls,udp,tcp",
            "--enable-small",
            "--enable-hwaccels",
            "--enable-pic",
            "--disable-static",
            "--disable-debug",
            "--enable-shared",
            "--enable-parser=aac,ac3,h261,h264,mpegaudio,mpeg4video,mpegvideo,vc1",
            "--enable-decoder=aac,h264,mpeg4,mpegvideo",
            "--enable-muxer=h264,mov,mp4,mpeg2video",
            "--enable-demuxer=aac,h264,m4v,mov,mpegvideo,vc1,rtsp",
            "--target-os=android",
            "--enable-cross-compile",
            f"--cross-prefix={cross_prefix}",
            f"--arch={arch_flag}",
            f"--strip={bin_dir / 'llvm-strip'}",
            f"--nm={bin_dir / 'llvm-nm'}",
            f"--sysroot={sysroot}",
            "--enable-neon",
            f"--prefix={src_dir}",
        ] + extra

        tools.run([str(src_dir / "configure"), *configure_args], env=env, cwd=src_dir)
        cpu = os.cpu_count() or 4
        tools.run(["/usr/bin/make", "-j", str(cpu)], env=env, cwd=src_dir)
        tools.run(["/usr/bin/make", "install"], env=env, cwd=src_dir)

        libs_dir = src_dir / "lib"
        include_dir = src_dir / "include"
        ffmpeg_bin = src_dir / "ffmpeg"
        if ffmpeg_bin.exists():
            shutil.copy2(ffmpeg_bin, libs_dir / "libffmpegbin.so")

        self._package_android(libs_dir, include_dir, version, wheels_dir)

    # ----------------------------------------------------------------------- iOS

    def _build_ios(self, working_dir: Path, version: str, wheels_dir: Path) -> None:
        sdk = self.platform.sdk
        arch = self.platform.arch
        sysroot = tools.get_sdk(sdk)
        url = f"https://www.ffmpeg.org/releases/ffmpeg-{version}.tar.xz"

        if sdk == SDK.iphoneos and arch == Arch.arm64:
            ffmpeg_arch, arch_str, target_triple = "aarch64", "arm64", "arm64-apple-ios13.0"
            extra_flags: list[str] = []
        elif sdk == SDK.iphonesimulator and arch == Arch.arm64:
            ffmpeg_arch, arch_str, target_triple = (
                "aarch64",
                "arm64",
                "arm64-apple-ios13.0-simulator",
            )
            extra_flags = []
        elif sdk == SDK.iphonesimulator and arch == Arch.x86_64:
            ffmpeg_arch, arch_str, target_triple = (
                "x86_64",
                "x86_64",
                "x86_64-apple-ios13.0-simulator",
            )
            extra_flags = ["--disable-asm"]
        else:
            return

        arch_work_dir = working_dir / f"{sdk}_{arch}"
        arch_work_dir.mkdir(parents=True, exist_ok=True)
        tools.download_tar_file(url, arch_work_dir)
        src_dir = arch_work_dir / f"ffmpeg-{version}"

        tools.patch_content(ffmpeg_configure_patch, "configure", src_dir)

        cc = tools.xcrun("--sdk", sdk.value, "--find", "clang")
        cxx = tools.xcrun("--sdk", sdk.value, "--find", "clang++")
        ar = tools.xcrun("--sdk", sdk.value, "--find", "ar")
        ranlib = tools.xcrun("--sdk", sdk.value, "--find", "ranlib")
        nm = tools.xcrun("--sdk", sdk.value, "--find", "nm")
        strip = tools.xcrun("--sdk", sdk.value, "--find", "strip")

        extra_cflags = f"-arch {arch_str} -target {target_triple} -isysroot {sysroot}"
        extra_ldflags = extra_cflags

        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "CC": cc,
            "CXX": cxx,
            "AR": ar,
            "RANLIB": ranlib,
            "NM": nm,
            "STRIP": strip,
            "SDKROOT": str(sysroot),
        }

        configure_args = [
            "--target-os=darwin",
            "--enable-cross-compile",
            f"--arch={ffmpeg_arch}",
            f"--sysroot={sysroot}",
            "--host-cc=/usr/bin/clang",
            "--disable-videotoolbox",
            f"--extra-cflags={extra_cflags}",
            f"--extra-ldflags={extra_ldflags}",
            "--enable-shared",
            "--disable-static",
            "--enable-pic",
            "--disable-debug",
            "--disable-doc",
            "--disable-programs",
            "--disable-symver",
            "--enable-filter=aresample,resample,crop,adelay,volume,scale",
            "--enable-protocol=file,http,hls,udp,tcp",
            "--enable-small",
            "--enable-hwaccels",
            "--enable-parser=aac,ac3,h261,h264,mpegaudio,mpeg4video,mpegvideo,vc1",
            "--enable-decoder=aac,h264,mpeg4,mpegvideo",
            "--enable-muxer=h264,mov,mp4,mpeg2video",
            "--enable-demuxer=aac,h264,m4v,mov,mpegvideo,vc1,rtsp",
            f"--prefix={src_dir}",
        ] + extra_flags

        tools.run([str(src_dir / "configure"), *configure_args], env=env, cwd=src_dir)
        cpu = os.cpu_count() or 4
        tools.run(["/usr/bin/make", "-j", str(cpu)], env=env, cwd=src_dir)
        tools.run(["/usr/bin/make", "install"], env=env, cwd=src_dir)

        self._package_ios(src_dir / "lib", src_dir / "include", version, wheels_dir)

    # ----------------------------------------------------------------- packaging

    def _package_ios(
        self, libs_dir: Path, include_dir: Path, version: str, wheels_dir: Path
    ) -> None:
        platform_tag = self.platform.wheel_file_platform
        wheel_name = f"libffmpeg-{version}-py3-none-{platform_tag}.whl"

        with tools.with_temp() as staging:
            pkg = staging / "libffmpeg"
            dot_fw = staging / ".frameworks"
            dot_inc = staging / ".includes"
            dist_info = staging / f"libffmpeg-{version}.dist-info"
            for d in (pkg, dot_fw, dot_inc, dist_info):
                d.mkdir(parents=True, exist_ok=True)
            (pkg / "__init__.py").write_text("")

            for dylib in libs_dir.iterdir():
                if dylib.suffix != ".dylib":
                    continue
                if dylib.name.count(".") != 1:
                    continue
                lib_name = dylib.stem
                xc_out = dot_fw / f"{lib_name}.xcframework"
                xc_args = ["-create-xcframework", "-library", str(dylib)]
                headers_dir = include_dir / lib_name
                if headers_dir.exists():
                    xc_args += ["-headers", str(headers_dir)]
                xc_args += ["-output", str(xc_out)]
                tools.run(["/usr/bin/xcodebuild", *xc_args], cwd=staging)

            if include_dir.exists():
                shutil.copytree(include_dir, dot_inc / "ffmpeg")

            (dist_info / "METADATA").write_text(
                "Metadata-Version: 2.1\n"
                "Name: libffmpeg\n"
                f"Version: {version}\n"
                "Summary: FFmpeg shared libraries for iOS\n"
                "Home-page: https://ffmpeg.org\n"
                "License: LGPL-2.1\n"
                "Platform: iOS"
            )
            (dist_info / "WHEEL").write_text(
                "Wheel-Version: 1.0\n"
                "Generator: WheelBuilder\n"
                "Root-Is-Purelib: false\n"
                f"Tag: py3-none-{platform_tag}"
            )
            (dist_info / "RECORD").write_text("")

            wheels_dir.mkdir(parents=True, exist_ok=True)
            wheel_path = wheels_dir / wheel_name
            tools.run(
                [
                    "/usr/bin/zip",
                    "-r",
                    str(wheel_path),
                    "libffmpeg",
                    ".frameworks",
                    ".includes",
                    f"libffmpeg-{version}.dist-info",
                ],
                cwd=staging,
            )

    def _package_android(
        self, libs_dir: Path, include_dir: Path, version: str, wheels_dir: Path
    ) -> None:
        abi_tag = "arm64_v8a" if self.platform.arch == Arch.arm64 else "x86_64"
        api = tools.android_api_level()
        platform_tag = f"android_{api}_{abi_tag}"
        wheel_name = f"libffmpeg-{version}-py3-none-{platform_tag}.whl"

        with tools.with_temp() as staging:
            pkg = staging / "libffmpeg"
            dot_libs = staging / ".libs"
            dot_inc = staging / ".includes"
            dist_info = staging / f"libffmpeg-{version}.dist-info"
            for d in (pkg, dot_libs, dot_inc, dist_info):
                d.mkdir(parents=True, exist_ok=True)
            (pkg / "__init__.py").write_text("")

            for so in libs_dir.iterdir():
                if so.suffix == ".so":
                    shutil.copy2(so, dot_libs / so.name)

            if include_dir.exists():
                shutil.copytree(include_dir, dot_inc / "ffmpeg")

            (dist_info / "METADATA").write_text(
                "Metadata-Version: 2.1\n"
                "Name: libffmpeg\n"
                f"Version: {version}\n"
                "Summary: FFmpeg shared libraries for Android\n"
                "Home-page: https://ffmpeg.org\n"
                "License: LGPL-2.1\n"
                "Platform: Android"
            )
            (dist_info / "WHEEL").write_text(
                "Wheel-Version: 1.0\n"
                "Generator: WheelBuilder\n"
                "Root-Is-Purelib: false\n"
                f"Tag: py3-none-{platform_tag}"
            )
            (dist_info / "RECORD").write_text("")

            wheels_dir.mkdir(parents=True, exist_ok=True)
            wheel_path = wheels_dir / wheel_name
            tools.run(
                [
                    "/usr/bin/zip",
                    "-r",
                    str(wheel_path),
                    "libffmpeg",
                    ".libs",
                    ".includes",
                    f"libffmpeg-{version}.dist-info",
                ],
                cwd=staging,
            )
