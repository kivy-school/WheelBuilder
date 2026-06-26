from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from wheelbuilder.platforminfo import SDK

_EXTRA_PATH = [
    "/usr/local/bin",
    "/opt/homebrew/bin",
    "/Library/Frameworks/Python.framework/Versions/3.13/bin",
]


def _augmented_path_env() -> dict[str, str]:
    env = os.environ.copy()
    current = env.get("PATH", "")
    env["PATH"] = ":".join([current, *_EXTRA_PATH])
    return env


def which(name: str) -> str:
    env = _augmented_path_env()
    path = shutil.which(name, path=env["PATH"])
    if path is None:
        raise FileNotFoundError(f"{name!r} not found on PATH")
    return path


def run(
    argv: list[str],
    env: dict[str, str] | None = None,
    cwd: str | Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    print(f"+ {' '.join(argv)}")
    return subprocess.run(argv, env=env, cwd=str(cwd) if cwd else None, check=check)


def run_capture(argv: list[str], env: dict[str, str] | None = None) -> str:
    res = subprocess.run(argv, env=env, check=True, capture_output=True, text=True)
    return res.stdout.strip()


def xcrun(*args: str) -> str:
    return run_capture(["xcrun", *args])


def android_api_level() -> str:
    return os.environ.get("ANDROID_API_LEVEL", "24")


def android_ndk_host() -> str:
    return os.environ.get("ANDROID_NDK_HOST", "darwin-x86_64")


def get_android_ndk() -> Path:
    ndk_home = os.environ.get("ANDROID_NDK_HOME")
    if not ndk_home:
        raise RuntimeError("ANDROID_NDK_HOME environment variable is not set")
    base = Path(ndk_home)
    if (base / "toolchains").exists():
        return base
    ndk_dir = base / "ndk"
    if ndk_dir.exists():
        children = sorted(
            (p for p in ndk_dir.iterdir() if p.is_dir()),
            key=lambda p: p.name,
            reverse=True,
        )
        if children:
            return children[0]
    raise RuntimeError(
        f"ANDROID_NDK_HOME={ndk_home} is not an NDK root. "
        f"Point it to e.g. .../ndk/27.3.13750724"
    )


def android_home() -> str:
    home = os.environ.get("ANDROID_HOME")
    if home:
        return home
    ndk_home = os.environ.get("ANDROID_NDK_HOME")
    if ndk_home:
        base = Path(ndk_home)
        if (base / "toolchains").exists():
            return str(base.parent.parent)
        if (base / "ndk").exists():
            return str(base)
    return ""


def get_sdk(sdk: SDK) -> Path:
    if sdk == SDK.android:
        sysroot = os.environ.get("ANDROID_SYSROOT")
        if sysroot:
            return Path(sysroot)
        host = android_ndk_host()
        return get_android_ndk() / "toolchains/llvm/prebuilt" / host / "sysroot"
    return Path(xcrun("--show-sdk-path", "--sdk", str(sdk)))


def get_macos_sdk() -> Path:
    return Path(xcrun("--show-sdk-path", "--sdk", "macosx"))


@contextmanager
def with_temp() -> Iterator[Path]:
    tmp = Path(tempfile.mkdtemp(prefix="wheelbuilder-"))
    try:
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def download_url(url: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = url.rsplit("/", 1)[-1] or "download"
    dest = dest_dir / name
    print(f"download {url} -> {dest}")
    with urllib.request.urlopen(url) as resp, open(dest, "wb") as fh:
        shutil.copyfileobj(resp, fh)
    return dest


def untar(tar_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    # Use system tar for full compatibility with .tar.gz / .tar.xz.
    run(["tar", "-xf", str(tar_path), "-C", str(destination)])


def download_tar_file(url: str, destination: Path) -> None:
    tar_path = download_url(url, destination)
    untar(tar_path, destination)
    tar_path.unlink(missing_ok=True)


def patch_file(file: Path, target: Path) -> None:
    run(["patch", "-t", "-d", str(target), "-p1", "-i", str(file)])


def patch_content(content: str, fn: str, target: Path) -> None:
    with with_temp() as tmp:
        pfile = tmp / f"{fn}.patch"
        pfile.write_text(content)
        patch_file(pfile, target)


def git_apply(file: Path, target: Path) -> None:
    run(["git", "apply", "--no-index", str(file)], cwd=target)


def pip_download(name: str, version: str | None, output: Path) -> Path | None:
    spec = f"{name}=={version}" if version else name
    run(
        [
            "pip3.13",
            "download",
            spec,
            "-d",
            str(output),
            "--no-deps",
            "--no-binary",
            ":all:",
        ]
    )
    for child in list(output.iterdir()):
        if child.suffix == ".gz":
            untar(child, output)
            child.unlink(missing_ok=True)
    name_lower = name.lower()
    for child in output.iterdir():
        if child.is_dir() and child.name.lower().startswith(name_lower):
            return child
    return None


def url_download(url: str, name: str, output: Path) -> Path | None:
    last = url.rsplit("/", 1)[-1]
    filename = last if last else f"{name}.tar.gz"
    destination = output / filename
    output.mkdir(parents=True, exist_ok=True)
    print(f"url_download {url} -> {destination} (name: {name})")
    with urllib.request.urlopen(url) as resp, open(destination, "wb") as fh:
        shutil.copyfileobj(resp, fh)
    for child in list(output.iterdir()):
        if child.suffix == ".gz":
            untar(child, output)
            child.unlink(missing_ok=True)
    for child in output.iterdir():
        if child.is_dir() and name in child.name:
            return child
    return None


def ndk_cmake_build(
    source_dir: Path,
    install_prefix: Path,
    arch: str,
    api: str | None = None,
    extra_args: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> None:
    """Cross-compile a CMake project for Android using the NDK toolchain.

    `arch` is the wheelbuilder Arch value ("arm64" or "x86_64"). `api` defaults
    to `android_api_level()`. Headers/libs land under `install_prefix/{include,lib}`.
    Builds static libs (BUILD_SHARED_LIBS=OFF) in Release mode using Ninja.
    """
    cmake = which("cmake")
    ninja = which("ninja")
    ndk = get_android_ndk()
    toolchain = ndk / "build/cmake/android.toolchain.cmake"
    if not toolchain.exists():
        raise RuntimeError(f"NDK CMake toolchain not found at {toolchain}")
    abi = "arm64-v8a" if arch == "arm64" else "x86_64"
    api_level = api or android_api_level()
    build_dir = source_dir / "_wb_build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    install_prefix.mkdir(parents=True, exist_ok=True)
    configure = [
        cmake,
        "-S", str(source_dir),
        "-B", str(build_dir),
        "-G", "Ninja",
        f"-DCMAKE_MAKE_PROGRAM={ninja}",
        f"-DCMAKE_TOOLCHAIN_FILE={toolchain}",
        f"-DANDROID_ABI={abi}",
        f"-DANDROID_PLATFORM=android-{api_level}",
        f"-DCMAKE_INSTALL_PREFIX={install_prefix}",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DBUILD_SHARED_LIBS=OFF",
    ]
    if extra_args:
        configure.extend(extra_args)
    run(configure, env=env)
    run([cmake, "--build", str(build_dir), "--target", "install"], env=env)


def cibuildwheel(
    target: Path,
    ci_platform: str,
    ci_archs: str,
    env: dict[str, str] | None,
    output: Path,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    before = {p: p.stat().st_mtime for p in output.iterdir()}
    result = run(
        [
            "cibuildwheel",
            str(target),
            "--platform",
            ci_platform,
            "--archs",
            ci_archs,
            "--output-dir",
            str(output),
        ],
        env=env,
        check=False,
    )
    if result.returncode != 0:
        after = {p: p.stat().st_mtime for p in output.iterdir()}
        new_or_updated = {p for p, t in after.items() if before.get(p) != t}
        if not new_or_updated:
            raise subprocess.CalledProcessError(result.returncode, result.args)
        print(
            f"cibuildwheel exited {result.returncode} but {len(new_or_updated)} wheel(s) built — "
            "some Python versions may not be installed locally."
        )
