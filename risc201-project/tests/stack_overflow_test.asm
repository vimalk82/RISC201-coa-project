# Benchmark 7: Deep Infinite Recursion to Verify Stack Boundary Protection (Part 2f)
main:
    MOV r1, 1
    CALL deep_recurse
    HLT

deep_recurse:
    PUSH r1
    ADD r1, r1, 1
    CALL deep_recurse
    POP r1
    RET
