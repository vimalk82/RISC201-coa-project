# RISC201 Processor Simulation & Evaluation Suite

A cycle-accurate simulator for **RISC201**, a 32-bit RISC processor. It models both a **4-stage** and a **6-stage** pipeline, microprogrammed control in **horizontal** and **vertical** forms, a multi-algorithm ALU, a full-descending stack with safety checks, and an interactive CLI debugger.

---

## Table of Contents

- [Repository Structure](#repository-structure)
- [Features](#features)
- [Getting Started](#getting-started)
- [Debugger Commands](#debugger-commands)
- [Team Work Distribution](#team-work-distribution)

---

## Repository Structure

```text
risc201_project/
├── isa.py                      # Instruction set, formats and bit extraction
├── assembler.py                # Two-pass assembler (.org, .word, label resolution)
├── disassembler.py             # Round-trip disassembler, rebuilds symbolic code
├── preprocessor.py             # Macro preprocessor (PUSH, POP, HLT, CLR)
├── memory.py                   # 64 KB segmented memory, register file, stack checks
├── exceptions.py               # Runtime exception hierarchy
├── stack_viz.py                # Live ASCII stack frame visualizer
├── microcode_h.py              # Horizontal control store (29-bit unencoded word)
├── microcode_v.py              # Vertical control store (18-bit encoded word + decoders)
├── sequencer.py                # Micro-sequencer, uPC progression, dispatch ROM
├── control_unit_4stage.py      # 4-stage microprogrammed control unit
├── control_unit_6stage.py      # 6-stage microprogrammed control unit
├── alu.py                      # Multi-algorithm ALU
├── pipeline.py                 # Cycle-accurate 4/6-stage simulator (RAW stalls, flushes)
├── cli.py                      # Interactive debugger shell
├── evaluate.py                 # Verification, benchmarks, CSV export and plots
├── tests/                      # Assembly benchmark programs (.asm)
└── plots/                      # Generated charts and CSV metrics
```

---

## Features

### Instruction Set & Toolchain *(Parts 1a, 2a, 2b, 2e)*

- 21 native instructions with 3 operand formats (branch, register, immediate).
- Source-to-source preprocessor that expands the full-descending stack macros (`PUSH rX`, `POP rX`) and the pseudo-ops (`HLT`, `CLR`).
- Two-pass assembler supporting `.org`, `.word`, bracketed memory operands (`LD r1, 4[r14]`) and immediate modifiers (`u`, `h`).
- Round-trip disassembler, verified to give bit-identical machine code on every benchmark.

### Memory, Exceptions & Stack Visualization *(Parts 2f, 2g)*

- 64 KB segmented memory layout:

  | Segment | Range | Size |
  |---|---|---|
  | Code | `0x0000` to `0x3FFF` | 16 KB |
  | Data / heap | `0x4000` to `0xDFFF` | 40 KB |
  | Stack | `0xFC00` to `0xFFFC` | 1 KB |

- Runtime exceptions: `StackOverflowError`, `StackUnderflowError`, `UnalignedAccessError`, `MemoryAccessViolation`, `InvalidOpcodeError` and `DivideByZeroError`.
- Live ASCII stack frame renderer that marks SP (`r14`) and annotates the target of each `CALL` return address.

### Microprogrammed Control Unit *(Parts 1b, 3)*

- Truly microprogrammed: all control comes from a numbered `CONTROL_STORE` array and a `DISPATCH_ROM`.
- **Horizontal mode:** 29-bit unencoded control word, no decoder delay.
- **Vertical mode:** 18-bit encoded word (4-bit ALU field and 2-bit memory, branch and stack fields), cutting control memory by **37.93%**.

### Parameterized Pipeline Datapath *(Parts 1a, 2c, 2d, 4)*

- 4-stage pipeline: `IF → OF → EX → RW`
- 6-stage pipeline: `IF1 → IF2 → OF → EX → MEM → RW`
- Dynamic RAW hazard detection with stalls (NOP bubbles), plus flushing on taken branches, jumps, `CALL` and `RET`.

### Multi-Algorithm ALU *(Parts 1c, 4, 5)*

| Operation | Selectable algorithms |
|---|---|
| Add / subtract | Ripple-carry, 4-bit carry-lookahead |
| Multiply | Shift-and-add, radix-2 Booth, modified radix-4 Booth |
| Divide / modulo | Restoring, Goldschmidt convergence |

---

## Getting Started

### Prerequisites

- Python 3.8 or newer
- `pandas` and `matplotlib` (for the evaluation suite and charts)

```bash
pip install pandas matplotlib
```

### 1. Run the automated evaluation suite

This runs round-trip verification, 600 randomized ALU test vectors, and the benchmarks on both pipelines, then exports CSVs and plots to `plots/`.

```bash
python evaluate.py
```

### 2. Launch the interactive CLI debugger

```bash
python cli.py tests/factorial_rec.asm 4 horizontal
```

The arguments are the program file, the pipeline depth (`4` or `6`) and the control mode (`horizontal` or `vertical`).

---

## Debugger Commands

At the `risc201-dbg` prompt:

| Command | What it does |
|---|---|
| `step 5` | Advance 5 clock cycles and show the pipeline stage latches |
| `micro` | Show per-stage uPC, microword and control signals |
| `break fact_recurse` | Set a symbolic breakpoint |
| `run` | Run until the breakpoint or `HLT` |
| `stack` | Render the active ASCII stack frame table |
| `regs` | Show registers `r0` to `r15` and the Z/C/N/V flags |
| `metrics` | Print total cycles, retired instructions, CPI, RAW stalls and branch flushes |

---

## Team Work Distribution

| Member | Responsibility | Files |
|---|---|---|
| Ritesh | ISA, two-pass assembler, disassembler | `isa.py`, `assembler.py`, `disassembler.py` |
| Vansh Khureja | Macro preprocessor, memory subsystem, exception hierarchy | `preprocessor.py`, `exceptions.py`, `memory.py` |
| Aditya | Horizontal/vertical control stores, micro-sequencer, interactive CLI debugger | `microcode_h.py`, `microcode_v.py`, `sequencer.py`, `cli.py` |
| Yogenra Nirala | Parameterized 4/6-stage pipeline datapath, RAW stalling, branch flushing, ASCII stack visualizer | `pipeline.py`, `stack_viz.py` |
| Vimal Kumar | Multi-algorithm ALU, benchmark test suite, automated evaluation runner | `alu.py`, `tests/*.asm`, `evaluate.py` |

> Replace "Person 1" to "Person 5" with your team members' real names before submitting.
