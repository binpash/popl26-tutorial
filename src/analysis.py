from typing import runtime_checkable
import libdash
import shasta.ast_node as AST
from shasta.json_to_ast import to_ast_node
import argparse
import sys
import functools
import itertools
import os
import shlex

def identity(func):
    @functools.wraps(func)
    def wrapper(node):
        return func(node)
    return wrapper

def count_features(func):
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
    counts = {name: 0 for name in features}

    @functools.wraps(func)
    def wrapper(node):
        if isinstance(node, AST.BackgroundNode):
            counts["background"] += 1
        if isinstance(node, AST.PipeNode):
            counts["pipeline"] += 1
            if getattr(node, "is_background", False):
                counts["background"] += 1
        if isinstance(node, AST.SubshellNode):
            counts["subshell"] += 1
        if isinstance(node, AST.TArgChar):
            counts["home_tilde"] += 1
        if isinstance(node, AST.AArgChar):
            counts["$((arithmetic))"] += 1
        if isinstance(node, AST.BArgChar):
            counts["$(substitution)"] += 1
        if isinstance(node, AST.VArgChar):
            counts["variable_use"] += 1
        if isinstance(node, AST.AssignNode):
            counts["assignment"] += 1
        if isinstance(node, AST.DefunNode):
            counts["function"] += 1
        if isinstance(node, AST.WhileNode):
            counts["while"] += 1
        if isinstance(node, (AST.ForNode, AST.ArithForNode)):
            counts["for"] += 1
        if isinstance(node, AST.CaseNode):
            counts["case"] += 1
        if isinstance(node, AST.IfNode):
            counts["if"] += 1
        if isinstance(node, AST.AndNode):
            counts["and"] += 1
        if isinstance(node, AST.OrNode):
            counts["or"] += 1
        if isinstance(node, AST.NotNode):
            counts["negate"] += 1
        if isinstance(node, AST.HeredocRedirNode):
            counts["heredoc_redir"] += 1
        if isinstance(node, AST.DupRedirNode):
            counts["dup_redir"] += 1
        if isinstance(node, AST.FileRedirNode):
            counts["file_redir"] += 1
        if isinstance(node, AST.CommandNode):
            counts["command"] += 1
            if node.arguments:
                cmd_name = AST.string_of_arg(node.arguments[0])
                if cmd_name == "eval":
                    counts["eval"] += 1
                elif cmd_name == "alias":
                    counts["alias"] += 1
        return func(node)

    wrapper.feature_counts = counts
    wrapper.features = features
    return wrapper

