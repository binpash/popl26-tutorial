import shasta.ast_node as AST


from ast_helper import *

## TODO: Fix this 
## TODO: Michael make sure it corresponds to your slides
def is_safe_to_expand(node):
    if node is None:
        return True
    impure = False

    def visit(n):
        nonlocal impure
        if impure:
            return
        match n:
            case AST.IfNode() | AST.WhileNode() | AST.ForNode() | AST.CaseNode():
                impure = True
            case AST.VArgChar() if n.fmt == "Assign":
                impure = True
            case AST.BArgChar():
                impure = True
            case AST.AArgChar():
                impure = True
            case AST.AssignNode():
                impure = True
            ## TODO: If anything other than word return impure immediately
            case _:
                pass

    walk_ast_node(node, visit=visit, replace=None)
    return not impure

def get_safe_to_expand_subtrees(ast):
    subtrees = []
    def replace(n):
        match n:
            case AST.ArgChar():
                return None
            case AST.AstNode() if is_safe_to_expand(n):
                subtrees.append(n)
                return n
            case _:
                return None

    walk_ast(ast, replace=replace)
    return subtrees
