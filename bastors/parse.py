""" Formal grammar of Tiny Basic (https://en.wikipedia.org/wiki/Tiny_BASIC)
    line ::= number statement CR | statement CR
    statement ::= PRINT expr-list
                  IF expression operator expression THEN statement
                  GOTO number
                  INPUT var-list
                  LET var = expression
                  GOSUB number
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
    operator ::= < (>|=|ε) | > (<|=|ε) | =
    string ::= " (a|b|c ... |x|y|z|A|B|C ... |X|Y|Z|digit)* " """
from enum import Enum
from collections import defaultdict
from collections import namedtuple
import sys
import bastors.lex as lex


class ConditionEnum(Enum):
    """Represents the types of a condition, used in if statements or loops"""

    INITIAL = 0
    AND = 1
    OR = 2


VariableCondition = namedtuple("VariableCondition", ["var", "type"])
NotVariableCondition = namedtuple("VariableCondition", ["var", "type"])
Condition = namedtuple("Condition", ["left", "operator", "right", "type"])


def invert_conditions(conditions):
    """
    Use De Morgan's law to perform not(conditions):
        not(A and B) = not A or  not B
        not(A or  B) = not A and not B
    """
    table = {"<>": "=", "<=": ">", ">=": "<"}
    inv_conds = []
    for cond in conditions:
        if isinstance(cond, VariableCondition):
            inv_conds.append(NotVariableCondition(cond.var, cond.type))
            continue

        if isinstance(cond, VariableCondition):
            inv_conds.append(VariableCondition(cond.var, cond.type))
            continue

        # invert the relation
        for op1, op2 in table.items():
            if cond.operator == op1:
                new_op = op2
                break
            elif cond.operator == op2:
                new_op = op1
                break

        # Turn AND to OR and OR to AND
        new_type = cond.type
        if cond.type == ConditionEnum.AND:
            new_type = ConditionEnum.OR
        elif cond.type == ConditionEnum.OR:
            new_type = ConditionEnum.AND

        inv_conds.append(Condition(cond.left, new_op, cond.right, new_type))

    return inv_conds


#
# These are the statements that we currently construct from TinyBasic
#
Program = namedtuple("Program", "statements")
Let = namedtuple("Let", ["label", "lval", "rval"])
If = namedtuple("If", ["label", "conditions", "then"])
Goto = namedtuple("Goto", ["label", "target_label"])
Print = namedtuple("Print", ["label", "exp_list"])
Gosub = namedtuple("Gosub", ["label", "target_label"])
Return = namedtuple("Return", ["label"])
Input = namedtuple("Input", ["label", "variables"])
End = namedtuple("End", ["label"])

ArithmeticExpression = namedtuple("ArithmeticExpression", ["left", "operator", "right"])
BooleanExpression = namedtuple("BooleanExpression", ["conditions"])
VariableExpression = namedtuple("VariableExpression", ["var"])
NotExpression = namedtuple("NotExpression", ["exp"])


class ParseError(Exception):
    """ An error while parsing TinyBasic """

    def __init__(self, message, line, col):
        super(ParseError, self).__init__(message)
        self.line = line
        self.col = col


