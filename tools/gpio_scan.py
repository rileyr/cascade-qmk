#!/usr/bin/env python3
"""Sweep the stock image for code that touches SN32F240B GPIO ports and the
CT16B1 PWM, and print each access with the instructions around it.

Thumb code on Cortex-M0 reaches a peripheral by loading its address from a
literal pool (ldr rX,[pc,#imm]) and then ldr/str with a small offset. We walk
the whole image as Thumb, resolve every pc-relative literal, and report every
instruction whose base register was just loaded with a peripheral address.
"""
import struct
import sys
from collections import defaultdict

from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_OP_REG, ARM_REG_PC

PERIPH = {
    0x40044000: "GPIO0", 0x40046000: "GPIO1", 0x40048000: "GPIO2", 0x4004A000: "GPIO3",
    0x40000000: "CT16B0", 0x40002000: "CT16B1", 0x4001C000: "SPI0", 0x40026000: "ADC",
    0x40042000: "PFPA", 0x40032000: "PMU", 0x40060000: "SYS0", 0x4005E000: "SYS1",
    0x40016000: "UART0", 0x40014000: "UART1", 0x40012000: "UART2", 0x40018000: "I2C0",
}
GPIO_REGS = {0x00: "DATA", 0x04: "MODE", 0x08: "CFG", 0x0C: "IS", 0x10: "IBS", 0x14: "IEV",
             0x18: "IE", 0x1C: "RIS", 0x20: "IC", 0x24: "BSET", 0x28: "BCLR"}


def periph_name(addr):
    for base, name in PERIPH.items():
        if base <= addr < base + 0x1000:
            off = addr - base
            if name.startswith("GPIO"):
                return f"{name}.{GPIO_REGS.get(off, hex(off))}"
            return f"{name}+0x{off:x}"
    return None


def main():
    fw = open(sys.argv[1], "rb").read()
    start = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x100
    end = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0xB192
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    md.detail = True
    insns = list(md.disasm(fw[start:end], start))
    by_addr = {i.address: k for k, i in enumerate(insns)}
    regval = {}          # reg -> literal value, invalidated on any write to the reg
    hits = defaultdict(list)
    for k, i in enumerate(insns):
        ops = i.operands
        # record literal loads
        if i.mnemonic == "ldr" and len(ops) == 2 and ops[1].type == ARM_OP_MEM and ops[1].mem.base == ARM_REG_PC:
            lit = ((i.address + 4) & ~3) + ops[1].mem.disp
            if lit + 4 <= len(fw):
                regval[ops[0].reg] = struct.unpack_from("<I", fw, lit)[0]
            continue
        # memory access through a register that holds a peripheral address
        if i.mnemonic.startswith(("ldr", "str")) and ops and ops[-1].type == ARM_OP_MEM:
            m = ops[-1].mem
            base = regval.get(m.base)
            if base is not None and 0x40000000 <= base < 0x40100000 and m.index == 0:
                name = periph_name(base + m.disp)
                if name:
                    ctx = " | ".join(f"{x.mnemonic} {x.op_str}" for x in insns[max(0, k - 4): k + 3])
                    hits[name].append((i.address, f"{i.mnemonic} {i.op_str}", ctx))
        # invalidate written registers (first operand of most ALU/load ops)
        if ops and ops[0].type == ARM_OP_REG and not i.mnemonic.startswith(("str", "cmp", "tst", "b", "push")):
            regval.pop(ops[0].reg, None)
        if i.mnemonic in ("bl", "blx", "bx", "pop"):
            regval.clear()
    for name in sorted(hits):
        print(f"\n## {name}: {len(hits[name])} accesses")
        for a, ins, ctx in hits[name][:40]:
            print(f"  0x{a:05x}  {ins:28s}   [{ctx}]")


if __name__ == "__main__":
    main()
