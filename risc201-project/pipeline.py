"""
RISC201 Parameterized 4-Stage & 6-Stage Pipeline Simulator (Part 1a, 2c, 2d, 3, 4)
Stages:
  - 4-Stage Mode: IF  -> OF -> EX -> RW
  - 6-Stage Mode: IF1 -> IF2 -> OF -> EX -> MEM -> RW

Features:
  - Driven directly by MicroSequencer (Horizontal or Vertical Control Store)
  - Driven by multi-algorithm ALU class for all arithmetic/logical/address/SP ops
  - Cycle-accurate RAW data hazard detection & pipeline stalling (inserts bubbles)
  - Control hazard branch/jump/call/ret resolution & pipeline flushing
  - Full-descending stack boundary verification & exception hooks
"""
from dataclasses import dataclass
from isa import (
    OPCODE,
    MNEMONIC,
    REG_SP,
    REG_RA,
    Decoded,
    is_halt,
)
from memory import Memory, RegisterFile, STACK_BASE
from sequencer import MicroSequencer
from alu import ALU, ALUResult, branch_taken
from disassembler import disassemble_word


@dataclass
class PipelineSlot:
    valid: bool = False
    pc: int = 0
    raw_instr: int = 0
    decoded: Decoded = None
    mnem: str = "Bubble"
    uPC: int = -1
    op_a: int = 0
    op_b: int = 0
    store_val: int = 0
    alu_out: int = 0
    mem_data: int = 0
    is_halt_instr: bool = False
    target_pc: int = 0


