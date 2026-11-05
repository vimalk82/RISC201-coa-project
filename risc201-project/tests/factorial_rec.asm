# Benchmark 2: Recursive Factorial (5! = 120 in r1) using CALL/RET & PUSH/POP
main:
    MOV r1, 5           # Compute 5!
    CALL fact
    ST r1, 4[r0]        # Store 120 at Mem[4]
    HLT

fact:
    CMP r1, 1
    BGT fact_recurse
    MOV r1, 1
    RET

fact_recurse:
    PUSH r1             # Save current N on full-descending stack
    SUB r1, r1, 1       # N - 1
    CALL fact           # r1 = fact(N - 1)
    POP r2              # Restore N into r2
    MUL r1, r1, r2      # r1 = N * fact(N - 1)
    RET
