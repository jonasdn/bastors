import unittest
import glob
import os
import subprocess
import sys
from bastors.goto_elimination import eliminate_goto
from bastors.parse import ParseError, Parser
from bastors.rustify import Rustify


class TestGotoELim(unittest.TestCase):
    def __assert_output(self, program, output):
        try:
            file = open("%s/goto_cases/%s" % (os.path.dirname(__file__), program), "r")
            content = file.read()
        except IOError:
            self.assertFalse(True)

        try:
            tree = Parser(content).parse()
            file.close()
        except ParseError:
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

    def tearDown(self):
        globs = [u"1_1_bas*", u"1_1_bare_bas*", u"1_2_bas*"]
        for g in globs:
            for file in glob.glob(g):
                os.unlink(os.path.abspath(file))
