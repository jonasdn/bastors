""" This moudle handles the elimination of GOTO statements from a program """
from collections import namedtuple
import sys
import bastors.parse as parse

#
# A path is the way you need to travel throguh a list of statements to get
# to a statement. An IF statement creates a new block and a new possible path.
#
# If we have a program like:
#
# Index Label Statement
# [0]   10      PRINT "Hello"
# [1]   20      LET A=2
# [2]   30      IF A <> 2 THEN IF A > 0 THEN GOTO 10
#
# The path of the label '10' is [0] and the path of the GOTO statement is
# [2, 0, 0].
#
GotoLabelPair = namedtuple("GotoLabelPair", ["goto_path", "label_path"])
Loop = namedtuple("Loop", ["label", "conditions", "statements"])
Break = namedtuple("Break", ["label"])

temp_var_num = 0  # global


class GotoEliminationError(Exception):
    """ An error while eliminating GOTOs """

    def __init__(self, message):
        super(GotoEliminationError, self).__init__(message)


def eliminate_goto(program):
    """
    This function will loop until there is no more GOTO statements found in
    the provided program.

    Base Algorithm:
      1) Take the original program as input
      2) Collect all goto and label statements as pairs
      3) For Each goto-label pair:
        a) Convert goto to single statement conditional goto, if it is not
           already

        b) Classify the goto-label pair to a single case (from among the cases
           outlined below in classify_pair())

        c) Execute specific case's algorithm of which the current goto-label pair corresponds to

      4) Output the restructured program

    Key Points:
      * For the all case specific algorithms that are detailed below, following
        are some of the key points to consider:

        * Every goto statement should be conditional (i.e. conditional with the
          single goto statement in it)
          Eg:

            if (cond) {
              goto L1
            }

        * For any goto-label pair, only the goto statement must be
          adjusted/moved to reduce the structure to primitive case/state

    Note: In all the algorithms outline below, when referring to goto
          statement, it refers to the single statement conditional goto i.e.:

        if (cond) {
            goto L1
        }
    """
    statements = program.statements
    while True:  # loop until no GOTOs found
        found = False
        for context in statements.keys():
            pair = find_pair(statements[context])
            if pair is not None:
                found = True
                case = classify_pair(pair)
                if case == "1.1":
                    algo_1_1_same_level_same_block__before(pair, statements[context])
                    break
                if case == "1.2":
                    algo_1_2_same_level_same_block__after(pair, statements[context])
                    break
                if case == "2.1":
                    raise GotoEliminationError(
                        "case %s is not implemented: GOTO occurs in some "
                        "parent block (> 1) of the block where the label "
                        "is contained in and goto occurs before the label." % case
                    )
                if case == "2.2":
                    raise GotoEliminationError(
                        "case %s is not implemented: GOTO occurs in some "
                        "parent block (> 1) of the block where the label "
                        "is contained in and label occurs before the goto." % case
                    )
                if case == "3.1":
                    algo_3_1__label_in_parent_block__before(pair, statements[context])
                    break
                if case == "3.2":
                    raise GotoEliminationError(
                        "case %s not implemented: Label occurs in some "
                        "parent block (> 1) of the block where the goto is "
                        "contained in and label occurs before the goto." % case
                    )

                # No matches among supported cases
                block = get_block(statements[context], pair.goto_path)
                if_stmt = block[pair.goto_path[-1]]
                raise GotoEliminationError(
                    "Unsupported GOTO case (GOTO %s)" % if_stmt.then[0].target_label
                )

        if found is False:
            break  # no GOTOs found in program!

    return program


def classify_goto(program):
    """
    Used for test: return the classification for first goto/label pair
    found, or None if none found.
    """
    for context in program.statements.keys():
        pair = find_pair(program.statements[context])
        if pair is not None:
            return classify_pair(pair)


