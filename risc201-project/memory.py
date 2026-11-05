"""
RISC201 Memory Subsystem, Register File & Stack Safety (Part 2c, 2f)
"""
from isa import MEMORY_SIZE, REGISTERS, REG_SP, REG_RA, BITS
from exceptions import (
    StackOverflowError,
    StackUnderflowError,
    MemoryAccessViolation,
    UnalignedAccessError,
)

WORD_MASK = (1 << BITS) - 1

# Address Space Layout (64 KB total)
CODE_BASE = 0x0000
CODE_LIMIT = 0x3FFF      # 16 KB Code Segment
DATA_BASE = 0x4000
DATA_LIMIT = 0xDFFF      # 40 KB Data/Heap Segment
STACK_LIMIT = 0xFC00     # 1 KB Stack Segment (0xFC00 .. 0xFFFC) for fast overflow testing & visualization
STACK_BASE = 0xFFFC      # Full-descending stack starts at 0xFFFC


class RegisterFile:
    """16 x 32-bit general purpose registers (r0..r15). r14=SP, r15=RA."""
    def __init__(self, stack_base: int = STACK_BASE):
        self.stack_base = stack_base
        self.regs = [0] * REGISTERS
        self.regs[REG_SP] = self.stack_base

    def read(self, reg_idx: int) -> int:
        if not (0 <= reg_idx < REGISTERS):
            raise ValueError(f"Invalid register index: r{reg_idx}")
        return self.regs[reg_idx] & WORD_MASK

    def write(self, reg_idx: int, value: int):
        if not (0 <= reg_idx < REGISTERS):
            raise ValueError(f"Invalid register index: r{reg_idx}")
        self.regs[reg_idx] = value & WORD_MASK

    def reset(self):
        self.regs = [0] * REGISTERS
        self.regs[REG_SP] = self.stack_base

    def dump(self) -> dict[str, int]:
        return {f"r{i}": self.regs[i] for i in range(REGISTERS)}


class Memory:
    """Byte-addressable, word-aligned 64 KB memory with stack boundary protection."""
    def __init__(self, size: int = MEMORY_SIZE, stack_base: int = STACK_BASE, stack_limit: int = STACK_LIMIT):
        self.size = size
        self.stack_base = stack_base
        self.stack_limit = stack_limit
        self._mem: dict[int, int] = {}
        # Tracks active stack annotations: sp_addr -> description string
        self.stack_annotations: dict[int, str] = {}
        # Tracks active CALL frames: list of (sp_addr, return_pc, target_pc)
        self.call_frames: list[tuple[int, int, int]] = []

    def reset(self):
        self._mem.clear()
        self.stack_annotations.clear()
        self.call_frames.clear()

    def load_program(self, words: list[int], base_addr: int = 0x0000):
        for i, word in enumerate(words):
            addr = base_addr + i * 4
            self._mem[addr] = word & WORD_MASK

    def _check_address(self, addr: int, pc: int = 0, instr: int = 0):
        if addr % 4 != 0:
            raise UnalignedAccessError(
                f"Unaligned word access at address 0x{addr:04X}", pc=pc, instruction=instr
            )
        if addr < 0 or addr >= self.size:
            raise MemoryAccessViolation(
                f"Address 0x{addr:04X} out of valid memory range [0x0000, 0x{self.size - 1:04X}]",
                pc=pc,
                instruction=instr,
            )

    def validate_stack_pointer(self, new_sp: int, is_push: bool, pc: int = 0, instr: int = 0):
        if new_sp % 4 != 0:
            raise UnalignedAccessError(
                f"Stack pointer 0x{new_sp:04X} is not 4-byte aligned", pc=pc, instruction=instr
            )
        if is_push and new_sp < self.stack_limit:
            raise StackOverflowError(
                f"Stack overflow! SP=0x{new_sp:04X} crossed below STACK_LIMIT=0x{self.stack_limit:04X}",
                pc=pc,
                instruction=instr,
            )
        if (not is_push) and new_sp > self.stack_base:
            raise StackUnderflowError(
                f"Stack underflow! SP=0x{new_sp:04X} exceeded STACK_BASE=0x{self.stack_base:04X}",
                pc=pc,
                instruction=instr,
            )

    def read_word(self, addr: int, pc: int = 0, instr: int = 0) -> int:
        self._check_address(addr, pc, instr)
        return self._mem.get(addr, 0) & WORD_MASK

    def write_word(self, addr: int, value: int, pc: int = 0, instr: int = 0, annotation: str = None):
        self._check_address(addr, pc, instr)
        self._mem[addr] = value & WORD_MASK
        if annotation:
            self.stack_annotations[addr] = annotation

    def record_call(self, sp_addr: int, return_pc: int, target_pc: int, label_name: str = None):
        self.call_frames.append((sp_addr, return_pc, target_pc))
        target_str = f"{label_name} (0x{target_pc:04X})" if label_name else f"0x{target_pc:04X}"
        self.stack_annotations[sp_addr] = f"<RET ADDR -> 0x{return_pc:04X} [from CALL {target_str}]>"

    def record_ret(self, old_sp_addr: int):
        if self.call_frames and self.call_frames[-1][0] == old_sp_addr:
            self.call_frames.pop()
