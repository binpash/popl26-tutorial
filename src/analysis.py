import libdash
import shasta.ast_node as AST
from shasta.json_to_ast import to_ast_node
import argparse
import sys
import itertools
import os
import shlex

def is_pure(node):
    if node is None:
        return True
    impure = False

    def visit(n):
        nonlocal impure
        if impure:
            return
        match n:
            case AST.VArgChar() if n.fmt == "Assign":
                impure = True
            case AST.BArgChar():
                impure = True
            case AST.CArgChar() | AST.EArgChar() if n.char == ord("`"):
                impure = True
            case AST.CommandNode():
                if n.arguments:
                    cmd_name = AST.string_of_arg(n.arguments[0])
                    if cmd_name in ("rm", "alias"):
                        impure = True
            case _:
                pass

    walk_ast_node(node, visit=visit, replace=None)
    return not impure

def _string_to_argchars(text):
    return [AST.CArgChar(ord(ch)) for ch in text]

def _is_stub_command(node, stub_dir="/tmp"):
    match node:
        case AST.CommandNode() if len(node.arguments) >= 2:
            cmd = AST.string_of_arg(node.arguments[0])
            path = AST.string_of_arg(node.arguments[1])
            return cmd == "source" and path.startswith(f"{stub_dir}/stub_")
        case _:
            return False

def walk_ast_node(node, visit=None, replace=None):
    if visit:
        visit(node)
    if replace:
        replaced = replace(node)
        if replaced is not None:
            return replaced

    def walk_fd(fd):
        match fd:
            case ("var", argchars):
                return ("var", walk_ast_node(argchars, visit=visit, replace=replace))
            case _:
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

def pure_replacer(stub_dir="/tmp"):
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
        match node:
            case AST.Command() if is_pure(node):
                return stubber(node)
            case _:
                return None

    return replace

def replace_pure_subtrees(ast, stub_dir="/tmp"):
    return walk_ast(ast, replace=pure_replacer(stub_dir))

def command_prepender(prefix_cmd, only_commands=None, stub_dir="/tmp"):
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
                if _is_stub_command(node, stub_dir=stub_dir):
                    return None
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

def prepend_commands(ast, prefix_cmd, only_commands=None, stub_dir="/tmp"):
    return walk_ast(
        ast,
        replace=command_prepender(prefix_cmd, only_commands=only_commands, stub_dir=stub_dir),
    )

def get_pure_subtrees(ast):
    subtrees = []
    def replace(n):
        match n:
            case AST.ArgChar():
                return None
            case AST.AstNode() if is_pure(n):
                subtrees.append(n)
                return n
            case _:
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
    for (
        untyped_ast,
        original_text,
        linno_before,
        linno_after,
    ) in new_ast_objects:
        typed_ast = to_ast_node(untyped_ast)
        yield (typed_ast, original_text, linno_before, linno_after)

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
            case AST.ForNode() | AST.ArithForNode():
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

    original_ast = list(parse_shell_to_asts(arg_parser.parse_args().input_script))
    original_code = ast_to_code(walk_ast(original_ast, visit=walk_node))
    print(original_code)
    
    walk_ast(original_ast, visit=feature_counter())
    print('\n'.join(
            f'- {feature} : {count}'
            for feature, count in feature_counter.feature_counts.items()
        ), file=sys.stderr)
    
    pure_subtrees = get_pure_subtrees(original_ast)
    print(f"Pure subtrees:", file=sys.stderr)
    for subtree in pure_subtrees:
        print("-", subtree.pretty(), file=sys.stderr)

    stubbed_ast = walk_ast(original_ast, replace=pure_replacer("/tmp"))
    print(ast_to_code(stubbed_ast))

    prepended_ast = prepend_commands(original_ast, "try")
    print(ast_to_code(prepended_ast))

    prepended_rm_ast = prepend_commands(original_ast, "try", only_commands=["rm"])
    print(ast_to_code(prepended_rm_ast))

if __name__ == "__main__":
    main()
