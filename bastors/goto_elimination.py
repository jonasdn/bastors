""" This moudle handles the elimination of GOTO statements from a program """
from collections import namedtuple
import sys
import bastors.parse as parse
import bastors.debug as debug


class GotoLabelPair:
    """
    Represents a GOTO statement and its corresponding target label,
    constrained to a list of statements.

    See comment in find_pair() for a description of paths.
    """

    def __init__(self, statements, goto_path, label_path):
        self.goto_path = goto_path
        self.label_path = label_path
        self._statements = statements

    def __is_goto_before_label(self):
        """
        Returns true if the GOTO statement occurs before its target label.
        """
        for index, goto_index in enumerate(self.goto_path):
            if index >= len(self.label_path):
                return True
            label_index = self.label_path[index]
            if goto_index < label_index:
                return True
            if goto_index > label_index:
                return False
        return False

    def __path_in_loop(self, statements, path):
        """
        Given a list of statements and a path, return true if the statement's
        parent block is a loop.
        """
        if len(path) <= 1:
            return False

        for i, index in enumerate(path):
            statement = statements[index]

            if i == len(path) - 2:
                return isinstance(statement, Loop) or isinstance(statement, parse.For)

            if isinstance(statement, (Loop, parse.If)):
                return self.__path_in_loop(statement.statements, path[1:])

        return False

    def goto_in_loop(self):
        """ Return True if GOTO is in a Loop block """
        return self.__path_in_loop(self._statements, self.goto_path)

    def label_in_loop(self):
        """ Return True if label is in a Loop block """
        return self.__path_in_loop(self._statements, self.label_path)

    def goto_temp_var(self):
        """
        Introduce a new temporary variable to the store the value of the
        condition that is applied on the goto statement and use this new
        variable as the conditional for the goto statement. Or if one already
        exists for this GOTO statement, return the name.
        """
        block = get_block(self._statements, self.goto_path)
        goto_stmt = block[self.goto_path[-1]]
        conds = goto_stmt.conditions
        if len(conds) > 1 or not isinstance(conds[0], parse.VariableCondition):
            temp_name = get_temp_name()
            temp_var = parse.Let(
                None,
                parse.VariableExpression(temp_name),
                parse.BooleanExpression(conds),
            )
            block.insert(self.goto_path[len(self.goto_path) - 1], temp_var)
            goto_stmt = parse.If(
                goto_stmt.label,
                [parse.VariableCondition(temp_name, parse.ConditionEnum.INITIAL)],
                goto_stmt.statements,
            )
            # Update the GotoLabelPair to account for new statement
            self.goto_path[-1] += 1
            if len(self.goto_path) <= len(self.label_path):
                if self.goto_path[-1] < self.label_path[len(self.goto_path) - 1]:
                    self.label_path[len(self.goto_path) - 1] += 1

            # Add new modified goto stmt
            block[self.goto_path[-1]] = goto_stmt
            return temp_name
        return conds[0].var

    def classify(self):
        """
        Given a GOTO and label pair, classify it into one of 8 cases, see below
        in line comments for details about the cases.
        Each case has a specific algorithm to handle elimination.
        This algo was found at:
            https://dzone.com/articles/goto-elimination-algorithm
        """
        length_goto_path = len(self.goto_path)
        length_label_path = len(self.label_path)
        #
        # First we determinate if the goto occurs before or after the label
        #
        before = self.__is_goto_before_label()
        #
        # Case 1.1 / 1.2:
        #   Goto and label occur at the same indent level in the same
        #   container/block. If goto occurs before label this is case 1.1
        #   otherwise it is 1.2.
        #
        # This means the path leading up to the last index needs to be identical.
        #
        if length_goto_path == length_label_path:
            if length_goto_path == 1 or self.goto_path[:-1] == self.label_path[:-1]:
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
            label_sub_path = self.label_path[:length_goto_path]
            if label_sub_path[:-1] == self.goto_path[:-1]:
                return "2.1" if before else "2.2"
        #
        # Case 3.1 / 3.2:
        #  This is the "inverse" of the 2.1 / 2.2 case, but here we are checking
        #  for if the label occurs in a parent block.
        #
        if length_goto_path - length_label_path >= 1:  # potential case of 3.x
            goto_sub_path = self.goto_path[:length_label_path]
            if goto_sub_path[:-1] == self.label_path[:-1]:
                return "3.1" if before else "3.2"

        return "4.1" if before else "4.2"


Loop = namedtuple("Loop", ["label", "conditions", "statements"])
Break = namedtuple("Break", ["label"])

# pylint: disable=W0603
TEMP_VAR_NUM = 0  # global


