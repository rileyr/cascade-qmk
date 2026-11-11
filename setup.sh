#!/usr/bin/env bash
# One-time setup: Python env, SonixQMK checkout, board link, toolchain check.
set -euo pipefail
cd "$(dirname "$0")"

python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

if [ ! -d qmk_firmware ]; then
  git clone --depth 1 --branch sn32_develop --recurse-submodules --shallow-submodules \
    https://github.com/SonixQMK/qmk_firmware.git qmk_firmware
fi
mkdir -p qmk_firmware/keyboards/azio
rm -rf qmk_firmware/keyboards/azio/cascade_slim
ln -s "$PWD/qmk/keyboards/azio/cascade_slim" qmk_firmware/keyboards/azio/cascade_slim

.venv/bin/python tools/gen_board.py

# Safety: fetch Azio's stock firmware image so every flash is reversible. Flashing refuses to run without it.
if [ ! -f stock/cascade_v15_sn32.bin ]; then
  .venv/bin/python stock/extract_stock.py || echo "WARNING: could not fetch the stock image; flashing will refuse until stock/cascade_v15_sn32.bin exists"
fi

if ! command -v arm-none-eabi-gcc >/dev/null || ! echo '#include <stdint.h>' | arm-none-eabi-gcc -E - >/dev/null 2>&1; then
  cat <<'MSG'

You need an ARM toolchain WITH newlib on PATH (Homebrew's arm-none-eabi-gcc has no libc headers).
Arm's own build works: https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads
Unpack it to tools/arm-gnu-toolchain and prepend tools/arm-gnu-toolchain/bin to PATH when compiling.
MSG
fi
echo
echo "      .venv/bin/python app/server.py    (web app on http://127.0.0.1:8765)"
echo "      cd qmk_firmware && ../.venv/bin/qmk compile -kb azio/cascade_slim -km default"
