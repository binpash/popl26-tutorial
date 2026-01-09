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
##   Parse a script, print its AST, unparse it,
##   and print the unparsed script.
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
    ast = list(parse_shell_to_asts(input_script))  # REPLACE ast = 'FILL IN A CALL HERE'
    print(ast)

    return ast


##
## Step 2:
##   Use our `walk_ast` visitor to print out every AST node.
##


def step2_walk_print(ast):
    show_step("1: visiting with walk_ast")

    walk_ast(ast, visit=print)  # REPLACE # FILL IN A CALL HERE to `walk_ast` with `print` as the `visit` function


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
    unparsed_code = ast_to_code([node for (node, _, _, _) in ast])  # REPLACE original_code = 'FILL IN A CALL HERE'
    print(unparsed_code)

    return unparsed_code


##
## Step 4:
##   Use our simple feature counter to count different shell scripts.
##
## Find a (POSIX) shell script you use frequently (or pull one from GitHub) and see what features it uses.
##


def feature_counter():
    features = [
        "background",
        "subshell",
        "home_tilde",
        "$((arithmetic))",
        "eval",
        "alias",
        "while",
        "for",
        "case",
        "if",
        "and",
        "or",
        "negate",
        "heredoc_redir",
        "dup_redir",
        "file_redir",
        "$(substitution)",
        "function",
        "assignment",
        "variable_use",
        "pipeline",
        "command",
    ]
    feature_counts = {name: 0 for name in features}

    def count_features(node):
        match node:
            case AST.BackgroundNode():
                feature_counts["background"] += 1
            case AST.PipeNode():
                feature_counts["pipeline"] += 1
                if node.is_background:
                    feature_counts["background"] += 1
            case AST.SubshellNode():
                feature_counts["subshell"] += 1
            case AST.TArgChar():
                feature_counts["home_tilde"] += 1
            case AST.AArgChar():
                feature_counts["$((arithmetic))"] += 1
            case AST.BArgChar():
                feature_counts["$(substitution)"] += 1
            case AST.VArgChar():
                feature_counts["variable_use"] += 1
            case AST.AssignNode():
                feature_counts["assignment"] += 1
            case AST.DefunNode():
                feature_counts["function"] += 1
            case AST.WhileNode():
                feature_counts["while"] += 1
            case AST.ForNode():
                feature_counts["for"] += 1
            case AST.CaseNode():
                feature_counts["case"] += 1
            case AST.IfNode():
                feature_counts["if"] += 1
            case AST.AndNode():
                feature_counts["and"] += 1
            case AST.OrNode():
                feature_counts["or"] += 1
            case AST.NotNode():
                feature_counts["negate"] += 1
            case AST.HeredocRedirNode():
                feature_counts["heredoc_redir"] += 1
            case AST.DupRedirNode():
                feature_counts["dup_redir"] += 1
            case AST.FileRedirNode():
                feature_counts["file_redir"] += 1
            case AST.CommandNode():
                feature_counts["command"] += 1
                if node.arguments:
                    cmd_name = AST.string_of_arg(node.arguments[0])
                    # NB this is conservative---we're detecting static uses of these constructs
                    if cmd_name == "eval":
                        feature_counts["eval"] += 1
                    elif cmd_name == "alias":
                        feature_counts["alias"] += 1
            case _:
                pass
        return node

    return (count_features, feature_counts)


def step4_feature_counter(ast):
    show_step("4: counting shell features")

    (counter, counts) = feature_counter()
    walk_ast(ast, visit=counter)  # REPLACE # FILL IN HERE WITH CALL to `walk_ast` with the `counter` as `visit`
    for (feature, count) in (counts.items()):  # REPLACE # FILL IN HERE WITH LOOP to print out the features (HINT: use the `dict.items` method)
        print(f"- {feature}: {count}")  # REMOVE

##
## Step 5:
##   Write an analysis that finds all subtrees that are safe to expand
##
## Challenge: Think carefully about what parts of the AST are pure
##
## Run it on multiple scripts
##


def is_safe_to_expand(node):
    if node is None:
        return True

    safe = True

    def check_for_effects(n):
        nonlocal safe
        if not safe:
            return

        match n:
            # bare assignments affect state; functions can't be safely expanded in advance
            case AST.AssignNode() | AST.DefunNode():
                safe = False
            # commands with assignments affect state
            # this underapproximates---special builtins like `export` and `set` can affect shell state, too!
            case AST.CommandNode() if len(n.assignments) > 0:
                safe = False
            # assignments in a word expansion
            case AST.VArgChar() if n.fmt == "Assign":
                safe = False
            # backquotes, arithmetic
            case AST.BArgChar() | AST.AArgChar():
                safe = False
            case _:
                pass

    walk_ast_node(node, visit=check_for_effects)
    return safe


def step5_safe_to_toplevel_commands(ast):
    show_step("5: safe-to-expand top-level commands")

    safe = []
    # only look at top-level nodes!
    for node, _, _, _ in ast:
        if is_safe_to_expand(node): # REPLACE pass # FILL IN HERE WITH conditional printing of `is_safe_to_expand` nodes
            print(f"- {node.pretty()}") # REMOVE


##
## Step 6:
##   Write a transformation pass that saves all simple commands
##   and pipelines, saving the AST in separate files, and
##   replaces them with calls to `cat` and that file instead of
##   running them
##
## TODO: Add hints, this is hard
##
## Inspect by running the transformed script and seeing if all the
## commands are printed properly
##