class GotoEliminationError(Exception):
    """ An error while eliminating GOTOs """


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
    global TEMP_VAR_NUM
    TEMP_VAR_NUM = 0
    statements = program.statements
    while True:  # loop until no GOTOs found
        found = False
        for context in statements.keys():
            pair = find_pair(statements[context])
            if pair is not None:
                found = True
                case = pair.classify()
                if case == "1.1":
                    algo_1_1_same_level_same_block__before(pair, statements[context])
                    break
                if case == "1.2":
                    algo_1_2_same_level_same_block__after(pair, statements[context])
                    break
                if case == "2.1":
                    algo_2_1__goto_in_parent_block__before(pair, statements[context])
                    break
                if case == "2.2":
                    algo_2_2__goto_in_parent_block__after(pair, statements[context])
                    break
                if case == "3.1":
                    algo_3_1__label_in_parent_block__before(pair, statements[context])
                    break
                if case == "3.2":
                    algo_3_2__label_in_parent_block__after(pair, statements[context])
                    break
                if case == "4.1":
                    algo_4_1__label_in_disjunct__before(pair, statements[context])
                    break
                if case == "4.2":
                    algo_4_2__label_in_disjunct__after(pair, statements[context])
                    break

                # No matches among supported cases
                debug.dump(program)
                raise GotoEliminationError("Unsupported GOTO case")

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
            return pair.classify()
    return None


def get_block(statements, path):
    """
    Given a list of statements and a path, return the block the statments
    belongs to.
    """
    for i, index in enumerate(path):
        if i == len(path) - 1:
            return statements

        statement = statements[index]
        if isinstance(statement, (Loop, parse.If)):
            return get_block(statement.statements, path[1:])

    return None


def get_temp_name():
    """Return the next available name for a temporary variable"""
    global TEMP_VAR_NUM
    TEMP_VAR_NUM += 1
    return "t%d" % TEMP_VAR_NUM


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
    if len(block[between]) > 0:
        if_stmt = parse.If(
            goto_stmt.label,
            parse.invert_conditions(goto_stmt.conditions),
            block[between],
        )
        block[pair.goto_path[-1]] = if_stmt
        del block[between]
    else:
        del block[pair.goto_path[-1]]


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
    pair.goto_path[-1] -= len(block[between]) + 1
    pair.label_path[-1] += 1


def algo_2_1__goto_in_parent_block__before(pair, statements):
    """
    1) Introduce a new temporary variable to the store the value of the
       condition that is applied on the goto statement and use this new
       variable as the conditional for the goto statement.

    2) Modify the condition of immediate child block, if it is conditioned,
       to include the goto condition with the OR (||) operator (short-circuit).

    3) Conditionally execute all the statements after the goto statement in the
       same block, based on the inverse condition that is applied on the goto
       statement.

    4) Move the goto statement downwards to that child block (identified in
       step#2) (i.e. move the goto statement as the first statement in the
       child block).

    5) Repeat steps #2 to #4 till the goto statement and label statement end up
       in the same block.

    6) Apply Case 1.1 algorithm

    7) If the label statement was originally contained in a loop,
       re-initialize the temporary variable (introduced in step#1) to false,
       just before the statement where label was applied.
    """
    #
    # Step 1, introduce new variable and use it for goto conditional
    #
    temp_name = pair.goto_temp_var()

    while True:
        path_index = len(pair.goto_path) - 1
        #
        # Step 2, modify the immediate child block (if conditioned)
        #
        block = get_block(statements, pair.goto_path)
        label_block = None

        label_block_index = pair.label_path[path_index]
        stmt = block[label_block_index]
        if isinstance(stmt, Loop):
            label_block = stmt
            break
        if isinstance(stmt, parse.If):
            new_conditions = stmt.conditions + [
                parse.VariableCondition(temp_name, parse.ConditionEnum.OR)
            ]
            new_if = parse.If(stmt.label, new_conditions, stmt.statements)
            block[block.index(stmt)] = new_if
            label_block = new_if
        #
        # Step 3, conditionally execute statements after goto statement
        #
        stmts = block[pair.goto_path[-1] + 1 : label_block_index]
        if len(stmts) > 0:
            del block[pair.goto_path[-1] + 1 : label_block_index]
            block.insert(
                pair.goto_path[-1] + 1,
                parse.If(
                    None,
                    parse.invert_conditions(
                        [
                            parse.VariableCondition(
                                temp_name, parse.ConditionEnum.INITIAL
                            )
                        ]
                    ),
                    stmts,
                ),
            )
        # Update label_block_index
        #
        # Step 4, move the goto statement down to child block from step 2
        #
        label_block_index = block.index(label_block)
        if isinstance(label_block, parse.If):
            label_block.statements.insert(0, block[pair.goto_path[path_index]])
        else:
            label_block.statements.insert(0, block[pair.goto_path[path_index]])
        del block[pair.goto_path[path_index]]

        # Update GotoLabelPaur to account for the churn
        # Decrease the label block index, because of the GOTO move
        # Increase the next blocks label index, because of the GOTO move
        label_block_index -= 1
        pair.label_path[path_index] = label_block_index
        del pair.goto_path[-1]
        pair.goto_path.extend([label_block_index, 0])
        pair.label_path[len(pair.goto_path) - 1] += 1
        #
        # Step 5, see if we need to do it again, or if algo 1.1 can take over
        #
        if pair.label_path[:-1] == pair.goto_path[:-1]:
            break
    #
    # Step 6, apply algo 1.1
    #
    block = get_block(statements, pair.label_path)
    label_stmt = block[pair.label_path[-1]]
    algo_1_1_same_level_same_block__before(pair, statements)
    #
    # Step 7, if label was in a loop, re-initialize temp var to false
    #
    if isinstance(label_block, Loop):
        temp_var = parse.Let(
            None,
            parse.VariableExpression(temp_name),
            parse.BooleanExpression(
                [parse.TrueFalseCondition("false", parse.ConditionEnum.INITIAL)]
            ),
        )
        label_path = list()
        find_label(label_stmt.label, statements, label_path)
        block = get_block(statements, label_path[:-1])
        label_index = label_path[:1][-1]
        label_block.statements.insert(label_index, temp_var)


