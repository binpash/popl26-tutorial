import shasta.ast_node as AST

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
            case AST.ForNode():
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