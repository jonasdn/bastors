""" Converts a basic TinyBasic program (bas) to rust code (rs) """
from collections import defaultdict
from collections import namedtuple
from enum import Enum
import bastors.parse as parse
from bastors.visitor import Visitor

# pylint: disable=C0116

# Represent a line of Rust code at an indentation level
Line = namedtuple("Line", ["indent", "code"])


class VariableTypeEnum(Enum):
    """Represents the types of a condition, used in if statements or loops"""

    INTEGER = 0
    BOOLEAN = 1


def expression(exp):
    if isinstance(exp, parse.VariableExpression):
        return "state.%s" % exp.var

    if isinstance(exp, parse.ArithmeticExpression):
        if exp.left is None:  # unary expression
            return "%s%s" % (exp.operator, expression(exp.right),)
        else:
            return "%s %s %s" % (
                expression(exp.left),
                exp.operator,
                expression(exp.right),
            )

    if isinstance(exp, parse.BooleanExpression):
        return format_condition(exp.conditions)

    if isinstance(exp, parse.ParenExpression):
        return "(%s)" % expression(exp.exp)

    return str(exp)


def format_condition(conditions):
    """
    Turns a list of the namedtuple basic condition to a Rust condition.
        Examples:
            a <> b becomes a != b
    The function will also add && or || in case of an array of condtions.
    """
    code = ""
    for cond in conditions:
        if cond.type == parse.ConditionEnum.AND:
            code += " && "
        elif cond.type == parse.ConditionEnum.OR:
            code += " || "

        if isinstance(cond, parse.VariableCondition):
            code += "state.%s" % cond.var
            continue

        if isinstance(cond, parse.NotVariableCondition):
            code += "!state.%s" % cond.var
            continue

        if isinstance(cond, parse.TrueFalseCondition):
            code += "%s" % cond.value
            continue

        if cond.operator == "<>":
            relop = "!="
        elif cond.operator == "=":
            relop = "=="
        else:
            relop = cond.operator

        code += "%s %s %s" % (expression(cond.left), relop, expression(cond.right))

    return code


