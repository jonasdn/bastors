"""
This module will attempt to transpile all TinyBasic programs in the programs
directory and then attemp to compile them using rustc.
"""
import os
import unittest
import subprocess
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

    def test_programs(self):
        programs_path = "%s/../programs/" % os.path.dirname(__file__)
        for filename in os.listdir(programs_path):
            if filename.endswith(".bas"):
                with open(os.path.join(programs_path, filename)) as basic:
                    try:
                        program = parse.Parser(basic.read()).parse()
                    except parse.ParseError:
                        self.assertFalse(True)

                    purged = eliminate_goto(program)
                    self.__assert_compile(purged, "1_1_a")
