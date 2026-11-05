# Benchmark 5: Bubble Sort of 5 Elements in Memory ([50, 10, 40, 20, 30] -> [10, 20, 30, 40, 50])
main:
    MOV r1, 512         # Array base at 0x0200
    MOV r2, 50
    ST r2, 0[r1]
    MOV r2, 10
    ST r2, 4[r1]
    MOV r2, 40
    ST r2, 8[r1]
    MOV r2, 20
    ST r2, 12[r1]
    MOV r2, 30
    ST r2, 16[r1]

    MOV r3, 4           # Outer loop counter (N-1 = 4)
outer_loop:
    MOV r4, 0           # Inner index i = 0
    MOV r5, 512         # Current element pointer
inner_loop:
    LD r6, 0[r5]        # A[i]
    LD r7, 4[r5]        # A[i+1]
    CMP r6, r7
    BGT swap_elems
    B next_inner
swap_elems:
    ST r7, 0[r5]
    ST r6, 4[r5]
next_inner:
    ADD r5, r5, 4
    ADD r4, r4, 1
    CMP r4, r3
    BGT end_inner
    BEQ end_inner
    B inner_loop
end_inner:
    SUB r3, r3, 1
    CMP r3, 0
    BGT outer_loop
    HLT
