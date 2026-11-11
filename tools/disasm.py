#!/usr/bin/env python3
"""Annotated Thumb disassembly of a range of the stock image.

Resolves pc-relative literal loads to their values, names SN32F240B peripheral
registers, and tracks which register currently holds which literal so that
ldr/str through it get a symbolic comment.

Usage: disasm.py image.bin START END
"""
import struct
import sys

from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs
from capstone.arm import ARM_OP_MEM, ARM_OP_REG, ARM_REG_PC

PERIPH = {0x40044000: "GPIO0", 0x40046000: "GPIO1", 0x40048000: "GPIO2", 0x4004A000: "GPIO3",
          0x40000000: "CT16B0", 0x40002000: "CT16B1", 0x4001C000: "SPI0", 0x40026000: "ADC",
          0x40042000: "PFPA", 0x40032000: "PMU", 0x40060000: "SYS0", 0x4005E000: "SYS1",
          0x4005C000: "USB", 0x40010000: "WDT", 0x40062000: "FLASH", 0x40016000: "UART0"}
GPIO_REGS = {0x00: "DATA", 0x04: "MODE", 0x08: "CFG", 0x0C: "IS", 0x10: "IBS", 0x14: "IEV",
             0x18: "IE", 0x1C: "RIS", 0x20: "IC", 0x24: "BSET", 0x28: "BCLR"}
CT16_REGS = {0x00: "TMRCTRL", 0x04: "TC", 0x08: "PRE", 0x0C: "PC", 0x10: "CNTCTRL", 0x14: "MCTRL", 0x18: "MCTRL2", 0x1C: "MCTRL3",
             0x20: "MR0", 0x24: "MR1", 0x28: "MR2", 0x2C: "MR3", 0x30: "MR4", 0x34: "MR5", 0x38: "MR6", 0x3C: "MR7", 0x40: "MR8",
             0x44: "MR9", 0x48: "MR10", 0x4C: "MR11", 0x50: "MR12", 0x54: "MR13", 0x58: "MR14", 0x5C: "MR15", 0x60: "MR16",
             0x64: "MR17", 0x68: "MR18", 0x6C: "MR19", 0x70: "MR20", 0x74: "MR21", 0x78: "MR22", 0x7C: "MR23", 0x80: "MR24",
             0x88: "CAP0", 0x8C: "EM", 0x90: "EMC", 0x94: "EMC2", 0x98: "PWMCTRL", 0x9C: "PWMCTRL2", 0xA0: "PWMENB", 0xA4: "PWMIOENB",
             0xA8: "RIS", 0xAC: "IC"}


def sym(addr):
    for base, name in PERIPH.items():
        if base <= addr < base + 0x1000:
            off = addr - base
            regs = GPIO_REGS if name.startswith("GPIO") else CT16_REGS if name.startswith("CT16") else {}
            return f"{name}.{regs.get(off, '+0x%x' % off)}"
    if 0x20000000 <= addr < 0x20002000:
        return f"ram_{addr & 0xFFFF:04x}"
    if addr < 0x10000:
        return f"flash_{addr:04x}"
    return None


def main():
    fw = open(sys.argv[1], "rb").read()
    start, end = int(sys.argv[2], 0), int(sys.argv[3], 0)
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    md.detail = True
    held = {}
    for i in md.disasm(fw[start:end], start):
        note = ""
        ops = i.operands
        if i.mnemonic == "ldr" and len(ops) == 2 and ops[1].type == ARM_OP_MEM and ops[1].mem.base == ARM_REG_PC:
            lit = ((i.address + 4) & ~3) + ops[1].mem.disp
            v = struct.unpack_from("<I", fw, lit)[0]
            held[ops[0].reg] = v
            note = f"= 0x{v:08x} {sym(v) or ''}"
        elif ops and ops[-1].type == ARM_OP_MEM and ops[-1].mem.base in held and ops[-1].mem.index == 0:
            a = held[ops[-1].mem.base] + ops[-1].mem.disp
            note = f"-> {sym(a) or '0x%x' % a}"
            if i.mnemonic.startswith("ldr") and ops[0].type == ARM_OP_REG:
                held.pop(ops[0].reg, None)
        elif ops and ops[0].type == ARM_OP_REG and not i.mnemonic.startswith(("str", "cmp", "tst", "b", "push")):
            if i.mnemonic in ("adds", "add") and len(ops) >= 2 and ops[0].reg in held and ops[-1].type != ARM_OP_REG:
                held[ops[0].reg] += ops[-1].imm
                note = f"= {sym(held[ops[0].reg]) or hex(held[ops[0].reg])}"
            else:
                held.pop(ops[0].reg, None)
        if i.mnemonic in ("bl",):
            note = f"call {sym(ops[0].imm) or hex(ops[0].imm)}"
        if i.mnemonic in ("bx", "pop") and "pc" in i.op_str or i.mnemonic == "bx":
            held.clear()
        print(f"{i.address:05x}: {i.mnemonic:6s} {i.op_str:28s} {note}")


if __name__ == "__main__":
    main()
