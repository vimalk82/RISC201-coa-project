"""
RISC201 Disassembler (Part 2b)
Parses 32-bit binary or hexadecimal words and reconstructs RISC201 assembly.
Supports round-trip verification (assemble -> disassemble -> reassemble).
"""
from isa import (
    OPCODE,
    MNEMONIC,
    modifier,
    Decoded,
    Isbranchformat,
    sign_extention,
)


def _format_imm(d: Decoded) -> str:
    if d.modifi == modifier.U:
        return f"{d.immvalue}u"
    elif d.modifi == modifier.H:
        return f"{d.immvalue}h"
    else:
        signed_val = sign_extention(d.immvalue, 16)
        return str(signed_val)


def disassemble_word(word: int, pc: int = 0, addr_to_label: dict[int, str] = None) -> str:
    d = Decoded.DECODE(word)
    mnem = MNEMONIC.get(d.opcode, "UNKNOWN")
    if mnem == "UNKNOWN":
        return f".word 0x{word:08X}"

    if mnem in ("NOP", "RET"):
        return mnem

    if Isbranchformat(d.opcode):
        target_addr = pc + d.offset * 4
        if addr_to_label and target_addr in addr_to_label:
            return f"{mnem} {addr_to_label[target_addr]}"
        return f"{mnem} {d.offset}"

    if mnem in ("LD", "ST"):
        signed_off = sign_extention(d.immvalue, 16)
        return f"{mnem} r{d.rd}, {signed_off}[r{d.rs1}]"

    if mnem in ("MOV", "NOT"):
        op2 = _format_imm(d) if d.IS_immediate else f"r{d.rs2}"
        return f"{mnem} r{d.rd}, {op2}"

    if mnem == "CMP":
        op2 = _format_imm(d) if d.IS_immediate else f"r{d.rs2}"
        return f"CMP r{d.rs1}, {op2}"

    op2 = _format_imm(d) if d.IS_immediate else f"r{d.rs2}"
    return f"{mnem} r{d.rd}, r{d.rs1}, {op2}"


def disassemble_program(words: list[int], symbol_table: dict[str, int] = None) -> str:
    addr_to_label = {addr: name for name, addr in (symbol_table or {}).items()}
    lines = []
    for i, w in enumerate(words):
        pc = i * 4
        if pc in addr_to_label:
            lines.append(f"{addr_to_label[pc]}:")
        lines.append(f"    {disassemble_word(w, pc, addr_to_label)}")
    return "\n".join(lines)
