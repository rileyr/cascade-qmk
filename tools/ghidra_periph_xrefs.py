# Ghidra headless post-script (Jython). Dumps every function and, for each
# function, the peripheral addresses (0x4xxxxxxx) it references via literal
# pools, plus RAM globals (0x2000xxxx). Output: <program>_xrefs.txt next to the
# project directory given as the first script argument.
# Usage: analyzeHeadless <proj> cascade -import fw.bin -processor ARM:LE:32:Cortex
#        -loader BinaryLoader -loader-baseAddr 0x0 -postScript ghidra_periph_xrefs.py <outdir>
import os
from ghidra.program.model.symbol import RefType

args = getScriptArgs()
outdir = args[0] if args else "."
prog = currentProgram
listing = prog.getListing()
fm = prog.getFunctionManager()
rm = prog.getReferenceManager()
out = open(os.path.join(outdir, prog.getName() + "_xrefs.txt"), "w")

out.write("# functions: %d\n" % fm.getFunctionCount())
funcs = list(fm.getFunctions(True))
for f in funcs:
    periph = {}
    rams = set()
    body = f.getBody()
    it = listing.getInstructions(body, True)
    while it.hasNext():
        ins = it.next()
        for r in rm.getReferencesFrom(ins.getAddress()):
            a = r.getToAddress().getOffset()
            if 0x40000000 <= a < 0x40100000:
                periph.setdefault(a, 0)
                periph[a] += 1
            elif 0x20000000 <= a < 0x20002000:
                rams.add(a)
        # literal-pool loads: the data the ldr points at may itself hold the address
        for r in rm.getReferencesFrom(ins.getAddress()):
            d = listing.getDataAt(r.getToAddress())
            if d is not None and d.isDefined() and d.getLength() == 4:
                try:
                    v = d.getValue()
                    if v is not None:
                        v = v.getValue() if hasattr(v, "getValue") else int(str(v), 0)
                        if 0x40000000 <= v < 0x40100000:
                            periph.setdefault(v, 0)
                            periph[v] += 1
                        elif 0x20000000 <= v < 0x20002000:
                            rams.add(v)
                except Exception:
                    pass
    callers = len(set(r.getFromAddress() for r in rm.getReferencesTo(f.getEntryPoint())))
    out.write("%s @%s size=%d callers=%d\n" % (f.getName(), f.getEntryPoint(), body.getNumAddresses(), callers))
    if periph:
        out.write("   periph: %s\n" % ", ".join("0x%08x x%d" % (k, periph[k]) for k in sorted(periph)))
    if rams:
        out.write("   ram: %s\n" % ", ".join("0x%08x" % k for k in sorted(rams)[:24]))
out.close()
print("wrote xrefs for %d functions" % len(funcs))
