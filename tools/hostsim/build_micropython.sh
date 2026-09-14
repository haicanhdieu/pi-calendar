#!/usr/bin/env bash
# Build a MicroPython unix interpreter for the heap simulation.
#
# The version must match the firmware flashed on the Pico, because the
# simulation loads the same .mpy files the device does and MicroPython rejects
# a .mpy whose format version it does not implement.  Check the device with:
#
#   mpremote connect <port> exec "import sys; print(sys.implementation)"
#
# and compare against `mpy-cross --version`.
#
# Usage:
#   tools/hostsim/build_micropython.sh [version]     # default: v1.20.0

set -euo pipefail

VERSION="${1:-v1.20.0}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$HERE/build"
SRC_DIR="$BUILD_DIR/micropython-$VERSION"

mkdir -p "$BUILD_DIR"

if [ ! -d "$SRC_DIR" ]; then
    echo "Cloning MicroPython $VERSION..."
    git clone --depth 1 --branch "$VERSION" \
        https://github.com/micropython/micropython.git "$SRC_DIR"
fi

cd "$SRC_DIR/ports/unix"
make submodules

# Released MicroPython predates some warnings that current clang/gcc emit, and
# the tree builds with -Werror; the bundled mbedtls trips this. The simulation
# does not use TLS, so downgrading these warnings is safe here.
make -j"$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)" \
    CFLAGS_EXTRA="-Wno-error -Wno-unused-but-set-variable"

cp build-standard/micropython "$BUILD_DIR/micropython"
echo
echo "Installed: $BUILD_DIR/micropython"
"$BUILD_DIR/micropython" -c "import sys; print(sys.implementation)"