class Parser:  # pylint: disable=too-few-public-methods
    """ The parse() method consumes tokens from the lexer (lex.py) and attempts
        to parse TinyBasic from that and will generate a SyntaxTreeish
        structure that can be used to generate Rust later on. """

    def __init__(self, code):
        self._code = code
        self._statements = defaultdict(list)
        self._context = "main"
        self._current_token = None
        self._token_iter = None
        self.functions = dict()

    def __parse_error(self, msg):
        token = self._current_token
        raise ParseError(
            "error: %s [%d:%d]" % (msg, token.line, token.col), token.line, token.col
        )

    def __eat(self, token_type):
        if self._current_token.type == token_type:
            try:
                self._current_token = next(self._token_iter)
            except StopIteration:
                self._current_token = lex.Token("EOF", lex.TokenEnum.EOF, -1, -1)
        else:
            self.__parse_error(
                "expected token %s was %s" % (token_type, self._current_token.type)
            )

    def __parse_factor(self):
        """factor ::= var | number | (expression)"""
        token = self._current_token
        if token.type == lex.TokenEnum.VARIABLE:
            self.__eat(lex.TokenEnum.VARIABLE)
            return VariableExpression(
                token.value.lower()
            )  # Rust does not like CAPS variables
        if token.type == lex.TokenEnum.NUMBER:
            self.__eat(lex.TokenEnum.NUMBER)
            return token.value
        if token.type == lex.TokenEnum.LPAREN:
            self.__eat(lex.TokenEnum.LPAREN)
            node = self.__parse_exp()
            self.__eat(lex.TokenEnum.RPAREN)
            return node
        return None

    def __parse_term(self):
        """term ::= factor ((*|/) factor)*"""
        node = self.__parse_factor()

        while self._current_token.value in ("*", "/"):
            token = self._current_token
            self.__eat(lex.TokenEnum.ARITHMETIC_OP)
            factor = self.__parse_factor()
            node = ArithmeticExpression(node, token.value, factor)

        return node

    def __parse_exp(self):
        """
        expression ::= term ((+|-) term)*
        term ::= factor ((*|/) factor)*
        factor ::= var | number | (expression)
        """
        node = self.__parse_term()

        while self._current_token.value in ("-", "+"):
            token = self._current_token
            self.__eat(lex.TokenEnum.ARITHMETIC_OP)
            node = ArithmeticExpression(node, token.value, self.__parse_term())

        return node

    def __parse_let(self, label):
        """
        LET var = expression
        """
        lval = VariableExpression(self._current_token.value.lower())
        self.__eat(lex.TokenEnum.VARIABLE)

        if not self._current_token.value == "=":
            self.__parse_error("expected assign operator (=)")

        self.__eat(lex.TokenEnum.RELATION_OP)

        rval = self.__parse_exp()

        return Let(label, lval, rval)

    def __parse_print(self, label):
        """
        PRINT expr-list
        expr-list ::= (string|expression) (, (string|expression) )*
        """
        exp_list = []

        while True:
            if self._current_token.type == lex.TokenEnum.STRING:
                exp_list.append(self._current_token.value)
                self.__eat(lex.TokenEnum.STRING)
            else:
                exp_list.append(self.__parse_exp())

            if self._current_token.type == lex.TokenEnum.COMMA:
                self.__eat(lex.TokenEnum.COMMA)
            else:
                break

        return Print(label, exp_list)

    def __parse_if(self, conditions, label):
        """
        IF expression operator expression THEN statement
        operator ::= < (>|=|ε) | > (<|=|ε) | =
        """
        left = self.__parse_exp()
        relop = self._current_token.value
        self.__eat(lex.TokenEnum.RELATION_OP)
        right = self.__parse_exp()

        if conditions is None:
            conditions = [Condition(left, relop, right, ConditionEnum.INITIAL)]
        else:
            cond_type = ConditionEnum.AND
            conditions.append(Condition(left, relop, right, cond_type))

        if self._current_token.value != "THEN":
            line = self._current_token.line
            col = self._current_token.col
            raise ParseError("expected THEN at %d:%d" % (line, col), line, col)
        self.__eat(lex.TokenEnum.STATEMENT)  # THEN

        if self._current_token.value == "GOTO":
            self.__eat(lex.TokenEnum.STATEMENT)
            goto = self.__parse_goto(label)
            return If(label, conditions, [goto])

        if self._current_token.value == "IF":
            self.__eat(lex.TokenEnum.STATEMENT)
            return self.__parse_if(conditions, None)

        return If(label, conditions, [self.__parse_statement(None)])

    def __parse_goto(self, label):
        """GOTO number"""
        try:
            target_label = int(self._current_token.value)
            self.__eat(lex.TokenEnum.NUMBER)
        except ValueError:
            line = self._current_token.line
            col = self._current_token.col
            raise ParseError("expected number [%d:%d]" % (line, col), line, col)

        return Goto(label, target_label)

    def __parse_gosub(self, label):
        """
        GOSUB number

        We turn a GOSUB statement into a function call.
        """
        try:
            target_label = int(self._current_token.value)
            self.__eat(lex.TokenEnum.NUMBER)
        except ValueError:
            line = self._current_token.line
            col = self._current_token.col
            raise ParseError("expected number [%d:%d]" % (line, col), line, col)

        fn = Gosub(label, target_label)
        self.functions[target_label] = fn
        return fn

    def __parse_input(self, label):
        """INPUT var-list"""
        variables = list()
        while True:
            token = self._current_token
            self.__eat(lex.TokenEnum.VARIABLE)
            variables.append(VariableExpression(token.value.lower()))

            if self._current_token.type == lex.TokenEnum.COMMA:
                self.__eat(lex.TokenEnum.COMMA)
            else:
                break

        return Input(label, variables)

    def __parse_statement(self, label):
        token = self._current_token
        if token.type == lex.TokenEnum.EOF:
            return None

        self.__eat(lex.TokenEnum.STATEMENT)
        if token.value == "RETURN":
            return Return(label)
        if token.value == "LET":
            return self.__parse_let(label)
        if token.value == "PRINT":
            return self.__parse_print(label)
        if token.value == "IF":
            return self.__parse_if(None, label)
        if token.value == "GOTO":
            return self.__parse_goto(label)
        if token.value == "GOSUB":
            return self.__parse_gosub(label)
        if token.value == "INPUT":
            return self.__parse_input(label)
        if token.value == "END":
            return End(label)

        raise ParseError(
            "Unknown statement: %s" % token.value,
            self._current_token.line,
            self._current_token.col,
        )

    def __process_line(self):
        while self._current_token.type == lex.TokenEnum.COMMENT:
            self.__eat(lex.TokenEnum.COMMENT)

        if self._current_token.type == lex.TokenEnum.NUMBER:
            label = int(self._current_token.value)
            self.__eat(lex.TokenEnum.NUMBER)
        else:
            label = None

        return self.__parse_statement(label)

    def __parse_program(self):
        while True:
            statement = self.__process_line()
            if statement is None:
                break

            # If the label matches a GOSUB target (stored in the
            # functions list) we are now in that functions context and store
            # the statements there.
            if statement.label is not None:
                if int(statement.label) in self.functions:
                    self._context = statement.label

            self._statements[self._context].append(statement)

        return Program(self._statements)

    def parse(self):
        """ Attempts to parse a TineBasic program based on the tokens received
            from the lexer (lex.py). See the namedtuples above for what
            statements are generated to a list on the program node. """
        lexer = lex.Lexer(self._code)
        self._token_iter = iter(lexer.get_tokens())
        self._current_token = next(self._token_iter)

        return self.__parse_program()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit()

    try:
        FP = open(sys.argv[1], "r")
        PROGRAM = FP.read()
    except IOError:
        print("could not read file: %s" % sys.argv[1])
        sys.exit()

    try:
        TREE = Parser(PROGRAM).parse()
    except ParseError as err:
        print(err)
        sys.exit(1)
