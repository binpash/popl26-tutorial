#!/usr/bin/env python3

import argparse
from copy import deepcopy
import os
import shlex
import sys

from utils import *  # type: ignore
from shasta import ast_node as AST
import sh_expand.expand as sh_expand


def command_prepender(prefix_cmd, only_commands=None):
    tokens = shlex.split(prefix_cmd)
    if not tokens:
        return lambda node: None
    prefix_args = [string_to_argchars(token) for token in tokens]
    only_commands = [cmd for cmd in (only_commands or []) if cmd]

    def _prepend_command_node(node, prefix_args):
        assignments = [walk_ast_node(ass, replace=None) for ass in node.assignments]
        arguments = [walk_ast_node(arg, replace=None) for arg in node.arguments]
        redirs = [walk_ast_node(r, replace=None) for r in node.redir_list]
        return AST.CommandNode(
            arguments=prefix_args + arguments,
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
            case AST.CommandNode() | AST.Command():
                if only_commands:
                    if not hasattr(node, "arguments"):
                        return None
                    cmd_name = AST.string_of_arg(node.arguments[0], quote_mode=AST.UNQUOTED)  # type: ignore
                    cmd_name = cmd_name.strip(
                        "\"'"
                    )  # Stripping quotes because sh_expand leaves them in
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


def _env_to_expansion_state(sh_expand):
    variables = {k: [None, v] for k, v in os.environ.items()}
    # Treat unset variables as errors so we can fall back to the original node. Otherwise, sh-expand treats unset variables as empty strings.
    variables["-"] = [None, "u"]
    for key, value in os.environ.items():
        if key.startswith("JIT_POS_"):
            suffix = key[len("JIT_POS_") :]
            if suffix.isdigit():
                variables[suffix] = [None, value]
    return sh_expand.ExpansionState(variables)


def main():
    parser = argparse.ArgumentParser(
        description="Expand a shell script using sh-expand"
    )
    parser.add_argument("input_script", help="Path to the input shell script")
    args = parser.parse_args()

    # reparse the stub
    # if we had pickled the AST, we could just unpickle it here
    ast = list(parse_shell_to_asts(args.input_script))
    exp_state = _env_to_expansion_state(sh_expand)
    expanded_ast = []
    for (node, orig, start, end) in ast:
        try:
            node_copy = deepcopy(node)  # sh_expand works in-place
            expanded_ast.append((sh_expand.expand_command(node_copy, exp_state), orig, start, end))
        except (
            sh_expand.ImpureExpansion,
            sh_expand.StuckExpansion,
            sh_expand.Unimplemented,
        ) as exc:
            if isinstance(exc, sh_expand.StuckExpansion):
                print(f"expand.py: skipping expansion: {exc}", file=sys.stderr)
            expanded_ast.append((node, orig, start, end))

    # Transformations on the expanded AST
    transformed_expanded_ast = prepend_commands(expanded_ast, "try", only_commands=["rm"])

    print(ast_to_code(transformed_expanded_ast))

if __name__ == "__main__":
    main()
