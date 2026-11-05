"""
RISC201 Active Stack Memory Visualizer (Part 2g)
Renders an ASCII stack frame table showing addresses, values, <-- SP marker,
and labeled return addresses from CALL instructions.
"""
from memory import Memory, STACK_BASE

def render_stack(
    memory: Memory,
    sp_value: int,
    symbol_table: dict[str, int] = None,
    max_rows: int = 24
) -> str:
    addr_to_label = {}
    if symbol_table:
        addr_to_label = {addr: name for name, addr in symbol_table.items()}

    base = memory.stack_base
    limit = memory.stack_limit

    # Determine lowest address to display
    lowest = min(sp_value, base)
    if lowest < limit:
        lowest = limit - 4

    lines = []
    header = "+------------+--------------+----------------------------------------------------+"
    lines.append(header)
    lines.append("|  Address   |  Hex Value   | Frame / Stack Annotation                           |")
    lines.append(header)

    total_slots = ((base - lowest) // 4) + 1
    start_addr = base
    if total_slots > max_rows:
        lines.append(f"|   ...      |     ...      | ({total_slots - max_rows} older stack words above omitted)              |")
        start_addr = lowest + (max_rows - 1) * 4

    for addr in range(start_addr, lowest - 4, -4):
        if addr < 0:
            break
        val = memory._mem.get(addr, 0)
        annot = memory.stack_annotations.get(addr, "")

        if addr == base and not annot:
            annot = "[STACK_BASE]"

        # Check if value matches a known return address if not already annotated
        if not annot and addr >= sp_value and addr < base:
            annot = "Stack Data / Saved Reg"

        sp_marker = " <-- SP (r14)" if addr == sp_value else ""
        full_note = f"{annot}{sp_marker}".strip()
        if len(full_note) > 50:
            full_note = full_note[:47] + "..."

        lines.append(f"| 0x{addr:08X} |  0x{val:08X}  | {full_note:<50} |")

    lines.append(header)
    lines.append(
        f"  Stack Bounds: STACK_BASE=0x{base:04X}, STACK_LIMIT=0x{limit:04X} | "
        f"Current SP=0x{sp_value:04X} ({(base - sp_value) // 4} words used)"
    )
    return "\n".join(lines)
