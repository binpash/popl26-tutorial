import itertools
import os

import shasta.ast_node as AST

import pure
from ast_helper import *


def replace_with_jit(stub_dir="/tmp", jit_script="src/jit.sh"):
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
                *node.assignments, # Keep original assignments
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
            case AST.Command() if pure.is_safe_to_expand(node):
                return stubber(node)
            case _:
                return None

    return replace

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
            assignments=node.assignments,
            line_number=line_number,
            arguments=[
                string_to_argchars("cat"),
                string_to_argchars(stub_path)
            ],
            redir_list=[],
        )
    def replace(node):
        match node:
            case AST.Command() if pure.is_safe_to_expand(node):
                return stubber(node)
            case _:
                return None

    return replace





##
## Old preprocess programs
##
def replace_safe_to_expand_subtrees(ast, stub_dir="/tmp"):
    return walk_ast(ast, replace=replace_with_jit(stub_dir))

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