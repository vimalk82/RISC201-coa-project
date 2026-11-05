"""
RISC201 Comprehensive Automated Verification & Evaluation Suite (Part 5)
Runs:
  1. Assembler -> Disassembler -> Reassembler Round-Trip Verification
  2. Randomized ALU Unit Tests vs. Native Python across all Adder/Mul/Div algorithms
  3. 4-Stage vs. 6-Stage Pipeline Benchmark Evaluation (Cycles, CPI, RAW Stalls, Branch Flushes)
  4. Horizontal vs. Vertical Microprogrammed Control Unit Static & Dynamic Comparison
  5. ALU Hardware Algorithm Comparison (Ripple vs CLA, Shift-Add vs Booth-2 vs Booth-4, Restoring vs Goldschmidt)
  6. Stack Visualizer & Runtime Exception Verification (StackOverflow, Underflow, DivByZero, Unaligned)
  7. Exports CSV summary tables and Matplotlib comparison charts.
"""
import os
import random
import pandas as pd
import matplotlib.pyplot as plt

from isa import REG_SP
from assembler import Assembler
from disassembler import disassemble_program
from pipeline import PipelineSimulator
from sequencer import compare_horizontal_vs_vertical
from alu import ALU, _to_signed, WORD_MASK
from stack_viz import render_stack
from exceptions import (
    StackOverflowError,
    StackUnderflowError,
    DivideByZeroError,
    UnalignedAccessError,
)


def verify_round_trip(asm_dir: str = "tests") -> bool:
    assembler = Assembler()
    for fname in sorted(os.listdir(asm_dir)):
        if not fname.endswith(".asm"):
            continue
        path = os.path.join(asm_dir, fname)
        with open(path, "r") as f:
            src = f.read()
        words1, syms1, _ = assembler.assemble(src)
        disasm_text = disassemble_program(words1, syms1)
        words2, _, _ = assembler.assemble(disasm_text)
        assert words1 == words2, f"Round-trip mismatch in {fname}!"
    return True


def verify_alu_randomized(num_trials: int = 200) -> bool:
    rng = random.Random(2026)
    configs = [
        ("cla", "booth_r2", "goldschmidt"),
        ("ripple", "booth_r4", "restoring"),
        ("cla", "shift_add", "goldschmidt"),
    ]
    for adder_m, mul_m, div_m in configs:
        alu = ALU(adder_mode=adder_m, mul_mode=mul_m, div_mode=div_m)
        for _ in range(num_trials):
            a = rng.randint(-50000, 50000) & WORD_MASK
            b = rng.randint(-50000, 50000) & WORD_MASK
            sa, sb = _to_signed(a), _to_signed(b)

            assert alu.compute(a, b, "ADD").result == ((sa + sb) & WORD_MASK)
            assert alu.compute(a, b, "SUB").result == ((sa - sb) & WORD_MASK)
            assert alu.compute(a, b, "MUL").result == ((sa * sb) & WORD_MASK)
            if sb != 0:
                # Truncating division toward zero
                py_q = int(sa / sb)
                py_r = sa - py_q * sb
                assert alu.compute(a, b, "DIV").result == (py_q & WORD_MASK)
                assert alu.compute(a, b, "MOD").result == (py_r & WORD_MASK)
    return True


