#!/usr/bin/env python3
"""Headless flasher for the Sonix SN32F24xB ISP bootloader (AZIO Cascade).

Protocol (from SonixQMK/sonix-flasher main.py, 64-byte HID feature reports):
  CMD_INIT    0x0055AA01                      -> echo
  CMD_PREPARE 0x0055AA05, offset, n_chunks    -> echo, status 0xFAFAFAFA
  <n_chunks x 64-byte data reports>
  CMD_REBOOT  0x0055AA07

Nothing here talks to the keyboard's normal-mode firmware. The board must
already be in bootloader mode (VID 0x0c45 PID 0x7040), which on the Cascade
means: short the two right-most of the five pads left of the spacebar switch
while plugging in USB.

Usage:
  cascade_flash.py list
  cascade_flash.py wait                      # block until a bootloader shows up
  cascade_flash.py flash image.bin --dry-run # check image + talk INIT only
  cascade_flash.py flash image.bin           # real flash, asks for "FLASH"
"""
import argparse
import os
import struct
import sys
import time

import hid

BOOTLOADERS = {(0x0C45, 0x7040): "SN32F248B bootloader (offset 0)",
               (0x0C45, 0x7900): "SN32F248 bootloader (offset 0)",
               (0x0C45, 0x7010): "SN32F268F bootloader (offset 0x200)"}
CASCADE = (0x05AC, 0x024F)        # stock firmware (spoofs an Apple keyboard)
CASCADE_QMK = (0xFEED, 0xCA5C)    # this QMK build
CMD_INIT, CMD_PREPARE, CMD_REBOOT = 0x55AA01, 0x55AA05, 0x55AA07
EXPECTED_STATUS = 0xFAFAFAFA
FLASH_SIZE = 64 * 1024
SRAM_LO, SRAM_HI = 0x20000000, 0x20002000  # SN32F24xB has 8 KB SRAM


def open_path(path):
    """Open a device by path with either Python HID binding: `hidapi`
    (hid.device().open_path) or `hid` (hid.Device(path=...))."""
    if hasattr(hid, "device"):
        d = hid.device()
        d.open_path(path)
        return d
    return hid.Device(path=path)


def set_feature(dev, report):
    assert len(report) <= 64
    dev.send_feature_report(b"\x00" + report + b"\x00" * (64 - len(report)))


def get_feature(dev):
    return bytes(dev.get_feature_report(0, 65))[1:]


def find_bootloader():
    for d in hid.enumerate():
        key = (d["vendor_id"], d["product_id"])
        if key in BOOTLOADERS and d["interface_number"] <= 0:
            return d
    return None


def cmd_list(a):
    seen = False
    for d in hid.enumerate():
        key = (d["vendor_id"], d["product_id"])
        if key in BOOTLOADERS or key in (CASCADE, CASCADE_QMK):
            seen = True
            what = BOOTLOADERS.get(key, "Cascade, QMK" if key == CASCADE_QMK or "Slim" in (d["product_string"] or "") else "Cascade, stock firmware")
            print(f"{key[0]:04x}:{key[1]:04x} if{d['interface_number']} {what}  {d['product_string']!r}")
    if not seen:
        print("no Cascade and no Sonix bootloader on USB")


def cmd_wait(a):
    print("waiting for a Sonix bootloader ... (ctrl-c to stop)")
    while True:
        d = find_bootloader()
        if d:
            print(f"bootloader present: {BOOTLOADERS[(d['vendor_id'], d['product_id'])]}")
            return
        time.sleep(0.5)


def check_image(fw, offset):
    if len(fw) + offset > FLASH_SIZE:
        sys.exit(f"image too large: {len(fw)} + {offset} > {FLASH_SIZE}")
    if len(fw) < 0x100:
        sys.exit("image too small")
    sp, r, nmi, hf = struct.unpack("<IIII", fw[:16])
    if not (SRAM_LO <= sp <= SRAM_HI) or not all(v & 1 and v < FLASH_SIZE for v in (r, nmi, hf)):
        sys.exit(f"vector table looks wrong: sp=0x{sp:x} reset=0x{r:x} nmi=0x{nmi:x} hardfault=0x{hf:x}")
    print(f"image ok: {len(fw)} bytes, sp=0x{sp:x} reset=0x{r:x}")


class FlashError(Exception):
    pass


