#!/usr/bin/env python3
"""Minimal ESP32 ROM UART flasher: SYNC, FLASH_BEGIN, FLASH_DATA, FLASH_END."""
import argparse
import hashlib
import struct
import time
from pathlib import Path

import serial

SYNC, FLASH_BEGIN, FLASH_DATA, FLASH_END, READ_REG = 0x08, 0x02, 0x03, 0x04, 0x0A
SPI_ATTACH, SPI_SET_PARAMS, SPI_FLASH_MD5 = 0x0D, 0x0B, 0x13
BLOCK = 0x400


def slip(packet):
    return b"\xc0" + packet.replace(b"\xdb", b"\xdb\xdd").replace(b"\xc0", b"\xdb\xdc") + b"\xc0"


def read_packet(port, timeout=3):
    deadline = time.monotonic() + timeout
    packet = bytearray()
    escaped = False
    while time.monotonic() < deadline:
        byte = port.read(1)
        if not byte:
            continue
        value = byte[0]
        if value == 0xC0:
            if packet:
                return bytes(packet)
            continue
        if escaped:
            packet.append(0xC0 if value == 0xDC else 0xDB if value == 0xDD else value)
            escaped = False
        elif value == 0xDB:
            escaped = True
        else:
            packet.append(value)
    raise TimeoutError("ROM did not return a packet")


def command(port, opcode, data=b"", checksum=0, timeout=3):
    port.write(slip(struct.pack("<BBHI", 0, opcode, len(data), checksum) + data))
    while True:
        packet = read_packet(port, timeout)
        if len(packet) < 8:
            continue
        direction, response, length, value = struct.unpack_from("<BBHI", packet)
        if len(packet) != 8 + length:
            # Boot messages or a partial response can still be in the UART
            # FIFO immediately after reset.  They are not SLIP command replies.
            continue
        status = packet[8 + length - 4:8 + length]
        if direction == 1 and response == opcode:
            if len(status) != 4:
                raise RuntimeError("ROM response has no four-byte status")
            if status[0]:
                raise RuntimeError(f"ROM command {opcode:#x} failed: {status.hex()}")
            return value, packet[8:8 + length - 4]


def xor_checksum(data):
    value = 0xEF
    for byte in data:
        value ^= byte
    return value


def reset_to_download(port):
    # The board inverts both CP2102 modem-control outputs: deasserted DTR
    # releases IO0 high; asserted RTS holds EN low.
    port.dtr = False
    port.rts = True
    time.sleep(0.1)
    port.dtr = True
    port.rts = False
    time.sleep(0.05)
    port.dtr = False
    time.sleep(0.05)


def synchronize(port):
    sync = b"\x07\x07\x12\x20" + b"\x55" * 32
    last_error = None
    for _ in range(25):
        port.reset_input_buffer()
        port.reset_output_buffer()
        try:
            command(port, SYNC, sync, timeout=0.1)
            for _ in range(7):
                read_packet(port, 0.2)
            return
        except (TimeoutError, RuntimeError) as error:
            last_error = error
            # The ROM commonly ignores the first one or two SYNC frames just
            # after reset.  Keep the chip in download mode and retry, rather
            # than resetting it between every frame.
            time.sleep(0.05)
    raise last_error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("offset", type=lambda s: int(s, 0))
    parser.add_argument("--port", required=True)
    parser.add_argument("--probe", action="store_true", help="synchronize and read chip ID only")
    args = parser.parse_args()
    image = args.image.read_bytes()
    padded = image + b"\xff" * (-len(image) % BLOCK)
    with serial.Serial(args.port, 115200, timeout=0.1, write_timeout=3) as port:
        reset_to_download(port)
        port.reset_input_buffer()
        synchronize(port)
        chip_id, _ = command(port, READ_REG, struct.pack("<I", 0x3FF00044))
        print(f"ROM synchronized; chip ID register: {chip_id:#010x}")
        if args.probe:
            return
        command(port, SPI_ATTACH, struct.pack("<II", 0, 0))
        command(port, SPI_SET_PARAMS, struct.pack("<IIIIII", 0, 4 * 1024 * 1024, 64 * 1024, 4096, 256, 0xFFFF))
        blocks = len(padded) // BLOCK
        command(port, FLASH_BEGIN, struct.pack("<IIII", len(padded), blocks, BLOCK, args.offset), timeout=10)
        for sequence in range(blocks):
            block = padded[sequence * BLOCK:(sequence + 1) * BLOCK]
            command(port, FLASH_DATA, struct.pack("<IIII", BLOCK, sequence, 0, 0) + block, xor_checksum(block))
        _, remote_md5 = command(port, SPI_FLASH_MD5, struct.pack("<IIII", args.offset, len(padded), 0, 0))
        if remote_md5.decode("ascii") != hashlib.md5(padded).hexdigest():
            raise RuntimeError("ROM flash MD5 does not match uploaded bytes")
        command(port, FLASH_END, struct.pack("<I", 0))
        print(f"Wrote and verified {len(image)} bytes at {args.offset:#x} using ESP32 ROM UART protocol.")


if __name__ == "__main__":
    main()
