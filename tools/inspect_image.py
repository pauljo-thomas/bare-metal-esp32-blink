#!/usr/bin/env python3
"""Independent validator for this project's single-segment ESP32 image."""
import argparse
import hashlib
import struct
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    blob = args.image.read_bytes()
    if len(blob) < 24 + 8 + 33 or blob[0] != 0xE9 or blob[1] != 1:
        raise ValueError("not a one-segment ESP32 ROM image")
    entry = struct.unpack_from("<I", blob, 4)[0]
    address, length = struct.unpack_from("<II", blob, 24)
    data_end = 32 + length
    checksum_offset = ((data_end + 1 + 15) & ~15) - 1
    if checksum_offset + 33 != len(blob):
        raise ValueError("unexpected image alignment or footer length")
    checksum = 0xEF
    for byte in blob[32:data_end]:
        checksum ^= byte
    if blob[checksum_offset] != checksum:
        raise ValueError("image XOR checksum is invalid")
    if hashlib.sha256(blob[:checksum_offset + 1]).digest() != blob[checksum_offset + 1:]:
        raise ValueError("image SHA-256 footer is invalid")
    if not address <= entry < address + length:
        raise ValueError("entry point is outside the load segment")
    print(f"valid: entry={entry:#010x} load={address:#010x} bytes={length}")


if __name__ == "__main__":
    main()
