#!/usr/bin/env python3
"""Decompile the whole stock image with Ghidra via PyGhidra.

Writes out/cascade_decomp.c (every function, decompiled, in address order)
and out/cascade_funcs.txt (address, size, name, peripheral addresses used).

Usage: GHIDRA_INSTALL_DIR=tools/ghidra_12.2_PUBLIC .venv/bin/python tools/decompile_all.py
"""
import os
import sys

import pyghidra

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "stock", "cascade_v15_sn32.bin")
PROJ = os.path.join(ROOT, "tools", "ghidra_proj")
OUT = os.path.join(ROOT, "out")

pyghidra.start()
from ghidra.app.decompiler import DecompInterface  # noqa: E402
from ghidra.program.model.address import AddressSet  # noqa: E402
from ghidra.util.task import ConsoleTaskMonitor  # noqa: E402

with pyghidra.open_program(BIN, project_location=PROJ, project_name="cascade_py",
                           language="ARM:LE:32:Cortex", analyze=False) as flat:
    prog = flat.getCurrentProgram()
    mem = prog.getMemory()
    space = prog.getAddressFactory().getDefaultAddressSpace()
    tx = prog.startTransaction("blocks")
    for name, start, size in (("sram", 0x20000000, 0x2000), ("periph", 0x40000000, 0x100000), ("ppb", 0xE0000000, 0x100000)):
        try:
            mem.createUninitializedBlock(name, space.getAddress(start), size, False)
        except Exception as e:  # already there on re-run
            print("block", name, e)
    # entry points from the vector table: reset + every populated IRQ vector
    import struct
    data = open(BIN, "rb").read()
    for i in range(1, 48):
        v = struct.unpack_from("<I", data, 4 * i)[0]
        if v and v < 0x10000:
            flat.disassemble(space.getAddress(v & ~1))
            flat.createFunction(space.getAddress(v & ~1), None)
    prog.endTransaction(tx, True)
    flat.analyzeAll(prog)

    monitor = ConsoleTaskMonitor()
    dec = DecompInterface()
    dec.openProgram(prog)
    fm = prog.getFunctionManager()
    rm = prog.getReferenceManager()
    listing = prog.getListing()
    funcs = sorted(fm.getFunctions(True), key=lambda f: f.getEntryPoint().getOffset())
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "cascade_decomp.c"), "w") as c, open(os.path.join(OUT, "cascade_funcs.txt"), "w") as t:
        for f in funcs:
            periph = set()
            it = listing.getInstructions(f.getBody(), True)
            while it.hasNext():
                ins = it.next()
                for r in rm.getReferencesFrom(ins.getAddress()):
                    a = r.getToAddress().getOffset()
                    if 0x40000000 <= a < 0x40100000:
                        periph.add(a)
                    d = listing.getDataAt(r.getToAddress())
                    if d is not None and d.isDefined() and d.getLength() == 4:
                        try:
                            v = int(str(d.getValue()), 0)
                            if 0x40000000 <= v < 0x40100000:
                                periph.add(v)
                        except Exception:
                            pass
            t.write("0x%05x size=%5d %s periph=%s\n" % (f.getEntryPoint().getOffset(), f.getBody().getNumAddresses(), f.getName(),
                    ",".join("0x%08x" % p for p in sorted(periph))))
            res = dec.decompileFunction(f, 60, monitor)
            c.write("\n// ===== %s @ 0x%05x =====\n" % (f.getName(), f.getEntryPoint().getOffset()))
            if res.decompileCompleted():
                c.write(res.getDecompiledFunction().getC())
            else:
                c.write("// decompile failed: %s\n" % res.getErrorMessage())
    print("functions:", len(funcs))