def is_pure(node):
    def _argchars_pure(argchars):
        for ch in argchars:
            if isinstance(ch, AST.VArgChar):
                if ch.fmt == "Assign":
                    return False
                if not _argchars_pure(ch.arg):
                    return False
            elif isinstance(ch, (AST.QArgChar, AST.AArgChar)):
                if not _argchars_pure(ch.arg):
                    return False
            elif isinstance(ch, AST.BArgChar):
                if not is_pure(ch.node):
                    return False
            elif isinstance(ch, list) and all(isinstance(x, AST.ArgChar) for x in ch):
                if not _argchars_pure(ch):
                    return False
        return True

    def _fd_pure(fd):
        if isinstance(fd, tuple) and len(fd) == 2 and fd[0] == "var":
            return _argchars_pure(fd[1])
        return True

    if node is None:
        return True
    if isinstance(node, list):
        if node and all(isinstance(x, AST.ArgChar) for x in node):
            return _argchars_pure(node)
        return all(is_pure(n) for n in node)
    if isinstance(node, AST.CommandNode):
        if node.arguments and not all(_argchars_pure(a) for a in node.arguments):
            return False
        for ass in node.assignments:
            if not is_pure(ass):
                return False
        for redir in node.redir_list:
            if not is_pure(redir):
                return False
        if node.arguments:
            cmd_name = AST.string_of_arg(node.arguments[0])
            if cmd_name in ("rm",):
                return False
        return True
    if isinstance(node, AST.AssignNode):
        return _argchars_pure(node.val)
    if isinstance(node, AST.PipeNode):
        return all(is_pure(n) for n in node.items)
    if isinstance(node, AST.SubshellNode):
        return is_pure(node.body) and all(is_pure(r) for r in node.redir_list)
    if isinstance(node, AST.BackgroundNode):
        return (
            is_pure(node.node)
            and (is_pure(node.after_ampersand) if node.after_ampersand else True)
            and all(is_pure(r) for r in node.redir_list)
        )
    if isinstance(node, AST.RedirNode):
        return is_pure(node.node) and all(is_pure(r) for r in node.redir_list)
    if isinstance(node, AST.FileRedirNode):
        return _argchars_pure(node.arg) if node.arg else True
    if isinstance(node, AST.DupRedirNode):
        return _fd_pure(node.fd) and _fd_pure(node.arg)
    if isinstance(node, AST.HeredocRedirNode):
        return _argchars_pure(node.arg)
    if isinstance(node, AST.SingleArgRedirNode):
        return _fd_pure(node.fd)
    if isinstance(node, AST.DefunNode):
        return is_pure(node.body)
    if isinstance(node, AST.ForNode):
        return (
            _argchars_pure(node.variable)
            and all(_argchars_pure(a) for a in node.argument)
            and is_pure(node.body)
        )
    if isinstance(node, AST.ArithForNode):
        return (
            all(_argchars_pure(a) for a in node.init)
            and all(_argchars_pure(a) for a in node.cond)
            and all(_argchars_pure(a) for a in node.step)
            and is_pure(node.body)
        )
    if isinstance(node, AST.WhileNode):
        return is_pure(node.test) and is_pure(node.body)
    if isinstance(node, AST.SemiNode):
        return is_pure(node.left_operand) and is_pure(node.right_operand)
    if isinstance(node, AST.AndNode):
        return is_pure(node.left_operand) and is_pure(node.right_operand)
    if isinstance(node, AST.OrNode):
        return is_pure(node.left_operand) and is_pure(node.right_operand)
    if isinstance(node, AST.NotNode):
        return is_pure(node.body)
    if isinstance(node, AST.IfNode):
        return is_pure(node.cond) and is_pure(node.then_b) and is_pure(node.else_b)
    if isinstance(node, AST.CaseNode):
        if not _argchars_pure(node.argument):
            return False
        for case in node.cases:
            for pat in case.get("cpattern", []):
                if not _argchars_pure(pat):
                    return False
            body = case.get("cbody")
            if body and not is_pure(body):
                return False
        return True
    if isinstance(node, AST.ArithNode):
        return all(_argchars_pure(a) for a in node.body)
    if isinstance(node, AST.SelectNode):
        return (
            _argchars_pure(node.variable)
            and all(_argchars_pure(a) for a in node.map_list)
            and is_pure(node.body)
        )
    if isinstance(node, AST.GroupNode):
        return is_pure(node.body)
    if isinstance(node, AST.TimeNode):
        return is_pure(node.command)
    if isinstance(node, AST.CoprocNode):
        return _argchars_pure(node.name) and is_pure(node.body)
    return True

def _string_to_argchars(text):
    return [AST.CArgChar(ord(ch)) for ch in text]

