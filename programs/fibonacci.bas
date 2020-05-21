        LET A=0
        LET B=1
    100 PRINT A
        LET B=A+B
        LET A=B-A
        IF B<=1000 THEN GOTO 100
