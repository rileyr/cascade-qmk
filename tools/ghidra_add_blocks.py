# Ghidra headless pre-script: add SRAM and peripheral memory blocks so that
# literal-pool addresses into them become real references during analysis.
from ghidra.program.model.address import AddressFactory

mem = currentProgram.getMemory()
space = currentProgram.getAddressFactory().getDefaultAddressSpace()
def blk(name, start, size):
    try:
        mem.createUninitializedBlock(name, space.getAddress(start), size, False)
        print("added block %s @0x%x" % (name, start))
    except Exception as e:
        print("block %s: %s" % (name, e))
blk("sram", 0x20000000, 0x2000)      # SN32F248B: 8 KB SRAM
blk("periph", 0x40000000, 0x100000)  # APB peripherals
blk("ppb", 0xE0000000, 0x100000)     # NVIC / SysTick
