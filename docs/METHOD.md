# How this was done

A short account, in case you want to do the same to another closed keyboard.

1. **Identify the chip without opening the case.** The USB descriptor gave Apple's VID/PID
   (spoofed for Mac media keys) and a 64-byte feature report, which is a flash channel of some
   kind. Azio's Windows updater turned out to be Sonix's own ISP tool: its strings name the
   SN32F2xx family and the bootloader commands. The FCC filing (ZPY-CASCADE) showed the
   Bluetooth daughterboard: a Cypress CYW20730 module, i.e. a separate, closed chip.
2. **Get the stock firmware without dumping the chip.** The updater embeds the full 64 KB image as
   a PE resource (type 10, id 4000), unencrypted. `stock/extract_stock.py` does the extraction.
3. **Prove recovery before changing anything.** The Sonix bootloader lives in ROM and is entered
   by shorting a boot pad at power-up; SonixQMK's flasher documents the HID protocol
   (`0x55AA01` init, `0x55AA05` prepare, 64-byte chunks, `0x55AA07` reboot). `tools/cascade_flash.py`
   speaks it. First flash was the stock image with only colour tables changed.
4. **Patch tables, then patch code.** The 8-colour palette and the 21-entry rainbow wheel are plain
   byte tables (0xadd0, 0xade8). Wave is not table-driven: it runs three phase-shifted ramps,
   one per colour channel. `stock/patch_wave.py` replaces its three lookups with `bl` calls to
   12-byte stubs in free flash that index per-channel tables sampled from the wheel.
5. **Recover the pinout from disassembly.** `tools/disasm.py` (capstone, with literal pools
   resolved and SN32 registers named) made the init code readable: the key rows are set as
   inputs in one function, the LED row pins are cleared together in another, the column drive is
   a 21-case switch table, and the LED scan is a 19-step state machine whose buffers map to red,
   green and blue. Everything matched the Keychron K2 family that SonixQMK already supports.
6. **Verify the matrix on hardware, not on paper.** A keys-only QMK build with the console on
   recorded each key's row/column; a later "probe" keymap that types `row.col` per key settled the
   last doubts. One column pin had been misread (the mask was built as 0xff+1, i.e. bit 8), which
   explained the one dead key.
7. **Shared matrix.** The LED columns and key columns are the same PWM pins. SonixQMK's driver
   scans keys between PWM frames when it is left to use the key column pins for both; giving it
   a separate column list breaks scanning.
8. **RAM is 8 KB.** VIA plus all effects overflowed by a few hundred bytes; a smaller
   wear-levelling cache and two keymap layers instead of four fixed it.
