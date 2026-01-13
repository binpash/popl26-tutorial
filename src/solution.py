#!/usr/bin/env python3

import argparse
from collections.abc import Iterator
import itertools
import sys
import os

from utils import *  # type: ignore
from shasta import ast_node as AST


def show_step(step: str, initial_blank=True):
    if initial_blank:
        print()
    print("-" * 80)
    print(f"STEP {step}")
    print("-" * 80)
    print()


##
## Step 1:
##   Parse a script and print its AST.
##
## You need `utils.parse_shell_to_asts` to parse the shell scripts.
##
## Note the structure of the `Parsed` type is a 4-tuple, comprising:
##   - the actual AST
##   - the original parsed text
##   - the starting line number
##   - the ending line number
##
## Look closely at the output to see the various node names.
##


def step1_parse_script(input_script):
    show_step(
        "1: parsing and printing the `Parsed` representation", initial_blank=False
    )

    # set ast to a list of parsed commands using `parse_shell_to_asts`
    ast = 'FILL IN A CALL HERE'
    print(ast)

    return ast


##
## Step 2:
##   Use our `walk_ast` visitor to print out every AST node.
##


def step2_walk_print(ast):
    show_step("2: visiting with walk_ast")

    # look in `utils.py` for more code for you to write!
    # FILL IN A CALL HERE to `walk_ast` with `print` as the `visit` function


##
## Step 3:
##   Unparse the AST back to shell code
##
## You need `utils.ast_to_code` to unparse the AST.
## You can either call `walk_ast` with an identity visitor or use a comprehension to pull out the parsed AST.
##
## Also note the unparsed AST for its syntactic differences.
##
## Bonus exercise: can you write a script that unparses significantly differently,
##                 beyond just whitespace?
##
## Inspect the syntactic differences of the unparsed and original script
##
def step3_unparse(ast):
    show_step("3: unparse using `ast_to_code`")

    # convert the AST back using `ast_to_code`
    unparsed_code = 'FILL IN A CALL HERE'
    print(unparsed_code)

    return unparsed_code


##
## Step 4:
##   Create a simple analysis that returns the number of subshells a script will create:
##   Four ways to create a subshell:
##   - Asynchronous commands `&`
##   - Pipes `|`
##   - Subshells `(...)`
##   - Command Substitution `$(...)`
##
## Find a (POSIX) shell script you use frequently (or pull one from binpash/koala) and see how many it creates.
##

class Counter:
    def __init__(self):
        self.cnt = 0

    def add(self, n):
        self.cnt += n

    def get(self):
        return self.cnt

def step4_subshells(ast):
    show_step("4: counting shell features")

    subshells = Counter()

    # FILL IN HERE WITH CALL to `walk_ast` that counts subshells
    count = subshells.get()
    print("Number of subshells in script:", count)
    return count

##
## Step 5:
##   Identify top-level commands that are effect-free
##
## We say a top-level command is effect-free if executing the command doesn't have side-effects on the shell state.
##
## We'll confine our notion of "shell state" to the variables in the shell, so a top-level command is effect free
## when it does not set or change the values of variables. We can approximate this with the following syntactic restriction:
##
##   - It has no function definitions.
##   - Commands have no assignments in them. (`VAR=VAL cmd` usually won't affect the environment---unless `cmd` is a special builtin, like `set`.)
##   - The `${VAR=WORD}` and `${VAR:=WORD}` parameter formats are never used.
##   - There are no arithmetic expansions.
##
## Tip: if you're not sure what AST nodes correspond to a shell feature, create a custom file with just the code you're interested
## in, and then print the AST (unprettily).
##
##
## This list is not entirely sound---special builtins like `export` and `set` can affect shell state, as can `.` and `eval`.
## But it's a good start, and let's not get bogged down.


def is_effect_free(node):
    if node is None:
        return True

    safe = True
    def check_for_effects(n):
        nonlocal safe
        if not safe:
            return

        # FILL IN HERE with the checks described in the comment above (use a match!)

    walk_ast_node(node, visit=check_for_effects)
    return safe


def step5_effect_free(ast):
    show_step("5: safe-to-expand top-level commands")

    safe = []
    # only look at top-level nodes!
    for node, _, _, _ in ast:
        if is_effect_free(node):
            print(f"- {node.pretty()}")


