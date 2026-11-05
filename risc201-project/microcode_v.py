"""
RISC201 Vertical Microprogrammed Control Store (Part 1b, Part 3)
Uses compact encoded bit-fields for mutually exclusive control signals plus
combinational field decoders:
  - Bits 0..3   (4 bits) : ALUOp_Code (0=None, 1..12=ALU_OPS_LIST) -> 4-to-16 decoder
  - Bits 4..5   (2 bits) : ALUSrc_Code (0=None, 1=REG, 2=IMM)      -> 2-to-4 decoder
  - Bits 6..7   (2 bits) : MemOp_Code  (0=None, 1=MemRead, 2=MemWrite) -> 2-to-4 decoder
  - Bits 8..9   (2 bits) : Branch_Code (0=None, 1=EQ, 2=GT, 3=Jump) -> 2-to-4 decoder
  - Bits 10..11 (2 bits) : Stack_Code  (0=None, 1=Call/Push, 2=Ret/Pop) -> 2-to-4 decoder
  - Bit 12      (1 bit)  : RegRead
  - Bit 13      (1 bit)  : RegWrite
  - Bit 14      (1 bit)  : MemToReg
  - Bit 15      (1 bit)  : SetFlags
  - Bit 16      (1 bit)  : PCIncrement
  - Bit 17      (1 bit)  : EOI (End of Instruction)
Total Width = 18 bits per microword (vs 29 bits in Horizontal!).
"""
from isa import OPCODE
from microcode_h import ALU_OPS_LIST, default_signals, build_signal_table

VERTICAL_WORD_WIDTH = 18


def pack_vertical_word(sig: dict) -> int:
    word = 0
    # 1. ALUOp (4 bits: 0..3)
    alu_op = sig.get("ALUOp")
    if alu_op in ALU_OPS_LIST:
        word |= (ALU_OPS_LIST.index(alu_op) + 1) & 0xF

    # 2. ALUSrc (2 bits: 4..5)
    alu_src = sig.get("ALUSrc")
    if alu_src == "REG":
        word |= 1 << 4
    elif alu_src == "IMM":
        word |= 2 << 4

    # 3. MemOp (2 bits: 6..7)
    if sig.get("MemRead"):
        word |= 1 << 6
    elif sig.get("MemWrite"):
        word |= 2 << 6

    # 4. Branch/Jump (2 bits: 8..9)
    br = sig.get("Branch")
    if br == "EQ":
        word |= 1 << 8
    elif br == "GT":
        word |= 2 << 8
    elif sig.get("Jump"):
        word |= 3 << 8

    # 5. Stack/Subroutine (2 bits: 10..11)
    if sig.get("Call") or sig.get("StackPush"):
        # Note: In CALL, EX has Call=True & Jump=True; MEM/RW has StackPush=True & MemWrite=True
        code = 1 if sig.get("Call") else 2
        word |= code << 10
    elif sig.get("Return") or sig.get("StackPop"):
        code = 3 if sig.get("Return") else 4
        # Wait: 2 bits only hold 0..3! Let's use 1=Call(EX), 2=StackPush(MEM), 3=Return(EX)/StackPop(MEM)
        # Disambiguated by MemRead: if MemRead is active, 3 means StackPop; else Return!
        word |= 3 << 10

    if sig.get("RegRead"):
        word |= 1 << 12
    if sig.get("RegWrite"):
        word |= 1 << 13
    if sig.get("MemToReg"):
        word |= 1 << 14
    if sig.get("SetFlags"):
        word |= 1 << 15
    if sig.get("PCIncrement"):
        word |= 1 << 16
    if sig.get("EOI"):
        word |= 1 << 17

    return word


def unpack_vertical_word(word: int) -> dict:
    sig = default_signals()

    alu_code = word & 0xF
    if 1 <= alu_code <= len(ALU_OPS_LIST):
        sig["ALUOp"] = ALU_OPS_LIST[alu_code - 1]

    src_code = (word >> 4) & 0x3
    if src_code == 1:
        sig["ALUSrc"] = "REG"
    elif src_code == 2:
        sig["ALUSrc"] = "IMM"

    mem_code = (word >> 6) & 0x3
    if mem_code == 1:
        sig["MemRead"] = True
    elif mem_code == 2:
        sig["MemWrite"] = True

    br_code = (word >> 8) & 0x3
    if br_code == 1:
        sig["Branch"] = "EQ"
    elif br_code == 2:
        sig["Branch"] = "GT"
    elif br_code == 3:
        sig["Jump"] = True

    stk_code = (word >> 10) & 0x3
    if stk_code == 1:
        sig["Call"] = True
        sig["Jump"] = True
    elif stk_code == 2:
        sig["StackPush"] = True
    elif stk_code == 3:
        if sig["MemRead"]:
            sig["StackPop"] = True
        else:
            sig["Return"] = True

    sig["RegRead"] = bool((word >> 12) & 1)
    sig["RegWrite"] = bool((word >> 13) & 1)
    sig["MemToReg"] = bool((word >> 14) & 1)
    sig["SetFlags"] = bool((word >> 15) & 1)
    sig["PCIncrement"] = bool((word >> 16) & 1)
    sig["EOI"] = bool((word >> 17) & 1)

    return sig


def build_vertical_store(num_stages: int = 4) -> tuple[list[int], dict[int, int]]:
    sig_table = build_signal_table(num_stages)
    control_store: list[int] = []
    dispatch_rom: dict[int, int] = {}

    for mnem, op_code in sorted(OPCODE.items(), key=lambda x: x[1]):
        dispatch_rom[op_code] = len(control_store)
        for stage_sig in sig_table[mnem]:
            control_store.append(pack_vertical_word(stage_sig))

    return control_store, dispatch_rom
