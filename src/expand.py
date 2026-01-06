#!/usr/bin/env python3

import argparse
import copy
import os
import sys

import shasta.ast_node as AST

import parsing

import sh_expand.expand as sh_expand


def _env_to_expansion_state(sh_expand):
    variables = {k: [None, v] for k, v in os.environ.items()}
    return sh_expand.ExpansionState(variables)


def _expand_assignments(node, exp_state, sh_expand):
    for assignment in node.assignments:
        try:
            expanded_val = sh_expand.expand_arg(assignment.val, exp_state)
        except (sh_expand.ImpureExpansion, sh_expand.StuckExpansion, sh_expand.Unimplemented) as exc:
            print(f"expand.py: skipping assignment expansion: {exc}", file=sys.stderr)
            continue
        assignment.val = expanded_val
        try:
            value_str = sh_expand.string_of_arg(expanded_val)
        except Exception:
            continue
        exp_state.variables[assignment.var] = [None, value_str]
    return node


def expand_script(input_path, sh_expand):
    ast_with_meta = list(parsing.parse_shell_to_asts(input_path))
    nodes = [node for node, _, _, _ in ast_with_meta]
    exp_state = _env_to_expansion_state(sh_expand)
    expanded_nodes = []
    for node in nodes:
        try:
            node_copy = copy.deepcopy(node)
            if isinstance(node_copy, AST.CommandNode) and node_copy.assignments:
                expanded_nodes.append(
                    _expand_assignments(node_copy, exp_state, sh_expand)
                )
            else:
                expanded_nodes.append(
                    sh_expand.expand_command(node_copy, exp_state)
                )
        except (sh_expand.ImpureExpansion, sh_expand.StuckExpansion, sh_expand.Unimplemented) as exc:
            if isinstance(exc, sh_expand.StuckExpansion):
                print(f"expand.py: skipping expansion: {exc}", file=sys.stderr)
            expanded_nodes.append(node)
    return parsing.ast_to_code(expanded_nodes)


def main():
    parser = argparse.ArgumentParser(description="Expand a shell script using sh-expand")
    parser.add_argument("input_script", help="Path to the input shell script")
    args = parser.parse_args()

    output = expand_script(args.input_script, sh_expand)
    print(output)
    return 0

if __name__ == "__main__":
    main()
