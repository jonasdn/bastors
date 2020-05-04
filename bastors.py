#!/usr/bin/env python3
import argparse
import sys
from bastors.lex import LexError
from bastors.parse import Parser, ParseError
from bastors.goto_elimination import GotoEliminationError, eliminate_goto
from bastors.rustify import Rustify

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", help="file to output rust to")
    parser.add_argument("input")
    args = parser.parse_args()

    try:
        f = open(args.input, "r")
        program = f.read()
    except IOError:
        print("could not read file: %s" % args.input)
        sys.exit()

    try:
        tree = eliminate_goto(Parser(program).parse())
    except ParseError as err:
        print("parse error: %s" % err)
        sys.exit(1)
    except LexError as err:
        print("syntax error: %s [%d:%d]" % (err, err.line, err.col))
        sys.exit(1)
    except GotoEliminationError as err:
        print(err)
        sys.exit(1)

    out = open(args.output, "w") if args.output else sys.stdout

    rust = Rustify()
    rust.visit(tree)
    rust.output(out)
