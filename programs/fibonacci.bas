        PRINT "To which iteration?"
        INPUT L
        LET I=1
        LET A=0
        LET B=1
        IF L<1 THEN END
        PRINT 0,": ",A
        IF L<2 THEN END
    100 PRINT I,": ",A
        LET B=A+B
        LET A=B-A
        LET I=I+1
        IF I<=L THEN GOTO 100
