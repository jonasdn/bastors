import unittest
import bastors.parse as parse
from bastors.parse import ParseError


class TestParse(unittest.TestCase):
    def test_parse_error(self):
        program = """ 10 LET A=20
                      20 PRINT "Hello World"
                      30 GOTO A
                  """
        try:
            parser = parse.Parser(program)
            node = parser.parse()
            print(node)
        except ParseError as err:
            self.assertEqual(err.line, 3)
            self.assertEqual(err.col, 31)
