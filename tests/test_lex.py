import unittest
import bastors.lex as lex
from bastors.lex import TokenEnum, LexError


class TestLex(unittest.TestCase):
    def __assert_tokens(self, program, expected):
        lexer = lex.Lexer(program)
        tokens = lexer.get_tokens()
        for i, token in enumerate(tokens):
            self.assertEqual(token.type, expected[i])

    def test_let(self):
        program = """
            LET A=1
            LET B=A+2
            LET C=A*4 """

        expected = [
            TokenEnum.STATEMENT,
            TokenEnum.VARIABLE,
            TokenEnum.RELATION_OP,
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
            TokenEnum.VARIABLE,
            TokenEnum.RELATION_OP,
            TokenEnum.VARIABLE,
            TokenEnum.ARITHMETIC_OP,
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
            TokenEnum.VARIABLE,
            TokenEnum.RELATION_OP,
            TokenEnum.VARIABLE,
            TokenEnum.ARITHMETIC_OP,
            TokenEnum.NUMBER,
        ]
        self.__assert_tokens(program, expected)

    def test_if(self):
        program = """
            LET A=1
            LET B=2
            IF A < 2 IF B > 1 THEN PRINT "Success"
            """
        expected = [
            TokenEnum.STATEMENT,
            TokenEnum.VARIABLE,
            TokenEnum.RELATION_OP,
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
            TokenEnum.VARIABLE,
            TokenEnum.RELATION_OP,
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
            TokenEnum.VARIABLE,
            TokenEnum.RELATION_OP,
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
            TokenEnum.VARIABLE,
            TokenEnum.RELATION_OP,
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
            TokenEnum.STATEMENT,
            TokenEnum.STRING,
        ]
        self.__assert_tokens(program, expected)

    def test_all(self):
        program = """
            10 PRINT "HELLO WORLD"
            20 LET A=2
            30 LET B=A*3+5
            30 IF A=2 THEN GOTO 10
            40 INPUT B
            50 IF B<=A THEN GOSUB 140
            60 CLEAR
            70 LIST
            80 RUN
            90 END
            140 RETURN
            150 END
        """

        expected = [
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
            TokenEnum.STRING,
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
            TokenEnum.VARIABLE,
            TokenEnum.RELATION_OP,
            TokenEnum.NUMBER,
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
            TokenEnum.VARIABLE,
            TokenEnum.RELATION_OP,
            TokenEnum.VARIABLE,
            TokenEnum.ARITHMETIC_OP,
            TokenEnum.NUMBER,
            TokenEnum.ARITHMETIC_OP,
            TokenEnum.NUMBER,
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
            TokenEnum.VARIABLE,
            TokenEnum.RELATION_OP,
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
            TokenEnum.STATEMENT,
            TokenEnum.NUMBER,
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
            TokenEnum.VARIABLE,
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
            TokenEnum.VARIABLE,
            TokenEnum.RELATION_OP,
            TokenEnum.VARIABLE,
            TokenEnum.STATEMENT,
            TokenEnum.STATEMENT,
            TokenEnum.NUMBER,
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
        ]
        self.__assert_tokens(program, expected)

    def test_REM(self):
        expected = [
            TokenEnum.COMMENT,
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
            TokenEnum.STRING,
            TokenEnum.COMMENT,
            TokenEnum.NUMBER,
            TokenEnum.STATEMENT,
            TokenEnum.NUMBER,
        ]
        program = """
                    REM
                    REM --- This is a comment
                    10 PRINT "HELLO WORLD"
                    REM --- Another one
                    20 GOTO 10
                """
        self.__assert_tokens(program, expected)

    def test_bad_statement(self):
        program = """ 10 PRINT "Hello World"
                      20 GOFO 10
                  """
        try:
            lexer = lex.Lexer(program)
            tokens = lexer.get_tokens()
            print(tokens)
        except LexError as err:
            self.assertEqual(err.line, 2)
            self.assertEqual(err.col, 26)