def algo_2_2__goto_in_parent_block__after(pair, statements):
    """
    1) Introduce a new temporary variable to the store the value of the
       condition that is applied on the goto statement and use this new
       variable as the conditional for the goto statement.

    2) Find the parent block where the label is contained, which is in the
       same block as the goto statement. Encapsulate this parent block and
       all the statements till the goto statement in a do-while loop, based on
       the condition that is applied on the goto statement.

    3) Move the goto statement as the first statement in the do-while loop
       created in step#2

    4) Apply Case 2.1 algorithm

    """
    #
    # Step 1, introduce new variable and use it for goto conditional
    #
    temp_name = pair.goto_temp_var()
    #
    # Step 2, encapsulate parent block in do-while
    #
    block = get_block(statements, pair.goto_path)
    goto_stmt = block[pair.goto_path[-1]]
    label_block_index = pair.label_path[len(pair.goto_path) - 1]
    stmts = block[label_block_index : pair.goto_path[-1]]
    del block[label_block_index : pair.goto_path[-1]]
    loop_stmt = Loop(
        None, [parse.VariableCondition(temp_name, parse.ConditionEnum.INITIAL)], stmts,
    )
    block.insert(label_block_index, loop_stmt)
    #
    # Step 3, move GOTO to first in loop
    #
    new_goto_index = block.index(goto_stmt)
    del block[new_goto_index]
    stmts.insert(0, goto_stmt)


def move_up_a_block(pair, statements, temp_name, is_after):
    """
    1) If goto is inside a block that is not a loop, statements conditionally execute
       all the statements after the goto statement in the same block, based on
       the inverse condition that is applied on the goto statement. If goto is
       inside a loop, use break to break out of the loop.

    2) Move the goto statement upwards to the parent block (i.e. move the goto
       statement to the next statement after the current block).
    """
    block = get_block(statements, pair.goto_path)
    goto_stmt = block[pair.goto_path[-1]]
    #
    # Step 2, use if-statement, or break out of loop.
    #
    if pair.goto_in_loop():
        block[pair.goto_path[-1]] = (
            parse.If(
                None,
                [parse.VariableCondition(temp_name, parse.ConditionEnum.INITIAL)],
                [Break(None)],
            ),
        )
    else:
        stmts = block[pair.goto_path[-1] + 1 :]
        if len(stmts) > 0:
            del block[pair.goto_path[-1] + 1 :]
            if_stmt = parse.If(
                None,
                parse.invert_conditions(
                    [parse.VariableCondition(temp_name, parse.ConditionEnum.INITIAL)]
                ),
                stmts,
            )
            block[pair.goto_path[-1]] = if_stmt
        else:
            del block[pair.goto_path[-1]]
    #
    # Step 3, move goto up one block
    #
    pair.goto_path = pair.goto_path[:-1]
    pair.goto_path[-1] += 1
    new_block = get_block(statements, pair.goto_path)
    new_block.insert(pair.goto_path[-1], goto_stmt)

    # We need to update the label path if the label occurs after the goto
    if not is_after and len(pair.goto_path) <= len(pair.label_path):
        pair.label_path[len(pair.goto_path) - 1] += 1


