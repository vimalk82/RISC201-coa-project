"""
RISC201 Horizontal Microprogrammed Control Store (Part 1b, Part 3)
Each microinstruction is an unencoded wide 30-bit control word (1 bit per control line,
one-hot ALU operation bits) with zero combinational decoding delay.
"""
from isa import OPCODE, MNEMONIC

STAGES_4 = ["IF", "OF", "EX", "RW"]
STAGES_6 = ["IF1", "IF2", "OF", "EX", "MEM", "RW"]

ALU_OPS_LIST = [
    "ADD", "SUB", "MUL", "DIV", "MOD", "AND", "OR",
    "NOT", "MOV", "LSL", "LSR", "ASR"
]

# Horizontal Bit Assignments (30 bits total: bits 0..29)
# Bits 0..11  : 12 One-Hot ALUOp lines
# Bit 12..13  : ALUSrc one-hot (bit 12 = REG, bit 13 = IMM)
# Bit 14      : RegRead
# Bit 15      : RegWrite
# Bit 16      : MemRead
# Bit 17      : MemWrite
# Bit 18      : MemToReg
# Bit 19      : SetFlags
# Bit 20..21  : Branch one-hot (bit 20 = EQ, bit 21 = GT)
# Bit 22      : Jump
# Bit 23      : Call
# Bit 24      : Return
# Bit 25      : StackPush
# Bit 26      : StackPop
# Bit 27      : PCIncrement
# Bit 28      : EOI (End of Instruction sequence flag)
HORIZONTAL_WORD_WIDTH = 29


def default_signals() -> dict:
    return {
        "ALUOp": None,
        "ALUSrc": None,
        "RegRead": False,
        "RegWrite": False,
        "MemRead": False,
        "MemWrite": False,
        "MemToReg": False,
        "SetFlags": False,
        "Branch": None,
        "Jump": False,
        "Call": False,
        "Return": False,
        "StackPush": False,
        "StackPop": False,
        "PCIncrement": False,
        "EOI": False,
    }


def pack_horizontal_word(sig: dict) -> int:
    word = 0
    alu_op = sig.get("ALUOp")
    if alu_op in ALU_OPS_LIST:
        word |= 1 << ALU_OPS_LIST.index(alu_op)

    alu_src = sig.get("ALUSrc")
    if alu_src == "REG":
        word |= 1 << 12
    elif alu_src == "IMM":
        word |= 1 << 13

    bool_fields = [
        (14, "RegRead"),
        (15, "RegWrite"),
        (16, "MemRead"),
        (17, "MemWrite"),
        (18, "MemToReg"),
        (19, "SetFlags"),
        (22, "Jump"),
        (23, "Call"),
        (24, "Return"),
        (25, "StackPush"),
        (26, "StackPop"),
        (27, "PCIncrement"),
        (28, "EOI"),
    ]
    for bit_pos, name in bool_fields:
        if sig.get(name):
            word |= 1 << bit_pos

    br = sig.get("Branch")
    if br == "EQ":
        word |= 1 << 20
    elif br == "GT":
        word |= 1 << 21

    return word


def unpack_horizontal_word(word: int) -> dict:
    sig = default_signals()
    for idx, op_name in enumerate(ALU_OPS_LIST):
        if (word >> idx) & 1:
            sig["ALUOp"] = op_name
            break

    if (word >> 12) & 1:
        sig["ALUSrc"] = "REG"
    elif (word >> 13) & 1:
        sig["ALUSrc"] = "IMM"

    bool_fields = [
        (14, "RegRead"),
        (15, "RegWrite"),
        (16, "MemRead"),
        (17, "MemWrite"),
        (18, "MemToReg"),
        (19, "SetFlags"),
        (22, "Jump"),
        (23, "Call"),
        (24, "Return"),
        (25, "StackPush"),
        (26, "StackPop"),
        (27, "PCIncrement"),
        (28, "EOI"),
    ]
    for bit_pos, name in bool_fields:
        sig[name] = bool((word >> bit_pos) & 1)

    if (word >> 20) & 1:
        sig["Branch"] = "EQ"
    elif (word >> 21) & 1:
        sig["Branch"] = "GT"

    return sig


def build_signal_table(num_stages: int = 4) -> dict[str, list[dict]]:
    stages = STAGES_4 if num_stages == 4 else STAGES_6
    table: dict[str, list[dict]] = {}

    def _add(mnem: str, of=None, ex=None, mem=None, rw=None):
        rows = [default_signals() for _ in stages]
        rows[0]["PCIncrement"] = True  # IF or IF1
        if num_stages == 4:
            if of: rows[1].update(of)
            if ex: rows[2].update(ex)
            if mem: rows[3].update(mem)
            if rw: rows[3].update(rw)
            rows[3]["EOI"] = True
        else:
            if of: rows[2].update(of)
            if ex: rows[3].update(ex)
            if mem: rows[4].update(mem)
            if rw: rows[5].update(rw)
            rows[5]["EOI"] = True
        table[mnem] = rows

    for mnem in ["ADD", "SUB", "MUL", "DIV", "MOD", "AND", "OR", "LSL", "LSR", "ASR"]:
        _add(
            mnem,
            of={"RegRead": True},
            ex={"ALUOp": mnem, "ALUSrc": "REG"},
            rw={"RegWrite": True, "MemToReg": False},
        )

    _add("CMP", of={"RegRead": True}, ex={"ALUOp": "SUB", "ALUSrc": "REG", "SetFlags": True})
    _add("NOT", of={"RegRead": True}, ex={"ALUOp": "NOT", "ALUSrc": "REG"}, rw={"RegWrite": True})
    _add("MOV", of={"RegRead": True}, ex={"ALUOp": "MOV", "ALUSrc": "REG"}, rw={"RegWrite": True})
    _add("NOP")
    _add(
        "LD",
        of={"RegRead": True},
        ex={"ALUOp": "ADD", "ALUSrc": "IMM"},
        mem={"MemRead": True},
        rw={"RegWrite": True, "MemToReg": True},
    )
    _add(
        "ST",
        of={"RegRead": True},
        ex={"ALUOp": "ADD", "ALUSrc": "IMM"},
        mem={"MemWrite": True},
    )
    _add("BEQ", ex={"Branch": "EQ"})
    _add("BGT", ex={"Branch": "GT"})
    _add("B", ex={"Jump": True})
    _add(
        "CALL",
        ex={"Jump": True, "Call": True, "ALUOp": "SUB", "ALUSrc": "IMM"},
        mem={"MemWrite": True, "StackPush": True},
    )
    _add(
        "RET",
        ex={"Return": True, "ALUOp": "ADD", "ALUSrc": "IMM"},
        mem={"MemRead": True, "StackPop": True},
    )
    return table


def build_horizontal_store(num_stages: int = 4) -> tuple[list[int], dict[int, int]]:
    """
    Returns:
      - control_store: numbered array of 29-bit horizontal microwords
      - dispatch_rom: dict mapping numeric opcode -> starting microPC (uPC)
    """
    sig_table = build_signal_table(num_stages)
    control_store: list[int] = []
    dispatch_rom: dict[int, int] = {}

    for mnem, op_code in sorted(OPCODE.items(), key=lambda x: x[1]):
        dispatch_rom[op_code] = len(control_store)
        for stage_sig in sig_table[mnem]:
            control_store.append(pack_horizontal_word(stage_sig))

    return control_store, dispatch_rom
