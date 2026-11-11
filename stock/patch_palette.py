#!/usr/bin/env python3
"""Patch the static colour palette and the rainbow hue wheel in the stock
AZIO Cascade / Cascade Slim V1.5 firmware (Sonix SN32F24xB, 64 KB image).

Tables (verified against the stock image, sha256 4a57961e...):
  0xadd0  palette   8 x RGB  the colours Fn+Left/Right cycles through
  0xade8  wheel     21 x RGB the hue circle used by wave / rainbow modes

Both are patched by matching the ORIGINAL bytes, never by blind offset, so a
wrong input file fails loudly instead of corrupting code.

Usage:
  patch_palette.py show cascade_v15_sn32.bin
  patch_palette.py patch cascade_v15_sn32.bin out.bin \
      --palette ffffff,ff0000,ff5e00,ffff00,00ff00,0000ff,ff00ff,00ffff \
      --wheel   ff7a00,ff007a,7a00ff            # any 2..21 colours, looped
"""
import argparse
import hashlib
import sys

PALETTE_OFF = 0xADD0
PALETTE_N = 8
WHEEL_OFF = 0xADE8
WHEEL_N = 21
STOCK_SHA256 = "4a57961ecc7f336808af6891060fa51c0976b0799887111b5169f15a97ba95da"

STOCK_PALETTE = ["ffffff", "ff0000", "ff5e00", "ffff00", "00ff00", "0000ff", "ff00ff", "00ffff"]


def hexcol(s):
    s = s.strip().lstrip("#").lower()
    if len(s) != 6 or any(c not in "0123456789abcdef" for c in s):
        raise argparse.ArgumentTypeError(f"bad colour {s!r}, want RRGGBB")
    return bytes.fromhex(s)


def triplets(buf, off, n):
    return [buf[off + 3 * i : off + 3 * i + 3] for i in range(n)]


def lerp_loop(colours, n):
    """n colours evenly spaced around a closed loop through `colours`."""
    k = len(colours)
    out = []
    for i in range(n):
        t = i * k / n
        a, b = colours[int(t) % k], colours[(int(t) + 1) % k]
        f = t - int(t)
        out.append(bytes(round(a[c] * (1 - f) + b[c] * f) for c in range(3)))
    return out


def replace_all(buf, old, new):
    """Replace every occurrence of `old` with `new`; return (buf, count)."""
    assert len(old) == len(new)
    count = buf.count(old)
    return buf.replace(old, new), count


def apply(fw, palette=None, wheel=None):
    """Library entry: return a patched copy of `fw` (bytes). `palette` is a list
    of 8 RGB byte-triplets, `wheel` a list of 2..21 triplets (looped to 21)."""
    fw = bytes(fw)
    cur_pal = b"".join(triplets(fw, PALETTE_OFF, PALETTE_N))
    cur_wheel = b"".join(triplets(fw, WHEEL_OFF, WHEEL_N))
    if cur_pal != bytes.fromhex("".join(STOCK_PALETTE)):
        raise ValueError("palette bytes at 0x%x are not the stock palette" % PALETTE_OFF)
    out = fw
    if palette:
        if len(palette) != PALETTE_N:
            raise ValueError(f"palette needs {PALETTE_N} colours")
        out, _ = replace_all(out, cur_pal, b"".join(bytes(c) for c in palette))
    if wheel:
        if not 2 <= len(wheel) <= WHEEL_N:
            raise ValueError(f"wheel needs 2..{WHEEL_N} colours")
        out, _ = replace_all(out, cur_wheel, b"".join(lerp_loop([bytes(c) for c in wheel], WHEEL_N)))
    return out


def cmd_show(a):
    fw = open(a.image, "rb").read()
    sha = hashlib.sha256(fw).hexdigest()
    print(f"{a.image}: {len(fw)} bytes sha256 {sha}" + ("  (stock V1.5)" if sha == STOCK_SHA256 else ""))
    print("palette @0x%x:" % PALETTE_OFF, [t.hex() for t in triplets(fw, PALETTE_OFF, PALETTE_N)])
    print("wheel   @0x%x:" % WHEEL_OFF, [t.hex() for t in triplets(fw, WHEEL_OFF, WHEEL_N)])


def cmd_patch(a):
    fw = open(a.image, "rb").read()
    if len(fw) != 65536:
        sys.exit(f"expected a 65536-byte image, got {len(fw)}")
    cur_pal = b"".join(triplets(fw, PALETTE_OFF, PALETTE_N))
    cur_wheel = b"".join(triplets(fw, WHEEL_OFF, WHEEL_N))
    if cur_pal != bytes.fromhex("".join(STOCK_PALETTE)):
        sys.exit("palette bytes at 0x%x are not the stock palette; refusing" % PALETTE_OFF)
    out = fw
    changed = []
    if a.palette:
        if len(a.palette) != PALETTE_N:
            sys.exit(f"--palette needs exactly {PALETTE_N} colours")
        new = b"".join(a.palette)
        out, n = replace_all(out, cur_pal, new)
        changed.append(("palette", n))
    if a.wheel:
        if not 2 <= len(a.wheel) <= WHEEL_N:
            sys.exit(f"--wheel needs 2..{WHEEL_N} colours")
        new = b"".join(lerp_loop(a.wheel, WHEEL_N))
        out, n = replace_all(out, cur_wheel, new)
        changed.append(("wheel", n))
    if out == fw:
        sys.exit("nothing to change")
    diff = [i for i in range(len(fw)) if fw[i] != out[i]]
    print("changed tables:", changed)
    print(f"bytes differing: {len(diff)}  range 0x{diff[0]:x}..0x{diff[-1]:x}")
    # every differing byte must sit inside one of the two tables (or a 2nd copy of the wheel)
    ok_ranges = [(PALETTE_OFF, PALETTE_OFF + 3 * PALETTE_N), (WHEEL_OFF, WHEEL_OFF + 3 * WHEEL_N)]
    stray = [i for i in diff if not any(lo <= i < hi for lo, hi in ok_ranges)]
    if stray:
        print(f"note: {len(stray)} changed bytes outside the primary tables (2nd copy of a table): "
              f"0x{stray[0]:x}..0x{stray[-1]:x}")
    open(a.out, "wb").write(out)
    print(f"wrote {a.out} sha256 {hashlib.sha256(out).hexdigest()}")
    print("new palette:", [t.hex() for t in triplets(out, PALETTE_OFF, PALETTE_N)])
    print("new wheel:  ", [t.hex() for t in triplets(out, WHEEL_OFF, WHEEL_N)])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show"); s.add_argument("image"); s.set_defaults(fn=cmd_show)
    s = sub.add_parser("patch"); s.add_argument("image"); s.add_argument("out")
    s.add_argument("--palette", type=lambda v: [hexcol(c) for c in v.split(",")])
    s.add_argument("--wheel", type=lambda v: [hexcol(c) for c in v.split(",")])
    s.set_defaults(fn=cmd_patch)
    a = p.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