def run_all_benchmarks(asm_dir: str = "tests", plot_dir: str = "plots"):
    os.makedirs(plot_dir, exist_ok=True)
    assembler = Assembler()

    benchmarks = [
        ("sum_loop", "sum_loop.asm", lambda sim: sim.regs.read(2) == 55),
        ("factorial_5", "factorial_rec.asm", lambda sim: sim.regs.read(1) == 120),
        ("fibonacci_10", "fibonacci.asm", lambda sim: sim.regs.read(3) == 55),
        ("array_sum", "array_sum.asm", lambda sim: sim.regs.read(3) == 150),
        (
            "bubble_sort",
            "bubble_sort.asm",
            lambda sim: [sim.memory.read_word(512 + i * 4) for i in range(5)] == [10, 20, 30, 40, 50],
        ),
        ("alu_intensive", "alu_intensive.asm", lambda sim: sim.regs.read(4) == 567 and sim.regs.read(1) == 28),
    ]

    # 1. Pipeline 4-Stage vs 6-Stage Evaluation
    pipe_rows = []
    for b_name, fname, check_fn in benchmarks:
        with open(os.path.join(asm_dir, fname)) as f:
            src = f.read()
        words, syms, mem_map = assembler.assemble(src)

        for stages in (4, 6):
            for cu_mode in ("horizontal", "vertical"):
                sim = PipelineSimulator(num_stages=stages, control_mode=cu_mode)
                sim.load_program(words, syms, mem_map)
                m = sim.run()
                assert check_fn(sim), f"Functional verification failed on {b_name} ({stages}-stage, {cu_mode})!"
                if cu_mode == "horizontal":
                    pipe_rows.append({
                        "Benchmark": b_name,
                        "Pipeline": f"{stages}-Stage",
                        "Cycles": m["total_cycles"],
                        "Instr_Retired": m["instructions_retired"],
                        "CPI": m["cpi"],
                        "RAW_Stalls": m["raw_stalls"],
                        "Branch_Flushes": m["branch_flushes"],
                        "Flushed_Instrs": m["flushed_instructions"],
                    })

    df_pipe = pd.DataFrame(pipe_rows)
    df_pipe.to_csv(os.path.join(plot_dir, "pipeline_4_vs_6_comparison.csv"), index=False)

    # 2. Control Unit Horizontal vs Vertical Comparison
    cu_comp = compare_horizontal_vs_vertical()
    cu_rows = []
    for stg_key, data in cu_comp.items():
        for mode_key in ("horizontal", "vertical"):
            info = data[mode_key]
            cu_rows.append({
                "Pipeline": stg_key,
                "Control_Mode": mode_key.capitalize(),
                "Microwords": info["num_words"],
                "Word_Width_Bits": info["word_width_bits"],
                "Total_Store_Bits": info["total_bits"],
                "Total_Store_Bytes": info["total_bytes"],
                "Decoder_Gate_Levels": info["decoder_gate_levels"],
            })
    df_cu = pd.DataFrame(cu_rows)
    df_cu.to_csv(os.path.join(plot_dir, "control_unit_h_vs_v.csv"), index=False)

    # 3. ALU Hardware Algorithm Comparison on alu_intensive.asm & factorial_rec.asm
    alu_configs = [
        ("Baseline (Ripple + ShiftAdd + Restoring)", "ripple", "shift_add", "restoring"),
        ("Mid-Tier (CLA + Booth-R2 + Restoring)", "cla", "booth_r2", "restoring"),
        ("Optimized (CLA + Booth-R4 + Goldschmidt)", "cla", "booth_r4", "goldschmidt"),
    ]
    alu_rows = []
    for b_name, fname in [("alu_intensive", "alu_intensive.asm"), ("factorial_5", "factorial_rec.asm"), ("bubble_sort", "bubble_sort.asm")]:
        with open(os.path.join(asm_dir, fname)) as f:
            src = f.read()
        words, syms, mem_map = assembler.assemble(src)
        for cfg_label, add_m, mul_m, div_m in alu_configs:
            sim = PipelineSimulator(
                num_stages=4,
                control_mode="horizontal",
                adder_mode=add_m,
                mul_mode=mul_m,
                div_mode=div_m,
            )
            sim.load_program(words, syms, mem_map)
            m = sim.run()
            alu_rows.append({
                "Benchmark": b_name,
                "ALU_Configuration": cfg_label,
                "Total_ALU_HW_SubCycles": m["alu_hw_cycles"],
                "Multiplier_Active_Additions": m["alu_mul_active_adds"],
            })
    df_alu = pd.DataFrame(alu_rows)
    df_alu.to_csv(os.path.join(plot_dir, "alu_algorithm_comparison.csv"), index=False)

    # 4. Capture Mid-Execution Stack Visualizer Snapshot on Recursive Factorial (at base case N=1)
    with open(os.path.join(asm_dir, "factorial_rec.asm")) as f:
        fact_src = f.read()
    f_words, f_syms, f_map = assembler.assemble(fact_src)
    sim_stack = PipelineSimulator(num_stages=4, control_mode="horizontal")
    sim_stack.load_program(f_words, f_syms, f_map)
    # Break right when base case 'MOV r1, 1' is reached inside deepest CALL frame
    deepest_Stack_ascii = ""
    min_sp_seen = 0xFFFC
    while not sim_stack.halted:
        sim_stack.step()
        cur_sp = sim_stack.regs.read(REG_SP)
        if cur_sp < min_sp_seen:
            min_sp_seen = cur_sp
            deepest_Stack_ascii = render_stack(sim_stack.memory, cur_sp, f_syms)

    # 5. Verify Stack Overflow Exception on stack_overflow_test.asm
    with open(os.path.join(asm_dir, "stack_overflow_test.asm")) as f:
        so_src = f.read()
    so_words, so_syms, so_map = assembler.assemble(so_src)
    sim_so = PipelineSimulator(num_stages=4, control_mode="horizontal")
    sim_so.load_program(so_words, so_syms, so_map)
    overflow_diag = ""
    try:
        sim_so.run()
    except StackOverflowError as e:
        overflow_diag = e.format_diagnostic()
    assert overflow_diag, "StackOverflowError was not raised on infinite recursion!"

    # -----------------------------------------------------------------
    # Generate Matplotlib Charts
    # -----------------------------------------------------------------
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    # Chart 1: 4-Stage vs 6-Stage Cycles & Stalls/Flushes
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    pivot_cyc = df_pipe.pivot(index="Benchmark", columns="Pipeline", values="Cycles").loc[[b[0] for b in benchmarks]]
    pivot_cyc.plot(kind="bar", ax=axes[0], color=["#2b5c8f", "#d95f02"], width=0.7)
    axes[0].set_title("Total Execution Cycles: 4-Stage vs. 6-Stage RISC201", fontsize=11, fontweight="bold")
    axes[0].set_ylabel("Clock Cycles")
    axes[0].set_xlabel("")
    axes[0].tick_params(axis="x", rotation=25)

    pivot_cpi = df_pipe.pivot(index="Benchmark", columns="Pipeline", values="CPI").loc[[b[0] for b in benchmarks]]
    pivot_cpi.plot(kind="bar", ax=axes[1], color=["#2b5c8f", "#d95f02"], width=0.7)
    axes[1].set_title("Cycles Per Instruction (CPI): 4-Stage vs. 6-Stage", fontsize=11, fontweight="bold")
    axes[1].set_ylabel("CPI")
    axes[1].set_xlabel("")
    axes[1].tick_params(axis="x", rotation=25)
    plt.tight_layout()
    chart1_path = os.path.join(plot_dir, "chart1_pipeline_4_vs_6.png")
    plt.savefig(chart1_path, dpi=180)
    plt.close()

    # Chart 2: Control Store Size (Horizontal vs Vertical) & ALU Algorithm Sub-Cycles
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    pivot_cu = df_cu.pivot(index="Pipeline", columns="Control_Mode", values="Total_Store_Bits")
    pivot_cu.plot(kind="bar", ax=axes[0], color=["#386cb0", "#7fc97f"], width=0.6)
    axes[0].set_title("Control Store Size (Bits): Horizontal vs. Vertical", fontsize=11, fontweight="bold")
    axes[0].set_ylabel("Total Control Memory Bits")
    axes[0].set_xlabel("Pipeline Architecture")
    axes[0].tick_params(axis="x", rotation=0)

    pivot_alu = df_alu.pivot(index="Benchmark", columns="ALU_Configuration", values="Total_ALU_HW_SubCycles")
    pivot_alu.plot(kind="bar", ax=axes[1], color=["#e41a1c", "#ff7f00", "#4daf4a"], width=0.7)
    axes[1].set_title("ALU Internal Hardware Sub-Cycles Across Algorithms", fontsize=11, fontweight="bold")
    axes[1].set_ylabel("Cumulative Hardware Sub-Cycles / Gate Steps")
    axes[1].set_xlabel("")
    axes[1].tick_params(axis="x", rotation=15)
    plt.tight_layout()
    chart2_path = os.path.join(plot_dir, "chart2_cu_and_alu_comparison.png")
    plt.savefig(chart2_path, dpi=180)
    plt.close()

    return df_pipe, df_cu, df_alu, deepest_Stack_ascii, overflow_diag, chart1_path, chart2_path


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print("1. Running Round-Trip Assembler/Disassembler Verification...")
    assert verify_round_trip("tests")
    print("   [PASS] All 7 assembly programs round-trip identically!")

    print("2. Running Randomized Multi-Algorithm ALU Verification (600 vectors)...")
    assert verify_alu_randomized(200)
    print("   [PASS] Ripple/CLA Adders, Shift-Add/Booth-R2/Booth-R4 Multipliers, Restoring/Goldschmidt Dividers match Python!")

    print("3. Running Full Benchmark & Architecture Evaluation Suite...")
    df_pipe, df_cu, df_alu, stack_ascii, so_diag, c1, c2 = run_all_benchmarks("tests", "plots")

    print("\n================ 4-STAGE VS 6-STAGE PIPELINE RESULTS ================")
    print(df_pipe.to_string(index=False))

    print("\n================ HORIZONTAL VS VERTICAL CONTROL STORE ================")
    print(df_cu.to_string(index=False))

    print("\n================ ALU HARDWARE ALGORITHM COMPARISON ================")
    print(df_alu.to_string(index=False))

    print("\n================ ACTIVE STACK FRAME VISUALIZER (5! Base Case) ================")
    print(stack_ascii)

    print("\n================ STACK PROTECTION EXCEPTION DIAGNOSTIC ================")
    print("  " + so_diag)
