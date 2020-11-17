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


KEYWORDS = [
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
    "FOR",
    "TO",
    "STEP",
    "NEXT"
]


class LexError(Exception):
    """ An error while token TinyBasic """

    def __init__(self, message, line, col):
        super(LexError, self).__init__(message)
        self.line = line
        self.col = col


class LexIterator:
    """
    An iterator capable of peeking one(1) char ahead, needed for the lexer
    we have. It will also keep track of line and column number for us.

    Call peek() to see next char without consuming it.
    """

    def __init__(self, str_iter):
        self._iter = str_iter
        self._char = None
        self._peeked = False
        self.line = 1
        self.col = 0

    def peek(self):
        """ Look-ahead at what char next() will return """
        if not self._peeked:
            self._char = next(self._iter, None)
            self._peeked = True
        return self._char

    def next(self):
        """ Return the next char and move the iter formward """
        self._char = self.peek()

        if self._char == "\n":
            self.line += 1
            self.col = 0
        else:
            self.col += 1

        self._peeked = False
        return self._char


class Lexer:  # pylint: disable=too-few-public-methods,too-many-branches
    """ Perform lexical analysis of BASIC grammar above """

    def __init__(self, program):
        self._arithmetic_ops = ["+", "-", "*", "/"]
        self._relation_ops = ["<", ">", "=", "<>", "<=", ">="]
        self._sym = ["(", ")", ","] + self._arithmetic_ops + self._relation_ops
        self._iter = LexIterator(iter(program))
        self._lexeme = ""
        self._tokens = list()

    def __append_token(self, token_type):
        start = (self._iter.col + 1) - len(self._lexeme)
        token = Token(self._lexeme, token_type, self._iter.line, start)
        self._tokens.append(token)

    def __append_symbol(self):
        token_type = None

        if self._lexeme in self._arithmetic_ops:
            token_type = TokenEnum.ARITHMETIC_OP
        if self._lexeme in self._relation_ops:
            token_type = TokenEnum.RELATION_OP
        if self._lexeme == "(":
            token_type = TokenEnum.LPAREN
        if self._lexeme == ")":
            token_type = TokenEnum.RPAREN
        if self._lexeme == ",":
            token_type = TokenEnum.COMMA

        if token_type is None:
            raise LexError(
                "unknown symbol [%s]" % self._lexeme, self._iter.line, self._iter.col
            )

        self.__append_token(token_type)

    def __string_literal(self):
        # Check for complete string literal
        if len(self._lexeme) > 1 and self._lexeme.endswith('"'):
            self.__append_token(TokenEnum.STRING)
            return True
        return False

    def __comment(self):
        if len(self._lexeme) > 1 and self._lexeme[-1] == "\n":
            self.__append_token(TokenEnum.COMMENT)
            return True
        if len(self._lexeme) == 0:
            return True
        return False

    def __symbol(self):
        # We need to look-ahead to determine if a token is
        # the symbol '<' or the symbol '<='
        next_1 = self._iter.peek()

        # Make sure we do not add '<' if the actual token is '<='
        if next_1 is not None and self._lexeme + next_1 in self._sym:
            self._lexeme += next_1
            self.__append_symbol()
            self._iter.next()  # consume the next iteration
            return True

        if self._lexeme in self._sym:
            self.__append_symbol()
            return True

        return False

    def __complete_lexeme(self):
        # Look-ahead to determine if next char is a self._lexeme separator
        next_1 = self._iter.peek()
        # Is this the end of a self._lexeme?
        # It is if is next char is whitespace or ...
        # ... if next char is a reserved symbol or ...
        # ... if the next two chars is a reserved symbol or ...
        # ... there is no next char
        return next_1 is None or next_1 in string.whitespace or next_1 in self._sym

    def get_tokens(self):
        """ Return a list of tokens in the given program """
        is_comment = False
        while True:
            char = self._iter.next()
            if char is None:
                break

            if is_comment:
                self._lexeme += char
                if self.__comment():
                    is_comment = False
                    self._lexeme = ""
                continue

            # Are we parsing a string?
            if char == '"' or self._lexeme.startswith('"'):
                self._lexeme += char
                if self.__string_literal():
                    self._lexeme = ""
                continue

            # Now we are done with all tokens that can have whitespace in them
            if char not in string.whitespace:
                self._lexeme += char

            # Symbols does not need separators around them to be valid
            if self.__symbol():
                self._lexeme = ""
                continue

            # If next char is a self._lexeme separator then we should check that we
            # have a known token here.
            if self.__complete_lexeme():
                if self._lexeme in KEYWORDS:
                    self.__append_token(TokenEnum.STATEMENT)
                    self._lexeme = ""
                    continue

                if self._lexeme == "REM":
                    is_comment = True
                    self._lexeme = ""
                    continue

                length = len(self._lexeme)
                if length == 1 and self._lexeme.isalpha() and self._lexeme.isupper():
                    self.__append_token(TokenEnum.VARIABLE)
                    self._lexeme = ""
                    continue

                if self._lexeme.isnumeric():
                    self.__append_token(TokenEnum.NUMBER)
                    self._lexeme = ""
                    continue

                if len(self._lexeme) > 1:
                    raise LexError(
                        "unknown token: [%s]" % self._lexeme,
                        self._iter.line,
                        (self._iter.col + 1) - len(self._lexeme),
                    )
                self._lexeme = ""
        return self._tokens


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
