#!/usr/bin/env python3
"""Local web app + JSON API for the Cascade lighting patch.

Runs on localhost only. Lets a person (or an agent) preview a palette and
rainbow wheel on a drawing of the keyboard, build the patched stock image,
and flash it through the Sonix bootloader.

    .venv/bin/python app/server.py            # http://127.0.0.1:8765

API (all JSON):
  GET  /api/state            config, stock image info, device state, last build, job
  PUT  /api/config           {"palette":[8 hex], "wheel":[2..21 hex]}  -> saved config
  GET  /api/presets          named presets; PUT /api/config {"preset":"ocean"} applies one
  GET  /api/images           every image in out/ (stock patches and QMK builds)
  GET  /api/qmk              the QMK build description: keys, Fn layer, effects, known issues
  GET  /api/live             the keyboard's current effect, hue/sat/val, speed (VIA raw HID; QMK build)
  PUT  /api/live             {"effect": name|id, "hue", "sat", "val", "speed"} changes it live (volatile);
                             add "save": true to also persist it in the keyboard's settings flash
  GET  /api/effects          every effect with enabled flag; PUT /api/effects {"enabled":[ids]}
                             saves the selection and regenerates the board (then compile)
  GET  /api/tables           the exact tables the firmware will contain for the
                             current config: wheel21 (static RGB columns), wave192
  POST /api/build            -> {"path","sha256","changed_bytes"}  (no device needed)
  POST /api/flash            {"image": path | "stock"} -> starts a job that waits for
                             the bootloader (pad short) and flashes. Poll /api/state.
  POST /api/job/cancel
  GET  /api/device           what is on USB right now

Nothing here writes to the keyboard until a flash job is explicitly started and
the person puts the board into the bootloader.
"""
import hashlib
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "stock"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import cascade_flash as cf  # noqa: E402
import patch_palette as pp  # noqa: E402
import patch_wave as pw  # noqa: E402
import via_lighting as via  # noqa: E402

STOCK = os.path.join(ROOT, "stock", "cascade_v15_sn32.bin")
CONFIG = os.path.join(ROOT, "app", "config.json")
OUT = os.path.join(ROOT, "out")
INDEX = os.path.join(ROOT, "app", "index.html")
DEFAULT = {"palette": ["ffe6b4", "ff5a3c", "ffaa00", "a0ff14", "00c8a0", "32b4ff", "7a3cff", "ff28b4"],
           "wheel": ["00c8a0", "ff28b4", "ffaa00", "7a3cff", "a0ff14", "ff5a3c", "32b4ff"]}

# Named presets: 8 palette slots + wheel stops (2..21, looped).
PRESETS = {
    "stock":     {"palette": ["ffffff", "ff0000", "ff5e00", "ffff00", "00ff00", "0000ff", "ff00ff", "00ffff"],
                  "wheel": ["ff0000", "ffff00", "00ff00", "00ffff", "0000ff", "ff00ff"]},
    "contrast":  DEFAULT,
    "sunset":    {"palette": ["fff1d6", "ffb347", "ff7a00", "ff4e50", "ff2d6e", "c94bff", "7a3cff", "3a1c71"],
                  "wheel": ["ff7a00", "ff2d6e", "7a3cff"]},
    "ocean":     {"palette": ["e0fbff", "7fe7ff", "32b4ff", "0077ff", "0044aa", "00c8a0", "00ffd0", "6a5acd"],
                  "wheel": ["00ffd0", "0077ff", "6a5acd"]},
    "forest":    {"palette": ["f0ffe0", "a0ff14", "4caf50", "1b7f3a", "8bc34a", "ffd54f", "ff8f00", "5d4037"],
                  "wheel": ["1b7f3a", "a0ff14", "ffd54f"]},
    "ember":     {"palette": ["fff3e0", "ffcc80", "ff9800", "ff5722", "e64a19", "b71c1c", "7f0000", "3e2723"],
                  "wheel": ["3e2723", "b71c1c", "ff5722", "ffcc80"]},
    "candy":     {"palette": ["ffffff", "ff6ec7", "ff9ff3", "ffd3e0", "9b5de5", "00bbf9", "00f5d4", "fee440"],
                  "wheel": ["ff6ec7", "9b5de5", "00bbf9", "00f5d4", "fee440"]},
    "warm-mono": {"palette": ["fff8e7", "ffe6b4", "ffd27f", "ffbf4d", "ffaa00", "ff8c00", "cc7000", "995400"],
                  "wheel": ["ffe6b4", "ffaa00", "cc7000"]},
    "cyberpunk": {"palette": ["00ffff", "ff00ff", "ffff00", "00ff88", "ff0080", "8000ff", "0080ff", "ffffff"],
                  "wheel": ["00ffff", "ff00ff", "ffff00"]},
    "nord":      {"palette": ["eceff4", "88c0d0", "81a1c1", "5e81ac", "a3be8c", "ebcb8b", "d08770", "bf616a"],
                  "wheel": ["5e81ac", "88c0d0", "a3be8c", "ebcb8b", "d08770", "bf616a", "b48ead"]},
}

