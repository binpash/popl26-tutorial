#!/usr/bin/env python3

import argparse
from copy import deepcopy
import os
import shlex
import sys

from utils import *  # type: ignore
from shasta import ast_node as AST
import sh_expand.expand as sh_expand


def command_prepender(exp_state: sh_expand.ExpansionState, prefix_cmd: str, unsafe_commands=None):
    tokens = shlex.split(prefix_cmd)
    if not tokens:
        return lambda node: None
    prefix_args: list[list[AST.ArgChar]] = [string_to_argchars(token) for token in tokens]
    unsafe_commands = list(unsafe_commands or [])

    def _prepend_command_node(node: AST.CommandNode, prefix_args: list[list[AST.ArgChar]]):
        assignments = [walk_ast_node(ass, replace=None) for ass in node.assignments]
        arguments = [walk_ast_node(arg, replace=None) for arg in node.arguments]
        redirs = [walk_ast_node(r, replace=None) for r in node.redir_list]
        return AST.CommandNode(
            arguments=prefix_args + arguments if len(arguments) > 0 else [],
            assignments=assignments,
            redir_list=redirs,
            **{
                k: v
                for k, v in vars(node).items()
                if k not in ("arguments", "assignments", "redir_list")
            },
        )

    def replace(node):
        match node:
            case AST.CommandNode() if len(node.arguments) > 0:
                if unsafe_commands:
                    # expansion mutates!
                    node = deepcopy(node)
                    try:
                        sh_expand.expand_command(node, exp_state)

                        cmd_name = AST.string_of_arg(node.arguments[0], quote_mode=AST.UNQUOTED)  # type: ignore
                        cmd_name = cmd_name.strip("\"'")  # stripping quotes because sh_expand leaves them in
                        print(f"!!! {node.pretty()} has command {cmd_name}", file=sys.stderr)

                        # is it a known-safe command?
                        if cmd_name not in unsafe_commands:
                            return None
                    except (sh_expand.ImpureExpansion, sh_expand.StuckExpansion, sh_expand.Unimplemented,) as exc:
                        print(f"!!! {exc} for {node.pretty()}", file=sys.stderr)
                        print(f"!!! {exp_state.variables.keys()}", file=sys.stderr)

                        pass

                print(f"!!! prepending try to {node.pretty()}", file=sys.stderr)
                prepended = _prepend_command_node(node, prefix_args)
                return prepended
            case _:
                return None

    return replace


def prepend_commands(ast: list[Parsed], exp_state: sh_expand.ExpansionState, prefix_cmd: str, unsafe_commands=None):
    return walk_ast(
        ast,
        replace=command_prepender(exp_state, prefix_cmd, unsafe_commands=unsafe_commands),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Expand a shell script using sh-expand"
    )
    parser.add_argument("input_script", help="Path to the input shell script")
    args = parser.parse_args()

    # reparse the stub
    # if we had pickled the AST, we could just unpickle it here
    ast = list(parse_shell_to_asts(args.input_script))

    # turn the environment into expansion state
    print(os.environ, file=sys.stderr)
    variables = {k: [None, v] for k, v in os.environ.items()}
    for key, value in os.environ.items():
        if key.startswith("JIT_POS_"):
            suffix = key[len("JIT_POS_") :]
            if suffix.isdigit():
                variables[suffix] = [None, value]
    exp_state = sh_expand.ExpansionState(variables)

    # Transformations on the expanded AST
    transformed_ast = prepend_commands(ast, exp_state, "try", unsafe_commands=["rm"])

    print(ast_to_code(transformed_ast))

if __name__ == "__main__":
    main()
