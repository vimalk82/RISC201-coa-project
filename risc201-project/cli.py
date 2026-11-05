"""
RISC201 Interactive CLI Simulator & Step-by-Step Debugger (Part 2c, 2d, Part 3)
Commands:
  - load <file.asm|file.hex> [4|6] [horizontal|vertical]
  - step [N]           : Advance N cycles (default 1) and print pipeline state
  - run                : Execute until HLT, breakpoint, or runtime exception
  - break <label|addr> : Set or toggle a PC breakpoint
  - regs               : Display all 16 registers (r0..r15) and ALU flags
  - mem <addr> [count] : Display memory words starting at <addr>
  - pipeline           : Show current pipeline stage occupancy
  - micro              : Show per-stage microPC (uPC), microword, and control signals
  - stack              : Render live ASCII stack memory frame visualizer
  - disasm             : Disassemble loaded program
  - metrics            : Print CPI, cycle count, stalls, flushes, and ALU stats
  - reset              : Reset CPU state to cycle 0
  - help / quit
"""
import sys
import cmd
from isa import REG_SP, REG_RA, sign_extention
from assembler import Assembler
from disassembler import disassemble_program
from pipeline import PipelineSimulator
from stack_viz import render_stack
from exceptions import RISC201Exception


def _to_signed32(val: int) -> int:
    val &= 0xFFFFFFFF
    return val - (1 << 32) if (val & (1 << 31)) else val


