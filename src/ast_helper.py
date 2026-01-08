import shasta.ast_node as AST

##
## Auxiliary functions for ASTs
##

def string_to_argchars(text):
    return [AST.CArgChar(ord(ch)) for ch in text]

def walk_node(node):
    return node

def walk_ast(ast, visit=None, replace=None):
    return [walk_ast_node(node, visit=visit, replace=replace) for node, _, _, _ in ast]

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
        case _:
            return node