def check_image_ok(fw, offset):
    """Same checks as check_image, raising FlashError instead of exiting."""
    if len(fw) + offset > FLASH_SIZE:
        raise FlashError(f"image too large: {len(fw)} + {offset} > {FLASH_SIZE}")
    if len(fw) < 0x100:
        raise FlashError("image too small")
    sp, r, nmi, hf = struct.unpack("<IIII", fw[:16])
    if not (SRAM_LO <= sp <= SRAM_HI) or not all(v & 1 and v < FLASH_SIZE for v in (r, nmi, hf)):
        raise FlashError(f"vector table looks wrong: sp=0x{sp:x} reset=0x{r:x}")


def flash_image(fw, offset=0, dry_run=False, log=print, progress=None):
    """Library entry used by the CLI and the web app. The bootloader must
    already be on USB. Raises FlashError; never erases unless INIT echoed."""
    fw = bytes(fw)
    while len(fw) % 64:
        fw += b"\x00"
    check_image_ok(fw, offset)
    d = find_bootloader()
    if not d:
        raise FlashError("no bootloader on USB")
    log("device: " + BOOTLOADERS[(d["vendor_id"], d["product_id"])])
    dev = open_path(d["path"])
    try:
        set_feature(dev, struct.pack("<I", CMD_INIT))
        cmd, status = struct.unpack("<II", get_feature(dev)[:8])
        log(f"INIT -> cmd=0x{cmd:08x} status=0x{status:08x}")
        if cmd != CMD_INIT:
            raise FlashError("bootloader did not echo INIT; nothing erased")
        if dry_run:
            log("dry run: nothing erased or written")
            return
        n = len(fw) // 64
        set_feature(dev, struct.pack("<III", CMD_PREPARE, offset, n))
        cmd, status = struct.unpack("<II", get_feature(dev)[:8])
        log(f"PREPARE -> cmd=0x{cmd:08x} status=0x{status:08x}")
        if cmd != CMD_PREPARE or status != EXPECTED_STATUS:
            raise FlashError("PREPARE rejected; nothing written. Power-cycle into bootloader and retry")
        t0 = time.time()
        for i in range(n):
            set_feature(dev, fw[i * 64 : (i + 1) * 64])
            if progress and (i % 32 == 0 or i == n - 1):
                progress((i + 1) / n)
        log(f"wrote {n} chunks in {time.time() - t0:.1f}s; rebooting")
        set_feature(dev, struct.pack("<I", CMD_REBOOT))
    finally:
        dev.close()


STOCK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stock", "cascade_v15_sn32.bin")


def recovery_check(image_path, override=False):
    """Refuse to flash anything but the stock image unless the stock image is on disk:
    it is the only way back to a working keyboard with Bluetooth."""
    if os.path.abspath(image_path) == os.path.abspath(STOCK) or os.path.exists(STOCK) or override:
        return
    raise FlashError("no stock firmware image at stock/cascade_v15_sn32.bin. Run stock/extract_stock.py first so you can "
                     "always restore the keyboard; or pass --no-recovery-check if you keep your own copy")


def cmd_flash(a):
    try:
        recovery_check(a.image, a.no_recovery_check)
    except FlashError as e:
        sys.exit(str(e))
    fw = open(a.image, "rb").read()
    try:
        check_image_ok(fw, a.offset)
    except FlashError as e:
        sys.exit(str(e))
    print(f"image ok: {len(fw)} bytes")
    if not find_bootloader():
        sys.exit("no bootloader on USB; enter it with the pad short while plugging in, then retry")
    if not a.dry_run and not a.yes and input("type FLASH to erase and write the image: ") != "FLASH":
        sys.exit("aborted")
    try:
        flash_image(fw, a.offset, a.dry_run, progress=lambda p: print(f"\r  {int(100 * p):3d}%", end="", flush=True))
    except FlashError as e:
        sys.exit(str(e))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    sub.add_parser("wait").set_defaults(fn=cmd_wait)
    s = sub.add_parser("flash"); s.add_argument("image"); s.add_argument("--offset", type=lambda v: int(v, 0), default=0)
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--yes", action="store_true", help="skip the typed FLASH confirmation (for unattended runs)")
    s.add_argument("--no-recovery-check", action="store_true", help="flash even without the stock image on disk (you keep your own backup)")
    s.set_defaults(fn=cmd_flash)
    a = p.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