class RISC201DebuggerCLI(cmd.Cmd):
    intro = (
        "========================================================================\n"
        "  RISC201 Interactive CPU Pipeline, Microcode & Stack Debugger (v1.0)   \n"
        "  Type 'help' or '?' to list commands.                                  \n"
        "========================================================================"
    )
    prompt = "(risc201-dbg) "

    def __init__(self, sim: PipelineSimulator = None):
        super().__init__()
        self.sim = sim or PipelineSimulator(num_stages=4, control_mode="horizontal")
        self.assembler = Assembler()
        self.loaded_words: list[int] = []
        self.loaded_symbols: dict[str, int] = {}
        self.loaded_mem_map: dict[int, int] = {}

    def do_load(self, arg: str):
        """load <path.asm|path.hex> [4|6] [horizontal|vertical]"""
        parts = arg.split()
        if not parts:
            print("Usage: load <file.asm|file.hex> [4|6] [horizontal|vertical]")
            return
        path = parts[0]
        stages = int(parts[1]) if len(parts) > 1 else self.sim.num_stages
        mode = parts[2].lower() if len(parts) > 2 else self.sim.control_mode

        try:
            with open(path, "r") as f:
                text = f.read()
            self.sim = PipelineSimulator(num_stages=stages, control_mode=mode)
            if path.endswith(".hex"):
                words = [int(line.strip(), 16) for line in text.splitlines() if line.strip()]
                self.loaded_words = words
                self.loaded_symbols = {}
                self.loaded_mem_map = {i * 4: w for i, w in enumerate(words)}
            else:
                words, syms, mem_map = self.assembler.assemble(text)
                self.loaded_words = words
                self.loaded_symbols = syms
                self.loaded_mem_map = mem_map

            self.sim.load_program(self.loaded_words, self.loaded_symbols, self.loaded_mem_map)
            print(
                f"Loaded '{path}' ({len(self.loaded_words)} words) into "
                f"{stages}-stage pipeline [{mode.upper()} control store]."
            )
        except Exception as e:
            print(f"[Load Error] {e}")

    def do_step(self, arg: str):
        """step [N] : Step N clock cycles (default 1)."""
        count = int(arg.strip()) if arg.strip().isdigit() else 1
        try:
            for _ in range(count):
                if self.sim.halted:
                    print("CPU is halted.")
                    break
                self.sim.step()
            print(self.sim.format_pipeline_ascii())
            print(self.sim.format_micro_ascii())
        except RISC201Exception as ex:
            print("\n" + "!" * 74)
            print("  RUNTIME EXCEPTION CAUGHT BY DEBUGGER:")
            print("  " + ex.format_diagnostic())
            print("!" * 74)
            self.do_regs("")
            self.do_stack("")

    def do_run(self, arg: str):
        """run : Run until HLT, breakpoint, or exception."""
        try:
            metrics = self.sim.run()
            print(self.sim.format_pipeline_ascii())
            print(f"Execution finished: {metrics}")
        except RISC201Exception as ex:
            print("\n" + "!" * 74)
            print("  RUNTIME EXCEPTION CAUGHT BY DEBUGGER:")
            print("  " + ex.format_diagnostic())
            print("!" * 74)
            self.do_regs("")
            self.do_stack("")

    def do_break(self, arg: str):
        """break <label_or_hex_addr> : Set a breakpoint."""
        target = arg.strip()
        if not target:
            print(f"Active breakpoints: {[f'0x{bp:04X}' for bp in sorted(self.sim.breakpoints)]}")
            return
        if target in self.loaded_symbols:
            addr = self.loaded_symbols[target]
        else:
            addr = int(target, 0)
        self.sim.breakpoints.add(addr)
        print(f"Breakpoint set at PC=0x{addr:04X}")

    def do_regs(self, arg: str):
        """regs : Display all 16 registers and condition flags."""
        print("=" * 72)
        print(f"  REGISTER FILE (PC = 0x{self.sim.pc:04X}, Cycle = {self.sim.cycles})")
        print("-" * 72)
        for row in range(4):
            items = []
            for col in range(4):
                r_idx = row * 4 + col
                val = self.sim.regs.read(r_idx)
                s_val = _to_signed32(val)
                tag = "(SP)" if r_idx == REG_SP else ("(RA)" if r_idx == REG_RA else f"    ")
                items.append(f"r{r_idx:<2}{tag}: 0x{val:08X} ({s_val:d})")
            print("  " + " | ".join(items[:2]))
            print("  " + " | ".join(items[2:]))
        f = self.sim.flags
        print("-" * 72)
        print(f"  FLAGS: Z={f.zero}  C={f.carry}  N={f.negative}  V={f.overflow}")
        print("=" * 72)

    def do_mem(self, arg: str):
        """mem <start_addr> [word_count] : Hex/Signed dump of memory words."""
        parts = arg.split()
        start = int(parts[0], 0) if parts else 0
        count = int(parts[1], 0) if len(parts) > 1 else 8
        for i in range(count):
            addr = start + i * 4
            val = self.sim.memory._mem.get(addr, 0)
            print(f"  Mem[0x{addr:04X}] = 0x{val:08X}  ({_to_signed32(val)})")

    def do_pipeline(self, arg: str):
        """pipeline : Display current pipeline latch state."""
        print(self.sim.format_pipeline_ascii())

    def do_micro(self, arg: str):
        """micro : Display per-stage microPC (uPC), raw microword, and control signals."""
        print(self.sim.format_micro_ascii())

    def do_stack(self, arg: str):
        """stack : Render ASCII stack frame visualizer."""
        sp_val = self.sim.regs.read(REG_SP)
        print(render_stack(self.sim.memory, sp_val, self.loaded_symbols))

    def do_disasm(self, arg: str):
        """disasm : Print disassembled program."""
        print(disassemble_program(self.loaded_words, self.loaded_symbols))

    def do_metrics(self, arg: str):
        """metrics : Print performance statistics."""
        for k, v in self.sim.get_metrics().items():
            print(f"  {k:<24}: {v}")

    def do_reset(self, arg: str):
        """reset : Reset CPU state and reload current program."""
        self.sim.load_program(self.loaded_words, self.loaded_symbols, self.loaded_mem_map)
        print("Simulator reset to Cycle 0.")

    def do_quit(self, arg: str):
        """quit : Exit the debugger."""
        return True

    def do_EOF(self, arg: str):
        print()
        return True


if __name__ == "__main__":
    cli = RISC201DebuggerCLI()
    if len(sys.argv) > 1:
        cli.do_load(" ".join(sys.argv[1:]))
    cli.cmdloop()
