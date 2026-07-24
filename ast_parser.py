import ast
import os


class AssignmentFinder(ast.NodeVisitor):
    def __init__(self):
        self.assignments = []

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.assignments.append((node.lineno, target.id))
        self.generic_visit(node)


def scan_file(filepath: str) -> list[tuple[int, str]]:
    with open(filepath, "r") as f:
        source = f.read()

    tree = ast.parse(source)
    finder = AssignmentFinder()
    finder.visit(tree)
    return finder.assignments


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_path = os.path.join(script_dir, "target_script.py")

    results = scan_file(target_path)
    for line_no, var_name in results:
        print(f"Line {line_no}: {var_name}")