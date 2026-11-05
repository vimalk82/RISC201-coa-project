"""
RISC201 Two-Pass Assembler (Part 2a)
Supports:
  - Full RISC201 instruction set (21 opcodes)
  - Macro expansion via preprocessor.py (PUSH, POP, HLT, CLR)
  - Directives: .org <addr>, .word <val>
  - Register & Immediate modes with optional 'u' (unsigned) and 'h' (high) modifiers
  - Bracketed memory addressing: LD r1, 8[r2] or LD r1, [r2]
  - Exports .hex, .bin, and symbol table dictionary
"""
import re
from isa import (
    OPCODE,
    FORMAT,
    modifier,
    Decoded,
    encode,
    Isbranchformat,
)
from preprocessor import preprocess_lines


def _parse_register(token: str) -> int:
    t = token.strip().lower()
    if t == "sp":
        return 14
    if t == "ra":
        return 15
    if t.startswith("r") and t[1:].isdigit():
        idx = int(t[1:])
        if 0 <= idx < 16:
            return idx
    raise ValueError(f"Invalid register token: '{token}'")


def _is_register(token: str) -> bool:
    try:
        _parse_register(token)
        return True
    except ValueError:
        return False


def _parse_immediate(token: str) -> tuple[int, modifier]:
    t = token.strip().lstrip("#")
    mod = modifier.D
    if t.lower().endswith("u") and not t.lower().startswith("0x"):
        mod = modifier.U
        t = t[:-1]
    elif t.lower().endswith("h") and not t.lower().startswith("0x"):
        mod = modifier.H
        t = t[:-1]
    elif t.lower().startswith("0x") and t.lower().endswith("u"):
        mod = modifier.U
        t = t[:-1]

    val = int(t, 0)
    return val & 0xFFFF, mod


