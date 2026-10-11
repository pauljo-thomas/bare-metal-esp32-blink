# Bare-metal ESP32 blink

A minimal blink program for a classic ESP32-D0WD-V3 / ESP32-WROOM-32 board.
It runs directly on the Xtensa LX6 CPU without Arduino, ESP-IDF, FreeRTOS,
a C runtime, GNU `ld`, or esptool image packing and flashing.

The program configures GPIO2 as an output, drives it high for one second,
drives it low for one second, and repeats forever.

## What this project builds

```text
firmware.S
  -> Xtensa assembler -> build/blink.o
  -> tools/layout.py -> build/blink.raw + build/blink.json
  -> tools/pack_image.py -> build/blink.bin
  -> tools/rom_flash.py -> ESP32 flash offset 0x1000
```

At reset, the ESP32's immutable ROM bootloader reads the image at flash
offset `0x1000`, copies its one segment into RAM at `0x40080000`, and jumps
to `_start`.

## Hardware

- Classic ESP32-D0WD-V3 or ESP32-WROOM-32 style board
- USB serial connection, normally available as `/dev/ttyUSB0`
- LED on GPIO2, or an external LED with its anode connected through a
  220–1k ohm resistor to GPIO2 and its cathode connected to GND

## Requirements

- GNU Make
- Python 3 with `pyserial` (`python3 -m pip install pyserial`)
- A compatible `xtensa-esp32-elf` toolchain

Only the assembler is needed for a normal build. `make inspect` also uses
`xtensa-esp32-elf-readelf` and `xtensa-esp32-elf-objdump`.

The default toolchain path is:

```text
./xtensa-esp32-elf/bin
```

The toolchain is intentionally excluded from Git. Place it there locally, or
provide another location when running Make:

```sh
make TOOLCHAIN=/path/to/xtensa-esp32-elf/bin
```

## Build, inspect, and flash

```sh
make
make inspect
make flash PORT=/dev/ttyUSB0
```

`make` produces `build/blink.bin`.

`make inspect` displays the assembled object relocations and instructions,
then validates the ESP32 image header, segment, checksum, SHA-256 footer,
and entry address.

`make flash` uses the project’s ROM UART client. It enters serial download
mode, writes the image at flash offset `0x1000`, asks the ROM for the written
range MD5, compares it with the local MD5, and resets into normal boot.

To remove generated output:

```sh
make clean
```

## Repository layout

| Path | Purpose |
|---|---|
| `firmware.S` | Bare-metal Xtensa assembly: stack setup, watchdog disable, timer setup, GPIO2 setup, and the blink loop. |
| `Makefile` | Build commands and the connections between each build stage. |
| `tools/layout.py` | Small, purpose-built layout stage. It places `.literal` and `.text` in RAM and resolves the Xtensa relocations used by this firmware. |
| `tools/pack_image.py` | Creates a one-segment ESP32 ROM image with headers, XOR checksum, alignment padding, and SHA-256 footer. |
| `tools/inspect_image.py` | Independently validates the image created by the packer. |
| `tools/rom_flash.py` | Minimal UART client for the ESP32 ROM bootloader: reset, sync, flash write, and MD5 verification. |
| `build/` | Generated object, raw payload, layout manifest, and final firmware image. Not committed. |
| `xtensa-esp32-elf/` | Local Xtensa toolchain installation. Not committed. |

## Scope

The Python tools intentionally target this small direct-ROM-load workflow:
one RAM segment on a classic ESP32, written at `0x1000`. They are not general
replacements for a full linker or esptool: they do not support partition
tables, multiple segments, encrypted flash, secure boot, or other ESP32
families.
