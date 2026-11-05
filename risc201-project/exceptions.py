"""
RISC201 Runtime Exception Hierarchy (Part 2f)
"""

class RISC201Exception(Exception):
    """Base class for all RISC201 processor & simulator runtime exceptions."""
    def __init__(self, message: str, pc: int = 0, instruction: int = 0):
        super().__init__(message)
        self.message = message
        self.pc = pc
        self.instruction = instruction

    def format_diagnostic(self) -> str:
        return (
            f"[{self.__class__.__name__}] at PC=0x{self.pc:04X} "
            f"(Instr=0x{self.instruction:08X}): {self.message}"
        )


class StackOverflowError(RISC201Exception):
    """Raised when SP drops below STACK_LIMIT during PUSH or CALL."""
    pass


class StackUnderflowError(RISC201Exception):
    """Raised when SP exceeds STACK_BASE during POP or RET."""
    pass


class MemoryAccessViolation(RISC201Exception):
    """Raised when accessing memory outside [0, MEMORY_SIZE) or writing to code segment."""
    pass


class UnalignedAccessError(RISC201Exception):
    """Raised when a word load/store/fetch address is not 4-byte aligned."""
    pass


class InvalidOpcodeError(RISC201Exception):
    """Raised when the control unit encounters an unknown opcode."""
    pass


class DivideByZeroError(RISC201Exception):
    """Raised when DIV or MOD attempts division by 0."""
    pass
