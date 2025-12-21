from typing import runtime_checkable
import libdash
import shasta.ast_node as AST
from shasta.json_to_ast import to_ast_node
import argparse
import sys
import functools
import itertools
import os

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

def _replace_fd(fd, stubber):
    if isinstance(fd, tuple) and len(fd) == 2 and fd[0] == "var":
        return ("var", _replace_argchars(fd[1], stubber))
    return fd

def _replace_argchars(argchars, stubber):
    updated = []
    for ch in argchars:
        if isinstance(ch, AST.BArgChar):
            updated.append(AST.BArgChar(
                node=replace_pure_node(ch.node, stubber),
                **{k: v for k, v in vars(ch).items() if k != "node"}
            ))
        elif isinstance(ch, AST.QArgChar):
            updated.append(AST.QArgChar(
                arg=_replace_argchars(ch.arg, stubber),
                **{k: v for k, v in vars(ch).items() if k != "arg"}
            ))
        elif isinstance(ch, AST.AArgChar):
            updated.append(AST.AArgChar(
                arg=_replace_argchars(ch.arg, stubber),
                **{k: v for k, v in vars(ch).items() if k != "arg"}
            ))
        elif isinstance(ch, AST.VArgChar):
            updated.append(AST.VArgChar(
                arg=_replace_argchars(ch.arg, stubber),
                **{k: v for k, v in vars(ch).items() if k != "arg"}
            ))
        else:
            updated.append(ch)
    return updated

