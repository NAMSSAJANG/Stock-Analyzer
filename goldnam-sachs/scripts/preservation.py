"""Normalize relocation and static typing only, retaining executable AST."""

import ast
import hashlib


class Normalize(ast.NodeTransformer):
    def visit_Import(self, node):
        return None

    def visit_ImportFrom(self, node):
        return None

    def visit_FunctionDef(self, node):
        node.returns = None
        self.generic_visit(node)
        return node

    def visit_arg(self, node):
        node.annotation = None
        return node

    def visit_AnnAssign(self, node):
        if node.value is None:
            # Preserve dataclass fields and their original annotation separately.
            return node
        return self.visit(ast.Assign(targets=[node.target], value=node.value))

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == "cast":
            return self.visit(node.args[1])
        return self.generic_visit(node)


def fingerprints(source):
    tree = Normalize().visit(ast.parse(source))
    result = {}
    for index, node in enumerate(tree.body):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue  # Module description only; function docstrings remain checked.
        key = getattr(node, "name", None)
        if key is None and isinstance(node, ast.Assign):
            key = ast.unparse(node.targets[0])
        key = key or f"statement:{index}"
        result[key] = hashlib.sha256(ast.dump(node).encode()).hexdigest()
    return result