def algo_3(pair, statements, is_after):
    """
    The parts of 3.1 algo and 3.2 algo that are equal:

    1) Introduce a new variable to the store the value of the condition that
       is applied on the goto statement and use this new variable as the
       conditional for the goto statement.

    2) Move goto up a block, encapsulating

    3) Repeat steps #2  till the goto statement and label statement end
       up in the same block.
    """
    #
    # Step 1, introduce new variable and use it for goto conditional
    #
    temp_name = pair.goto_temp_var()

    while True:
        move_up_a_block(pair, statements, temp_name, is_after)
        #
        # Step 4, see if we need to do it again, or if algo 1.x can take over
        #
        if pair.label_path[:-1] == pair.goto_path[:-1]:
            break


def algo_3_1__label_in_parent_block__before(pair, statements):
    """
    1 ... 4) Decribed in algo_3()

    5)       Apply Case 1.1 algorithm
    """
    algo_3(pair, statements, False)
    #
    # Step 5, apply algo 1.1
    #
    algo_1_1_same_level_same_block__before(pair, statements)


def algo_3_2__label_in_parent_block__after(pair, statements):
    """
    1 ... 4) Decribed in algo_3()

    5)       Apply Case 1.1 algorithm

    6)       Re-initialize the temporary variable (introduced in step#1) to
             false, just before the statement where label was applied
    """
    algo_3(pair, statements, True)
    path_index = len(pair.goto_path) - 1
    block = get_block(statements, pair.goto_path)
    goto_stmt = block[pair.goto_path[path_index]]
    goto_conds = goto_stmt.conditions
    #
    # Step 5, apply algo 1.2
    #
    algo_1_2_same_level_same_block__after(pair, statements)
    #
    # Step 6, Re-initialize the temporary variable
    #
    if pair.label_in_loop():
        let_stmt = parse.Let(
            None,
            parse.VariableExpression(goto_conds[0].var),
            parse.BooleanExpression(
                [parse.TrueFalseCondition("false", parse.ConditionEnum.INITIAL)]
            ),
        )
        block = get_block(statements, pair.label_path)
        block.insert(pair.label_path[-1], let_stmt)


def algo_4(pair, statements, is_after):
    """
    The parts of 4.1 algo and 4.2 algo that are equal:

    1) Introduce a new variable to the store the value of the condition that
       is applied on the goto statement and use this new variable as the
       conditional for the goto statement.

    2) Move goto up a block, encapsulating

    3) Repeat steps #2  till he goto statement occurs in some parent block
       of the block where the label is contained in
    """
    #
    # Step 1, introduce new variable and use it for goto conditional
    #
    temp_name = pair.goto_temp_var()

    while True:
        move_up_a_block(pair, statements, temp_name, is_after)
        #
        # Step 4, see if we need to do it again, or if algo 2.x can take over
        #
        if pair.classify().startswith("2."):
            break


def algo_4_1__label_in_disjunct__before(pair, statements):
    """
    1 ... 4) Decribed in algo_4()

    5)       Apply Case 2.1 algorithm
    """
    algo_4(pair, statements, False)
    #
    # Step 5, apply algo 2.1
    #
    algo_2_1__goto_in_parent_block__before(pair, statements)


def algo_4_2__label_in_disjunct__after(pair, statements):
    """
    1 ... 4) Decribed in algo_4()

    5)       Apply Case 2.2 algorithm
    """
    algo_4(pair, statements, True)
    #
    # Step 5, apply algo 2.2
    #
    algo_2_2__goto_in_parent_block__after(pair, statements)


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
    cond = parse.TrueFalseCondition("true", parse.ConditionEnum.INITIAL)
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
            label = find_goto(statement.statements, path)
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
            if find_label(target, statement.statements, path):
                path.insert(0, index)
                return True
    return False


def find_pair(statements):
    """
    Find the paths to the next pair of GOTO/label

    A path is the way you need to travel throguh a list of statements to get
    to a statement. An If statement or a Loop statement creates a new block
    and a new possible path.

    So, if we have a program like:

    Index    Label Statement
     [0]      10      IF A>0 THEN
     [0][0]   20        PRINT "Hello"
     [1]      20      LET A=2
     [2]      30      IF A <> 2 THEN
     [2][0]   40        IF A > 0 THEN GOTO 20

    The path of the label '20' is [0, 0] and the path of the GOTO statement is
    [2, 0].
    """
    goto_path = list()
    label = find_goto(statements, goto_path)
    if label is None:
        return None

    label_path = list()
    if not find_label(label, statements, label_path):
        raise Exception("could not find label: %s" % label)

    return GotoLabelPair(statements, goto_path, label_path)


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