def replace_pure_node(node, stubber=None):
    if stubber and isinstance(node, AST.Command) and is_pure(node):
        return stubber(node)
    if isinstance(node, list):
        if node and all(isinstance(x, AST.ArgChar) for x in node):
            return _replace_argchars(node, stubber)
        return [replace_pure_node(n, stubber) for n in node]
    if isinstance(node, AST.PipeNode):
        return AST.PipeNode(
            items=[replace_pure_node(n, stubber) for n in node.items],
            **{k: v for k, v in vars(node).items() if k != "items"}
        )
    if isinstance(node, AST.CommandNode):
        assignments = [replace_pure_node(ass, stubber) for ass in node.assignments]
        arguments = [_replace_argchars(arg, stubber) for arg in node.arguments]
        redirs = [replace_pure_node(r, stubber) for r in node.redir_list]
        return AST.CommandNode(
            arguments=arguments,
            assignments=assignments,
            redir_list=redirs,
            **{k: v for k, v in vars(node).items() if k not in ("arguments", "assignments", "redir_list")}
        )
    if isinstance(node, AST.AssignNode):
        return AST.AssignNode(
            val=_replace_argchars(node.val, stubber),
            **{k: v for k, v in vars(node).items() if k != "val"}
        )
    if isinstance(node, AST.BArgChar):
        return AST.BArgChar(
            node=replace_pure_node(node.node, stubber),
            **{k: v for k, v in vars(node).items() if k != "node"}
        )
    if isinstance(node, AST.QArgChar):
        return AST.QArgChar(
            arg=_replace_argchars(node.arg, stubber),
            **{k: v for k, v in vars(node).items() if k != "arg"}
        )
    if isinstance(node, AST.AArgChar):
        return AST.AArgChar(
            arg=_replace_argchars(node.arg, stubber),
            **{k: v for k, v in vars(node).items() if k != "arg"}
        )
    if isinstance(node, AST.VArgChar):
        return AST.VArgChar(
            arg=_replace_argchars(node.arg, stubber),
            **{k: v for k, v in vars(node).items() if k != "arg"}
        )
    if isinstance(node, AST.DefunNode):
        return AST.DefunNode(
            body=replace_pure_node(node.body, stubber),
            **{k: v for k, v in vars(node).items() if k != "body"}
        )
    if isinstance(node, AST.ForNode):
        return AST.ForNode(
            body=replace_pure_node(node.body, stubber),
            argument=[_replace_argchars(n, stubber) for n in node.argument],
            variable=_replace_argchars(node.variable, stubber),
            **{k: v for k, v in vars(node).items() if k not in ("body", "argument", "variable")}
        )
    if isinstance(node, AST.ArithForNode):
        return AST.ArithForNode(
            init=[_replace_argchars(n, stubber) for n in node.init],
            cond=[_replace_argchars(n, stubber) for n in node.cond],
            step=[_replace_argchars(n, stubber) for n in node.step],
            body=replace_pure_node(node.body, stubber),
            **{k: v for k, v in vars(node).items() if k not in ("init", "cond", "step", "body")}
        )
    if isinstance(node, AST.WhileNode):
        return AST.WhileNode(
            test=replace_pure_node(node.test, stubber),
            body=replace_pure_node(node.body, stubber),
            **{k: v for k, v in vars(node).items() if k not in ("test", "body")}
        )
    if isinstance(node, AST.SemiNode):
        return AST.SemiNode(
            left_operand=replace_pure_node(node.left_operand, stubber),
            right_operand=replace_pure_node(node.right_operand, stubber),
            **{k: v for k, v in vars(node).items() if k not in ("left_operand", "right_operand")}
        )
    if isinstance(node, AST.AndNode):
        return AST.AndNode(
            left_operand=replace_pure_node(node.left_operand, stubber),
            right_operand=replace_pure_node(node.right_operand, stubber),
            **{k: v for k, v in vars(node).items() if k not in ("left_operand", "right_operand")}
        )
    if isinstance(node, AST.OrNode):
        return AST.OrNode(
            left_operand=replace_pure_node(node.left_operand, stubber),
            right_operand=replace_pure_node(node.right_operand, stubber),
            **{k: v for k, v in vars(node).items() if k not in ("left_operand", "right_operand")}
        )
    if isinstance(node, AST.NotNode):
        return AST.NotNode(
            body=replace_pure_node(node.body, stubber),
            **{k: v for k, v in vars(node).items() if k != "body"}
        )
    if isinstance(node, AST.IfNode):
        return AST.IfNode(
            cond=replace_pure_node(node.cond, stubber),
            then_b=replace_pure_node(node.then_b, stubber),
            else_b=replace_pure_node(node.else_b, stubber) if node.else_b else None,
            **{k: v for k, v in vars(node).items() if k not in ("cond", "then_b", "else_b")}
        )
    if isinstance(node, AST.CaseNode):
        updated_cases = []
        for case in node.cases:
            new_case = dict(case)
            if "cpattern" in case:
                new_case["cpattern"] = [_replace_argchars(p, stubber) for p in case["cpattern"]]
            if case.get("cbody"):
                new_case["cbody"] = replace_pure_node(case["cbody"], stubber)
            updated_cases.append(new_case)
        return AST.CaseNode(
            argument=_replace_argchars(node.argument, stubber),
            cases=updated_cases,
            **{k: v for k, v in vars(node).items() if k not in ("argument", "cases")}
        )
    if isinstance(node, AST.SubshellNode):
        return AST.SubshellNode(
            body=replace_pure_node(node.body, stubber),
            redir_list=[replace_pure_node(r, stubber) for r in node.redir_list],
            **{k: v for k, v in vars(node).items() if k not in ("body", "redir_list")}
        )
    if isinstance(node, AST.BackgroundNode):
        return AST.BackgroundNode(
            node=replace_pure_node(node.node, stubber),
            redir_list=[replace_pure_node(r, stubber) for r in node.redir_list],
            after_ampersand=replace_pure_node(node.after_ampersand, stubber) if node.after_ampersand else None,
            **{k: v for k, v in vars(node).items() if k not in ("node", "redir_list", "after_ampersand")}
        )
    if isinstance(node, AST.RedirNode):
        return AST.RedirNode(
            node=replace_pure_node(node.node, stubber),
            redir_list=[replace_pure_node(r, stubber) for r in node.redir_list],
            **{k: v for k, v in vars(node).items() if k not in ("node", "redir_list")}
        )
    if isinstance(node, AST.FileRedirNode):
        return AST.FileRedirNode(
            arg=_replace_argchars(node.arg, stubber) if node.arg else None,
            **{k: v for k, v in vars(node).items() if k != "arg"}
        )
    if isinstance(node, AST.DupRedirNode):
        return AST.DupRedirNode(
            fd=_replace_fd(node.fd, stubber),
            arg=_replace_fd(node.arg, stubber),
            **{k: v for k, v in vars(node).items() if k not in ("fd", "arg")}
        )
    if isinstance(node, AST.HeredocRedirNode):
        return AST.HeredocRedirNode(
            arg=_replace_argchars(node.arg, stubber),
            **{k: v for k, v in vars(node).items() if k != "arg"}
        )
    if isinstance(node, AST.SingleArgRedirNode):
        return AST.SingleArgRedirNode(
            fd=_replace_fd(node.fd, stubber),
            **{k: v for k, v in vars(node).items() if k != "fd"}
        )
    if isinstance(node, AST.ArithNode):
        return AST.ArithNode(
            body=[_replace_argchars(n, stubber) for n in node.body],
            **{k: v for k, v in vars(node).items() if k != "body"}
        )
    if isinstance(node, AST.SelectNode):
        return AST.SelectNode(
            variable=_replace_argchars(node.variable, stubber),
            map_list=[_replace_argchars(n, stubber) for n in node.map_list],
            body=replace_pure_node(node.body, stubber),
            **{k: v for k, v in vars(node).items() if k not in ("variable", "map_list", "body")}
        )
    if isinstance(node, AST.GroupNode):
        return AST.GroupNode(
            body=replace_pure_node(node.body, stubber),
            **{k: v for k, v in vars(node).items() if k != "body"}
        )
    if isinstance(node, AST.TimeNode):
        return AST.TimeNode(
            command=replace_pure_node(node.command, stubber),
            **{k: v for k, v in vars(node).items() if k != "command"}
        )
    if isinstance(node, AST.CoprocNode):
        return AST.CoprocNode(
            name=_replace_argchars(node.name, stubber),
            body=replace_pure_node(node.body, stubber),
            **{k: v for k, v in vars(node).items() if k not in ("name", "body")}
        )
    return node

