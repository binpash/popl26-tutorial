import shasta.ast_node as AST
import argparse
import sys
import itertools
import os
import shlex

from ast_helper import *
from feature_counter import feature_counter
import parsing
import pure


def _string_to_argchars(text):
    return [AST.CArgChar(ord(ch)) for ch in text]

def pure_replacer(stub_dir="/tmp"):
    counter = itertools.count()

    def stubber(node):
        idx = next(counter)
        stub_path = os.path.join(stub_dir, f"stub_{idx}")
        with open(stub_path, "w", encoding="utf-8") as handle:
            text = node.pretty() + "\n"
            ## Whatever you do before executing this here is JIT
            ## Goal: JIT expand using sh_expand, and then do sth for safety (if the command is rm run it with try, or if command is rm with first argument don't run it)
            handle.write(text)
        line_number = getattr(node, "line_number", -1)
        return AST.CommandNode(
            line_number=line_number,
            assignments=[
                AST.AssignNode(var="JIT_INPUT", val=_string_to_argchars(stub_path)),
            ],
            arguments=[
                _string_to_argchars("."),
                _string_to_argchars("src/jit.sh"),
            ],
            redir_list=[],
        )
    def replace(node):
        match node:
            case AST.Command() if pure.is_pure(node):
                return stubber(node)
            case _:
                return None

    return replace

def replace_pure_subtrees(ast, stub_dir="/tmp"):
    return walk_ast(ast, replace=pure_replacer(stub_dir))

def command_prepender(prefix_cmd, only_commands=None):
    tokens = shlex.split(prefix_cmd)
    if not tokens:
        return lambda node: None
    prefix_args = [_string_to_argchars(token) for token in tokens]
    only_commands = [cmd for cmd in (only_commands or []) if cmd]

    def _prepend_command_node(node, prefix_args):
        assignments = [walk_ast_node(ass, replace=None) for ass in node.assignments]
        arguments = [walk_ast_node(arg, replace=None) for arg in node.arguments]
        redirs = [walk_ast_node(r, replace=None) for r in node.redir_list]
        return AST.CommandNode(
            arguments=prefix_args + arguments,
            assignments=assignments,
            redir_list=redirs,
            **{k: v for k, v in vars(node).items() if k not in ("arguments", "assignments", "redir_list")}
        )

    def replace(node):
        match node:
            case AST.CommandNode() | AST.Command():
                if only_commands:
                    if not node.arguments:
                        return None
                    cmd_name = AST.string_of_arg(node.arguments[0], quote_mode=AST.UNQUOTED)
                    cmd_name = cmd_name.strip("\"'") # Stripping quotes because sh_expand leaves them in
                    if cmd_name not in only_commands:
                        return None
                return _prepend_command_node(node, prefix_args)
            case _:
                return None

    return replace

def prepend_commands(ast, prefix_cmd, only_commands=None):
    return walk_ast(
        ast,
        replace=command_prepender(prefix_cmd, only_commands=only_commands),
    )




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
    ast = list(parsing.parse_shell_to_asts(input_script))
    print("Script AST, pay attention to the different nodes:")
    print(ast)
    original_code = parsing.ast_to_code(walk_ast(ast, visit=lambda node: node))
    print()
    print("Unparsed AST, pay attention to syntactic differences with the original script:")
    print(original_code)
    print()
    return ast


##  
## Step 2: 
##   Build a generic walk_ast function that can apply a
##   visitor and a transformer function to each node.
##
##   def walk_ast(ast, visit=None, replace=None):
##   
##   It should take three arguments:
##     1. The shasta AST
##     2. An optional visit argument that is a function that will be applied on every node
##     3. An optional replace argument that is a function that can replace a node
##
## Inspect if it works by printing each node (should be the same as print)
##
def step2_walk_print(ast):
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
    print("Unparsed AST, pay attention to syntactic differences with the original script:")
    unparsed_code = parsing.ast_to_code(walk_ast(ast, visit=lambda node: node))
    print(unparsed_code)
    print()
    return unparsed_code

##
## Step 4: 
##   Write a feature counter
##
## Inspect by running on multiple scripts
##
def step4_feature_counter(ast):
    walk_ast(ast, visit=feature_counter())
    print('Features:')
    print('\n'.join(
            f'- {feature} : {count}'
            for feature, count in feature_counter.feature_counts.items()
        ), file=sys.stderr)
    print()


##
## Step 5:
##   Write an analysis that finds all subtrees that are safe to expand
##
## Challenge: Think carefully about what parts of the AST are pure
##
## Run it on multiple scripts
##
def step5_safe_to_expand_subtrees(ast):    
    pure_subtrees = pure.get_pure_subtrees(ast)
    print(f"Safe to expand subtrees:", file=sys.stderr)
    for subtree in pure_subtrees:
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
def step6_preprocess_print(ast):
    ## TODO: (Vagos) Change this to replace with cat instead of JIT
    stubbed_ast = walk_ast(ast, replace=pure_replacer("/tmp"))
    preprocessed_script = parsing.ast_to_code(stubbed_ast)
    print("Preprocessed script:")
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
def step7_preprocess_print(ast):
    ## TODO: (Vagos) Change this to replace with jit_step5.sh
    stubbed_ast = walk_ast(ast, replace=pure_replacer("/tmp"))
    preprocessed_script = parsing.ast_to_code(stubbed_ast)
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
    ## TODO: (Vagos) Make sure this runs the same way as the original script
    stubbed_ast = walk_ast(ast, replace=pure_replacer("/tmp"))
    preprocessed_script = parsing.ast_to_code(stubbed_ast)
    print("JIT-expanded script):")
    print(preprocessed_script)
    print()
    return preprocessed_script


## TODOs:
## - (Vagos) Change name of is_pure to is_safe_to_expand
## - (Vagos) Fix the safe_to_expand to only print safe to expand words
## - (Vagos) Fix preprocessing. When running `python src/analysis.py sh/audit.sh` the if structure is gone completely. Only simple commands and pipelines should be replaced
## - (Vagos) Create a new version of the preprocessing replacer for step 6 that doesn't replace with JIT, but rather replaces with a cat and the saved command file, so essentially it just prints all commands
## - (Vagos) Create a new version of preprocessing replacer for Step 7 that replcaes with jit_step5.sh
## - (Vagos) How are we supposed to run the final script? I get errors for sh_expand
## - (Vagos) Create a mini script that prints something simple with an if-else and add a test that makes sure that the final step8 jit returns the same as the uncompiled script
## - (Michael) Decide what to cut and what to provide
## - (Michael) Polish comments
## - (Michael) Make sure that the complete script corresponds to what you are talking about in the slides
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

    ## Step 7: Preprocess using the JIT
    preprocessed_script = step6_preprocess_print(original_ast)
    with open(f"{input_script}.preprocessed.2", "w", encoding="utf-8") as out_file:
        print(preprocessed_script, file=out_file)

    ## Step 8: Preprocess using the JIT and expand before executing
    preprocessed_script = step6_preprocess_print(original_ast)
    with open(f"{input_script}.preprocessed.3", "w", encoding="utf-8") as out_file:
        print(preprocessed_script, file=out_file)
    print(f"Run {input_script}.preprocessed.3 to inspect it runs the same as the original")

if __name__ == "__main__":
    main()
