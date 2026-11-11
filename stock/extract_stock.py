#!/usr/bin/env python3
"""Obtain the stock AZIO Cascade / Cascade Slim V1.5 firmware image from
Azio's own firmware updater, so this repository never has to ship it.

The updater is a Windows build of Sonix's ISP tool with the 64 KB firmware
image embedded as PE resource 10/4000. Azio publishes it on their support
site; this script downloads that file, extracts the .exe from the .rar
(needs `bsdtar`, which macOS has, or `unrar`), locates the resource and
writes stock/cascade_v15_sn32.bin. The sha256 is checked against the image
this project was developed with.

    python3 stock/extract_stock.py            # downloads
    python3 stock/extract_stock.py path.rar   # or use a file you already have
"""
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "https://support.aziocorp.com/hc/article_attachments/14936580888461"  # AZIO_Cascade_Firmware_win_V1.5 (.rar)
EXE = "20230414_5164_AZIOCav1.5_USB_UPDAT_REV148_NMOS_V37.exe"
OUT = os.path.join(HERE, "cascade_v15_sn32.bin")
SHA = "4a57961ecc7f336808af6891060fa51c0976b0799887111b5169f15a97ba95da"


def find_resource(pe, res_type=10, res_id=4000):
    """Walk the PE resource directory and return the raw bytes of RT type/id."""
    off = struct.unpack_from("<I", pe, 0x3C)[0]
    nsec = struct.unpack_from("<H", pe, off + 6)[0]
    optsz = struct.unpack_from("<H", pe, off + 20)[0]
    secs = []
    for i in range(nsec):
        s = off + 24 + optsz + i * 40
        name = pe[s : s + 8].rstrip(b"\0")
        vs, va, rs, ro = struct.unpack_from("<IIII", pe, s + 8)
        secs.append((name, va, vs, ro, rs))
    rsrc = next(s for s in secs if s[0] == b".rsrc")
    base, roff = rsrc[1], rsrc[3]

    def rva2off(r):
        for _, va, vs, ro, rs in secs:
            if va <= r < va + max(vs, rs):
                return ro + (r - va)
        raise ValueError("bad rva")

    def entries(dir_off):
        ne, ni = struct.unpack_from("<HH", pe, roff + dir_off + 12)
        for k in range(ne + ni):
            name, data = struct.unpack_from("<II", pe, roff + dir_off + 16 + k * 8)
            yield name, data

    for t, d in entries(0):
        if t != res_type:
            continue
        for i, d2 in entries(d & 0x7FFFFFFF):
            if i != res_id:
                continue
            for _, d3 in entries(d2 & 0x7FFFFFFF):
                rva, size = struct.unpack_from("<II", pe, roff + d3)
                o = rva2off(rva)
                return pe[o : o + size]
    raise ValueError("resource not found")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        if len(sys.argv) > 1:
            rar = sys.argv[1]
        else:
            rar = os.path.join(tmp, "fw.rar")
            print("downloading", URL)
            req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as r, open(rar, "wb") as f:
                shutil.copyfileobj(r, f)
        tool = shutil.which("bsdtar") or shutil.which("unar") or shutil.which("unrar")
        if not tool:
            sys.exit("need bsdtar (macOS/libarchive), unar or unrar to open the .rar")
        if "unrar" in tool:
            subprocess.run([tool, "x", "-y", rar, tmp + "/"], check=True, capture_output=True)
        elif "unar" in tool:
            subprocess.run([tool, "-o", tmp, rar], check=True, capture_output=True)
        else:
            subprocess.run([tool, "-xf", rar, "-C", tmp], check=True)
        exe = None
        for root, _, files in os.walk(tmp):
            for fn in files:
                if fn.lower().endswith(".exe"):
                    exe = os.path.join(root, fn)
        if not exe:
            sys.exit("no .exe found in the archive")
        pe = open(exe, "rb").read()
        img = find_resource(pe)
        if len(img) != 65536:
            sys.exit(f"unexpected image size {len(img)}")
        sha = hashlib.sha256(img).hexdigest()
        open(OUT, "wb").write(img)
        print(f"wrote {OUT} ({len(img)} bytes) sha256 {sha}")
        if sha != SHA:
            print("WARNING: sha256 differs from the image this project was built against; the table offsets in patch_*.py may not apply")


if __name__ == "__main__":
    main()
