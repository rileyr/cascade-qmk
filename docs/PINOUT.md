# Cascade Slim pinout, recovered from stock V1.5 (SN32F248B)

Port naming: GPIO0=A, GPIO1=B, GPIO2=C, GPIO3=D (SonixQMK convention).

## Key matrix (confirmed from scan code FUN_00001490)
- 16 columns, scanned in a loop `for col in 0..15`, column selected by FUN_000031b8(col).
- 6 row inputs sampled into one byte: bit0=C15, bit1=D11, bit2=D10, bit3=D9, bit4=D8, bit5=D7.
  Set as inputs in FUN_00002afc. Identical set and order to Keychron K2 v2 RGB
  (`rows: C15 D11 D10 D9 D8 D7`).
- Column pins are the CT16B1 PWM pins (shared matrix). PWMENB |= 0x00ffff00 enables
  channels 8..23 → pins A8..A15, B0..B7 (same as Keychron K2 `cols: A8..A15 B0..B7`).
  PFPA.CT16B1 = 0x1f (channels 0..4 mapped to B-pins; those channels are unused).
- Diode direction: to confirm (K2 is COL2ROW).

## LED matrix (FUN_00002b48 sets outputs, FUN_00002b70 clears all)
18 row-drive pins = 6 rows x 3 channels:
B12 C6 C9 C12 B13 B14 C0 C4 C7 C10 C13 D3 C1 C5 C8 C11 C14 B15
Keychron K2 uses the same set with C3 instead of B12. Per-row R/G/B grouping and
active level still to be read from the LED scan routine.
CT16B1: PRE=0x2f, period MR=0xff, interrupt at IRQ16 (handler 0x695c), NVIC enabled.
Framebuffer: three 128-word arrays at 0x20000674 (R), 0x20000874 (G), 0x20000a74 (B).
LED index tables: 0xa9c0 (21 cols x 6 rows → index, 127 = none), wave bands 0xac4e (12 x 12).

## Other pins seen in init
- A0 output (cleared), A1 input (FUN_00000ab8); A1 and A5 read with masks 2 / 0x20.
- C3 input with CFG pull (FUN_00000b8a), read early in init with mask 8 → likely the
  USB/OFF/BT slide switch. B11 input → likely the Mac/PC switch.
- SPI0 used (IRQ6 handler 0x36be) → Bluetooth module link. No UART use anywhere.
- GPIO interrupts: P0 (0x3694), P2 (0x54b8), P3 (0x54e6).

## Interrupt vectors
IRQ1 USB 0x5626 | IRQ6 SPI0 0x36be | IRQ15 CT16B0 0x441a (scan tick) | IRQ16 CT16B1 0x695c (LED PWM)
IRQ28 P3 0x54e6 | IRQ29 P2 0x54b8 | IRQ31 P0 0x3694 | SysTick 0x9fd0

## Column pins (decoded from the switch tables in FUN_00002eec / 0x3052 / 0x31b8)
Scan order col 0..15: B7 B6 B5 B4 B3 B2 B1 B0 A15 A14 A13 A12 A11 A10 A9 A8 (case 15 mask is 0xff+1 = bit 8; an earlier decode misread it as A7)
(16 key columns; the scan loop runs 16). Cases 16..20 of the same switch select
B7 B9 B10 B11 B12 and are used for something else (not key columns).
Note A7, not A8, is the 16th column; A7 is CT16B1 channel 7, which the LED PWM mask
0x00ffff00 does not enable, so that column may carry keys but no LEDs.

## LED matrix, fully decoded (LED scan state machine FUN_0000497a case 5 → steps 0..17)
Three PWM duty buffers in RAM: red 0x20000cf4, green 0x20000eec, blue 0x200010e4
(filled from framebuffers 0x674/0x874/0xa74 by FUN_00006cbc with brightness scaling).
Each row is 0x54 bytes = 21 x 32-bit duty words. FUN_000029b6 loads word i into
CT16B1 MR(23-i) for i=0..15, i.e. LED column c ↔ PWM channel 23-c ↔ pins
B7 B6 B5 B4 B3 B2 B1 B0 A15 A14 A13 A12 A11 A10 A9 A8 (words 16..20 go to MR0.. and are unused).
Rows are driven HIGH to light (BSET), all cleared between steps (FUN_00002b70) → active high.
Row pins by LED row and colour:
  row0 R=B12 G=C0  B=C1
  row1 R=C6  G=C4  B=C5
  row2 R=C9  G=C7  B=C8
  row3 R=C12 G=C10 B=C11
  row4 R=B13 G=C13 B=C14
  row5 R=B14 G=D3  B=B15
SonixQMK hardware-PWM driver consumes row pins per row in B,G,R order (case 0=b,1=g,2=r), so
SN32F2XX_RGB_MATRIX_ROW_PINS = { C1,C0,B12, C5,C4,C6, C8,C7,C9, C11,C10,C12, C14,C13,B13, B15,D3,B14 }
SN32F2XX_RGB_MATRIX_COL_PINS = { B7,B6,B5,B4,B3,B2,B1,B0, A15,A14,A13,A12,A11,A10,A9,A8 }
PWM: PRE=0x2f, period 0xff, channels 8..23 enabled; polarity to confirm on hardware (K2 uses active low).

## Verified key matrix (QMK, shared-matrix scan, 2025-11-11)
row 0: Esc F1..F12 PrtSc Ins Del  (cols 0..15)
row 1: ` 1 2 3 4 5 6 7 8 9 0 - = Bksp(13) Home(14)
row 2: Tab Q W E R T Y U I O P [ ] \(13) End(14)
row 3: Caps A S D F G H J K L ;(10) '(11) Enter(13) PgUp(14)
row 4: LShift(0) Z X C V B N M , . /(11) RShift(12) Up(13) PgDn(14)
row 5: LCtrl(0) Opt(1) LCmd(2) Space(6) RCmd(9) Fn(10) RCtrl(11) Left(12) Down(13) Right(14)
Empty slots (ISO/wide-key gaps): (1,15) (2,15) (3,12) (3,15) (4,1) (4,15) (5,3) (5,4) (5,5) (5,7) (5,8) (5,15)
LED columns share the key column pins (shared-matrix); separate COL_PINS breaks key scanning.
