import shasta.ast_node as AST
import argparse
import sys
import itertools
import os
import shlex

from ast_helper import *
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
            case AST.CommandNode():
                if only_commands:
                    if not node.arguments:
                        return None
                    cmd_name = AST.string_of_arg(node.arguments[0])
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
    # Weird way to do this, but avoids global variable/reset logic
    feature_counter.feature_counts = feature_counts

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

    return count_features







##
## Step 1: 
## Parse a script, print its AST, unparse it,
## and print the unparsed script.        
##
def step1_parse_unparse_script(input_script):
    ast = list(parsing.parse_shell_to_asts(input_script))
    print("Script AST, pay attention to the different nodes:")
    print(ast)
    original_code = parsing.ast_to_code(walk_ast(ast, visit=lambda node: node))
    print()
    print("Unparsed AST, pay attention to syntactic differences with the original script:")
    print(original_code)
    print()
    return ast

## New proposed exercise steps for the first half:
## Step 1: 
##   Parse script
##   Hint: Use libdash and figure out how to call it
##   Inspect results by checking AST
##  
## Step 2: 
##   Build a generic walk_ast function (provide signature) 
##   Inspect if it works by printing each node (should be the same as print)
##
## Step 3: 
##   Unparse (trivial application of walk_ast)
##   Hint: Check the AST class for useful method
##   Inspect the syntactic differences of
##
## Step 4: 
##   Write a feature counter
##   Run it on multiple scripts and inspect differences
##
## Step 5:
##   Write an analysis that finds all subtrees that are safe to expand
##   Challenge: Think carefully about what parts of the AST are pure
##   Run it on multiple scripts

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
    original_ast = step1_parse_unparse_script(input_script)

    walk_ast(original_ast, visit=feature_counter())
    print('Features:')
    print('\n'.join(
            f'- {feature} : {count}'
            for feature, count in feature_counter.feature_counts.items()
        ), file=sys.stderr)
    print()

    
    pure_subtrees = pure.get_pure_subtrees(original_ast)
    print(f"Pure subtrees:", file=sys.stderr)
    for subtree in pure_subtrees:
        print("-", subtree.pretty(), file=sys.stderr)
    print()

    stubbed_ast = walk_ast(original_ast, replace=pure_replacer("/tmp"))
    compiled_file = open("/tmp/stubbed_output.sh", "w", encoding="utf-8")
    print(parsing.ast_to_code(stubbed_ast), file=compiled_file)
    compiled_file.close()

    prepended_ast = prepend_commands(original_ast, "try")
    print(parsing.ast_to_code(prepended_ast))

    prepended_rm_ast = prepend_commands(original_ast, "try", only_commands=["rm"])
    print(parsing.ast_to_code(prepended_rm_ast))

if __name__ == "__main__":
    main()