def replace_with_cat(stub_dir="/tmp"):
    counter = itertools.count()

    def stubber(node):
        # our stubs have two parts
        #
        #   - a file `.../cat_stub_IDX` where we hold the code we would have executed
        #   - the new line of code we'll execute (here, `cat`ing the code in the stub file)

        # stub file name
        idx = next(counter)
        stub_path = os.path.join(stub_dir, f"cat_stub_{idx}")

        # generate stub file
        with open(stub_path, "w", encoding="utf-8") as handle:
            text = node.pretty() + "\n"
            # Whatever code you write here is executed _at run time_
            # We'll just write out the line we would have executed
            handle.write(text)

        # replacement command
        line_number = getattr(node, "line_number", -1)
        return AST.CommandNode(
            assignments=node.assignments if getattr(node, "assignments", None) else [],
            line_number=line_number,
            arguments=[string_to_argchars("cat"), string_to_argchars(stub_path)], # REPLACE arguments=[] # FILL IN HERE WITH a call to `cat` on the `stub_path`
            redir_list=[],
        )

    def replace(node):
        match node:
            case AST.Command() if is_safe_to_expand(node):
                return stubber(node)
            case _:
                return None

    return replace


def step6_preprocess_print(ast):
    show_step("6: preprocess script to print commands")

    stubbed_ast = walk_ast(ast, replace=replace_with_cat("/tmp"))
    preprocessed_script = ast_to_code(stubbed_ast)
    print(preprocessed_script)

    return preprocessed_script


##
## Step 7:
##   Create a JIT script that saves the shell state, prints out
##   the command that it will run, and then restores the state and runs it
##   Use the preprocessing that you built before to replace all
##   simple commands and pipelines with this JIT
##
## TODO: Hints
##
## Inspect by running the transformed script and seeing if it runs properly
##


def replace_with_jit(stub_dir="/tmp", jit_script="src/jit.sh"):
    counter = itertools.count()

    def stubber(node):
        idx = next(counter)
        stub_path = os.path.join(stub_dir, f"stub_{idx}")
        with open(
            stub_path, "w", encoding="utf-8"
        ) as handle:  # we write this as text... but better to store the pickled AST!
            text = node.pretty() + "\n"
            handle.write(text)
        line_number = getattr(node, "line_number", -1)
        return AST.CommandNode(
            line_number=line_number,
            assignments=[
                *(
                    node.assignments if getattr(node, "assignments", None) else []
                ),  # Keep original assigments
                AST.AssignNode(var="JIT_INPUT", val=string_to_argchars(stub_path)),
            ],
            arguments=[
                string_to_argchars("."),
                string_to_argchars(jit_script),
            ],
            redir_list=[],
        )

    def replace(node):
        match node:
            case AST.Command() if is_safe_to_expand(node):
                return stubber(node)
            case _:
                return None

    return replace


def step7_preprocess_print(ast):
    show_step("7: JIT stubs for debugging")

    stubbed_ast = walk_ast(ast, replace=replace_with_jit("/tmp", jit_script="src/debug_jit.sh"))
    preprocessed_script = ast_to_code(stubbed_ast)
    print(preprocessed_script)

    return preprocessed_script


##
## Step 8:
##   Modify the JIT script to first expand the simple command or pipeline
##   then print out this expanded command, and then run it
##
## TODO: Hints
##
## Inspect by running the transformed script and seeing if it returns the same results
## as the original one
##
def step8_preprocess_print(ast):
    show_step("8: JIT expansion")

    stubbed_ast = walk_ast(ast, replace=replace_with_jit("/tmp"))
    preprocessed_script = ast_to_code(stubbed_ast)
    print(preprocessed_script)

    return preprocessed_script


## TODOs:
## - (Michael) Decide what to cut for each step and what to provide
## - (Michael) Come up with hints for steps 6-8
## - (Michael) Make sure that the complete script corresponds to your slides
## - (Michael) Come up with a couple scripts that we can propose to them to run their tool


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
    step2_walk_print(original_ast)

    ## Step 3: Unparse
    unparsed_code = step3_unparse(original_ast)

    ## Step 4: Feature counter
    step4_feature_counter(original_ast)

    ## Step 5: Safe to expand subtrees
    step5_safe_to_toplevel_commands(original_ast)

    ## Part 2

    ## Step 6: Preprocess and print each command
    preprocessed_script = step6_preprocess_print(original_ast)
    with open(f"{input_script}.preprocessed.1", "w", encoding="utf-8") as out_file:
        print(preprocessed_script, file=out_file)
    print(
        f"Run {input_script}.preprocessed.1 and inspect whether it returns the commands {input_script} would run"
    )
    print()

    ## Step 7: Preprocess using the JIT
    preprocessed_script = step7_preprocess_print(original_ast)
    with open(f"{input_script}.preprocessed.2", "w", encoding="utf-8") as out_file:
        print(preprocessed_script, file=out_file)

    ## Step 8: Preprocess using the JIT and expand before executing
    preprocessed_script = step8_preprocess_print(original_ast)
    with open(f"{input_script}.preprocessed.3", "w", encoding="utf-8") as out_file:
        print(preprocessed_script, file=out_file)
    print(
        f"Run {input_script}.preprocessed.3 and confirm it produces the same output as {input_script}"
    )


if __name__ == "__main__":
    main()
