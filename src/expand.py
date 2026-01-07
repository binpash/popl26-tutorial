#!/usr/bin/env python3

import argparse
import copy
import os
import sys

import sh_expand.expand as sh_expand

import parsing
import analysis


def _env_to_expansion_state(sh_expand):
    variables = {k: [None, v] for k, v in os.environ.items()}
    # Treat unset variables as errors so we can fall back to the original node. Otherwise, sh-expand treats unset variables as empty strings.
    variables["-"] = [None, "u"]
    for key, value in os.environ.items():
        if key.startswith("JIT_POS_"):
            suffix = key[len("JIT_POS_"):]
            if suffix.isdigit():
                variables[suffix] = [None, value]
    return sh_expand.ExpansionState(variables)

def expand_script(input_path, sh_expand):
    ast_with_meta = list(parsing.parse_shell_to_asts(input_path))
    nodes = [node for node, _, _, _ in ast_with_meta]
    exp_state = _env_to_expansion_state(sh_expand)
    expanded_ast = []
    for node in nodes:
        try:
            node_copy = copy.deepcopy(node) # We apply the expansions in-place
            expanded_ast.append(
                sh_expand.expand_command(node_copy, exp_state)
            )
        except (sh_expand.ImpureExpansion, sh_expand.StuckExpansion, sh_expand.Unimplemented) as exc:
            if isinstance(exc, sh_expand.StuckExpansion):
                print(f"expand.py: skipping expansion: {exc}", file=sys.stderr)
            expanded_ast.append(node)

    # Transformations on the expanded AST
    expanded_ast = [(node, "", -1, -1) for node in expanded_ast]
    transformed_expanded_ast = analysis.prepend_commands(expanded_ast, "try", only_commands=["rm"])
    return parsing.ast_to_code(transformed_expanded_ast)


def main():
    parser = argparse.ArgumentParser(description="Expand a shell script using sh-expand")
    parser.add_argument("input_script", help="Path to the input shell script")
    args = parser.parse_args()

    output = expand_script(args.input_script, sh_expand)
    print(output)

if __name__ == "__main__":
    main()
