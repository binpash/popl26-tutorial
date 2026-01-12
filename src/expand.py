#!/usr/bin/env python3

import argparse
from copy import deepcopy
import os
import re
import shlex
import sys

from utils import *  # type: ignore
from shasta import ast_node as AST
import sh_expand.expand as expand
from sh_expand.env_vars_util import read_vars_file

def string_of_expanded_arg(arg: list[AST.ArgChar]):
    """
    Stringifies a fully expanded argument

    :param arg: The arg to expand
    :type arg: list[AST.ArgChar]
    """
    s = AST.string_of_arg(arg, quote_mode=AST.UNQUOTED)
    return s.strip("\"'") # stripping quotes because sh_expand leaves them in

def command_prepender(exp_state: expand.ExpansionState, unsafe_commands=None):
    try_prefix_args = [string_to_argchars("try")] # REMOVE
    unsafe_commands = list(unsafe_commands or [])

    def replace(node):
        match node:
            case AST.CommandNode() if len(node.arguments) > 0:
                # expansion mutates!
                # node = deepcopy(node) # UNCOMMENT when you start working on the optimization

                try:
                    # If we can expand the command and know for sure that we won't be invoking
                    # a command in our `unsafe_commands` list, then we don't need to prepend `try`.
                    #
                    # You can expand the command with `expand.expand_command`.
                    #
                    # You can get the command name by using `string_of_expanded_arg`.
                    #
                    # Only fill in this part once you have the rest of the JIT working.
                    #
                    expand.expand_command(node, exp_state) # REPLACE pass # FILL IN OPTIMIZATION HERE
# REMOVE
                    cmd_name = string_of_expanded_arg(node.arguments[0]) # REMOVE
                    # is it a known-safe command? # REMOVE
                    if cmd_name not in unsafe_commands: # REMOVE
                        return None # REMOVE
                except (expand.ImpureExpansion, expand.StuckExpansion, expand.Unimplemented,) as exc:
                    # if expansion fails, we should be conservative and prepend
                    pass

                print(f"!!! prepending try to {node.pretty()}", file=sys.stderr)
                # When prepending with `try`, we have to be careful: a plain assignment will be a `CommandNode`
                # with no arguments at all. In that case, we don't want to add a `try`!
                #
                # Hint: don't forget `string_to_argchars`
                return AST.CommandNode( # REPLACE # return # FILL IN HERE with a new `CommandNode` that prepends the command with `try`
                        arguments=try_prefix_args + node.arguments if len(node.arguments) > 0 else [], # REMOVE
                        assignments=node.assignments, # REMOVE
                        redir_list=node.redir_list, # REMOVE
                        line_number=node.line_number # REMOVE
                       ) # REMOVE
            case _:
                return None

    return replace


def prepend_try_to_commands(ast: list[Parsed], exp_state: expand.ExpansionState, unsafe_commands=None):
    return walk_ast(
        ast,
        replace=command_prepender(exp_state, unsafe_commands=unsafe_commands),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Expand a shell script using sh-expand"
    )
    parser.add_argument("input_script", help="Path to the input shell script")
    parser.add_argument("bash_version", help="The version of bash used to capture the environment in the JIT")
    args = parser.parse_args()

    # reparse the stub
    # if we had pickled the AST, we could just unpickle it here
    ast = list(parse_shell_to_asts(args.input_script))

    # load the environment
    m = re.match(r"(\d+)\.(\d+)\.(\d+)", args.bash_version)
    assert m is not None, f"must be running in bash (BASH_VERSION={args.bash_version})"
    variables = read_vars_file(args.input_script + ".env", (int(m.group(1)), int(m.group(2)), int(m.group(3))))
    assert variables is not None, "could not parse environment variables"
    exp_state = expand.ExpansionState(variables)

    # Transformations on the expanded AST
    transformed_ast = prepend_try_to_commands(ast, exp_state, unsafe_commands=["rm"])

    print(ast_to_code(transformed_ast))

if __name__ == "__main__":
    main()
