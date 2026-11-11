#!/usr/bin/env python3
"""Minimal QMK console reader (what `hid_listen` / `qmk console` do), plus a
matrix-discovery mode.

  qmk_console.py                  print console lines
  qmk_console.py discover         press keys in the order listed in KEY_ORDER;
                                  writes out/matrix_map.json (key label -> [row, col])

The QMK console is a raw HID interface with usage page 0xFF31, usage 0x74.
With `debug_matrix` on, QMK prints the matrix state whenever it changes, e.g.
  r/c 0123456789ABCDEF
  00: 0000000000000000
  ...
"""
import json
import os
import re
import sys
import time

import hid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY_ORDER = (
    "Esc F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 F11 F12 PrtSc Ins Del "
    "` 1 2 3 4 5 6 7 8 9 0 - = Bksp Home "
    "Tab Q W E R T Y U I O P [ ] \\ End "
    "Caps A S D F G H J K L ; ' Enter PgUp "
    "LShift Z X C V B N M , . / RShift Up PgDn "
    "LCtrl Opt LCmd Space RCmd Fn RCtrl Left Down Right"
).split()


def open_console():
    for d in hid.enumerate():
        if d.get("usage_page") == 0xFF31 and d.get("usage") == 0x74:
            dev = hid.Device(path=d["path"]) if hasattr(hid, "Device") else hid.device()
            if not hasattr(hid, "Device"):
                dev.open_path(d["path"])
            return dev
    return None


def lines(dev):
    buf = ""
    while True:
        data = bytes(dev.read(32, 100))
        if not data:
            continue
        buf += data.split(b"\x00", 1)[0].decode(errors="replace")
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            yield line.rstrip("\r")


def parse_matrix(block):
    """block: list of 'RR: bbbbbbbbbbbbbbbb' lines -> set of (row, col) pressed."""
    pressed = set()
    for ln in block:
        m = re.match(r"\s*([0-9A-Fa-f]+):\s*([01]+)", ln)
        if m:
            r = int(m.group(1), 16)
            for c, bit in enumerate(m.group(2)):
                if bit == "1":
                    pressed.add((r, c))
    return pressed


def main():
    dev = open_console()
    if not dev:
        print("waiting for a QMK console device (flash the discovery firmware) ...", flush=True)
        t0 = time.time()
        while not dev and time.time() - t0 < 1800:
            time.sleep(1)
            dev = open_console()
        if not dev:
            sys.exit("no QMK console device appeared in 30 minutes")
        time.sleep(1)
    if len(sys.argv) > 1 and sys.argv[1] == "discover":
        mapping = {}
        idx = 0
        block, prev = [], set()
        print(f"press: {KEY_ORDER[idx]}")
        for ln in lines(dev):
            if ln.startswith("r/c"):
                block = []
                continue
            block.append(ln)
            if len(block) >= 6:
                cur = parse_matrix(block)
                block = []
                new = cur - prev
                prev = cur
                if new and idx < len(KEY_ORDER):
                    rc = sorted(new)[0]
                    mapping[KEY_ORDER[idx]] = list(rc)
                    print(f"  {KEY_ORDER[idx]} -> row {rc[0]} col {rc[1]}")
                    idx += 1
                    if idx < len(KEY_ORDER):
                        print(f"press: {KEY_ORDER[idx]}")
                    else:
                        os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)
                        json.dump(mapping, open(os.path.join(ROOT, "out", "matrix_map.json"), "w"), indent=1)
                        print("done, wrote out/matrix_map.json")
                        return
    else:
        for ln in lines(dev):
            print(ln)


if __name__ == "__main__":
    main()
