""" Functions to help with debugging """
from collections import defaultdict
from collections import namedtuple
import bastors.parse as parse
from bastors.visitor import Visitor

import sys


def expression(exp):
    if isinstance(exp, parse.VariableExpression):
        return "%s" % exp.var

    if isinstance(exp, parse.NotExpression):
        return "not %s" % expression(exp.exp)

    if isinstance(exp, parse.ArithmeticExpression):
        return "%s %s %s" % (expression(exp.left), exp.operator, expression(exp.right),)

    if isinstance(exp, parse.BooleanExpression):
        return format_condition(exp.conditions)

    return str(exp)


def format_condition(conditions):
    code = ""
    for cond in conditions:
        if cond.type == parse.ConditionEnum.AND:
            code += " AND "
        elif cond.type == parse.ConditionEnum.OR:
            code += " OR "

        if isinstance(cond, parse.VariableCondition):
            code += "%s" % cond.var
            continue

        if isinstance(cond, parse.NotVariableCondition):
            code += "NOT %s" % cond.var
            continue

        code += "%s %s %s" % (
            expression(cond.left),
            cond.operator,
            expression(cond.right),
        )

    return code


# pylint: disable=C0103
class Print(Visitor):
    """
        This class visit all nodes of the statement tree and prints a
        reprsentation.
    """

    def __init__(self, program, out=sys.stdout):
        super().__init__(self.__default)
        self._out = out
        self._program = program
        self._indent = 1

    def __print(self, output, label=None):
        indent = self._indent * 2 * " "
        label_str = "     " if label is None else "%-5s" % label
        print("%s%s%s" % (label_str, indent, output), file=self._out)

    def __default(self, node):
        self.__print("%s" % type(node).__name__, node.label)

    def output(self):
        self.visit(self._program)

    def visit_Program(self, node):
        for context in node.statements.keys():
            print("\n%s:" % context, file=self._out)
            self._indent += 1
            for statement in node.statements[context]:
                self.visit(statement)
            self._indent -= 1

    def visit_Input(self, node):
        variables = str()
        for var in node.variables:
            variables += "%s, " % var.var
        self.__print("Input %s" % variables, node.label)

    def visit_Gosub(self, node):
        self.__print("Gosub %s" % node.target_label, node.label)

    def visit_Goto(self, node):
        self.__print("Goto %s" % node.target_label, node.label)

    def visit_Let(self, node):
        let = "LET %s=%s" % (expression(node.lval), expression(node.rval),)
        self.__print(let, node.label)

    def visit_Print(self, node):
        arguments = ",".join([expression(exp) for exp in node.exp_list])
        self.__print("Print %s" % arguments, node.label)

    def visit_Loop(self, node):
        self.__print("Loop", node.label)
        self._indent += 1
        for statement in node.statements:
            self.visit(statement)

        if node.conditions is not None:
            conditions = parse.invert_conditions(node.conditions)
            self.__print("If %s Then Break" % format_condition(conditions))

        self._indent -= 1

    def visit_If(self, node):
        self.__print("If %s Then" % format_condition(node.conditions), node.label)

        self._indent += 1
        for statement in node.then:
            self.visit(statement)
        self._indent -= 1


def dump(program, path=None):
    if path is not None:
        out = open(path, "w")
    else:
        out = sys.stdout

    if isinstance(program, list):
        statements = dict()
        statements["listing"] = program
        program = parse.Program(statements)

    printer = Print(program, out)
    printer.output()
    if path is not None:
        out.close()
