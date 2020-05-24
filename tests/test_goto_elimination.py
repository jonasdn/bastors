"""
This module will test the GOTO elimination pass of the transpiler.
It will do so by comparing the (debug) output of the program after
GOTO elimination with a reference file, found in tests/goto_cases.

If the output does not match, the test will fail and display the diff.
"""

import unittest
import glob
import os
import subprocess
import sys
import bastors.parse as parse
import bastors.debug as debug
from bastors.goto_elimination import eliminate_goto, classify_goto
from bastors.rustify import Rustify


class TestGotoELim(unittest.TestCase):
    def __assert_compile(self, program, name):
        rs = "%s.rs" % name
        with open(rs, "w") as out:
            rust = Rustify()
            rust.visit(eliminate_goto(program))
            rust.output(out)

        rc = subprocess.call(["rustc", rs], subprocess.PIPE)
        self.assertEqual(rc, 0)

    def __assert_ref(self, program, out, ref):
        path = "%s/goto_cases/" % os.path.dirname(__file__)

        debug.dump(program, out)

        process = subprocess.Popen(
            ["diff", "-u", os.path.join(path, ref), out], stdout=subprocess.PIPE,
        )
        output = process.communicate()[0]
        if process.returncode != 0:
            print(output.decode("ascii"))
            self.assertEqual(process.returncode, 0)

    def test_1_1_a(self):
        """
        Goto and label occur at the same indent level in the same block and
        goto occurs before the label.
        """
        source = """
            10 LET A=1
            20 IF A=1 THEN GOTO 50
            30 LET B=A+2
            40 PRINT B
            50 PRINT A
            60 END
            """
        try:
            program = parse.Parser(source).parse()
        except parse.ParseError as err:
            self.fail(err)

        purged = eliminate_goto(program)
        self.__assert_ref(purged, "1_1_a.pseudo", "1_1_a.ref")
        self.__assert_compile(program, "1_1_a")

    def test_1_1_b(self):
        """
        Goto and label occur at the same indent level in the same block and
        goto occurs before the label. (No conditional GOTO)
        """
        source = """
            10 LET A=1
            20 GOTO 50
            30 LET B=A+2
            40 PRINT B
            50 PRINT A
            60 END
            """
        try:
            program = parse.Parser(source).parse()
        except parse.ParseError as err:
            self.fail(err)

        purged = eliminate_goto(program)
        self.__assert_ref(purged, "1_1_b.pseudo", "1_1_b.ref")
        self.__assert_compile(program, "1_1_b")

    def test_1_2(self):
        """
        Goto and label occur at the same indent level in the same block and
        goto occurs after the label.
        """
        source = """
            10 LET A=2
            20 LET B=B+2+A
            30 LET C=A*2+B
            40 LET A=A+1
            50 IF C < 50 THEN GOTO 30
            60 PRINT A, B, C
            70 END
            """
        try:
            program = parse.Parser(source).parse()
        except parse.ParseError as err:
            self.fail(err)

        purged = eliminate_goto(program)
        self.__assert_ref(purged, "1_2.pseudo", "1_2.ref")
        self.__assert_compile(program, "1_2")

    def test_2_1_a(self):
        """
        GOTO occurs in some parent block (> 1) of the block where the label is
        contained in and goto occurs before the label.

        This cannot be constructed by a TinyBasic program since our TinyBasic
        does not allow multi-statement then. It can occur as part of goto
        elimination though. So we construct an example here.
        """
        statements = dict()
        statements["main"] = [
            parse.Let(1, parse.VariableExpression("a"), 0),
            parse.Let(2, parse.VariableExpression("b"), 2),
            parse.If(
                None,
                [
                    parse.Condition(
                        parse.VariableExpression("a"),
                        ">=",
                        0,
                        parse.ConditionEnum.INITIAL,
                    )
                ],
                [
                    parse.Print(3, [parse.VariableExpression("a")]),
                    parse.If(
                        None,
                        [
                            parse.Condition(
                                parse.VariableExpression("b"),
                                "<>",
                                2,
                                parse.ConditionEnum.INITIAL,
                            )
                        ],
                        [parse.Goto(None, 9)],
                    ),
                    parse.Let(4, parse.VariableExpression("d"), 78),
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
                            parse.Print(5, [parse.VariableExpression("a")]),
                            parse.Let(6, parse.VariableExpression("c"), 7),
                            parse.If(
                                None,
                                [
                                    parse.Condition(
                                        parse.VariableExpression("c"),
                                        "=",
                                        5,
                                        parse.ConditionEnum.INITIAL,
                                    )
                                ],
                                [
                                    parse.Let(7, parse.VariableExpression("b"), 2),
                                    parse.Print(8, [parse.VariableExpression("c")]),
                                    parse.Let(9, parse.VariableExpression("d"), 32),
                                    parse.Let(10, parse.VariableExpression("e"), 5),
                                ],
                            ),
                            parse.Let(
                                11,
                                parse.VariableExpression("a"),
                                parse.VariableExpression("d"),
                            ),
                            parse.Print(12, [parse.VariableExpression("a")]),
                        ],
                    ),
                    parse.Let(13, parse.VariableExpression("b"), 2),
                    parse.Let(14, parse.VariableExpression("a"), 2),
                    parse.Let(15, parse.VariableExpression("e"), 2),
                ],
            ),
            parse.End(16),
        ]
        program = parse.Program(statements)
        self.assertEqual(classify_goto(program), "2.1")

        purged = eliminate_goto(program)
        self.__assert_ref(purged, "2_1_a.purged", "2_1_a.ref")
        self.__assert_compile(program, "2_1_a")

    def test_2_2(self):
        """
        GOTO occurs in some parent block (> 1) of the block where the label is
        contained in and goto occurs after the label.

        This cannot be constructed by a TinyBasic program since our TinyBasic
        does not allow multi-statement then. It can occur as part of goto
        elimination though. So we construct an example here.
        """

        statements = dict()
        statements["main"] = [
            parse.Let(1, parse.VariableExpression("a"), 0),
            parse.Let(2, parse.VariableExpression("d"), 78),
            parse.If(
                None,
                [
                    parse.Condition(
                        parse.VariableExpression("a"),
                        ">=",
                        0,
                        parse.ConditionEnum.INITIAL,
                    )
                ],
                [
                    parse.Print(3, [parse.VariableExpression("a")]),
                    parse.Let(4, parse.VariableExpression("a"), 4),
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
                            parse.Print(5, [parse.VariableExpression("a")]),
                            parse.Let(6, parse.VariableExpression("c"), 7),
                            parse.If(
                                None,
                                [
                                    parse.Condition(
                                        parse.VariableExpression("c"),
                                        "=",
                                        5,
                                        parse.ConditionEnum.INITIAL,
                                    )
                                ],
                                [
                                    parse.Let(7, parse.VariableExpression("b"), 2),
                                    parse.Print(8, [parse.VariableExpression("c")]),
                                    parse.Let(9, parse.VariableExpression("d"), 32),
                                    parse.Let(10, parse.VariableExpression("e"), 5),
                                ],
                            ),
                            parse.Let(
                                11,
                                parse.VariableExpression("a"),
                                parse.VariableExpression("d"),
                            ),
                            parse.Print(12, [parse.VariableExpression("a")]),
                        ],
                    ),
                    parse.Let(13, parse.VariableExpression("b"), 2),
                    parse.Let(14, parse.VariableExpression("a"), 2),
                    parse.If(
                        None,
                        [
                            parse.Condition(
                                parse.VariableExpression("b"),
                                "<>",
                                2,
                                parse.ConditionEnum.INITIAL,
                            )
                        ],
                        [parse.Goto(None, 9)],
                    ),
                    parse.Let(15, parse.VariableExpression("b"), 7),
                ],
            ),
            parse.End(16),
        ]
        program = parse.Program(statements)
        self.assertEqual(classify_goto(program), "2.2")

        purged = eliminate_goto(program)
        self.__assert_ref(program, "2_2.pseudo", "2_2.ref")
        self.__assert_compile(purged, "2_2")

    def test_3_1_a(self):
        """
        Label occurs in some parent block (> 1) of the block where the goto is
        contained in and goto occurs before the label.

        This cannot be constructed by a TinyBasic program since our TinyBasic
        does not allow multi-statement then. It can occur as part of goto
        elimination though. So we construct an example here.
        """
        statements = dict()
        statements["main"] = [
            parse.Let(1, parse.VariableExpression("a"), 1),
            parse.Let(2, parse.VariableExpression("b"), 2),
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
                    parse.Print(3, [parse.VariableExpression("a")]),
                    parse.Let(4, parse.VariableExpression("b"), 0),
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
                            parse.Let(5, parse.VariableExpression("b"), 5),
                            parse.Print(6, [parse.VariableExpression("a")]),
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
                                [parse.Goto(None, 8)],
                            ),
                            parse.Print(7, ['"No droids here."']),
                        ],
                    ),
                ],
            ),
            parse.Let(8, parse.VariableExpression("a"), 7),
            parse.Print(9, [parse.VariableExpression("b")]),
            parse.Print(10, [parse.VariableExpression("a")]),
        ]
        program = parse.Program(statements)
        self.assertEqual(classify_goto(program), "3.1")

        purged = eliminate_goto(program)
        self.__assert_ref(program, "3_1_a.pseudo", "3_1_a.ref")
        self.__assert_compile(purged, "3_1_a")

    def test_3_1_b(self):
        """
        Label occurs in some parent block (> 1) of the block where the goto is
        contained in and goto occurs before the label.

        This cannot be constructed by a TinyBasic program since our TinyBasic
        does not allow multi-statement then. It can occur as part of goto
        elimination though. So we construct an example here.
        """
        statements = dict()
        statements["main"] = [
            parse.Let(1, parse.VariableExpression("a"), 1),
            parse.Let(2, parse.VariableExpression("b"), 2),
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
                    parse.Print(3, [parse.VariableExpression("a")]),
                    parse.Let(4, parse.VariableExpression("b"), 0),
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
                            parse.Let(5, parse.VariableExpression("b"), 5),
                            parse.Print(6, [parse.VariableExpression("a")]),
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
                                [
                                    parse.Let(7, parse.VariableExpression("a"), 55),
                                    parse.Let(8, parse.VariableExpression("b"), 0),
                                    parse.If(
                                        None,
                                        [
                                            parse.Condition(
                                                parse.VariableExpression("b"),
                                                "<>",
                                                0,
                                                parse.ConditionEnum.INITIAL,
                                            )
                                        ],
                                        [parse.Goto(None, 14)],
                                    ),
                                    parse.Print(9, ['"Hello"']),
                                    parse.Print(10, ['"World"']),
                                ],
                            ),
                            parse.Let(11, parse.VariableExpression("a"), 0),
                            parse.Let(12, parse.VariableExpression("b"), 5),
                        ],
                    ),
                    parse.Print(13, ['"No droids here."']),
                    parse.Print(14, ['"Game"']),
                    parse.Print(15, ['"over"']),
                ],
            ),
            parse.End(16),
        ]
        program = parse.Program(statements)
        self.assertEqual(classify_goto(program), "3.1")

        purged = eliminate_goto(program)
        self.__assert_ref(program, "3_1_b.pseudo", "3_1_b.ref")
        self.__assert_compile(purged, "3_1_b")

    def test_3_2(self):
        """
        Label occurs in some parent container/block (container level > 1) of
        the container/block where the goto is contained in and label occurs
        before the goto.

        This cannot be constructed by a TinyBasic program since our TinyBasic
        does not allow multi-statement then. It can occur as part of goto
        elimination though. So we construct an example here.
        """
        statements = dict()
        statements["main"] = [
            parse.Let(1, parse.VariableExpression("a"), 1),
            parse.Let(2, parse.VariableExpression("b"), 2),
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
                    parse.Print(3, [parse.VariableExpression("a")]),
                    parse.Let(4, parse.VariableExpression("b"), 0),
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
                            parse.Let(5, parse.VariableExpression("b"), 5),
                            parse.Print(6, [parse.VariableExpression("a")]),
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
                                [parse.Goto(None, 3)],
                            ),
                            parse.Print(7, ['"Hello"']),
                        ],
                    ),
                    parse.Let(8, parse.VariableExpression("a"), 0),
                    parse.Let(9, parse.VariableExpression("b"), 5),
                ],
            ),
            parse.End(10),
        ]
        program = parse.Program(statements)
        self.assertEqual(classify_goto(program), "3.2")

        purged = eliminate_goto(program)
        self.__assert_ref(program, "3_2.pseudo", "3_2.ref")
        self.__assert_compile(purged, "3_2")

    def test_4_1(self):
        """
        Goto occurs in a disjoint container/block compared to where label is
        located and goto occurs before the label.

        This cannot be constructed by a TinyBasic program since our TinyBasic
        does not allow multi-statement then. It can occur as part of goto
        elimination though. So we construct an example here.
        """
        statements = dict()
        statements["main"] = [
            parse.Let(1, parse.VariableExpression("a"), 0),
            parse.Print(2, ['"S2"']),
            parse.If(
                None,
                [
                    parse.Condition(
                        parse.VariableExpression("a"),
                        "=",
                        0,
                        parse.ConditionEnum.INITIAL,
                    )
                ],
                [
                    parse.Print(3, ['"S3"']),
                    parse.Print(4, ['"S4"']),
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
                            parse.Print(5, ['"S5"']),
                            parse.Print(7, ['"S7"']),
                            parse.If(
                                None,
                                [
                                    parse.Condition(
                                        parse.VariableExpression("a"),
                                        "<",
                                        0,
                                        parse.ConditionEnum.INITIAL,
                                    )
                                ],
                                [parse.Goto(None, 15)],
                            ),
                            parse.Print(8, ['"S8"']),
                            parse.Print(9, ['"S9"']),
                        ],
                    ),
                    parse.Print(10, ['"S10"']),
                    parse.If(
                        None,
                        [
                            parse.Condition(
                                parse.VariableExpression("a"),
                                "=",
                                0,
                                parse.ConditionEnum.INITIAL,
                            )
                        ],
                        [
                            parse.Print(11, ['"S11"']),
                            parse.Print(12, ['"S12"']),
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
                                    parse.Print(13, ['"S13"']),
                                    parse.Print(14, ['"S14"']),
                                    parse.Print(15, ['"S15"']),
                                    parse.Print(16, ['"S16"']),
                                ],
                            ),
                            parse.Print(17, ['"S17"']),
                        ],
                    ),
                    parse.Print(18, ['"S18"']),
                ],
            ),
            parse.End(10),
        ]
        program = parse.Program(statements)
        self.assertEqual(classify_goto(program), "4.1")

        purged = eliminate_goto(program)
        self.__assert_ref(program, "4_1.pseudo", "4_1.ref")
        self.__assert_compile(purged, "4_1")

    def test_4_2(self):
        """
        Goto occurs in a disjoint container/block compared to where label is
        located and goto occurs afterthe label.

        This cannot be constructed by a TinyBasic program since our TinyBasic
        does not allow multi-statement then. It can occur as part of goto
        elimination though. So we construct an example here.
        """
        statements = dict()
        statements["main"] = [
            parse.Let(1, parse.VariableExpression("a"), 0),
            parse.Print(2, ['"S2"']),
            parse.If(
                None,
                [
                    parse.Condition(
                        parse.VariableExpression("a"),
                        "=",
                        0,
                        parse.ConditionEnum.INITIAL,
                    )
                ],
                [
                    parse.Print(3, ['"S3"']),
                    parse.Print(4, ['"S4"']),
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
                            parse.Print(5, ['"S5"']),
                            parse.Print(7, ['"S7"']),
                            parse.Print(8, ['"S8"']),
                            parse.Print(9, ['"S9"']),
                        ],
                    ),
                    parse.Print(10, ['"S10"']),
                    parse.If(
                        None,
                        [
                            parse.Condition(
                                parse.VariableExpression("a"),
                                "=",
                                0,
                                parse.ConditionEnum.INITIAL,
                            )
                        ],
                        [
                            parse.Print(11, ['"S11"']),
                            parse.Print(12, ['"S12"']),
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
                                    parse.Print(13, ['"S13"']),
                                    parse.Print(14, ['"S14"']),
                                    parse.If(
                                        None,
                                        [
                                            parse.Condition(
                                                parse.VariableExpression("a"),
                                                "<",
                                                0,
                                                parse.ConditionEnum.INITIAL,
                                            )
                                        ],
                                        [parse.Goto(None, 8)],
                                    ),
                                    parse.Print(15, ['"S15"']),
                                    parse.Print(16, ['"S16"']),
                                ],
                            ),
                            parse.Print(17, ['"S17"']),
                        ],
                    ),
                    parse.Print(18, ['"S18"']),
                ],
            ),
            parse.End(10),
        ]
        program = parse.Program(statements)
        self.assertEqual(classify_goto(program), "4.2")

        purged = eliminate_goto(program)
        self.__assert_ref(program, "4_2.pseudo", "4_2.ref")
        self.__assert_compile(purged, "4_2")

    def test_SP1(self):
        """
        Two goto-label pairs overlap each other
        """
        source = """
            1  LET A=2
            2  LET B=B+2+A
               IF A = 0 THEN GOTO 7
            3  LET C=A*2+B
            4  LET A=A+1
               IF B > 3 THEN GOTO 10
            5  LET C=A+B
            6  PRINT A, B, C
            7  INPUT A
            8  PRINT "HELLO"
            9  PRINT "WORLD"
            10 INPUT B
            11 END
            """
        try:
            program = parse.Parser(source).parse()
        except parse.ParseError as err:
            self.fail(err)

        purged = eliminate_goto(program)
        self.__assert_ref(purged, "sp1.pseudo", "sp1.ref")
        self.__assert_compile(program, "sp1")

    def test_SP2(self):
        """
        Multiple gotos branch to a single label (M:1 relationship between goto
        and labels)
        """
        source = """
            1  LET A=2
            2  LET B=B+2+A
               IF A = 0 THEN GOTO 7
            3  LET C=A*2+B
            4  LET A=A+1
               IF B > 3 THEN GOTO 7
            5  LET C=A+B
            6  PRINT A, B, C
            7  INPUT A
            8  PRINT "HELLO"
            9  END
            """
        try:
            program = parse.Parser(source).parse()
        except parse.ParseError as err:
            self.fail(err)

        purged = eliminate_goto(program)
        self.__assert_ref(purged, "sp2.pseudo", "sp2.ref")
        self.__assert_compile(program, "sp2")

    def tearDown(self):
        globs = [
            u"1_1*",
            u"1_2*",
            u"2_1*",
            u"2_2*",
            u"3_1*",
            u"3_2*",
            u"4_1*",
            u"4_2*",
            u"sp*",
        ]
        for g in globs:
            for file in glob.glob(g):
                os.unlink(os.path.abspath(file))