def classify_pair(pair):
    """
    Given a GOTO and label pair, classify it into one of 9 cases, see below
    in line comments for details about the cases.
    Each case has a specific algorithm to handle elimination.
    This algo was found at:
        https://dzone.com/articles/goto-elimination-algorithm
    """
    length_goto_path = len(pair.goto_path)
    length_label_path = len(pair.label_path)
    #
    # First we determinate if the goto occurs before or after the label
    #
    before = goto_before_label(pair)
    #
    # Case 1.1 / 1.2:
    #   Goto and label occur at the same indent level in the same
    #   container/block. If goto occurs before label this is case 1.1
    #   otherwise it is 1.2.
    #
    # This means the path leading up to the last index needs to be identical.
    #
    if length_goto_path == length_label_path:
        if length_goto_path == 1 or pair.goto_path[:-1] == pair.label_path[:-1]:
            return "1.1" if before else "1.2"
    #
    # Case 2.1 / 2.2:
    #  Goto occurs in some parent block of where the label is contained in.
    #
    #  Example:
    # 10   LET A=1
    # 20   LET B=2
    # 30   IF B>1 THEN GOTO 50
    # 40   IF A>0 THEN
    # 50     PRINT B
    # 60     PRINT "HEJ"
    # 70   END
    #
    #   Note that this can't happen in a simple TinyBasic program, it needs
    #   to have been transformed in some way by goto elimnation.
    #
    #   This means that the entire goto path needs to be in the label path.
    #   We will check this by slicing the subset of the label path that is
    #   the same length as the goto path.
    if length_label_path - length_goto_path >= 1:  # potential case of 2.x
        label_sub_path = pair.label_path[:length_goto_path]
        if label_sub_path[:-1] == pair.goto_path[:-1]:
            return "2.1" if before else "2.2"
    #
    # Case 3.1 / 3.2:
    #  This is the "inverse" of the 2.1 / 2.2 case, but here we are checking
    #  for if the label occurs in a parent block.
    #
    if length_goto_path - length_label_path >= 1:  # potential case of 3.x
        goto_sub_path = pair.goto_path[:length_label_path]
        if goto_sub_path[:-1] == pair.label_path[:-1]:
            return "3.1" if before else "3.2"

    return None


def goto_before_label(pair):
    """
    Returns true if the GOTO statement occurs before its target label.
    """
    for index, goto_index in enumerate(pair.goto_path):
        if index >= len(pair.label_path):
            return True
        label_index = pair.label_path[index]
        if goto_index < label_index:
            return True
        if goto_index > label_index:
            return False
    return False


def get_block(statements, path):
    """
    Given a list of statements and a path, return the block the statments
    belongs to.
    """
    for i, index in enumerate(path):
        if i == len(path) - 1:
            return statements

        statement = statements[index]
        if isinstance(statement, parse.If) or isinstance(statement, Loop):
            return get_block(statement.then, path[1:])

    return None


def is_in_loop(statements, path):
    """
    Given a list of statements and a path, return true if the statement's
    parent block is a loop.
    """
    if len(path) <= 1:
        return False

    for i, index in enumerate(path):
        statement = statements[index]

        if i == len(path) - 2:
            return isinstance(statement, Loop)

        if isinstance(statement, parse.If) or isinstance(statement, Loop):
            return is_in_loop(statement.then, path[1:])

    return False


def get_temp_name():
    """Return the next available name for a temporary variable"""
    global temp_var_num
    temp_var_num += 1
    return "t%d" % temp_var_num


def algo_1_1_same_level_same_block__before(pair, statements):
    """
    Conditionally execute all the statements between the goto statement and the
    label statement, based on the inverse condition that is applied on the goto
    statement and remove the goto statement and the label.
    """
    block = get_block(statements, pair.goto_path)
    goto_stmt = block[pair.goto_path[-1]]
    #
    # The statements between the goto and the label can be represented as:
    #   block[pair.goto_path[-1] + 1 : pair.label_path[-1]]
    # Which is the subset of the list between the goto  and the
    # label index.
    #
    between = slice(pair.goto_path[-1] + 1, pair.label_path[-1])
    if_stmt = parse.If(
        goto_stmt.label, parse.invert_conditions(goto_stmt.conditions), block[between]
    )
    block[pair.goto_path[-1]] = if_stmt
    del block[between]


def algo_1_2_same_level_same_block__after(pair, statements):
    """
    Execute all the statements between the label statement and the goto
    statement in a loop, including the label statement, based on the
    condition that is applied on the goto statement and remove the label and
    the goto statement.
    """
    block = get_block(statements, pair.goto_path)
    goto_stmt = block[pair.goto_path[-1]]
    #
    # This slice gets us all statements between the label and the goto
    # including the label.
    #
    between = slice(pair.label_path[-1], pair.goto_path[-1])
    #
    # Insert a loop statement where the label was and create a loop based
    # on the goto statement condition.
    #
    loop_stmt = Loop(None, goto_stmt.conditions, block[between])
    block[pair.label_path[-1]] = loop_stmt
    #
    # Remove statements between the label statements and the goto statement
    # including the goto statement. They being replaced by the loop statement
    # above.
    #
    del block[pair.label_path[-1] + 1 : pair.goto_path[-1] + 1]


