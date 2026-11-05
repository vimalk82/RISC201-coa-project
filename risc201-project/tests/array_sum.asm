# Benchmark 4: Array Initialize & Memory Sum using LD/ST (Sum = 10+20+30+40+50 = 150)
main:
    MOV r1, 256         # Base address 0x0100
    MOV r2, 10
    ST r2, 0[r1]
    MOV r2, 20
    ST r2, 4[r1]
    MOV r2, 30
    ST r2, 8[r1]
    MOV r2, 40
    ST r2, 12[r1]
    MOV r2, 50
    ST r2, 16[r1]

    MOV r3, 0           # Sum accumulator
    MOV r4, 5           # 5 elements
    MOV r5, 256         # Pointer
sum_arr:
    LD r6, 0[r5]
    ADD r3, r3, r6
    ADD r5, r5, 4
    SUB r4, r4, 1
    CMP r4, 0
    BGT sum_arr
    HLT