state = {"last_build": None, "job": None}
lock = threading.Lock()


def load_config():
    try:
        return json.load(open(CONFIG))
    except Exception:
        return dict(DEFAULT)


def save_config(c):
    json.dump(c, open(CONFIG, "w"), indent=1)


def validate(c):
    if c.get("preset"):
        if c["preset"] not in PRESETS:
            raise ValueError("unknown preset; see GET /api/presets")
        c = dict(PRESETS[c["preset"]])
    pal = [pp.hexcol(x) for x in c.get("palette", [])]
    wheel = [pp.hexcol(x) for x in c.get("wheel", [])]
    if len(pal) != 8:
        raise ValueError("palette needs exactly 8 colours")
    if not 2 <= len(wheel) <= 21:
        raise ValueError("wheel needs 2..21 colours")
    return {"palette": [p.hex() for p in pal], "wheel": [w.hex() for w in wheel]}


def tables(c):
    wheel = [bytes.fromhex(x) for x in c["wheel"]]
    wheel21 = pp.lerp_loop(wheel, 21)
    wave192 = pw.sample_wheel([tuple(w) for w in wheel21], pw.PERIOD)
    return {"palette": c["palette"], "wheel21": [w.hex() for w in wheel21],
            "wave192": [bytes(s).hex() for s in wave192], "period": pw.PERIOD}


def build(c):
    if not os.path.exists(STOCK):
        raise FileNotFoundError("stock image missing: run stock/extract_stock.py first")
    stock = open(STOCK, "rb").read()
    img = pp.apply(stock, [bytes.fromhex(x) for x in c["palette"]], [bytes.fromhex(x) for x in c["wheel"]])
    img = pw.apply(img)
    cf.check_image_ok(img, 0)
    name = "webapp_%s.bin" % time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUT, name)
    os.makedirs(OUT, exist_ok=True)
    open(path, "wb").write(img)
    info = {"path": path, "sha256": hashlib.sha256(img).hexdigest(), "changed_bytes": sum(a != b for a, b in zip(stock, img)),
            "config": c, "time": time.time()}
    with lock:
        state["last_build"] = info
    return info


def device():
    bl = cf.find_bootloader()
    if bl:
        return {"state": "bootloader", "name": cf.BOOTLOADERS[(bl["vendor_id"], bl["product_id"])]}
    for d in cf.hid.enumerate():
        key = (d["vendor_id"], d["product_id"])
        if key in (cf.CASCADE, cf.CASCADE_QMK):
            kind = "qmk" if key == cf.CASCADE_QMK or "Slim" in (d["product_string"] or "") else "stock"
            return {"state": "normal", "name": d["product_string"], "firmware": kind}
    return {"state": "none", "name": None, "firmware": None}


def run_job(image_path, timeout=600):
    job = state["job"]

    def log(msg):
        job["log"].append(msg)

    try:
        fw = open(image_path, "rb").read()
        cf.check_image_ok(fw, 0)
        job["phase"] = "waiting"
        log("waiting for the Sonix bootloader: short the two right-most pads left of the spacebar while plugging in USB")
        t0 = time.time()
        while not cf.find_bootloader():
            if job.get("cancel"):
                job["phase"] = "cancelled"
                return
            if time.time() - t0 > timeout:
                job["phase"] = "timeout"
                log("no bootloader seen in %ds" % timeout)
                return
            time.sleep(0.5)
        time.sleep(2)
        job["phase"] = "flashing"
        cf.flash_image(fw, 0, log=log, progress=lambda p: job.__setitem__("progress", p))
        job["phase"] = "done"
        log("flashed %s; the keyboard reboots itself" % os.path.basename(image_path))
    except Exception as e:
        job["phase"] = "error"
        log("error: %s" % e)