# pylint: disable=C0103
class Rustify(Visitor):
    """ This class visit all nodes of the statement tree generated by
        the Parse class and create Rust code from it. It follows some kind
        of visitor pattern, the base clase is defined in visitor.py """

    def __init__(self):
        super().__init__()
        self._code = defaultdict(list)
        self._variables = set()
        self._crates = set()
        self._indent = 1
        self._context = "main"

    def __in_function(self):
        return self._context != "main"

    def __add_line(self, indent, code):
        self._code[self._context].append(Line(indent, code))

    def __output_state(self, file):
        if len(self._variables) > 0:
            print("struct State {", file=file)
            for var, var_type in sorted(self._variables):
                if var_type == VariableTypeEnum.BOOLEAN:
                    type_rep = "bool"
                else:
                    type_rep = "i32"
                print("%s%s: %s," % (" " * 4, var, type_rep), file=file)
            print("}\n", file=file)

            decl = list()
            decl.append(Line(self._indent, "let mut state: State = State {"))
            for var, var_type in sorted(self._variables):
                if var_type == VariableTypeEnum.BOOLEAN:
                    decl.append(Line(self._indent + 1, "%s: false," % var))
                else:
                    decl.append(Line(self._indent + 1, "%s: 0," % var))
            decl.append(Line(self._indent, "};"))
            self._code["main"] = decl + self._code["main"]

    def __output_function(self, name, code, argument, file):
        print("fn %s(%s) {" % (name, argument), file=file)
        for line in code:
            print("%s%s" % (line.indent * (" " * 4), line.code), file=file)
        print("}\n", file=file)

    def __output_functions(self, file):
        for fn in sorted(self._code.keys()):
            if fn != "main":
                name = "f_%s" % fn
                argument = "state: &mut State" if len(self._variables) > 0 else None
            else:
                name = fn
                argument = None

            self.__output_function(name, self._code[fn], argument or str(), file)

    def __output_crates(self, file):
        for crate in sorted(self._crates):
            print("use %s;" % crate, file=file)

    def output(self, file):
        """ Writes Rust code to the file specified in argument """
        self.__output_crates(file)
        self.__output_state(file)
        self.__output_functions(file)

    def visit_Program(self, node):
        """ Iterate through all statements in the TinyBasic program and
            generate Rust"""
        for context in node.statements.keys():
            self._context = str(context)
            for statement in node.statements[context]:
                self.visit(statement)

    def visit_End(self, node):
        # pylint: disable=unused-argument
        if self._context == "main":
            self.__add_line(self._indent, "return;")
        else:
            self._crates.add("std::process")
            self.__add_line(self._indent, "process::exit(0x0);")

    def visit_Input(self, node):
        self._crates.add("std::io")

        for var in node.variables:
            self._variables.add((var.var, VariableTypeEnum.INTEGER))
            self.__add_line(self._indent, "loop {")
            self.__add_line(self._indent + 1, "let mut input = String::new();")

            self.__add_line(
                self._indent + 1, "io::stdin().read_line(&mut input).unwrap();"
            )
            self.__add_line(self._indent + 1, "match input.trim().parse::<i32>() {")
            self.__add_line(
                self._indent + 2, "Ok(i) => { %s = i; break }," % expression(var)
            )
            self.__add_line(self._indent + 2, 'Err(_) => println!("invalid number")')
            self.__add_line(self._indent + 1, "}")
            self.__add_line(self._indent, "}")

    def visit_Gosub(self, node):
        if self.__in_function():
            argument = "state"
        else:
            argument = "&mut state"
        code = "f_%s(%s);" % (node.target_label, argument)
        self.__add_line(self._indent, code)

    def visit_Return(self, node):
        # pylint: disable=unused-argument
        self.__add_line(self._indent, "return;")

    def visit_Let(self, let_node):
        """ Generate Rust from TinyBasic LET """
        if isinstance(let_node.rval, parse.BooleanExpression):
            self._variables.add((let_node.lval.var, VariableTypeEnum.BOOLEAN))
        else:
            self._variables.add((let_node.lval.var, VariableTypeEnum.INTEGER))

        code = "%s = %s;" % (expression(let_node.lval), expression(let_node.rval),)
        self.__add_line(self._indent, code)

    def visit_Print(self, print_node):
        """ Generate Rust from TinyBasic PRINT, by ways of the println! macro
        and the: println!()"{}", arguments), notation. """
        num = len(print_node.exp_list)
        arguments = ", ".join([expression(exp) for exp in print_node.exp_list])
        code = 'println!("%s", %s);' % ("{}" * num, arguments)
        self.__add_line(self._indent, code)

    def visit_Loop(self, loop_node):
        """ Generate Rust code from a Loop statement """
        self.__add_line(self._indent, "loop {")
        self._indent = self._indent + 1
        for statement in loop_node.statements:
            self.visit(statement)

        if loop_node.conditions is not None:
            conditions = parse.invert_conditions(loop_node.conditions)
            code = "if %s {" % format_condition(conditions)
            self.__add_line(self._indent, code)
            self.__add_line(self._indent + 1, "break;")
            self.__add_line(self._indent, "}")

        self._indent = self._indent - 1
        self.__add_line(self._indent, "}")

    def visit_Break(self, node):
        # pylint: disable=unused-argument
        self.__add_line(self._indent, "break;")

    def visit_If(self, if_node):
        """ Generate Rust code from TInyBasic IF statement, the grunt work is
            performed by the format_condition() function. """
        code = "if %s {" % format_condition(if_node.conditions)
        self.__add_line(self._indent, code)

        self._indent = self._indent + 1
        for statement in if_node.statements:
            self.visit(statement)
        self._indent = self._indent - 1

        self.__add_line(self._indent, "}")
