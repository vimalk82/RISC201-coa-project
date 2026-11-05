"""
RISC201 Macro Preprocessor (Part 2e)
Expands full-descending stack macros (PUSH, POP) and pseudo-ops (HLT, CLR)
before Assembler Pass 1.
"""
import re

def preprocess_lines(lines: list[str]) -> list[str]:
    """
    Takes raw assembly source lines and expands macros:
      - PUSH rX  -> SUB r14, r14, 4  ; ST rX, 0[r14]
      - POP rX   -> LD rX, 0[r14]    ; ADD r14, r14, 4
      - HLT      -> B 0
      - CLR rX   -> MOV rX, 0
    Preserves line labels on the first expanded instruction.
    """
    expanded = []
    for raw_line in lines:
        # Strip comments (; or # or @)
        line = re.split(r'[;#@]', raw_line)[0].strip()
        if not line:
            continue

        # Extract optional label prefix "label:"
        label_prefix = ""
        if ":" in line:
            parts = line.split(":", 1)
            label_prefix = parts[0].strip() + ": "
            line = parts[1].strip()
            if not line:
                expanded.append(label_prefix.strip())
                continue

        tokens = re.split(r'[,\s]+', line)
        mnem = tokens[0].upper()

        if mnem == "PUSH" and len(tokens) >= 2:
            reg = tokens[1]
            expanded.append(f"{label_prefix}SUB r14, r14, 4")
            expanded.append(f"ST {reg}, 0[r14]")
        elif mnem == "POP" and len(tokens) >= 2:
            reg = tokens[1]
            expanded.append(f"{label_prefix}LD {reg}, 0[r14]")
            expanded.append(f"ADD r14, r14, 4")
        elif mnem in ("HLT", "HALT"):
            expanded.append(f"{label_prefix}B 0")
        elif mnem == "CLR" and len(tokens) >= 2:
            reg = tokens[1]
            expanded.append(f"{label_prefix}MOV {reg}, 0")
        else:
            expanded.append(f"{label_prefix}{line}")

    return expanded


def preprocess_text(source_text: str) -> str:
    return "\n".join(preprocess_lines(source_text.splitlines()))