class PipelineSimulator:
    def __init__(
        self,
        num_stages: int = 4,
        control_mode: str = "horizontal",
        adder_mode: str = "cla",
        mul_mode: str = "booth_r2",
        div_mode: str = "goldschmidt",
    ):
        if num_stages not in (4, 6):
            raise ValueError("num_stages must be 4 or 6")
        self.num_stages = num_stages
        self.control_mode = control_mode
        self.sequencer = MicroSequencer(num_stages=num_stages, mode=control_mode)
        self.stage_names = self.sequencer.stages

        self.memory = Memory()
        self.regs = RegisterFile()
        self.alu = ALU(adder_mode=adder_mode, mul_mode=mul_mode, div_mode=div_mode)

        self.symbol_table: dict[str, int] = {}
        self.addr_to_label: dict[int, str] = {}
        self.breakpoints: set[int] = set()
        self.reset()

    def reset(self):
        self.memory.reset()
        self.regs.reset()
        self.alu.reset_stats()
        self.pc = 0
        self.flags = ALUResult(result=0, zero=0, carry=0, negative=0, overflow=0, hw_cycles=0)
        self.slots: list[PipelineSlot] = [PipelineSlot() for _ in range(self.num_stages)]
        self.halted = False
        self.fetch_halted = False

        # Performance Metrics
        self.cycles = 0
        self.instructions_retired = 0
        self.raw_stalls = 0
        self.branch_flushes = 0
        self.flushed_instructions = 0
        self.history: list[dict] = []

    def load_program(
        self,
        words: list[int],
        symbol_table: dict[str, int] = None,
        memory_map: dict[int, int] = None,
    ):
        self.reset()
        if memory_map:
            for addr, w in memory_map.items():
                self.memory.write_word(addr, w)
        else:
            self.memory.load_program(words, 0x0000)

        self.symbol_table = symbol_table or {}
        self.addr_to_label = {addr: name for name, addr in self.symbol_table.items()}

    def _dest_registers_of(self, slot: PipelineSlot) -> set[int]:
        """Returns registers modified by an active instruction slot in EX/MEM/RW."""
        if not slot.valid or slot.decoded is None:
            return set()
        mnem = slot.mnem
        d = slot.decoded
        dests = set()
        if mnem in (
            "ADD", "SUB", "MUL", "DIV", "MOD", "AND", "OR",
            "NOT", "MOV", "LSL", "LSR", "ASR", "LD"
        ):
            dests.add(d.rd)
        elif mnem in ("CALL", "RET"):
            dests.add(REG_SP)
        return dests

    def _source_registers_of(self, d: Decoded) -> set[int]:
        """Returns registers read by an instruction in the OF stage."""
        if d is None:
            return set()
        mnem = MNEMONIC.get(d.opcode, "NOP")
        srcs = set()
        if mnem in ("ADD", "SUB", "MUL", "DIV", "MOD", "AND", "OR", "LSL", "LSR", "ASR", "CMP"):
            srcs.add(d.rs1)
            if not d.IS_immediate:
                srcs.add(d.rs2)
        elif mnem in ("MOV", "NOT"):
            if not d.IS_immediate:
                srcs.add(d.rs2)
        elif mnem == "LD":
            srcs.add(d.rs1)
        elif mnem == "ST":
            srcs.add(d.rs1)
            srcs.add(d.rd)  # ST stores rd into Mem[rs1 + offset]
        elif mnem in ("CALL", "RET"):
            srcs.add(REG_SP)
        return srcs

    def _has_raw_hazard(self, of_slot: PipelineSlot, older_slots: list[PipelineSlot]) -> bool:
        if not of_slot.valid or of_slot.decoded is None:
            return False
        srcs = self._source_registers_of(of_slot.decoded)
        if not srcs:
            return False
        for older in older_slots:
            if srcs & self._dest_registers_of(older):
                return True
        return False

    def step(self) -> dict:
        """Advances the pipeline by 1 clock cycle."""
        if self.halted:
            return self.get_cycle_snapshot()

        self.cycles += 1
        n = self.num_stages

        # Identify stage indices for 4-stage vs 6-stage
        if n == 4:
            # 0:IF, 1:OF, 2:EX, 3:RW
            idx_of, idx_ex, idx_mem, idx_rw = 1, 2, 3, 3
        else:
            # 0:IF1, 1:IF2, 2:OF, 3:EX, 4:MEM, 5:RW
            idx_of, idx_ex, idx_mem, idx_rw = 2, 3, 4, 5

        next_slots = [PipelineSlot() for _ in range(n)]
        flush_younger = False
        new_pc_override = None

        # -----------------------------------------------------------------
        # 1. Stage RW (and combined MEM/RW in 4-stage)
        # -----------------------------------------------------------------
        rw_slot = self.slots[idx_rw]
        if rw_slot.valid:
            sig = self.sequencer.decode_microword(rw_slot.uPC)
            d = rw_slot.decoded

            if n == 4:
                # In 4-stage mode, memory access happens inside RW
                if sig.get("StackPush"):
                    self.memory.validate_stack_pointer(rw_slot.alu_out, is_push=True, pc=rw_slot.pc, instr=rw_slot.raw_instr)
                    self.memory.write_word(rw_slot.alu_out, rw_slot.pc + 4, pc=rw_slot.pc, instr=rw_slot.raw_instr)
                    lbl = self.addr_to_label.get(rw_slot.target_pc)
                    self.memory.record_call(rw_slot.alu_out, rw_slot.pc + 4, rw_slot.target_pc, lbl)
                    self.regs.write(REG_SP, rw_slot.alu_out)
                elif sig.get("StackPop"):
                    old_sp = self.regs.read(REG_SP)
                    self.memory.validate_stack_pointer(rw_slot.alu_out, is_push=False, pc=rw_slot.pc, instr=rw_slot.raw_instr)
                    ret_addr = self.memory.read_word(old_sp, pc=rw_slot.pc, instr=rw_slot.raw_instr)
                    self.memory.record_ret(old_sp)
                    self.regs.write(REG_SP, rw_slot.alu_out)
                    rw_slot.mem_data = ret_addr
                elif sig.get("MemRead"):
                    # Check if this LD is part of a POP macro on SP
                    rw_slot.mem_data = self.memory.read_word(rw_slot.alu_out, pc=rw_slot.pc, instr=rw_slot.raw_instr)
                elif sig.get("MemWrite"):
                    # Check if writing to stack region
                    if rw_slot.decoded.rs1 == REG_SP:
                        self.memory.validate_stack_pointer(rw_slot.alu_out, is_push=True, pc=rw_slot.pc, instr=rw_slot.raw_instr)
                    self.memory.write_word(
                        rw_slot.alu_out,
                        rw_slot.store_val,
                        pc=rw_slot.pc,
                        instr=rw_slot.raw_instr,
                        annotation=f"Saved r{d.rd}" if d.rs1 == REG_SP else None,
                    )

            # Register Writeback
            if sig.get("RegWrite"):
                val = rw_slot.mem_data if sig.get("MemToReg") else rw_slot.alu_out
                if d.rd == REG_SP and rw_slot.mnem in ("ADD", "SUB"):
                    is_push = (rw_slot.mnem == "SUB")
                    self.memory.validate_stack_pointer(val, is_push=is_push, pc=rw_slot.pc, instr=rw_slot.raw_instr)
                self.regs.write(d.rd, val)

            self.instructions_retired += 1
            if rw_slot.is_halt_instr:
                self.halted = True

        # -----------------------------------------------------------------
        # 2. Stage MEM (6-stage only: separate from RW)
        # -----------------------------------------------------------------
        if n == 6:
            mem_slot = self.slots[idx_mem]
            if mem_slot.valid:
                sig = self.sequencer.decode_microword(mem_slot.uPC)
                d = mem_slot.decoded

                if sig.get("StackPush"):
                    self.memory.validate_stack_pointer(mem_slot.alu_out, is_push=True, pc=mem_slot.pc, instr=mem_slot.raw_instr)
                    self.memory.write_word(mem_slot.alu_out, mem_slot.pc + 4, pc=mem_slot.pc, instr=mem_slot.raw_instr)
                    lbl = self.addr_to_label.get(mem_slot.target_pc)
                    self.memory.record_call(mem_slot.alu_out, mem_slot.pc + 4, mem_slot.target_pc, lbl)
                    self.regs.write(REG_SP, mem_slot.alu_out)
                elif sig.get("StackPop"):
                    old_sp = self.regs.read(REG_SP)
                    self.memory.validate_stack_pointer(mem_slot.alu_out, is_push=False, pc=mem_slot.pc, instr=mem_slot.raw_instr)
                    ret_addr = self.memory.read_word(old_sp, pc=mem_slot.pc, instr=mem_slot.raw_instr)
                    self.memory.record_ret(old_sp)
                    self.regs.write(REG_SP, mem_slot.alu_out)
                    mem_slot.mem_data = ret_addr
                elif sig.get("MemRead"):
                    mem_slot.mem_data = self.memory.read_word(mem_slot.alu_out, pc=mem_slot.pc, instr=mem_slot.raw_instr)
                elif sig.get("MemWrite"):
                    if d.rs1 == REG_SP:
                        self.memory.validate_stack_pointer(mem_slot.alu_out, is_push=True, pc=mem_slot.pc, instr=mem_slot.raw_instr)
                    self.memory.write_word(
                        mem_slot.alu_out,
                        mem_slot.store_val,
                        pc=mem_slot.pc,
                        instr=mem_slot.raw_instr,
                        annotation=f"Saved r{d.rd}" if d.rs1 == REG_SP else None,
                    )

                # Advance MEM -> RW
                adv = PipelineSlot(**mem_slot.__dict__)
                adv.uPC = self.sequencer.next_uPC(mem_slot.uPC)
                next_slots[idx_rw] = adv

        # -----------------------------------------------------------------
        # 3. Stage EX (ALU computation & Branch/Jump/Call/Ret resolution)
        # -----------------------------------------------------------------
        ex_slot = self.slots[idx_ex]
        if ex_slot.valid:
            sig = self.sequencer.decode_microword(ex_slot.uPC)
            d = ex_slot.decoded
            alu_op = sig.get("ALUOp")

            if sig.get("Call"):
                # SP - 4 via ALU
                sp_val = self.regs.read(REG_SP)
                res = self.alu.compute(sp_val, 4, "SUB", pc=ex_slot.pc, instr=ex_slot.raw_instr)
                ex_slot.alu_out = res.result
                target = (ex_slot.pc + d.offset * 4) & 0xFFFFFFFF
                ex_slot.target_pc = target
                flush_younger = True
                new_pc_override = target
            elif sig.get("Return"):
                # SP + 4 via ALU, and fetch return address from Mem[SP] to redirect PC
                sp_val = self.regs.read(REG_SP)
                res = self.alu.compute(sp_val, 4, "ADD", pc=ex_slot.pc, instr=ex_slot.raw_instr)
                ex_slot.alu_out = res.result
                self.memory.validate_stack_pointer(res.result, is_push=False, pc=ex_slot.pc, instr=ex_slot.raw_instr)
                ret_addr = self.memory.read_word(sp_val, pc=ex_slot.pc, instr=ex_slot.raw_instr)
                flush_younger = True
                new_pc_override = ret_addr
            elif alu_op:
                res = self.alu.compute(ex_slot.op_a, ex_slot.op_b, alu_op, pc=ex_slot.pc, instr=ex_slot.raw_instr)
                ex_slot.alu_out = res.result
                if sig.get("SetFlags"):
                    self.flags = res

            # Conditional or Unconditional Branch check
            if not ex_slot.is_halt_instr:
                if sig.get("Branch") == "EQ" and branch_taken("BEQ", self.flags):
                    flush_younger = True
                    new_pc_override = (ex_slot.pc + d.offset * 4) & 0xFFFFFFFF
                elif sig.get("Branch") == "GT" and branch_taken("BGT", self.flags):
                    flush_younger = True
                    new_pc_override = (ex_slot.pc + d.offset * 4) & 0xFFFFFFFF
                elif sig.get("Jump") and not sig.get("Call"):
                    flush_younger = True
                    new_pc_override = (ex_slot.pc + d.offset * 4) & 0xFFFFFFFF

            # Advance EX -> next stage (RW in 4-stage, MEM in 6-stage)
            adv = PipelineSlot(**ex_slot.__dict__)
            adv.uPC = self.sequencer.next_uPC(ex_slot.uPC)
            next_slots[idx_ex + 1] = adv

        # -----------------------------------------------------------------
        # 4. Handle Control Hazard Flush vs. Normal OF/IF Progression
        # -----------------------------------------------------------------
        if flush_younger:
            self.branch_flushes += 1
            for s_idx in range(idx_ex):
                if self.slots[s_idx].valid:
                    self.flushed_instructions += 1
            self.pc = new_pc_override
            self.fetch_halted = False
        else:
            # Check for RAW Data Hazard in OF stage against older instructions in next_slots
            of_slot = self.slots[idx_of]
            older_in_flight = [next_slots[i] for i in range(idx_ex, n) if next_slots[i].valid]
            if self._has_raw_hazard(of_slot, older_in_flight):
                # Stall OF and IF/IF1/IF2; insert bubble into EX
                self.raw_stalls += 1
                for i in range(idx_of + 1):
                    next_slots[i] = self.slots[i]
            else:
                # Operand Fetch (OF) reads registers and advances to EX
                if of_slot.valid:
                    sig = self.sequencer.decode_microword(of_slot.uPC)
                    d = of_slot.decoded
                    if sig.get("RegRead"):
                        of_slot.op_a = self.regs.read(d.rs1)
                        if d.IS_immediate:
                            of_slot.op_b = d.imm
                        else:
                            of_slot.op_b = self.regs.read(d.rs2)
                        if of_slot.mnem == "ST":
                            of_slot.store_val = self.regs.read(d.rd)

                    adv = PipelineSlot(**of_slot.__dict__)
                    adv.uPC = self.sequencer.next_uPC(of_slot.uPC)
                    next_slots[idx_ex] = adv

                # Advance IF stages
                if n == 6:
                    # IF2 -> OF
                    if2_slot = self.slots[1]
                    if if2_slot.valid:
                        adv = PipelineSlot(**if2_slot.__dict__)
                        adv.uPC = self.sequencer.next_uPC(if2_slot.uPC)
                        next_slots[2] = adv
                    # IF1 -> IF2
                    if1_slot = self.slots[0]
                    if if1_slot.valid:
                        adv = PipelineSlot(**if1_slot.__dict__)
                        adv.uPC = self.sequencer.next_uPC(if1_slot.uPC)
                        next_slots[1] = adv
                else:
                    # 4-stage: IF -> OF
                    if_slot = self.slots[0]
                    if if_slot.valid:
                        adv = PipelineSlot(**if_slot.__dict__)
                        adv.uPC = self.sequencer.next_uPC(if_slot.uPC)
                        next_slots[1] = adv

                # Fetch new instruction into stage 0 (IF or IF1)
                if not self.fetch_halted and (0 <= self.pc < self.memory.size):
                    raw_word = self.memory.read_word(self.pc, pc=self.pc)
                    d = Decoded.DECODE(raw_word)
                    start_uPC = self.sequencer.dispatch(d.opcode, pc=self.pc, instr=raw_word)
                    mnem = MNEMONIC.get(d.opcode, "UNKNOWN")
                    halt_flag = is_halt(d)
                    next_slots[0] = PipelineSlot(
                        valid=True,
                        pc=self.pc,
                        raw_instr=raw_word,
                        decoded=d,
                        mnem="HLT" if halt_flag else mnem,
                        uPC=start_uPC,
                        is_halt_instr=halt_flag,
                    )
                    if halt_flag:
                        self.fetch_halted = True
                    else:
                        self.pc += 4

        self.slots = next_slots
        snap = self.get_cycle_snapshot()
        self.history.append(snap)
        return snap

    def run(self, max_cycles: int = 50000) -> dict:
        while not self.halted and self.cycles < max_cycles:
            # Check breakpoints on IF stage PC
            if self.slots[0].valid and self.slots[0].pc in self.breakpoints:
                break
            self.step()
        return self.get_metrics()

    def get_cycle_snapshot(self) -> dict:
        stage_info = {}
        for s_name, slot in zip(self.stage_names, self.slots):
            if slot.valid:
                asm_str = "HLT" if slot.is_halt_instr else disassemble_word(slot.raw_instr, slot.pc, self.addr_to_label)
                stage_info[s_name] = {
                    "pc": slot.pc,
                    "asm": asm_str,
                    "mnem": slot.mnem,
                    "uPC": slot.uPC,
                }
            else:
                stage_info[s_name] = {"pc": None, "asm": "--- (Bubble)", "mnem": "Bubble", "uPC": -1}
        return {
            "cycle": self.cycles,
            "pc": self.pc,
            "halted": self.halted,
            "stages": stage_info,
        }

    def format_pipeline_ascii(self) -> str:
        lines = [f"Cycle {self.cycles:4d} | Next Fetch PC: 0x{self.pc:04X} | Halted: {self.halted}"]
        lines.append("-" * 74)
        for s_name, slot in zip(self.stage_names, self.slots):
            if slot.valid:
                asm = "HLT (B 0)" if slot.is_halt_instr else disassemble_word(slot.raw_instr, slot.pc, self.addr_to_label)
                lines.append(f"  [{s_name:<3}] PC=0x{slot.pc:04X} | {asm:<26} | uPC=0x{slot.uPC:02X}")
            else:
                lines.append(f"  [{s_name:<3}] ----      | --- (Bubble)               | uPC=----")
        lines.append("-" * 74)
        return "\n".join(lines)

    def format_micro_ascii(self) -> str:
        lines = [
            f"Cycle {self.cycles:4d} | Microprogrammed Control Unit ({self.control_mode.upper()}, {self.num_stages}-Stage)"
        ]
        lines.append("=" * 86)
        for s_name, slot in zip(self.stage_names, self.slots):
            lines.append(self.sequencer.format_stage_micro(s_name, slot.mnem, slot.uPC if slot.valid else -1))
        lines.append("=" * 86)
        return "\n".join(lines)

    def get_metrics(self) -> dict:
        cpi = self.cycles / max(1, self.instructions_retired)
        return {
            "num_stages": self.num_stages,
            "control_mode": self.control_mode,
            "total_cycles": self.cycles,
            "instructions_retired": self.instructions_retired,
            "cpi": round(cpi, 3),
            "raw_stalls": self.raw_stalls,
            "branch_flushes": self.branch_flushes,
            "flushed_instructions": self.flushed_instructions,
            "alu_hw_cycles": self.alu.total_hw_cycles,
            "alu_mul_active_adds": self.alu.mul_active_adds,
        }