class H(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def log_message(self, *a):
        pass

    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/":
            body = open(INDEX, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif p == "/api/state":
            c = load_config()
            stock = {"path": STOCK, "present": os.path.exists(STOCK)}
            if stock["present"]:
                stock["sha256"] = hashlib.sha256(open(STOCK, "rb").read()).hexdigest()
            self._json(200, {"config": c, "stock": stock,
                             "device": device(), "last_build": state["last_build"], "job": state["job"], "tables": tables(c)})
        elif p == "/api/tables":
            self._json(200, tables(load_config()))
        elif p == "/api/device":
            self._json(200, device())
        elif p == "/api/presets":
            self._json(200, PRESETS)
        elif p == "/api/images":
            out = []
            for name in sorted(os.listdir(OUT)) if os.path.isdir(OUT) else []:
                if name.endswith(".bin"):
                    fp = os.path.join(OUT, name)
                    data = open(fp, "rb").read()
                    out.append({"name": name, "path": fp, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()[:16],
                                "mtime": os.path.getmtime(fp), "kind": "qmk" if name.startswith("qmk") else "stock-patch"})
            out.sort(key=lambda x: -x["mtime"])
            self._json(200, out)
        elif p == "/api/live":
            try:
                self._json(200, via.get_state())
            except Exception as e:
                self._json(200, {"error": str(e)})
        elif p == "/api/effects":
            try:
                self._json(200, json.load(open(os.path.join(ROOT, "app", "qmk_info.json")))["effects"])
            except Exception as e:
                self._json(404, {"error": str(e)})
        elif p == "/api/qmk":
            try:
                self._json(200, json.load(open(os.path.join(ROOT, "app", "qmk_info.json"))))
            except Exception as e:
                self._json(404, {"error": str(e)})
        else:
            self._json(404, {"error": "not found"})

    def do_PUT(self):
        p = urlparse(self.path).path
        if p == "/api/live":
            b = self._body()
            try:
                self._json(200, via.set_state(b.get("effect"), b.get("hue"), b.get("sat"), b.get("val"), b.get("speed"), b.get("save", False)))
            except Exception as e:
                self._json(400, {"error": str(e)})
        elif p == "/api/effects":
            body = self._body()
            enabled = body.get("enabled")
            if not isinstance(enabled, list) or not enabled:
                return self._json(400, {"error": "enabled must be a non-empty list of effect ids"})
            json.dump({"enabled": enabled}, open(os.path.join(ROOT, "app", "effects.json"), "w"), indent=1)
            import subprocess
            r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "gen_board.py")], capture_output=True, text=True)
            if r.returncode != 0:
                return self._json(500, {"error": "generator failed", "output": r.stdout + r.stderr})
            self._json(200, {"enabled": enabled, "generator": r.stdout.strip().splitlines()[-1:], "next": "compile: cd qmk_firmware && ../.venv/bin/qmk compile -kb azio/cascade_slim -km default"})
        elif p == "/api/config":
            try:
                c = validate(self._body())
            except Exception as e:
                return self._json(400, {"error": str(e)})
            save_config(c)
            self._json(200, {"config": c, "tables": tables(c)})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        p = urlparse(self.path).path
        if p == "/api/build":
            try:
                body = self._body()
                c = validate(body) if body.get("palette") else load_config()
                self._json(200, build(c))
            except Exception as e:
                self._json(400, {"error": str(e)})
        elif p == "/api/flash":
            body = self._body()
            img = body.get("image") or (state["last_build"] or {}).get("path")
            if img == "stock":
                img = STOCK
                if not os.path.exists(img):
                    return self._json(400, {"error": "stock image missing: run stock/extract_stock.py first"})
            elif img and "/" not in img:
                img = os.path.join(OUT, img)
            if not img or not os.path.exists(img):
                return self._json(400, {"error": "no image; build first or pass {'image': 'stock'}"})
            try:
                cf.recovery_check(img, bool(body.get("no_recovery_check")))
            except cf.FlashError as e:
                return self._json(400, {"error": str(e)})
            with lock:
                if state["job"] and state["job"]["phase"] in ("waiting", "flashing"):
                    return self._json(409, {"error": "a flash job is already running"})
                state["job"] = {"image": img, "phase": "starting", "progress": 0, "log": [], "started": time.time()}
            threading.Thread(target=run_job, args=(img,), daemon=True).start()
            self._json(200, state["job"])
        elif p == "/api/job/cancel":
            if state["job"]:
                state["job"]["cancel"] = True
            self._json(200, state["job"] or {})
        else:
            self._json(404, {"error": "not found"})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"cascade lighting app on http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
