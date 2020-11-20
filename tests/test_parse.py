import unittest
import bastors.parse as parse
from bastors.parse import ParseError


class TestParse(unittest.TestCase):
    def test_parse_error(self):
        program = """ 10 LET A=20
                      20 PRINT "Hello World"
                      30 GOTO A
                      40 END
                  """
        with self.assertRaises(ParseError) as ctx:
            parser = parse.Parser(program)
            node = parser.parse()
            _ = node  # avoid node being unused

        self.assertEqual(ctx.exception.line, 3)
        self.assertEqual(ctx.exception.col, 31)


    def test_for(self):
        program = """ 20 FOR I = 1 TO 15 STEP 2
                      30 PRINT I
                      40 NEXT I
                      50 END
                """
        try:
            parser = parse.Parser(program)
            parser.parse()
        except ParseError as err:
            self.fail(err)


    def test_assign(self):
        program = """ 20 I=5
                      30 PRINT I
                      40 END
                """
        try:
            parser = parse.Parser(program)
            parser.parse()
        except ParseError as err:
            self.fail(err)

    def test_comment(self):
        program = """ REM
                      REM --- This is a comment
                      10 PRINT "HELLO WORLD"
                      REM --- Another one
                      20 GOTO 10
                      30 END
                 """
        try:
            parser = parse.Parser(program)
            parser.parse()
        except ParseError as err:
            self.fail(err)