def algo_3_1__label_in_parent_block__before(pair, statements):
    """
    1) Introduce a new variable to the store the value of the condition that
       is applied on the goto statement and use this new variable as the
       conditional for the goto statement.

    2) If goto is inside a block that is not a loop, then conditionally execute
       all the statements after the goto statement in the same block, based on
       the inverse condition that is applied on the goto statement. If goto is
       inside a loop, use break to break out of the loop.

    3) Move the goto statement upwards to the parent block (i.e. move the goto
       statement to the next statement after the current block).

    4) Repeat steps #2 and #3 till the goto statement and label statement end
       up in the same block.

    5) Apply Case 1.1 algorithm
    """
    #
    # Step 1, introduce new variable and use it for goto conditional
    #
    block = get_block(statements, pair.goto_path)
    goto_stmt = block[pair.goto_path[-1]]
    goto_conds = goto_stmt.conditions
    temp_name = get_temp_name()
    temp_var = parse.Let(
        None, parse.VariableExpression(temp_name), parse.BooleanExpression(goto_conds),
    )
    block.insert(pair.goto_path[-1], temp_var)
    goto_stmt = parse.If(
        goto_stmt.label,
        [parse.VariableCondition(temp_name, parse.ConditionEnum.INITIAL)],
        goto_stmt.then,
    )

    # Update the GotoLabelPair
    new_goto_path = pair.goto_path
    new_goto_path[-1] += 1
    pair = GotoLabelPair(new_goto_path, pair.label_path)
    block[pair.goto_path[-1]] = goto_stmt

    while True:
        block = get_block(statements, pair.goto_path)
        #
        # Step 2, use if-statement, or break out of loop.
        #
        print
        if is_in_loop(statements, pair.goto_path):
            block[pair.goto_path[-1]] = (
                parse.If(
                    None,
                    [parse.VariableCondition(temp_name, parse.ConditionEnum.INITIAL)],
                    [Break(None)],
                ),
            )
        else:
            stmts = block[pair.goto_path[-1] + 1 :]
            del block[pair.goto_path[-1] + 1 :]

            if_stmt = parse.If(
                None,
                parse.invert_conditions(
                    [parse.VariableCondition(temp_name, parse.ConditionEnum.INITIAL)]
                ),
                stmts,
            )
            block[pair.goto_path[-1]] = if_stmt
        #
        # Step 3, move goto up one block
        #
        new_goto_path = pair.goto_path[:-1]
        new_goto_path[-1] = new_goto_path[-1] + 1
        new_block = get_block(statements, new_goto_path)
        new_block.insert(new_goto_path[-1], goto_stmt)
        pair = GotoLabelPair(new_goto_path, pair.label_path)
        #
        # Step 4, see if we need to do it again, or if algo 1.1 can take over
        #
        if pair.label_path[:-1] == pair.goto_path[:-1]:
            break
    #
    # Step 5, apply algo 1.1
    #
    algo_1_1_same_level_same_block__before(pair, statements)


def convert_to_conditional(goto, label, index, statements):
    """
    This function converts a bare GOTO to a conditional GOTO.
    Example:
      10 PRINT "Hello"
      20 GOTO 10
      30 END

    Becomes:
      10 PRINT "Hello"
      20 IF 1 = 1 THEN GOTO 10
      30 END

    The reason for this is that the algorithm used assumes all GOTOs are
    conditional GOTOs.
    """
    cond = parse.Condition(1, "=", 1, parse.ConditionEnum.INITIAL)
    replacement = parse.If(label, [cond], [goto])
    statements[index] = replacement


def find_goto(statements, path):
    """
    This function attempts to find the path to the first GOTO statement in the
    block of statements provided.
    A path is a path of indexes, for instance:
      10 PRINT "Hello"
      20 LET A=2
      30 IF A > 0 THEN GOTO 10
      40 PRINT A
      50 END
    Gives a path of [1, 0], the initial 1 leads us to the IF statement and
    the second 0 leads us to the GOTO in the THEN block.
    """
    for index, statement in enumerate(statements):
        if isinstance(statement, parse.Goto):
            if len(statements) != 1:
                convert_to_conditional(statement, statement.label, index, statements)
                path.insert(0, index)
            return statement.target_label

        if isinstance(statement, Loop):
            label = find_goto(statement.statements, path)
            if label is not None:
                path.insert(0, index)
                return label

        if isinstance(statement, parse.If):
            label = find_goto(statement.then, path)
            if label is not None:
                path.insert(0, index)
                return label
    return None


def find_label(target, statements, path):
    """ Find the path to the label target of a GOTO statement """
    for index, statement in enumerate(statements):
        if target == statement.label:
            path.insert(0, index)
            return True

        if isinstance(statement, Loop):
            if find_label(target, statement.statements, path):
                path.insert(0, index)
                return True

        if isinstance(statement, parse.If):
            if find_label(target, statement.then, path):
                path.insert(0, index)
                return True
    return False


def find_pair(statements):
    """ Find the paths to the next pair of GOTO/label """
    goto_path = list()
    label = find_goto(statements, goto_path)
    if label is None:
        return None

    label_path = list()
    if not find_label(label, statements, label_path):
        raise Exception("could not find label: %s" % label)

    return GotoLabelPair(goto_path, label_path)


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
        TREE = parse.Parser(PROGRAM).parse()
        ELIM = eliminate_goto(TREE)
    except parse.ParseError as err:
        print(err)
        sys.exit(1)
