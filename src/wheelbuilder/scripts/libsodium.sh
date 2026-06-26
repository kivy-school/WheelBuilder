#!/bin/bash
# Cross-compile libsodium from source (skips 'make check').
# Usage: libsodium.sh <src_dir> <install_prefix>
# Detects target platform via Python sysconfig (reliable in cibuildwheel BEFORE_BUILD).
set -euo pipefail

SRC_DIR="$1"
PREFIX="$2"

# sysconfig.get_platform() format examples:
#   ios-13.0-arm64-iphoneos
#   ios-13.0-arm64-iphonesimulator
#   ios-13.0-x86_64-iphonesimulator
#   android-24-arm64 / android-24-x86_64
PLAT=$(python3 -c "import sysconfig; print(sysconfig.get_platform())" 2>/dev/null || echo "")
echo "=== libsodium.sh: PLAT='$PLAT' CC='${CC:-}' NDK='${ANDROID_NDK_HOME:-}' ==="

HOST=""
IOS_SDK=""

case "$PLAT" in
    ios-*-arm64-iphoneos)
        HOST="arm-apple-darwin"
        IOS_SDK="iphoneos"
        ;;
    ios-*-arm64-iphonesimulator)
        HOST="arm-apple-darwin"
        IOS_SDK="iphonesimulator"
        ;;
    ios-*-x86_64-iphonesimulator)
        HOST="x86_64-apple-darwin"
        IOS_SDK="iphonesimulator"
        ;;
    android-*-arm64|android-*-aarch64)
        HOST="aarch64-linux-android"
        API="${ANDROID_API_LEVEL:-24}"
        NDK="${ANDROID_NDK_HOME:?ANDROID_NDK_HOME must be set}"
        TC="$NDK/toolchains/llvm/prebuilt/darwin-x86_64/bin"
        export CC="$TC/aarch64-linux-android${API}-clang"
        export CXX="$TC/aarch64-linux-android${API}-clang++"
        export AR="$TC/llvm-ar"
        export RANLIB="$TC/llvm-ranlib"
        ;;
    android-*-x86_64)
        HOST="x86_64-linux-android"
        API="${ANDROID_API_LEVEL:-24}"
        NDK="${ANDROID_NDK_HOME:?ANDROID_NDK_HOME must be set}"
        TC="$NDK/toolchains/llvm/prebuilt/darwin-x86_64/bin"
        export CC="$TC/x86_64-linux-android${API}-clang"
        export CXX="$TC/x86_64-linux-android${API}-clang++"
        export AR="$TC/llvm-ar"
        export RANLIB="$TC/llvm-ranlib"
        ;;
    *)
        # Fallback: sniff from CC full path
        CC_VAL="${CC:-}"
        if echo "$CC_VAL" | grep -q 'linux-android'; then
            HOST=$(basename "$(echo "$CC_VAL" | awk '{print $1}')" | sed 's/[0-9]*-clang.*$//')
        elif echo "$CC_VAL" | grep -qE '(x86_64).*(simulator|ios)|(simulator|ios).*(x86_64)'; then
            HOST="x86_64-apple-darwin"
        elif echo "$CC_VAL" | grep -qiE '(arm64|aarch64).*(simulator|iphoneos|ios)|(simulator|iphoneos|ios).*(arm64|aarch64)'; then
            HOST="arm-apple-darwin"
        fi
        ;;
esac

if [ -n "$IOS_SDK" ]; then
    SYSROOT=$(xcrun --sdk "$IOS_SDK" --show-sdk-path)
    export CC="$(xcrun --sdk "$IOS_SDK" -f clang)"
    export CXX="$(xcrun --sdk "$IOS_SDK" -f clang++)"
    export AR="$(xcrun --sdk "$IOS_SDK" -f ar)"
    case "$HOST" in
        x86_64-*) ARCH_FLAG="-arch x86_64" ;;
        *) ARCH_FLAG="-arch arm64" ;;
    esac
    export CFLAGS="${CFLAGS:-} -isysroot $SYSROOT $ARCH_FLAG"
fi

echo "Using HOST='$HOST' CC='${CC:-}'"

mkdir -p "$PREFIX"
BUILD_DIR=$(mktemp -d)
trap 'rm -rf "$BUILD_DIR"' EXIT

CONFIGURE_FLAGS=(
    "--disable-shared"
    "--enable-static"
    "--disable-debug"
    "--disable-dependency-tracking"
    "--with-pic"
    "--prefix=$PREFIX"
)
[ -n "$HOST" ] && CONFIGURE_FLAGS+=("--host=$HOST")

(cd "$BUILD_DIR" && "$SRC_DIR/configure" "${CONFIGURE_FLAGS[@]}")
JOBS=$(sysctl -n hw.logicalcpu 2>/dev/null || nproc 2>/dev/null || echo 4)
make -C "$BUILD_DIR" -j"$JOBS"
make -C "$BUILD_DIR" install
