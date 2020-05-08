import unittest
import glob
import os
import subprocess
import sys
import bastors.parse as parse
from bastors.goto_elimination import eliminate_goto, classify_goto
from bastors.rustify import Rustify


class TestGotoELim(unittest.TestCase):
    def __assert_output(self, program, output):
        try:
            file = open("%s/goto_cases/%s" % (os.path.dirname(__file__), program), "r")
            content = file.read()
        except IOError:
            self.assertFalse(True)

        try:
            tree = parse.Parser(content).parse()
            file.close()
        except parse.ParseError:
            self.assertFalse(True)

        rs = "%s.rs" % program.replace(".", "_")
        out = open(rs, "w")
        rust = Rustify()
        rust.visit(eliminate_goto(tree))
        rust.output(out)
        out.close()

        process = subprocess.call(["rustc", rs], subprocess.PIPE)
        process = subprocess.Popen(
            ["./%s" % program.replace(".", "_")], stdout=subprocess.PIPE
        )
        (program_output, _) = process.communicate()
        self.assertEqual(output, program_output)

    def test_1_1(self):
        """
        1.1.bas:
            REM "1.1 conditional goto"
            10 LET A=1
            20 IF A=1 THEN GOTO 50
            30 LET B=A+2
            40 PRINT B
            50 PRINT A
            60 END
        """
        self.__assert_output("1.1.bas", b"1\n")

        def test_1_1_bare(self):
            """
        1.1_bare.bas:
            REM "1.1 conditional goto"
            10 LET A=1
            20 GOTO 50
            30 LET B=A+2
            40 PRINT B
            50 PRINT A
            60 END
        """

        self.__assert_output("1.1_bare.bas", b"1\n")

    def test_1_2(self):
        """
        1_2.bas:
            REM 1.2 make it loop
            10 LET A=2
            20 LET B=B+2+A
            30 LET C=A*2+B
            40 LET A=A+1
            50 IF C < 50 THEN GOTO 30
            60 PRINT A, B, C
            70 END
        """
        self.__assert_output("1.2.bas", b"24450\n")

    def test_3_1(self):
        """
        Label occurs in some parent block (> 1) of the block where the goto is
        contained in and goto occurs before the label.

        This cannot be constructed by a TinyBasic program since our TinyBasic
        does not allow multi-statement then. It can occur as part of goto
        elimination though. So we construct an example here.
        """
        statements = dict()
        statements["main"] = [
            parse.Let(None, parse.VariableExpression("a"), 1),
            parse.Let(None, parse.VariableExpression("b"), 2),
            parse.If(
                None,
                [
                    parse.Condition(
                        parse.VariableExpression("a"),
                        ">",
                        0,
                        parse.ConditionEnum.INITIAL,
                    )
                ],
                [
                    parse.Print(None, [parse.VariableExpression("a")]),
                    parse.Let(None, parse.VariableExpression("b"), 0),
                    parse.If(
                        None,
                        [
                            parse.Condition(
                                parse.VariableExpression("b"),
                                "=",
                                0,
                                parse.ConditionEnum.INITIAL,
                            )
                        ],
                        [
                            parse.Let(None, parse.VariableExpression("b"), 5),
                            parse.Print(None, [parse.VariableExpression("a")]),
                            parse.If(
                                None,
                                [
                                    parse.Condition(
                                        parse.VariableExpression("b"),
                                        ">",
                                        0,
                                        parse.ConditionEnum.INITIAL,
                                    )
                                ],
                                [parse.Goto(None, 20)],
                            ),
                            parse.Print(None, ['"No droids here."']),
                        ],
                    ),
                ],
            ),
            parse.Let(20, parse.VariableExpression("a"), 7),
            parse.Print(None, [parse.VariableExpression("b")]),
            parse.Print(None, [parse.VariableExpression("a")]),
        ]
        program = parse.Program(statements)
        self.assertEqual(classify_goto(program), "3.1")

        out = open("3_1.rs", "w")
        rust = Rustify()
        rust.visit(eliminate_goto(program))
        rust.output(out)
        out.close()

        process = subprocess.call(["rustc", "3_1.rs"], subprocess.PIPE)
        process = subprocess.Popen(["./3_1"], stdout=subprocess.PIPE)
        (program_output, _) = process.communicate()
        self.assertEqual(b"1\n1\n5\n7\n", program_output)

    def tearDown(self):
        globs = [u"1_1_bas*", u"1_1_bare_bas*", u"1_2_bas*", u"3_1*"]
        for g in globs:
            for file in glob.glob(g):
                os.unlink(os.path.abspath(file))
