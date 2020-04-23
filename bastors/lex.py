"""
Formal grammar of Tiny Basic (https://en.wikipedia.org/wiki/Tiny_BASIC)
    line ::= number statement CR | statement CR
    statement ::= PRINT expr-list
                  IF expression relop expression THEN statement
                  GOTO number
                  INPUT var-list
                  LET var = expression
                  GOSUB expression
                  RETURN
                  CLEAR
                  LIST
                  RUN
                  END
    expr-list ::= (string|expression) (, (string|expression) )*
    var-list ::= var (, var)*
    expression ::= term ((+|-) term)*
    term ::= factor ((*|/) factor)*
    factor ::= var | number | (expression)
    var ::= A | B | C ... | Y | Z
    number ::= digit digit*
    digit ::= 0 | 1 | 2 | 3 | ... | 8 | 9
    relop ::= < (>|=|ε) | > (<|=|ε) | =
    string ::= " (a|b|c ... |x|y|z|A|B|C ... |X|Y|Z|digit)* "
"""
import sys
import string
from enum import Enum
from collections import namedtuple


class TokenEnum(Enum):
    """The different types of tokens"""

    NUMBER = 0
    STRING = 1
    STATEMENT = 2
    VARIABLE = 3
    ARITHMETIC_OP = 4
    RELATION_OP = 5
    COMMA = 6
    LPAREN = 7
    RPAREN = 8


# The namedtuple Token represent a valid token of out flavor of TinyBasic
Token = namedtuple("Token", ["value", "type", "line", "col"])


STATEMENTS = [
    "PRINT",
    "IF",
    "THEN",
    "GOTO",
    "INPUT",
    "LET",
    "GOSUB",
    "RETURN",
    "CLEAR",
    "LIST",
    "RUN",
    "END",
]


class LexError(Exception):
    """ An error while token TinyBasic """

    def __init__(self, message, line, col):
        super(LexError, self).__init__(message)
        self.line = line
        self.col = col


class Lexer:  # pylint: disable=too-few-public-methods
    """ Perform lexical analysis of BASIC grammar above """

    def __init__(self, program):
        self._arithmetic_ops = ["+", "-", "*", "/"]
        self._relation_ops = ["<", ">", "=", "<>", "<=", ">="]
        self._sym = ["(", ")", ","] + self._arithmetic_ops + self._relation_ops
        self._program = program

    def __get_symbol(self, lexeme, line, col):
        if lexeme in self._arithmetic_ops:
            return Token(lexeme, TokenEnum.ARITHMETIC_OP, line, col)
        if lexeme in self._relation_ops:
            return Token(lexeme, TokenEnum.RELATION_OP, line, col)

        if lexeme == "(":
            return Token(lexeme, TokenEnum.LPAREN, line, col)
        if lexeme == ")":
            return Token(lexeme, TokenEnum.RPAREN, line, col)
        if lexeme == ",":
            return Token(lexeme, TokenEnum.COMMA, line, col)

        return None

    def get_tokens(self):
        """ Return a list of tokens in the given program """
        tokens = []
        line = 1
        col = 0

        lexeme = ""
        for idx, char in enumerate(self._program):
            col = col + 1
            if char == "\n":
                line = line + 1
                col = 0

            if char not in string.whitespace or lexeme.startswith('"'):
                lexeme += char

            # First, check for complete string literal
            if lexeme.startswith('"'):
                if len(lexeme) > 1 and lexeme.endswith('"'):
                    tokens.append(Token(lexeme, TokenEnum.STRING, line, col))
                    lexeme = ""
                continue

            # We need to look-ahead two chars to determine if a token is
            # the symbol '<' or the symbol '<='
            next_1 = next_2 = None
            if idx + 1 < len(self._program):
                next_1 = self._program[idx + 1]
            if idx + 2 < len(self._program):
                next_2 = self._program[idx + 1 : idx + 2]

            # Make sure we do not add '<' if the actual token is '<='
            sym_double = filter(lambda sym: len(sym) == 2, self._sym)
            if next_1 is not None and lexeme + next_1 in sym_double:
                continue

            if lexeme in self._sym:
                tokens.append(self.__get_symbol(lexeme, line, col))
                lexeme = ""
                continue

            # Is this the end of a lexeme?
            # It is if is next char is whitespace or ...
            # ... if next char is a reserved symbol or ...
            # ... if the next two chars is a reserved symbol or ...
            # ... there is no next char
            is_delim = (
                next_1 is None
                or next_1 in string.whitespace
                or next_1 in self._sym
                or (next_2 is not None and next_2 in self._sym)
            )

            if is_delim:
                start = (col + 1) - len(lexeme)
                if next_1 is None or next_1 in string.whitespace:
                    if lexeme in STATEMENTS:
                        token = Token(lexeme, TokenEnum.STATEMENT, line, start)
                        tokens.append(token)
                        lexeme = ""
                        continue

                if len(lexeme) == 1 and lexeme.isalpha() and lexeme.isupper():
                    token = Token(lexeme, TokenEnum.VARIABLE, line, start)
                    tokens.append(token)

                elif lexeme.isnumeric():
                    tokens.append(Token(lexeme, TokenEnum.NUMBER, line, start))

                elif len(lexeme) > 1:
                    raise LexError("unknown token: %s" % lexeme, line, start)

                lexeme = ""
        return tokens


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit()

    try:
        F = open(sys.argv[1], "r")
        P = F.read()
    except IOError:
        print("could not read file: %s" % sys.argv[1])
        sys.exit()

    for tk in Lexer(P).get_tokens():
        print("%s\t\t-\t%s\t[%d:%d]" % (tk.value, tk.type, tk.line, tk.col))
