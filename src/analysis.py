import libdash
import shasta.ast_node as AST
from shasta.json_to_ast import to_ast_node
import argparse
import sys
import functools

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
            print(f"Leaving node unchanged: {type(node)} {node}", sys.stderr)
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
    transformed_ast = walk_ast(original_ast)
    print(ast_to_code(transformed_ast))
    for feature in walk_node.features:
        print(f"{feature}: {walk_node.feature_counts[feature]}", file=sys.stderr)

if __name__ == "__main__":
    main()
