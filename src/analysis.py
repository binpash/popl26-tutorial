import shasta.ast_node as AST
import argparse
import sys
import os
import shlex

from ast_helper import *
from feature_counter import feature_counter
import parsing
import preprocess
import pure



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
    safe_to_expand_subtrees = pure.get_safe_to_expand_subtrees(ast)
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
def step6_preprocess_print(ast):
    stubbed_ast = walk_ast(ast, replace=preprocess.replace_with_cat("/tmp"))
    preprocessed_script = parsing.ast_to_code(stubbed_ast)
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
def step7_preprocess_print(ast):
    stubbed_ast = walk_ast(ast, replace=preprocess.replace_with_jit("/tmp", jit_script="src/jit_step5.sh"))
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
    stubbed_ast = walk_ast(ast, replace=preprocess.replace_with_jit("/tmp"))
    preprocessed_script = parsing.ast_to_code(stubbed_ast)
    print("JIT-expanded script):")
    print(preprocessed_script)
    print()
    return preprocessed_script


## TODOs:
## - (Michael) Decide what to cut for each step and what to provide
## - (Michael) Polish comments
## - (Michael) Come up with hints for steps 6-8
## - (Michael) Make sure that the complete script corresponds to your slides
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
    print(f"Run {input_script}.preprocessed.1 and inspect whether it returns the commands {input_script} would run")
    print()

    ## Step 7: Preprocess using the JIT
    preprocessed_script = step7_preprocess_print(original_ast)
    with open(f"{input_script}.preprocessed.2", "w", encoding="utf-8") as out_file:
        print(preprocessed_script, file=out_file)

    ## Step 8: Preprocess using the JIT and expand before executing
    preprocessed_script = step8_preprocess_print(original_ast)
    with open(f"{input_script}.preprocessed.3", "w", encoding="utf-8") as out_file:
        print(preprocessed_script, file=out_file)
    print(f"Run {input_script}.preprocessed.3 and confirm it produces the same output as {input_script}")

if __name__ == "__main__":
    main()
