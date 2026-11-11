#!/usr/bin/env python3
"""Read and set the keyboard's live RGB Matrix state through QMK's VIA raw-HID
protocol (needs a build with `via` enabled).

  via_lighting.py get
  via_lighting.py set [--effect NAME|ID] [--hue H] [--sat S] [--val V] [--speed S]

VIA protocol: 32-byte reports on the raw HID interface (usage page 0xFF60, usage
0x61). id_custom_get_value = 0x08, id_custom_set_value = 0x07, id_custom_save =
0x09; channel 3 = QMK RGB Matrix; value ids 1 brightness, 2 effect, 3 speed,
4 colour (hue, sat). Effect ids follow app/qmk_info.json "effect_order".
"""
import argparse
import json
import os
import sys

import hid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDS = {(0xFEED, 0xCA5C), (0x05AC, 0x024F)}  # this QMK build; older builds kept the stock IDs
CH = 3
GET, SET, SAVE = 0x08, 0x07, 0x09
BRIGHT, EFFECT, SPEED, COLOR = 1, 2, 3, 4


class ViaError(Exception):
    pass


def effect_order():
    try:
        return json.load(open(os.path.join(ROOT, "app", "qmk_info.json")))["effect_order"]
    except Exception:
        return []


def open_raw():
    for d in hid.enumerate():
        if (d["vendor_id"], d["product_id"]) in IDS and d.get("usage_page") == 0xFF60 and d.get("usage") == 0x61:
            if hasattr(hid, "Device"):
                return hid.Device(path=d["path"])
            dev = hid.device()
            dev.open_path(d["path"])
            return dev
    raise ViaError("no VIA raw HID interface (is a VIA-enabled QMK build running?)")


def xfer(dev, data):
    msg = bytes(data) + b"\x00" * (32 - len(data))
    dev.write(b"\x00" + msg)
    resp = bytes(dev.read(32, 1000))
    if not resp:
        raise ViaError("no reply from keyboard")
    return resp


def get_state(dev=None):
    own = dev is None
    dev = dev or open_raw()
    try:
        b = xfer(dev, [GET, CH, BRIGHT])[3]
        e = xfer(dev, [GET, CH, EFFECT])[3]
        s = xfer(dev, [GET, CH, SPEED])[3]
        c = xfer(dev, [GET, CH, COLOR])
        order = effect_order()
        return {"val": b, "effect": e, "effect_name": order[e] if e < len(order) else f"#{e}",
                "speed": s, "hue": c[3], "sat": c[4]}
    finally:
        if own:
            dev.close()


def set_state(effect=None, hue=None, sat=None, val=None, speed=None, save=False):
    dev = open_raw()
    try:
        if effect is not None:
            if isinstance(effect, str) and not effect.isdigit():
                order = effect_order()
                if effect not in order:
                    raise ViaError(f"unknown effect {effect!r}; in build: {order[1:]}")
                effect = order.index(effect)
            xfer(dev, [SET, CH, EFFECT, int(effect)])
        if val is not None:
            xfer(dev, [SET, CH, BRIGHT, int(val)])
        if speed is not None:
            xfer(dev, [SET, CH, SPEED, int(speed)])
        if hue is not None or sat is not None:
            cur = xfer(dev, [GET, CH, COLOR])
            xfer(dev, [SET, CH, COLOR, int(hue if hue is not None else cur[3]), int(sat if sat is not None else cur[4])])
        if save:
            xfer(dev, [SAVE, CH])
        return get_state(dev)
    finally:
        dev.close()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("get")
    s = sub.add_parser("set")
    s.add_argument("--effect"); s.add_argument("--hue", type=int); s.add_argument("--sat", type=int); s.add_argument("--val", type=int); s.add_argument("--speed", type=int)
    a = p.parse_args()
    try:
        if a.cmd == "get":
            print(json.dumps(get_state(), indent=1))
        else:
            print(json.dumps(set_state(a.effect, a.hue, a.sat, a.val, a.speed), indent=1))
    except ViaError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