def replace_pure_subtrees(ast, stub_dir="/tmp"):
    counter = itertools.count()

    def stubber(node):
        idx = next(counter)
        stub_path = os.path.join(stub_dir, f"stub_{idx}")
        with open(stub_path, "w", encoding="utf-8") as handle:
            text = node.pretty()
            if text and not text.endswith("\n"):
                text += "\n"
            handle.write(text)
        line_number = getattr(node, "line_number", -1)
        return AST.CommandNode(
            line_number=line_number,
            assignments=[],
            arguments=[_string_to_argchars(stub_path)],
            redir_list=[],
        )

    return [replace_pure_node(node, stubber) for node, _, _, _ in ast]

def flatten_ast(node):
    if isinstance(node, AST.PipeNode):
        return list(node.items)
    if isinstance(node, AST.CommandNode):
        return list(node.assignments) + list(node.arguments) + list(node.redir_list)
    if isinstance(node, AST.AssignNode):
        return list(node.val)
    if isinstance(node, AST.BArgChar):
        return [node.node]
    if isinstance(node, AST.QArgChar):
        return list(node.arg)
    if isinstance(node, AST.AArgChar):
        return list(node.arg)
    if isinstance(node, AST.VArgChar):
        return list(node.arg)
    if isinstance(node, AST.DefunNode):
        return [node.body]
    if isinstance(node, AST.ForNode):
        return list(node.argument) + [node.body]
    if isinstance(node, AST.ArithForNode):
        return list(node.init) + list(node.cond) + list(node.step) + [node.body]
    if isinstance(node, AST.WhileNode):
        return [node.test, node.body]
    if isinstance(node, AST.SemiNode):
        return [node.left_operand, node.right_operand]
    if isinstance(node, AST.AndNode):
        return [node.left_operand, node.right_operand]
    if isinstance(node, AST.OrNode):
        return [node.left_operand, node.right_operand]
    if isinstance(node, AST.NotNode):
        return [node.body]
    if isinstance(node, AST.IfNode):
        children = [node.cond, node.then_b]
        if node.else_b:
            children.append(node.else_b)
        return children
    if isinstance(node, AST.CaseNode):
        children = [node.argument]
        for case in node.cases:
            children.extend(case.get("cpattern", []))
            body = case.get("cbody")
            if body:
                children.append(body)
        return children
    if isinstance(node, AST.SubshellNode):
        return [node.body] + list(node.redir_list)
    if isinstance(node, AST.BackgroundNode):
        children = [node.node] + list(node.redir_list)
        if node.after_ampersand:
            children.append(node.after_ampersand)
        return children
    if isinstance(node, AST.RedirNode):
        return [node.node] + list(node.redir_list)
    if isinstance(node, AST.FileRedirNode):
        return [node.arg] if node.arg else []
    if isinstance(node, AST.DupRedirNode):
        return [node.fd, node.arg]
    if isinstance(node, AST.HeredocRedirNode):
        return [node.arg]
    if isinstance(node, AST.SingleArgRedirNode):
        return [node.fd]
    if isinstance(node, AST.ArithNode):
        return list(node.body)
    if isinstance(node, AST.SelectNode):
        return [node.variable] + list(node.map_list) + [node.body]
    if isinstance(node, AST.GroupNode):
        return [node.body]
    if isinstance(node, AST.TimeNode):
        return [node.command]
    if isinstance(node, AST.CoprocNode):
        return [node.name, node.body]
    return []

