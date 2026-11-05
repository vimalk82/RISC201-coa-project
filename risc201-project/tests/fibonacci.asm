# Benchmark 3: Iterative Fibonacci (F(10) = 55 in r3)
main:
    MOV r1, 0           # F(0) = 0
    MOV r2, 1           # F(1) = 1
    MOV r4, 9           # 9 iterations to reach F(10)
fib_loop:
    ADD r3, r1, r2      # r3 = r1 + r2
    MOV r1, r2
    MOV r2, r3
    SUB r4, r4, 1
    CMP r4, 0
    BGT fib_loop
    ST r3, 8[r0]
    HLT