class Assembler:
    def __init__(self):
        self.symbol_table: dict[str, int] = {}
        self.instructions: list[tuple[int, str]] = []

    def assemble(self, source_text: str) -> tuple[list[int], dict[str, int], dict[int, int]]:
        """
        Assembles RISC201 source text.
        Returns:
          - words: list of encoded 32-bit words (contiguous from 0 or loaded into memory_map)
          - symbol_table: dict mapping label -> byte address
          - memory_map: dict mapping byte_address -> encoded 32-bit word
        """
        expanded_lines = preprocess_lines(source_text.splitlines())
        self.symbol_table.clear()
        self.instructions.clear()

        #  PASS 1: Symbol Table & Address Tracking 
        pc = 0
        for line in expanded_lines:
            work = line.strip()
            if not work:
                continue

            while ":" in work:
                label, rest = work.split(":", 1)
                label = label.strip()
                if label in self.symbol_table:
                    raise ValueError(f"Duplicate label definition: '{label}'")
                self.symbol_table[label] = pc
                work = rest.strip()

            if not work:
                continue

            parts = work.split(None, 1)
            head = parts[0].lower()
            if head == ".org":
                pc = int(parts[1].strip(), 0)
                continue
            elif head == ".word":
                self.instructions.append((pc, work))
                pc += 4
                continue
            else:
                self.instructions.append((pc, work))
                pc += 4

        #  PASS 2: Instruction Encoding 
        memory_map: dict[int, int] = {}
        max_addr = 0
        for addr, instr_str in self.instructions:
            word = self._encode_statement(addr, instr_str)
            memory_map[addr] = word & 0xFFFFFFFF
            if addr > max_addr:
                max_addr = addr

        # Also return contiguous list from 0..max_addr for convenience
        num_words = (max_addr // 4) + 1 if memory_map else 0
        words = [memory_map.get(i * 4, 0) for i in range(num_words)]
        return words, dict(self.symbol_table), memory_map

    def _encode_statement(self, pc: int, stmt: str) -> int:
        parts = stmt.split(None, 1)
        mnem = parts[0].upper()
        arg_str = parts[1].strip() if len(parts) > 1 else ""

        if mnem == ".WORD":
            val = int(arg_str, 0) if not (arg_str in self.symbol_table) else self.symbol_table[arg_str]
            return val & 0xFFFFFFFF

        if mnem not in OPCODE:
            raise ValueError(f"Unknown instruction mnemonic '{mnem}' at PC=0x{pc:04X}")

        op = OPCODE[mnem]
        d = Decoded(opcode=op)

        # 1. Zero-operand instructions: NOP, RET
        if mnem in ("NOP", "RET"):
            d.format = FORMAT.BRANCH if mnem == "RET" else FORMAT.REGISTER
            return encode(d)

        # 2. Branch / Jump / Call: BEQ, BGT, B, CALL
        if Isbranchformat(op):
            d.format = FORMAT.BRANCH
            target = arg_str.strip()
            if target in self.symbol_table:
                target_addr = self.symbol_table[target]
                d.offset = (target_addr - pc) // 4
            else:
                d.offset = int(target, 0)
            return encode(d)

        # 3. Load / Store: LD rd, offset[rs1] or ST rd, offset[rs1]
        if mnem in ("LD", "ST"):
            args = [a.strip() for a in arg_str.split(",")]
            if len(args) != 2:
                raise ValueError(f"{mnem} expects 2 arguments (e.g. {mnem} r1, 4[r2]), got: {stmt}")
            d.rd = _parse_register(args[0])
            mem_expr = args[1]
            m = re.match(r'^([+-]?(?:0x[0-9a-fA-F]+|\d+))?\s*\[\s*([a-zA-Z0-9]+)\s*\]$', mem_expr)
            if not m:
                raise ValueError(f"Invalid memory operand '{mem_expr}' in '{stmt}'")
            offset_str, base_reg_str = m.group(1), m.group(2)
            d.rs1 = _parse_register(base_reg_str)
            d.IS_immediate = True
            d.format = FORMAT.IMMEDIATE
            d.modifi = modifier.D
            d.immvalue = (int(offset_str, 0) & 0xFFFF) if offset_str else 0
            return encode(d)

        # Split remaining comma-separated arguments
        args = [a.strip() for a in arg_str.split(",") if a.strip()]

        # 4. 2-operand instructions: MOV rd, op2 | NOT rd, op2 | CMP rs1, op2
        if mnem in ("MOV", "NOT"):
            if len(args) != 2:
                raise ValueError(f"{mnem} expects 2 operands, got: {stmt}")
            d.rd = _parse_register(args[0])
            d.rs1 = 0
            if _is_register(args[1]):
                d.IS_immediate = False
                d.format = FORMAT.REGISTER
                d.rs2 = _parse_register(args[1])
            else:
                d.IS_immediate = True
                d.format = FORMAT.IMMEDIATE
                d.immvalue, d.modifi = _parse_immediate(args[1])
            return encode(d)

        if mnem == "CMP":
            if len(args) != 2:
                raise ValueError(f"CMP expects 2 operands, got: {stmt}")
            d.rd = 0
            d.rs1 = _parse_register(args[0])
            if _is_register(args[1]):
                d.IS_immediate = False
                d.format = FORMAT.REGISTER
                d.rs2 = _parse_register(args[1])
            else:
                d.IS_immediate = True
                d.format = FORMAT.IMMEDIATE
                d.immvalue, d.modifi = _parse_immediate(args[1])
            return encode(d)

        # 5. 3-operand ALU & Shift instructions: ADD, SUB, MUL, DIV, MOD, AND, OR, LSL, LSR, ASR
        if len(args) != 3:
            raise ValueError(f"{mnem} expects 3 operands, got: {stmt}")
        d.rd = _parse_register(args[0])
        d.rs1 = _parse_register(args[1])
        if _is_register(args[2]):
            d.IS_immediate = False
            d.format = FORMAT.REGISTER
            d.rs2 = _parse_register(args[2])
        else:
            d.IS_immediate = True
            d.format = FORMAT.IMMEDIATE
            d.immvalue, d.modifi = _parse_immediate(args[2])
        return encode(d)

    def save_outputs(self, words: list[int], hex_path: str = None, bin_path: str = None):
        if hex_path:
            with open(hex_path, "w") as f:
                for w in words:
                    f.write(f"{w:08X}\n")
        if bin_path:
            with open(bin_path, "w") as f:
                for w in words:
                    f.write(f"{w:032b}\n")