def get_pure_subtrees(ast):
    subtrees = []
    def walk(n):
        if isinstance(n, list):
            for item in n:
                walk(item)
            return
        if isinstance(n, tuple):
            for item in n:
                walk(item)
            return
        if isinstance(n, AST.AstNode) and is_pure(n)\
            and not isinstance(n, AST.ArgChar): # Small hack to avoid many argchar-only subtrees
            subtrees.append(n)
            return
        for child in flatten_ast(n):
            walk(child)

    for node, _, _, _ in ast:
        walk(node)
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
    match node:
        case AST.PipeNode():
            return AST.PipeNode(
            items=[walk_node(node) for node in node.items],
            **{k: v for k, v in vars(node).items() if k != "items"}
            )
        case AST.CommandNode():
            if not node.arguments and not node.assignments:
                return node
            assignments = [walk_node(ass) for ass in node.assignments]
            arguments = [walk_node(arg) for arg in node.arguments]

            return AST.CommandNode(
                    arguments=arguments,
                    assignments=assignments,
                    **{k: v for k, v in vars(node).items() if k not in ("arguments", "assignments")})
        case AST.AssignNode():
            val = [walk_node(v) for v in node.val]
            return AST.AssignNode(
                    val=val,
                    **{k: v for k, v in vars(node).items() if k != "val"})
        case AST.BArgChar():
            return AST.BArgChar(
                    node=walk_node(node.node),
                    **{k: v for k, v in vars(node).items() if k != "node"})
        case AST.QArgChar():
            return AST.QArgChar(
                    arg=[walk_node(n) for n in node.arg],
                    **{k: v for k, v in vars(node).items() if k != "arg"})
        case AST.DefunNode():
            return AST.DefunNode(
                body=walk_node(node.body),
                **{k: v for k, v in vars(node).items() if k != "body"}
            )
        case AST.ForNode():
            return AST.ForNode(
                body=walk_node(node.body),
                argument=[walk_node(n) for n in node.argument],
                **{k: v for k, v in vars(node).items() if k not in ("body", "argument")}
            )
        case AST.WhileNode():
            return AST.WhileNode(
                    test=walk_node(node.test),
                    body=walk_node(node.body),
                    **{k: v for k, v in vars(node).items() if k not in ("test", "body")})
        case AST.SemiNode():
            return AST.SemiNode(
                    left_operand=walk_node(node.left_operand),
                    right_operand=walk_node(node.right_operand),
                    **{k: v for k, v in vars(node).items() if k not in ("left_operand", "right_operand")})
        case AST.RedirNode():
            return AST.RedirNode(
                    node=walk_node(node.node),
                    redir_list=[walk_node(n) for n in node.redir_list],
                    **{k: v for k, v in vars(node).items() if k not in ("node", "redir_list")})
        case AST.FileRedirNode():
            return node
        case list() if all(isinstance(x, AST.ArgChar) for x in node):
            return [walk_node(n) for n in node]
        case _:
            # print(f"Leaving node unchanged: {type(node)} {node}", sys.stderr)
            return node

def walk_ast(ast):
    return [walk_node(node) for node, _, _, _ in ast]

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
    walk_ast(original_ast)
    stubbed_ast = replace_pure_subtrees(original_ast)
    print(ast_to_code(stubbed_ast))
    for feature in walk_node.features:
        print(f"{feature}: {walk_node.feature_counts[feature]}", file=sys.stderr)
    pure_subtrees = get_pure_subtrees(original_ast)
    print(f"Pure subtrees:", file=sys.stderr)
    for subtree in pure_subtrees:
        print("-", subtree.pretty(), file=sys.stderr)

if __name__ == "__main__":
    main()