##
## Step 6:
##   Next, we'll implement a hybrid `set -x` mode, which runs effectful commands but not
##   effect-free ones. (We want to leave in effectful commands so we have variable values.)
##
##   To do this, we'll preprocess the script to stub out effect-free commands.
##   We'll write the command we _would_ have run to a file, and we'll change the script to
##   simply `cat` that stub (rather than running the command).
##
## There are a few moving parts here:
##
##   - We have to walk the AST and find effect free nodes.
##   - We need to save those nodes as text in a known place.
##   - We have to alter the AST to instead cat those saved nodes.
##
## We can do all this using `walk_ast`, `is_effect_free` and a bit of care.
##


def replace_with_cat(stub_dir="/tmp"):
    counter = itertools.count()

    def replace(node: AST.AstNode):
        match node:
            case AST.Command() if is_effect_free(node):
                # our stubs have two parts
                #
                #   - a file `.../cat_stub_IDX` where we hold the code we would have executed
                #   - the new line of code we'll execute (here, `cat`ing the code in the stub file)

                # stub file name
                idx = next(counter)
                stub_path = os.path.join(stub_dir, f"cat_stub_{idx}")

                # generate stub file
                with open(stub_path, "w", encoding="utf-8") as handle:
                    # Whatever code you write here is catted out _at run time_
                    # We'll just write out the line we would have executed
                    handle.write("FILL IN HERE with the text of the script being replaced")
                    handle.write("\n")

                # replacement command
                # return # FILL IN HERE with a `CommandNode` that will `cat` the file at `stub_path` (hint: checkout `string_to_argchars`)

            case _:
                return None

    return replace

def step6_stubs(ast):
    show_step("6: preprocess script to print commands")

    stubbed_ast = walk_ast(ast, replace=replace_with_cat("/tmp"))
    preprocessed_script = ast_to_code(stubbed_ast)
    print(preprocessed_script)

    return preprocessed_script


##
## Step 7:
##   Moving from stubs to JIT interposition is a matter of writing a more complex
##   script as the stub. In general, we want a single such script, which will take
##   stub information as input.
##
##  We've given you such a script in `debug_jit.sh`. It:
##
##    1. Prints out the command that would run on stderr, prepended with `+` like
##       when running `set -x` in the shell
##    2. Actually runs the command
##
##  Notice that we don't do any real processing, so we don't need to save or restore
##  shell state. We try to clean up after ourselves as best as possible, but we do
##  step on the $__cmd_status variable.
##
## Once you've filled in the code, test it out to ensure that the program runs the same!

def replace_with_debug_jit(stub_dir="/tmp"):
    counter = itertools.count()

    def replace(node: AST.AstNode):
        match node:
            case AST.Command() if is_effect_free(node):
                idx = next(counter)
                stub_path = os.path.join(stub_dir, f"debug_stub_{idx}")

                with open(stub_path, "w", encoding="utf-8") as handle:
                    # we write this as text... but it's much better to store the pickled AST!
                    handle.write(node.pretty())
                    handle.write("\n")

                # we want to run the command `JIT_INPUT=PATH_TO_STUB . PATH_TO_JIT_SCRIPT`
                return AST.CommandNode(
                    line_number = getattr(node, "line_number", -1),
                    assignments = [ # no original assignments (safe to expand!)
                        # FILL IN HERE WITH an assignment of `JIT_INPUT` to the `stub_path` (hint: you need to build an `AssignNode`; use `string_of_argchars`)
                    ],
                    arguments   = [], # FILL IN HERE WITH sourcing (via `.`) the `src/debug_jit.sh` JIT script (hint: use `string_of_argchars`)
                    redir_list  = [],
                )
            case _:
                return None

    return replace


def step7_debug_jit(ast):
    show_step("7: JIT stubs for debugging")

    stubbed_ast = walk_ast(ast, replace=replace_with_debug_jit("/tmp"))
    preprocessed_script = ast_to_code(stubbed_ast)
    print(preprocessed_script)

    return preprocessed_script


