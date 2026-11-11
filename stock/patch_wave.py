#!/usr/bin/env python3
"""Make the Wave mode of the stock AZIO Cascade V1.5 firmware use the colour
wheel (0xade8, 21 entries) instead of its built-in three-phase ramp rainbow.

Stock Wave (function at 0x9968, inner loop 0x9a58..0x9aac): for each of 12
bands it keeps three phase counters (R at +3, G at +15, B at +27 in a RAM
array), each 0..191, and looks every channel up in a 192-byte ramp at 0xae27.
The channels start 64 apart, which is what paints a rainbow.

Patch:
  0x9a74  add r2,#15 -> add r2,#3     G lookup uses the R phase
  0x9a8e  add r2,#27 -> add r2,#3     B lookup uses the R phase
  0x9a5e  ldr r3,=ramp ; ldrb r3,[r3,r2]  ->  bl stub_R      (4 bytes each)
  0x9a78  (same for G)                     ->  bl stub_G
  0x9a92  (same for B)                     ->  bl stub_B
  stubs at 0xb194 (free, zero-filled flash):  ldr r3,=tab ; ldrb r3,[r3,r2] ; bx lr
  tables at 0xb1c0: 3 x 192 bytes, channel values of the wheel sampled once
  around the loop per period, interpolated between the 21 stops.

lr is free to clobber inside the loop: the function saved it (push {r4,lr}).
Every original byte at every patch site is checked before writing.
"""
import hashlib
import struct
import sys

WHEEL_OFF, WHEEL_N = 0xADE8, 21
PERIOD = 192                      # fw[0xb173]
SITES = {                         # addr: (original bytes, replacement)
    0x9A74: (bytes.fromhex("0f32"), bytes.fromhex("0332")),
    0x9A8E: (bytes.fromhex("1b32"), bytes.fromhex("0332")),
}
LOOKUPS = {0x9A5E: bytes.fromhex("284b9b5c"), 0x9A78: bytes.fromhex("214b9b5c"), 0x9A92: bytes.fromhex("1b4b9b5c")}
STUB_BASE = 0xB194                # 3 stubs x 12 bytes
TAB_BASE = 0xB1C0                 # 3 tables x 192 bytes
FREE_LO, FREE_HI = 0xB192, 0xB400 # must be all zero in the input


def bl(from_addr, to_addr):
    off = to_addr - (from_addr + 4)
    assert -(1 << 22) <= off < (1 << 22) and off % 2 == 0
    hi = 0xF000 | ((off >> 12) & 0x7FF)
    lo = 0xF800 | ((off >> 1) & 0x7FF)
    return struct.pack("<HH", hi, lo)


def stub(addr, table):
    # ldr r3,[pc,#4] ; ldrb r3,[r3,r2] ; bx lr ; nop ; .word table
    assert addr % 4 == 0
    return struct.pack("<HHHHI", 0x4B01, 0x5C9B, 0x4770, 0xBF00, table)


def sample_wheel(wheel, n):
    k = len(wheel)
    out = []
    for i in range(n):
        t = i * k / n
        a, b = wheel[int(t) % k], wheel[(int(t) + 1) % k]
        f = t - int(t)
        out.append(tuple(round(a[c] * (1 - f) + b[c] * f) for c in range(3)))
    return out


def apply(fw):
    """Library entry: return a Wave-patched copy of `fw` (bytes), using the
    wheel already present in the image. Raises ValueError on any mismatch."""
    fw = bytearray(fw)
    if len(fw) != 65536:
        raise ValueError("need a 64 KB image")
    for a, (old, _) in SITES.items():
        if fw[a : a + len(old)] != old:
            raise ValueError(f"unexpected bytes at 0x{a:x}: {fw[a:a+len(old)].hex()}")
    for a, old in LOOKUPS.items():
        if fw[a : a + 4] != old:
            raise ValueError(f"unexpected bytes at 0x{a:x}: {fw[a:a+4].hex()}")
    if any(fw[FREE_LO:FREE_HI]):
        raise ValueError("free region is not empty; already patched?")
    if fw[0xB173] != PERIOD:
        raise ValueError(f"wave period is {fw[0xB173]}, expected {PERIOD}")
    wheel = [tuple(fw[WHEEL_OFF + 3 * i : WHEEL_OFF + 3 * i + 3]) for i in range(WHEEL_N)]
    samples = sample_wheel(wheel, PERIOD)
    for ch in range(3):
        tab = TAB_BASE + ch * PERIOD
        fw[tab : tab + PERIOD] = bytes(s[ch] for s in samples)
        st = STUB_BASE + ch * 12
        fw[st : st + 12] = stub(st, tab)
    for ch, site in enumerate(sorted(LOOKUPS)):
        fw[site : site + 4] = bl(site, STUB_BASE + ch * 12)
    for a, (_, new) in SITES.items():
        fw[a : a + len(new)] = new
    return bytes(fw)


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: patch_wave.py in.bin out.bin")
    fw = bytearray(open(sys.argv[1], "rb").read())
    if len(fw) != 65536:
        sys.exit("need a 64 KB image")
    for a, (old, _) in SITES.items():
        if fw[a : a + len(old)] != old:
            sys.exit(f"unexpected bytes at 0x{a:x}: {fw[a:a+len(old)].hex()}")
    for a, old in LOOKUPS.items():
        if fw[a : a + 4] != old:
            sys.exit(f"unexpected bytes at 0x{a:x}: {fw[a:a+4].hex()}")
    if any(fw[FREE_LO:FREE_HI]):
        sys.exit("free region is not empty; already patched?")
    if fw[0xB173] != PERIOD:
        sys.exit(f"wave period is {fw[0xB173]}, expected {PERIOD}")
    wheel = [tuple(fw[WHEEL_OFF + 3 * i : WHEEL_OFF + 3 * i + 3]) for i in range(WHEEL_N)]
    samples = sample_wheel(wheel, PERIOD)
    for ch in range(3):
        tab = TAB_BASE + ch * PERIOD
        fw[tab : tab + PERIOD] = bytes(s[ch] for s in samples)
        st = STUB_BASE + ch * 12
        fw[st : st + 12] = stub(st, tab)
    for ch, site in enumerate(sorted(LOOKUPS)):
        fw[site : site + 4] = bl(site, STUB_BASE + ch * 12)
    for a, (_, new) in SITES.items():
        fw[a : a + len(new)] = new
    open(sys.argv[2], "wb").write(fw)
    print(f"wrote {sys.argv[2]} sha256 {hashlib.sha256(fw).hexdigest()}")
    print("wheel used:", [bytes(w).hex() for w in wheel])
    print("stubs @0x%x..0x%x, tables @0x%x..0x%x" % (STUB_BASE, STUB_BASE + 36, TAB_BASE, TAB_BASE + 3 * PERIOD))


if __name__ == "__main__":
    main()