def walk_ast_node(node, visit=None, replace=None):
    if visit:
        visit(node)
    if replace:
        replaced = replace(node)
        if replaced is not None:
            return replaced

    def walk_fd(fd):
        if isinstance(fd, tuple) and len(fd) == 2 and fd[0] == "var":
            return ("var", walk_ast_node(fd[1], visit=visit, replace=replace))
        return fd

    match node:
        case list():
            return [walk_ast_node(n, visit=visit, replace=replace) for n in node]
        case tuple():
            return tuple(walk_ast_node(n, visit=visit, replace=replace) for n in node)
        case AST.BArgChar():
            return AST.BArgChar(
                node=walk_ast_node(node.node, visit=visit, replace=replace),
                **{k: v for k, v in vars(node).items() if k != "node"}
            )
        case AST.QArgChar():
            return AST.QArgChar(
                arg=walk_ast_node(node.arg, visit=visit, replace=replace),
                **{k: v for k, v in vars(node).items() if k != "arg"}
            )
        case AST.AArgChar():
            return AST.AArgChar(
                arg=walk_ast_node(node.arg, visit=visit, replace=replace),
                **{k: v for k, v in vars(node).items() if k != "arg"}
            )
        case AST.VArgChar():
            return AST.VArgChar(
                arg=walk_ast_node(node.arg, visit=visit, replace=replace),
                **{k: v for k, v in vars(node).items() if k != "arg"}
            )
        case AST.CArgChar() | AST.EArgChar() | AST.TArgChar():
            return node
        case AST.PipeNode():
            return AST.PipeNode(
                items=[walk_ast_node(n, visit=visit, replace=replace) for n in node.items],
                **{k: v for k, v in vars(node).items() if k != "items"}
            )
        case AST.CommandNode():
            assignments = [walk_ast_node(ass, visit=visit, replace=replace) for ass in node.assignments]
            arguments = [walk_ast_node(arg, visit=visit, replace=replace) for arg in node.arguments]
            redirs = [walk_ast_node(r, visit=visit, replace=replace) for r in node.redir_list]
            return AST.CommandNode(
                arguments=arguments,
                assignments=assignments,
                redir_list=redirs,
                **{k: v for k, v in vars(node).items() if k not in ("arguments", "assignments", "redir_list")}
            )
        case AST.AssignNode():
            return AST.AssignNode(
                val=walk_ast_node(node.val, visit=visit, replace=replace),
                **{k: v for k, v in vars(node).items() if k != "val"}
            )
        case AST.DefunNode():
            return AST.DefunNode(
                body=walk_ast_node(node.body, visit=visit, replace=replace),
                **{k: v for k, v in vars(node).items() if k != "body"}
            )
        case AST.ForNode():
            return AST.ForNode(
                body=walk_ast_node(node.body, visit=visit, replace=replace),
                argument=[walk_ast_node(n, visit=visit, replace=replace) for n in node.argument],
                variable=walk_ast_node(node.variable, visit=visit, replace=replace),
                **{k: v for k, v in vars(node).items() if k not in ("body", "argument", "variable")}
            )
        case AST.ArithForNode():
            return AST.ArithForNode(
                init=[walk_ast_node(n, visit=visit, replace=replace) for n in node.init],
                cond=[walk_ast_node(n, visit=visit, replace=replace) for n in node.cond],
                step=[walk_ast_node(n, visit=visit, replace=replace) for n in node.step],
                body=walk_ast_node(node.body, visit=visit, replace=replace),
                **{k: v for k, v in vars(node).items() if k not in ("init", "cond", "step", "body")}
            )
        case AST.WhileNode():
            return AST.WhileNode(
                test=walk_ast_node(node.test, visit=visit, replace=replace),
                body=walk_ast_node(node.body, visit=visit, replace=replace),
                **{k: v for k, v in vars(node).items() if k not in ("test", "body")}
            )
        case AST.SemiNode():
            return AST.SemiNode(
                left_operand=walk_ast_node(node.left_operand, visit=visit, replace=replace),
                right_operand=walk_ast_node(node.right_operand, visit=visit, replace=replace),
                **{k: v for k, v in vars(node).items() if k not in ("left_operand", "right_operand")}
            )
        case AST.AndNode():
            return AST.AndNode(
                left_operand=walk_ast_node(node.left_operand, visit=visit, replace=replace),
                right_operand=walk_ast_node(node.right_operand, visit=visit, replace=replace),
                **{k: v for k, v in vars(node).items() if k not in ("left_operand", "right_operand")}
            )
        case AST.OrNode():
            return AST.OrNode(
                left_operand=walk_ast_node(node.left_operand, visit=visit, replace=replace),
                right_operand=walk_ast_node(node.right_operand, visit=visit, replace=replace),
                **{k: v for k, v in vars(node).items() if k not in ("left_operand", "right_operand")}
            )
        case AST.NotNode():
            return AST.NotNode(
                body=walk_ast_node(node.body, visit=visit, replace=replace),
                **{k: v for k, v in vars(node).items() if k != "body"}
            )
        case AST.IfNode():
            return AST.IfNode(
                cond=walk_ast_node(node.cond, visit=visit, replace=replace),
                then_b=walk_ast_node(node.then_b, visit=visit, replace=replace),
                else_b=walk_ast_node(node.else_b, visit=visit, replace=replace) if node.else_b else None,
                **{k: v for k, v in vars(node).items() if k not in ("cond", "then_b", "else_b")}
            )
        case AST.CaseNode():
            updated_cases = []
            for case in node.cases:
                new_case = dict(case)
                if "cpattern" in case:
                    new_case["cpattern"] = [walk_ast_node(p, visit=visit, replace=replace) for p in case["cpattern"]]
                if case.get("cbody"):
                    new_case["cbody"] = walk_ast_node(case["cbody"], visit=visit, replace=replace)
                updated_cases.append(new_case)
            return AST.CaseNode(
                argument=walk_ast_node(node.argument, visit=visit, replace=replace),
                cases=updated_cases,
                **{k: v for k, v in vars(node).items() if k not in ("argument", "cases")}
            )
        case AST.SubshellNode():
            return AST.SubshellNode(
                body=walk_ast_node(node.body, visit=visit, replace=replace),
                redir_list=[walk_ast_node(r, visit=visit, replace=replace) for r in node.redir_list],
                **{k: v for k, v in vars(node).items() if k not in ("body", "redir_list")}
            )
        case AST.BackgroundNode():
            return AST.BackgroundNode(
                node=walk_ast_node(node.node, visit=visit, replace=replace),
                redir_list=[walk_ast_node(r, visit=visit, replace=replace) for r in node.redir_list],
                after_ampersand=walk_ast_node(node.after_ampersand, visit=visit, replace=replace) if node.after_ampersand else None,
                **{k: v for k, v in vars(node).items() if k not in ("node", "redir_list", "after_ampersand")}
            )
        case AST.RedirNode():
            return AST.RedirNode(
                node=walk_ast_node(node.node, visit=visit, replace=replace),
                redir_list=[walk_ast_node(r, visit=visit, replace=replace) for r in node.redir_list],
                **{k: v for k, v in vars(node).items() if k not in ("node", "redir_list")}
            )
        case AST.FileRedirNode():
            return AST.FileRedirNode(
                arg=walk_ast_node(node.arg, visit=visit, replace=replace) if node.arg else None,
                **{k: v for k, v in vars(node).items() if k != "arg"}
            )
        case AST.DupRedirNode():
            return AST.DupRedirNode(
                fd=walk_fd(node.fd),
                arg=walk_fd(node.arg),
                **{k: v for k, v in vars(node).items() if k not in ("fd", "arg")}
            )
        case AST.HeredocRedirNode():
            return AST.HeredocRedirNode(
                arg=walk_ast_node(node.arg, visit=visit, replace=replace),
                **{k: v for k, v in vars(node).items() if k != "arg"}
            )
        case AST.SingleArgRedirNode():
            return AST.SingleArgRedirNode(
                fd=walk_fd(node.fd),
                **{k: v for k, v in vars(node).items() if k != "fd"}
            )
        case AST.ArithNode():
            return AST.ArithNode(
                body=[walk_ast_node(n, visit=visit, replace=replace) for n in node.body],
                **{k: v for k, v in vars(node).items() if k != "body"}
            )
        case AST.SelectNode():
            return AST.SelectNode(
                variable=walk_ast_node(node.variable, visit=visit, replace=replace),
                map_list=[walk_ast_node(n, visit=visit, replace=replace) for n in node.map_list],
                body=walk_ast_node(node.body, visit=visit, replace=replace),
                **{k: v for k, v in vars(node).items() if k not in ("variable", "map_list", "body")}
            )
        case AST.GroupNode():
            return AST.GroupNode(
                body=walk_ast_node(node.body, visit=visit, replace=replace),
                **{k: v for k, v in vars(node).items() if k != "body"}
            )
        case AST.TimeNode():
            return AST.TimeNode(
                command=walk_ast_node(node.command, visit=visit, replace=replace),
                **{k: v for k, v in vars(node).items() if k != "command"}
            )
        case AST.CoprocNode():
            return AST.CoprocNode(
                name=walk_ast_node(node.name, visit=visit, replace=replace),
                body=walk_ast_node(node.body, visit=visit, replace=replace),
                **{k: v for k, v in vars(node).items() if k not in ("name", "body")}
            )
        case _:
            return node

