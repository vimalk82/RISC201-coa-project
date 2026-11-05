"""
RISC201 Microprogrammed Control Unit & Micro-Sequencer (Part 1b, Part 3)
Replaces dictionary-lookup control unit with a numbered Control Store array,
opcode-to-uPC Dispatch ROM, per-stage microPC progression, and Horizontal vs.
Vertical decoding comparison.
"""
from isa import MNEMONIC
from exceptions import InvalidOpcodeError
from microcode_h import (
    HORIZONTAL_WORD_WIDTH,
    STAGES_4,
    STAGES_6,
    build_horizontal_store,
    unpack_horizontal_word,
    default_signals,
)
from microcode_v import (
    VERTICAL_WORD_WIDTH,
    build_vertical_store,
    unpack_vertical_word,
)


class MicroSequencer:
    """
    Authentic Microprogrammed Control Unit with numbered Control Store and uPC tracking.
    Supports both 'horizontal' (29-bit unencoded) and 'vertical' (18-bit encoded) modes,
    and both 4-stage and 6-stage pipelines.
    """
    def __init__(self, num_stages: int = 4, mode: str = "horizontal"):
        if num_stages not in (4, 6):
            raise ValueError("num_stages must be 4 or 6")
        mode = mode.lower()
        if mode not in ("horizontal", "vertical"):
            raise ValueError("mode must be 'horizontal' or 'vertical'")

        self.num_stages = num_stages
        self.stages = STAGES_4 if num_stages == 4 else STAGES_6
        self.mode = mode
        self.word_width = HORIZONTAL_WORD_WIDTH if mode == "horizontal" else VERTICAL_WORD_WIDTH
        self.decoder_gate_levels = 0 if mode == "horizontal" else 2  # 4-to-16 decoder = 2 gate levels

        if mode == "horizontal":
            self.control_store, self.dispatch_rom = build_horizontal_store(num_stages)
            self._unpack = unpack_horizontal_word
        else:
            self.control_store, self.dispatch_rom = build_vertical_store(num_stages)
            self._unpack = unpack_vertical_word

    def dispatch(self, opcode: int, pc: int = 0, instr: int = 0) -> int:
        """Maps instruction opcode -> starting microPC address in Control Store."""
        if opcode not in self.dispatch_rom:
            raise InvalidOpcodeError(
                f"Invalid or unsupported opcode {opcode} in Dispatch ROM",
                pc=pc,
                instruction=instr,
            )
        return self.dispatch_rom[opcode]

    def fetch_microword(self, uPC: int) -> int:
        if not (0 <= uPC < len(self.control_store)):
            raise IndexError(f"uPC {uPC} out of Control Store bounds [0, {len(self.control_store)-1}]")
        return self.control_store[uPC]

    def decode_microword(self, uPC: int) -> dict:
        if uPC is None or uPC < 0:
            return default_signals()
        raw_word = self.fetch_microword(uPC)
        return self._unpack(raw_word)

    def next_uPC(self, current_uPC: int) -> int:
        """Advances uPC to the next microinstruction unless EOI (End-Of-Instruction) is set."""
        if current_uPC is None or current_uPC < 0:
            return -1
        sig = self.decode_microword(current_uPC)
        if sig.get("EOI"):
            return -1
        return current_uPC + 1

    def get_store_metrics(self) -> dict:
        num_words = len(self.control_store)
        total_bits = num_words * self.word_width
        return {
            "mode": self.mode,
            "num_stages": self.num_stages,
            "num_words": num_words,
            "word_width_bits": self.word_width,
            "total_bits": total_bits,
            "total_bytes": (total_bits + 7) // 8,
            "decoder_gate_levels": self.decoder_gate_levels,
        }

    def format_stage_micro(self, stage_name: str, instr_mnem: str, uPC: int) -> str:
        if uPC is None or uPC < 0:
            return f"  [{stage_name:<3}] Bubble/NOP   | uPC: ---- | Word: {'-' * ((self.word_width+3)//4)} | Active: None"
        raw = self.fetch_microword(uPC)
        sig = self.decode_microword(uPC)
        active = [f"{k}={v}" if not isinstance(v, bool) else k for k, v in sig.items() if v not in (False, None)]
        hex_digits = (self.word_width + 3) // 4
        return (
            f"  [{stage_name:<3}] {instr_mnem:<12} | uPC: 0x{uPC:02X} ({uPC:3d}) | "
            f"Word: 0x{raw:0{hex_digits}X} | Active: {', '.join(active) if active else 'None'}"
        )


def compare_horizontal_vs_vertical() -> dict:
    """Static comparison helper for Part 3 & Part 5 evaluation."""
    results = {}
    for stg in (4, 6):
        h_seq = MicroSequencer(num_stages=stg, mode="horizontal")
        v_seq = MicroSequencer(num_stages=stg, mode="vertical")
        # Verify 100% signal equivalence across every single uPC
        for u_addr in range(len(h_seq.control_store)):
            assert h_seq.decode_microword(u_addr) == v_seq.decode_microword(u_addr), (
                f"Signal mismatch at uPC={u_addr} for {stg}-stage store!"
            )
        h_m = h_seq.get_store_metrics()
        v_m = v_seq.get_store_metrics()
        savings_pct = (1.0 - (v_m["total_bits"] / h_m["total_bits"])) * 100.0
        results[f"{stg}stage"] = {
            "horizontal": h_m,
            "vertical": v_m,
            "bit_savings_percent": round(savings_pct, 2),
        }
    return results
