# Benchmark 6: Heavy MUL / DIV / MOD / Shift Workload for ALU Algorithm Comparison
main:
    MOV r1, 1234
    MOV r2, 567
    MUL r3, r1, r2      # 1234 * 567 = 699678
    DIV r4, r3, r1      # 699678 / 1234 = 567
    MOD r5, r3, r2      # 699678 % 567 = 0

    MOV r6, -450
    MOV r7, 33
    MUL r8, r6, r7      # -450 * 33 = -14850
    DIV r9, r8, r7      # -14850 / 33 = -450

    MOV r10, 7777
    MOV r11, 123
    MUL r12, r10, r11   # 956571
    DIV r13, r12, r11   # 7777
    MOD r1, r10, r11    # 7777 % 123 = 28

    LSL r2, r1, 3
    ASR r2, r2, 1
    HLT