def make_pure_replacer(stub_dir="/tmp"):
    counter = itertools.count()

    def stubber(node):
        idx = next(counter)
        stub_path = os.path.join(stub_dir, f"stub_{idx}")
        with open(stub_path, "w", encoding="utf-8") as handle:
            prologue = (
                "__saved_vars=$(set)\n"
                "__saved_aliases=$(alias)\n"
            )
            epilogue = (
                "unalias -a 2>/dev/null\n"
                "eval \"$__saved_aliases\"\n"
                "while IFS= read -r __line; do\n"
                "  case \"$__line\" in\n"
                "    *=*) eval \"$__line\" ;;\n"
                "  esac\n"
                "done <<'__CODEX_VARS__'\n"
                "${__saved_vars}\n"
                "__CODEX_VARS__\n"
                "unset __saved_vars __saved_aliases __line\n"
            )
            text = node.pretty()
            if text and not text.endswith("\n"):
                text += "\n"
            handle.write(prologue)
            handle.write(text)
            handle.write(epilogue)
        line_number = getattr(node, "line_number", -1)
        return AST.CommandNode(
            line_number=line_number,
            assignments=[],
            arguments=[
                _string_to_argchars("source"),
                _string_to_argchars(stub_path),
            ],
            redir_list=[],
        )

    def replace(node):
        if isinstance(node, AST.Command) and is_pure(node):
            return stubber(node)
        return None

    return replace

