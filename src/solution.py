import argparse
from collections.abc import Iterator
import itertools
import sys
import os

from utils import *  # type: ignore
from shasta import ast_node as AST


def show_step(step: str):
    print("-" * 80)
    print("STEP {step}")
    print("-" * 80)
    print()


##
## Step 1:
##   Parse a script, print its AST, unparse it,
##   and print the unparsed script.
##
## Hint: Use libdash and figure out how to call it
##
## Inspect results by checking AST
##


def step1_parse_script(input_script):
    show_step("1: parsing")

    ast = list(parse_shell_to_asts(input_script))
    print("Script AST, pay attention to the different nodes:")
    print(ast)
    original_code = ast_to_code(walk_ast(ast, visit=lambda node: node))
    print()
    print("Unparsed AST, note syntactic differences with the original script:")
    print(original_code)
    print()
    return ast


##
## Step 2:
##   Use our `walk_ast` visitor to print out every AST node.
##
def step2_walk_print(ast):
    show_step("1: visiting")

    print("Printing the AST through walk")
    walk_ast(ast, visit=print)


##
## Step 3:
##   Unparse the AST back to shell code
##
## Hint: Check the AST class for useful method to unparse
##
## Inspect the syntactic differences of the unparsed and original script
##
def step3_unparse(ast):
    show_step("3: unparsing")

    print("Unparsed AST, note syntactic differences with the original script:")
    unparsed_code = ast_to_code(walk_ast(ast, visit=lambda node: node))
    print(unparsed_code)
    print()
    return unparsed_code


##
## Step 4:
##   Write a feature counter
##
## Inspect by running on multiple scripts
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
                    if cmd_name == "eval":
                        feature_counts["eval"] += 1
                    elif cmd_name == "alias":
                        feature_counts["alias"] += 1
            case _:
                pass
        return node

    return (count_features, feature_counts)


def step4_feature_counter(ast):
    show_step("4: feature counting")

    (counter, counts) = feature_counter()
    walk_ast(ast, visit=counter)
    print("Features:")
    print(
        "\n".join(f"- {feature} : {count}" for feature, count in counts.items()),
        file=sys.stderr,
    )
    print()


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

    impure = False
    def visit(n):
        nonlocal impure
        if impure:
            return

        match n:
            # bare assignments and functions
            case AST.AssignNode() | AST.DefunNode():
                impure = True
            # commands with assignments
            case AST.CommandNode() if len(n.assignments) > 0:
                impure = True
            # assignments in a word expansion
            case AST.VArgChar() if n.fmt == "Assign":
                impure = True
            # backquotes, arithmetic
            case AST.BArgChar() | AST.AArgChar():
                impure = True
            case _:
                pass

    walk_ast_node(node, visit=visit, replace=None)
    return not impure


def get_safe_to_expand_subtrees(ast: Iterator[Parsed]):
    subtrees = []

    # only look at top-level nodes!
    for node, _, _, _ in ast:
        if is_safe_to_expand(node):
            subtrees.append(node)
    return subtrees


def step5_safe_to_expand_subtrees(ast):
    safe_to_expand_subtrees = get_safe_to_expand_subtrees(ast)
    print(f"Safe to expand subtrees:", file=sys.stderr)
    for subtree in safe_to_expand_subtrees:
        print("-", subtree.pretty(), file=sys.stderr)
    print()


##
## Step 6:
##   Write a transformation pass that saves all simple commands
##   and pipelinesreplaces in the AST in separate files, and
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
        idx = next(counter)
        stub_path = os.path.join(stub_dir, f"cat_stub_{idx}")
        with open(stub_path, "w", encoding="utf-8") as handle:
            text = node.pretty() + "\n"
            ## Whatever you do before executing this here is JIT
            ## Goal: JIT expand using sh_expand, and then do sth for safety (if the command is rm run it with try, or if command is rm with first argument don't run it)
            handle.write(text)
        line_number = getattr(node, "line_number", -1)
        return AST.CommandNode(
            assignments=node.assignments if getattr(node, "assignments", None) else [],
            line_number=line_number,
            arguments=[string_to_argchars("cat"), string_to_argchars(stub_path)],
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
    stubbed_ast = walk_ast(ast, replace=replace_with_cat("/tmp"))
    preprocessed_script = ast_to_code(stubbed_ast)
    print("Preprocessed script (just using cat to print commands):")
    print(preprocessed_script)
    print()
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
        with open(stub_path, "w", encoding="utf-8") as handle:
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
    stubbed_ast = walk_ast(
        ast, replace=replace_with_jit("/tmp", jit_script="src/jit_step5.sh")
    )
    preprocessed_script = ast_to_code(stubbed_ast)
    print("JIT-printed script:")
    print(preprocessed_script)
    print()
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
    stubbed_ast = walk_ast(ast, replace=replace_with_jit("/tmp"))
    preprocessed_script = ast_to_code(stubbed_ast)
    print("JIT-expanded script):")
    print(preprocessed_script)
    print()
    return preprocessed_script


## TODOs:
## - (Michael) Decide what to cut for each step and what to provide
## - (Michael) Polish comments
## - (Michael) Come up with hints for steps 6-8
## - (Michael) Make sure that the complete script corresponds to your slides
## - (Michael) Come up with a couple scripts that we can propose to them to run their tool
##


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
    step5_safe_to_expand_subtrees(original_ast)

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
