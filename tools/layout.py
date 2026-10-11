#!/usr/bin/env python3
"""A deliberately small linker/layout stage for this one-section firmware."""
import argparse
import json
import struct
from pathlib import Path

ELF_HEADER = struct.Struct("<16sHHIIIIIHHHHHH")
SECTION = struct.Struct("<IIIIIIIIII")
SYMBOL = struct.Struct("<IIIBBH")
RELOCATION = struct.Struct("<IIi")
SHT_RELA, SHT_REL, SHT_SYMTAB = 4, 9, 2
R_XTENSA_32, R_XTENSA_ASM_EXPAND, R_XTENSA_SLOT0_OP = 1, 11, 20


def read_elf(path: Path):
    blob = path.read_bytes()
    header = ELF_HEADER.unpack_from(blob)
    ident = header[0]
    shoff = header[6]
    shnum = header[12]
    shstrndx = header[13]
    if ident[:4] != b"\x7fELF" or ident[4] != 1 or ident[5] != 1:
        raise ValueError("expected 32-bit little-endian ELF")
    sections = [SECTION.unpack_from(blob, shoff + i * SECTION.size) for i in range(shnum)]
    names = blob[sections[shstrndx][4]:sections[shstrndx][4] + sections[shstrndx][5]]

    def name(index):
        end = names.find(b"\0", index)
        return names[index:end].decode()

    return blob, sections, [name(section[0]) for section in sections]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("object", type=Path)
    parser.add_argument("raw", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--load-address", type=lambda s: int(s, 0), required=True)
    args = parser.parse_args()

    blob, sections, names = read_elf(args.object)
    literal_index = names.index(".literal")
    text_index = names.index(".text")
    literal = sections[literal_index]
    text = sections[text_index]

    symbol_index = next(i for i, section in enumerate(sections) if section[1] == SHT_SYMTAB)
    symbols = sections[symbol_index]
    strings = sections[symbols[6]]
    strtab = blob[strings[4]:strings[4] + strings[5]]
    symbol_values = []
    entry_offset = None
    for offset in range(0, symbols[5], symbols[9]):
        st_name, st_value, _, _, _, st_shndx = SYMBOL.unpack_from(blob, symbols[4] + offset)
        end = strtab.find(b"\0", st_name)
        symbol_values.append((st_value, st_shndx))
        if st_shndx == text_index and strtab[st_name:end] == b"_start":
            entry_offset = st_value
            break
    if entry_offset is None:
        raise ValueError("_start is missing from .text")

    literal_bytes = bytearray(blob[literal[4]:literal[4] + literal[5]])
    literal_bytes += b"\0" * (-len(literal_bytes) % 4)
    text_bytes = bytearray(blob[text[4]:text[4] + text[5]])
    text_bytes += b"\0" * (-len(text_bytes) % 4)
    bases = {literal_index: args.load_address, text_index: args.load_address + len(literal_bytes)}

    def resolve(symbol, addend):
        value, section = symbol_values[symbol]
        if section not in bases:
            raise ValueError("relocation refers to an unsupported section")
        return bases[section] + value + addend

    for section, section_name in zip(sections, names):
        if section[1] not in (SHT_RELA, SHT_REL) or not section[5]:
            continue
        if section[1] != SHT_RELA or section[6] != symbol_index:
            raise ValueError(f"unsupported relocation encoding: {section_name}")
        if section[7] == literal_index:
            output, output_base = literal_bytes, bases[literal_index]
        elif section[7] == text_index:
            output, output_base = text_bytes, bases[text_index]
        else:
            continue  # metadata relocations have no role in a flat ROM image
        for offset in range(0, section[5], section[9]):
            location, info, addend = RELOCATION.unpack_from(blob, section[4] + offset)
            symbol, kind = info >> 8, info & 0xff
            target = resolve(symbol, addend)
            if kind == R_XTENSA_32:
                # Xtensa ELF stores the addend for this literal relocation in
                # the word itself (the two call targets start as 0xAB).
                target += struct.unpack_from("<I", output, location)[0]
                struct.pack_into("<I", output, location, target)
            elif kind == R_XTENSA_SLOT0_OP:
                if location + 3 > len(output):
                    raise ValueError("truncated instruction relocation")
                # Physical byte order is opcode/register, imm8 low, imm8 high.
                if output[location] & 0x0f != 1:
                    # Local PC-relative branches were resolved by the assembler.
                    # Their displacement survives moving the complete .text block.
                    continue
                pc_base = (output_base + location + 3) & ~3
                delta = target - pc_base
                if delta % 4 or not -(1 << 17) <= delta <= -4:
                    raise ValueError("l32r target is out of range")
                immediate = (delta // 4) & 0xffff
                output[location + 1] = immediate & 0xff
                output[location + 2] = immediate >> 8
                decoded = pc_base + ((immediate if immediate < 0x8000 else immediate - 0x10000) << 2)
                if decoded != target:
                    raise ValueError("l32r relocation verification failed")
            elif kind == R_XTENSA_ASM_EXPAND:
                pass  # call0 expands to l32r/callx; its literal was relocated above
            else:
                raise ValueError(f"unsupported relocation type {kind} in {section_name}")

    machine_code = literal_bytes + text_bytes
    args.raw.write_bytes(machine_code)
    args.manifest.write_text(json.dumps({
        "load_address": args.load_address,
        "entry_address": bases[text_index] + entry_offset,
        "bytes": len(machine_code),
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