def replace_pure_subtrees(ast, stub_dir="/tmp"):
    return walk_ast(ast, replace=make_pure_replacer(stub_dir))

def make_command_prepender(prefix_cmd):
    tokens = shlex.split(prefix_cmd)
    if not tokens:
        return lambda node: None
    prefix_args = [_string_to_argchars(token) for token in tokens]

    def replace(node):
        if not isinstance(node, AST.CommandNode):
            return None
        assignments = [walk_ast_node(ass, replace=replace) for ass in node.assignments]
        arguments = [walk_ast_node(arg, replace=replace) for arg in node.arguments]
        redirs = [walk_ast_node(r, replace=replace) for r in node.redir_list]
        return AST.CommandNode(
            arguments=prefix_args + arguments,
            assignments=assignments,
            redir_list=redirs,
            **{k: v for k, v in vars(node).items() if k not in ("arguments", "assignments", "redir_list")}
        )

    return replace

def prepend_commands(ast, prefix_cmd):
    return walk_ast(ast, replace=make_command_prepender(prefix_cmd))

def get_pure_subtrees(ast):
    subtrees = []
    def replace(n):
        if isinstance(n, AST.AstNode) and is_pure(n) and not isinstance(n, AST.ArgChar):
            subtrees.append(n)
            return n
        return None

    walk_ast(ast, replace=replace)
    return subtrees


# Parses straight a shell script to an AST
# through python without calling it as an executable
INITIALIZE_LIBDASH = True
def parse_shell_to_asts(input_script_path : str):
    global INITIALIZE_LIBDASH
    new_ast_objects = libdash.parser.parse(input_script_path,init=INITIALIZE_LIBDASH)
    INITIALIZE_LIBDASH = False
    # Transform the untyped ast objects to typed ones
    new_ast_objects = list(new_ast_objects)
    typed_ast_objects = []
    for (
        untyped_ast,
        original_text,
        linno_before,
        linno_after,
    ) in new_ast_objects:
        typed_ast = to_ast_node(untyped_ast)
        typed_ast_objects.append(
            (typed_ast, original_text, linno_before, linno_after)
        )
    return typed_ast_objects

@count_features
@identity
def walk_node(node):
    return node

def walk_ast(ast, visit=None, replace=None):
    return [walk_ast_node(node, visit=visit, replace=replace) for node, _, _, _ in ast]

def ast_to_code(ast):
    return "\n".join([node.pretty() for node in ast])

def main():
    arg_parser = argparse.ArgumentParser(
        description=f"Transform a shell script and outputs the modified script"
    )
    arg_parser.add_argument(
        "input_script",
        type=str,
        help="Path to the input shell script",
    )

    original_ast = parse_shell_to_asts(arg_parser.parse_args().input_script)
    original_code = ast_to_code(walk_ast(original_ast, visit=walk_node))
    print(original_code)

    for feature in walk_node.features:
        print(f"{feature}: {walk_node.feature_counts[feature]}", file=sys.stderr)
    pure_subtrees = get_pure_subtrees(original_ast)
    print(f"Pure subtrees:", file=sys.stderr)
    for subtree in pure_subtrees:
        print("-", subtree.pretty(), file=sys.stderr)

    stubbed_ast = walk_ast(original_ast, replace=make_pure_replacer("/tmp"))
    print(ast_to_code(stubbed_ast))

    prepended_ast = prepend_commands(original_ast, "try")
    print(ast_to_code(prepended_ast))

if __name__ == "__main__":
    main()