##
## Step 8:
##   With the JIT framework in place, we can write a more realistic JIT that
##   does more interposition by actually manipulating the script at runtime.
##
## We'll try to expand command-lines with our own code, just in time. JIT
## expansion is a key ingredient in PaSh's optimization pipeline. We don't have
## time to show the optimization pipeline, so we'll show this part.
##
## There are a few key mechanisms here:
##
##   1. `jit.sh` can capture the shell state to
##      a. hand it off to be expanded
##      b. be restored at the end
##   2. `expand.py` is the JIT expander, that reads stubbed scripts and
##      writes out expanded versions
##
## Inspect by running the transformed script and seeing if it returns the same results
## as the original one
##

def replace_with_jit(stub_dir="/tmp"):
    counter = itertools.count()

    def replace(node: AST.AstNode):
        match node:
            case AST.CommandNode():
                idx = next(counter)
                stub_path = os.path.join(stub_dir, f"stub_{idx}")

                with open(stub_path, "w", encoding="utf-8") as handle:
                    # we write this as text... but it's much better to store the pickled AST!
                    handle.write(node.pretty())
                    handle.write("\n")

                # we want to run the command `JIT_INPUT=PATH_TO_STUB . PATH_TO_JIT_SCRIPT`
                return AST.CommandNode(
                    line_number = getattr(node, "line_number", -1),
                    assignments = [ # no original assignments (safe to expand!)
                        AST.AssignNode(var="JIT_INPUT", val=string_to_argchars(stub_path)),
                    ],
                    arguments   = [string_to_argchars("."), string_to_argchars("src/jit.sh"),],
                    redir_list  = [],
                )
            case _:
                return None

    return replace

def step8_try_unsafe(ast):
    show_step("8: JIT expansion")

    stubbed_ast = walk_ast(ast, replace=replace_with_jit(stub_dir = "/tmp"))
    preprocessed_script = ast_to_code(stubbed_ast)
    print(preprocessed_script)

    return preprocessed_script

def main():
    arg_parser = argparse.ArgumentParser(
        description=f"Transform a shell script and outputs the modified script"
    )
    arg_parser.add_argument(
        "input_script",
        type=str,
        help="Path to the input shell script",
    )
    args = arg_parser.parse_args()
    input_script = args.input_script

    ## Step 1: Parse/unparse
    original_ast = step1_parse_script(input_script)

    ## Step 2: Walk and print
    # Uncomment when you get to step 2
    # step2_walk_print(original_ast)

    ## Step 3: Unparse
    # Uncomment when you get to step 3
    # step3_unparse(original_ast)

    ## Step 4: Feature counter
    # Uncomment when you get to step 4
    # step4_subshells(original_ast)

    # Uncomment when you get to step 4
    # subshell_test = step1_parse_script("sh/subshells.sh")
    # subshell_count = step4_subshells(subshell_test)
    # assert subshell_count in [4, 5], "subshell counting is not correct"

    ## Step 5: Safe to expand subtrees

    # tests for is_effect_free
    # Uncomment when you get to step 5
    # ef_test = step1_parse_script("sh/effectful.sh")
    # for (node, _, _, _) in ef_test:
        # pretty = node.pretty()
        # safe = is_effect_free(node)
        # assert safe == ("I am not effectful" in pretty)
    # print("🎉 CONGRATULATIONS! YOU WROTE YOUR FIRST SHELL ANALYSIS!!!!! 🎉")

    # step5_effect_free(original_ast)

    ## Part 2

    ## Step 6: Preprocess and print each command
    # Uncomment when you get to step 6
    # preprocessed_script = step6_stubs(original_ast)
    # with open(f"{input_script}.preprocessed.1", "w", encoding="utf-8") as out_file:
        # print(preprocessed_script, file=out_file)

    ## Step 7: Preprocess using the JIT
    # Uncomment when you get to step 7
    # preprocessed_script = step7_debug_jit(original_ast)
    # with open(f"{input_script}.preprocessed.2", "w", encoding="utf-8") as out_file:
        # print(preprocessed_script, file=out_file)

    ## Step 8: Preprocess using the JIT and expand before executing
    # Uncomment when you get to step 8
    # preprocessed_script = step8_try_unsafe(original_ast)
    # with open(f"{input_script}.safe", "w", encoding="utf-8") as out_file:
        # print(preprocessed_script, file=out_file)
    # print()
    # print(f"The transformed safer to run script is stored in: {input_script}.safe")
    # print()


if __name__ == "__main__":
    main()
