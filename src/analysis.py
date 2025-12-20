import libdash
import shasta.ast_node as AST
from shasta.json_to_ast import to_ast_node
import argparse
import sys

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

def visit_node(node):
    match node:
        case AST.PipeNode():
            return AST.PipeNode(
            items=[visit_node(node) for node in node.items],
            **{k: v for k, v in vars(node).items() if k != "items"}
            )
        case AST.CommandNode():
            if not node.arguments and not node.assignments:
                return node
            assignments = [visit_node(ass) for ass in node.assignments]
            arguments = [visit_node(arg) for arg in node.arguments]

            return AST.CommandNode(
                    arguments=arguments,
                    assignments=assignments,
                    **{k: v for k, v in vars(node).items() if k not in ("arguments", "assignments")})
        case AST.AssignNode():
            val = [visit_node(v) for v in node.val]
            return AST.AssignNode(
                    val=val,
                    **{k: v for k, v in vars(node).items() if k != "val"})
        case AST.BArgChar():
            return AST.BArgChar(
                    node=visit_node(node.node),
                    **{k: v for k, v in vars(node).items() if k != "node"})
        case AST.QArgChar():
            return AST.QArgChar(
                    arg=[visit_node(n) for n in node.arg],
                    **{k: v for k, v in vars(node).items() if k != "arg"})
        case AST.DefunNode():
            return AST.DefunNode(
                body=visit_node(node.body),
                **{k: v for k, v in vars(node).items() if k != "body"}
            )
        case AST.ForNode():
            return AST.ForNode(
                body=visit_node(node.body),
                argument=[visit_node(n) for n in node.argument],
                **{k: v for k, v in vars(node).items() if k not in ("body", "argument")}
            )
        case AST.WhileNode():
            return AST.WhileNode(
                    test=visit_node(node.test),
                    body=visit_node(node.body),
                    **{k: v for k, v in vars(node).items() if k not in ("test", "body")})
        case AST.SemiNode():
            return AST.SemiNode(
                    left_operand=visit_node(node.left_operand),
                    right_operand=visit_node(node.right_operand),
                    **{k: v for k, v in vars(node).items() if k not in ("left_operand", "right_operand")})
        case AST.RedirNode():
            return AST.RedirNode(
                    node=visit_node(node.node),
                    redir_list=[visit_node(n) for n in node.redir_list],
                    **{k: v for k, v in vars(node).items() if k not in ("node", "redir_list")})
        case AST.FileRedirNode():
            return node
        case list() if all(isinstance(x, AST.ArgChar) for x in node):
            return [visit_node(n) for n in node]
        case _:
            print(f"Leaving node unchanged: {type(node)} {node}", sys.stderr)
            return node

def transform_ast(ast):
    return [visit_node(node) for node, _, _, _ in ast]

def ast_statistics(ast):
    # print statistics on Expansions, stateful expansions, commands, etc
    pass


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
    transformed_ast = transform_ast(original_ast)
    print(ast_to_code(transformed_ast))

if __name__ == "__main__":
    main()
