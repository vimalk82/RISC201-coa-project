"""
RISC201 Instruction Set Architecture (ISA)
Fixed & Extended for Parts 1-5
"""
from enum import Enum
from dataclasses import dataclass

BITS = 32
REGISTERS = 16           # r0 to r15
REG_SP = 14              # Stack Pointer (r14)
REG_RA = 15              # Return Address (r15)
NUM_INSTRUCTIONS = 21
SIZE_INSTRUCTION = 4     # 4 bytes per instruction
MEMORY_SIZE = 1 << 16    # 64 KB address space

OPCODE = {
    "ADD": 0,
    "SUB": 1,
    "MUL": 2,
    "DIV": 3,
    "MOD": 4,
    "CMP": 5,
    "AND": 6,
    "OR":  7,
    "NOT": 8,
    "MOV": 9,
    "LSL": 10,
    "LSR": 11,
    "ASR": 12,
    "NOP": 13,
    "LD":  14,
    "ST":  15,
    "BEQ": 16,
    "BGT": 17,
    "B":   18,
    "CALL": 19,
    "RET": 20,
}

MNEMONIC = {code: name for name, code in OPCODE.items()}
INVALID_OPCODE = 65


class FORMAT(Enum):
    BRANCH = 1
    REGISTER = 2
    IMMEDIATE = 3


class modifier(Enum):
    D = 0  # Default signed 16-bit
    U = 1  # Unsigned 16-bit
    H = 2  # High 16-bit (shifted left by 16)


def Isbranchformat(opcode: int) -> bool:
    return opcode in {
        OPCODE["BEQ"],
        OPCODE["BGT"],
        OPCODE["B"],
        OPCODE["CALL"],
        OPCODE["RET"],
    }


def fmt(opcode: int) -> FORMAT:
    if Isbranchformat(opcode):
        return FORMAT.BRANCH
    return FORMAT.REGISTER


# Bit Extraction Helpers
def get_opcode(instruction: int) -> int:
    return (instruction >> 27) & 0x1F

def get_imm(instruction: int) -> int:
    return (instruction >> 26) & 0x1

def get_rd(instruction: int) -> int:
    return (instruction >> 22) & 0xF

def get_rs1(instruction: int) -> int:
    return (instruction >> 18) & 0xF

def get_rs2(instruction: int) -> int:
    return (instruction >> 14) & 0xF

def get_immvalue(instruction: int) -> int:
    return instruction & 0x3FFFF

def get_modifi(instruction: int) -> int:
    return (instruction >> 16) & 0x3

def get_16imm(instruction: int) -> int:
    return instruction & 0xFFFF

def get_offset(instruction: int) -> int:
    return instruction & 0x7FFFFFF


# Encoding Helpers
def encod_op(opcode: int) -> int:
    return (int(opcode) & 0x1F) << 27

def encode_I(i: int) -> int:
    return (1 if i else 0) << 26

def encode_rd(rd: int) -> int:
    return (int(rd) & 0xF) << 22

def encode_rs1(rs1: int) -> int:
    return (int(rs1) & 0xF) << 18

def encode_rs2(rs2: int) -> int:
    return (int(rs2) & 0xF) << 14

def encode_offset(offset: int) -> int:
    return int(offset) & 0x7FFFFFF

def encode_imm(mod: int, C: int) -> int:
    mod_val = mod.value if isinstance(mod, modifier) else int(mod)
    return ((mod_val & 0x3) << 16) | (int(C) & 0xFFFF)


def sign_extention(val: int, bits: int) -> int:
    val &= (1 << bits) - 1
    m = 1 << (bits - 1)
    return (val ^ m) - m


def expand_immediate(im: int, modifi: modifier) -> int:
    im = im & 0xFFFF
    if modifi == modifier.D:
        return sign_extention(im, 16) & 0xFFFFFFFF
    elif modifi == modifier.U:
        return im & 0xFFFFFFFF
    elif modifi == modifier.H:
        return (im << 16) & 0xFFFFFFFF
    return sign_extention(im, 16) & 0xFFFFFFFF


