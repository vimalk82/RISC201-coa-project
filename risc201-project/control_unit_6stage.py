"""
Role 3 -- Microprogrammed Control Unit (RISC201, 6-STAGE pipeline)
Updated to import ISA constants from isa.py and wrap MicroSequencer.
"""
from isa import (
    BITS, REGISTERS, REG_SP, REG_RA, NUM_INSTRUCTIONS,
    SIZE_INSTRUCTION, MEMORY_SIZE, OPCODE, MNEMONIC, INVALID_OPCODE
)
from microcode_h import STAGES_6 as STAGES, default_signals, build_signal_table
from sequencer import MicroSequencer

CONTROL_MEMORY = build_signal_table(num_stages=6)

class ControlUnit(MicroSequencer):
    def __init__(self, mode: str = "horizontal"):
        super().__init__(num_stages=6, mode=mode)
        self.control_memory = CONTROL_MEMORY

    def decode_opcode(self, opcode_value: int) -> str:
        if opcode_value not in MNEMONIC:
            raise ValueError(f"Unknown opcode: {opcode_value}")
        return MNEMONIC[opcode_value]

    def signals_for(self, mnemonic: str, stage_index: int) -> dict:
        op = OPCODE[mnemonic]
        uPC = self.dispatch(op) + stage_index
        return self.decode_microword(uPC)

    def full_microprogram(self, mnemonic: str) -> dict:
        return dict(zip(STAGES, [self.signals_for(mnemonic, i) for i in range(6)]))
