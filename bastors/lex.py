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
    COMMENT = 9
    EOF = 10


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


class Lexer:  # pylint: disable=too-few-public-methods,too-many-branches
    """ Perform lexical analysis of BASIC grammar above """

    def __init__(self, program):
        self._arithmetic_ops = ["+", "-", "*", "/"]
        self._relation_ops = ["<", ">", "=", "<>", "<=", ">="]
        self._sym = ["(", ")", ","] + self._arithmetic_ops + self._relation_ops
        self._program = program
        self._lexeme = ""

    def __get_symbol(self, line, col):
        if self._lexeme in self._arithmetic_ops:
            return Token(self._lexeme, TokenEnum.ARITHMETIC_OP, line, col)
        if self._lexeme in self._relation_ops:
            return Token(self._lexeme, TokenEnum.RELATION_OP, line, col)

        if self._lexeme == "(":
            return Token(self._lexeme, TokenEnum.LPAREN, line, col)
        if self._lexeme == ")":
            return Token(self._lexeme, TokenEnum.RPAREN, line, col)
        if self._lexeme == ",":
            return Token(self._lexeme, TokenEnum.COMMA, line, col)

        return None

    def __string_literal(self, tokens, line, col):
        # Check for complete string literal
        if len(self._lexeme) > 1 and self._lexeme.endswith('"'):
            tokens.append(Token(self._lexeme, TokenEnum.STRING, line, col))
            return True
        return False

    def __comment(self, tokens, line, col):
        if len(self._lexeme) > 1 and self._lexeme[-1] == "\n":
            tokens.append(Token(self._lexeme, TokenEnum.COMMENT, line, col))
            return True
        if len(self._lexeme) == 0:
            return True
        return False

    def __symbol(self, tokens, idx, line, col):
        # We need to look-ahead to determine if a token is
        # the symbol '<' or the symbol '<='
        next_1 = None
        if idx + 1 < len(self._program):
            next_1 = self._program[idx + 1]

        # Make sure we do not add '<' if the actual token is '<='
        sym_double = filter(lambda sym: len(sym) == 2, self._sym)
        if next_1 is not None and self._lexeme + next_1 in sym_double:
            # This will match a symbol next iteration
            return False

        if self._lexeme in self._sym:
            tokens.append(self.__get_symbol(line, col))
            return True

        return False

    def __complete_lexeme(self, idx):
        # Look-ahead to determine if next char is a self._lexeme separator
        next_1 = next_2 = None
        if idx + 1 < len(self._program):
            next_1 = self._program[idx + 1]
        if idx + 2 < len(self._program):
            next_2 = self._program[idx + 1 : idx + 2]
        # Is this the end of a self._lexeme?
        # It is if is next char is whitespace or ...
        # ... if next char is a reserved symbol or ...
        # ... if the next two chars is a reserved symbol or ...
        # ... there is no next char
        return (
            next_1 is None
            or next_1 in string.whitespace
            or next_1 in self._sym
            or (next_2 is not None and next_2 in self._sym)
        )

    def get_tokens(self):
        """ Return a list of tokens in the given program """
        tokens = []
        line = 1
        col = 0

        is_comment = False
        for idx, char in enumerate(self._program):
            col = col + 1
            if char == "\n":
                line = line + 1
                col = 0

            if is_comment:
                self._lexeme += char
                if self.__comment(tokens, line, col):
                    is_comment = False
                    self._lexeme = ""
                continue

            if char == '"' or self._lexeme.startswith('"'):
                self._lexeme += char
                if self.__string_literal(tokens, line, col):
                    self._lexeme = ""
                continue

            # Now we are done with all tokens that can have whitespace in them
            if char not in string.whitespace:
                self._lexeme += char

            # Symbols does not need separators around them to be valid
            if self.__symbol(tokens, idx, line, col):
                self._lexeme = ""
                continue

            # If next char is a self._lexeme separator then we should check that we
            # have a known token here.
            if self.__complete_lexeme(idx):
                start = (col + 1) - len(self._lexeme)
                if self._lexeme in STATEMENTS:
                    token = Token(self._lexeme, TokenEnum.STATEMENT, line, start)
                    tokens.append(token)
                    self._lexeme = ""
                    continue

                if self._lexeme == "REM":
                    is_comment = True
                    self._lexeme = ""
                    continue

                length = len(self._lexeme)
                if length == 1 and self._lexeme.isalpha() and self._lexeme.isupper():
                    token = Token(self._lexeme, TokenEnum.VARIABLE, line, start)
                    tokens.append(token)

                elif self._lexeme.isnumeric():
                    tokens.append(Token(self._lexeme, TokenEnum.NUMBER, line, start))

                elif len(self._lexeme) > 1:
                    raise LexError("unknown token: [%s]" % self._lexeme, line, start)

                self._lexeme = ""
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
