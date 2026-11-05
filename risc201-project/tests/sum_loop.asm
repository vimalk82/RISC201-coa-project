# Benchmark 1: Sum of 1..N (N=10 -> Result in r2 = 55)
main:
    MOV r1, 10          # Counter N = 10
    MOV r2, 0           # Accumulator sum = 0
loop:
    ADD r2, r2, r1      # sum += r1
    SUB r1, r1, 1       # r1 -= 1
    CMP r1, 0
    BGT loop            # Repeat while r1 > 0
    ST r2, 0[r0]        # Store final sum (55) at Mem[0]
    HLT