@dataclass
class Decoded:
    instruction: int = 0
    opcode: int = 0
    format: FORMAT = FORMAT.REGISTER
    modifi: modifier = modifier.D
    IS_immediate: bool = False
    rd: int = 0
    rs1: int = 0
    rs2: int = 0
    immvalue: int = 0
    imm: int = 0
    offset: int = 0

    @staticmethod
    def DECODE(instruction: int) -> "Decoded":
        d = Decoded()
        d.instruction = instruction & 0xFFFFFFFF
        d.opcode = get_opcode(d.instruction)

        if d.opcode == OPCODE["RET"]:
            d.format = FORMAT.BRANCH
            return d

        if Isbranchformat(d.opcode):
            d.format = FORMAT.BRANCH
            d.offset = sign_extention(get_offset(d.instruction), 27)
            return d

        d.rd = get_rd(d.instruction)
        d.rs1 = get_rs1(d.instruction)
        d.IS_immediate = (get_imm(d.instruction) == 1)

        if d.IS_immediate:
            d.format = FORMAT.IMMEDIATE
            mod_bits = get_modifi(d.instruction)
            if mod_bits > 2:
                mod_bits = 0
            d.modifi = modifier(mod_bits)
            d.immvalue = get_16imm(d.instruction)
            d.imm = expand_immediate(d.immvalue, d.modifi)
        else:
            d.format = FORMAT.REGISTER
            d.rs2 = get_rs2(d.instruction)

        return d


def encode(d: Decoded) -> int:
    instruction = encod_op(d.opcode)

    if d.format == FORMAT.BRANCH or Isbranchformat(d.opcode):
        if d.opcode != OPCODE["RET"]:
            instruction |= encode_offset(d.offset)
        return instruction & 0xFFFFFFFF

    instruction |= encode_I(1 if d.IS_immediate else 0)
    instruction |= encode_rd(d.rd)
    instruction |= encode_rs1(d.rs1)

    if d.IS_immediate:
        instruction |= encode_imm(d.modifi, d.immvalue & 0xFFFF)
    else:
        instruction |= encode_rs2(d.rs2)

    return instruction & 0xFFFFFFFF


@dataclass
class InstrInfo:
    mnem: str
    op: int
    writes_reg: bool
    supports_mod: bool
    uncond_branch: bool


INSTRUCTION_TABLE = [
    InstrInfo("ADD", OPCODE["ADD"], True, True, False),
    InstrInfo("SUB", OPCODE["SUB"], True, True, False),
    InstrInfo("MUL", OPCODE["MUL"], True, True, False),
    InstrInfo("DIV", OPCODE["DIV"], True, True, False),
    InstrInfo("MOD", OPCODE["MOD"], True, True, False),
    InstrInfo("CMP", OPCODE["CMP"], False, True, False),
    InstrInfo("AND", OPCODE["AND"], True, True, False),
    InstrInfo("OR", OPCODE["OR"], True, True, False),
    InstrInfo("NOT", OPCODE["NOT"], True, True, False),
    InstrInfo("MOV", OPCODE["MOV"], True, True, False),
    InstrInfo("LSL", OPCODE["LSL"], True, False, False),
    InstrInfo("LSR", OPCODE["LSR"], True, False, False),
    InstrInfo("ASR", OPCODE["ASR"], True, False, False),
    InstrInfo("NOP", OPCODE["NOP"], False, False, False),
    InstrInfo("LD", OPCODE["LD"], True, False, False),
    InstrInfo("ST", OPCODE["ST"], False, False, False),
    InstrInfo("BEQ", OPCODE["BEQ"], False, False, False),
    InstrInfo("BGT", OPCODE["BGT"], False, False, False),
    InstrInfo("B", OPCODE["B"], False, False, True),
    InstrInfo("CALL", OPCODE["CALL"], True, False, True),
    InstrInfo("RET", OPCODE["RET"], False, False, True),
]


def info_by_opcode(opcode: int):
    for info in INSTRUCTION_TABLE:
        if info.op == opcode:
            return info
    return None


def info_by_mnemonic(word: str):
    word = word.upper()
    for info in INSTRUCTION_TABLE:
        if info.mnem == word:
            return info
    return None


def opcode_mnemonic(opcode: int) -> str:
    info = info_by_opcode(opcode)
    return info.mnem if info else "UNKNOWN"


def writes_reg(d: Decoded) -> bool:
    info = info_by_opcode(d.opcode)
    return info is not None and info.writes_reg


def is_unconditional_branch(d: Decoded) -> bool:
    info = info_by_opcode(d.opcode)
    return info is not None and info.uncond_branch


def is_nop(d: Decoded) -> bool:
    return d.opcode == OPCODE["NOP"]


def is_halt(d: Decoded) -> bool:
    """HLT pseudo-op is encoded as B 0 (branch to self, offset == 0)."""
    return d.opcode == OPCODE["B"] and d.offset == 0
