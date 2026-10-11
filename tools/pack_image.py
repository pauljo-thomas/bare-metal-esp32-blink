#!/usr/bin/env python3
"""Pack one IRAM segment into the ESP32 ROM image format (version 1)."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

ESP32_HEADER_PREFIX = bytes((0xE9, 1, 2, 0x20))  # magic, segment count, DIO, 4 MB/40 MHz
# wp pin, six flash-drive fields, chip ID, legacy min revision,
# min/max full revision, reserved bytes, append-SHA256 flag.
ESP32_EXTENDED_HEADER = bytes((
    0xEE, 0, 0, 0, 0, 0, 0, 0, 0,
    0xFF, 0xFF, 0, 0, 0, 0, 1,
))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("raw", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    layout = json.loads(args.manifest.read_text())
    code = args.raw.read_bytes()
    if len(code) != layout["bytes"] or len(code) % 4:
        raise ValueError("raw image does not match aligned layout")

    image = bytearray(ESP32_HEADER_PREFIX)
    image += struct.pack("<I", layout["entry_address"])
    image += ESP32_EXTENDED_HEADER
    image += struct.pack("<II", layout["load_address"], len(code))
    image += code

    checksum = 0xEF
    for byte in code:
        checksum ^= byte
    image += b"\0" * (-(len(image) + 1) % 16)
    image.append(checksum)
    image += hashlib.sha256(image).digest()
    args.output.write_bytes(image)


if __name__ == "__main__":
    main()
