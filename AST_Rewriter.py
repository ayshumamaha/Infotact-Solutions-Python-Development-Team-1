import ast


def trace_hook(function_name):
    """Hook executed whenever a function is entered."""
    print(f"[TRACE] Entering function: {function_name}")


class HookInjector(ast.NodeTransformer):
    """Inject trace_hook() into every function."""

    def visit_FunctionDef(self, node):
        self.generic_visit(node)

        hook = ast.Expr(
            value=ast.Call(
                func=ast.Name(id="trace_hook", ctx=ast.Load()),
                args=[ast.Constant(node.name)],
                keywords=[]
            )
        )

        node.body.insert(0, hook)
        return node


def rewrite_code(source_code):
    """Rewrite source code by injecting tracing hooks."""

    tree = ast.parse(source_code)
    tree = HookInjector().visit(tree)
    ast.fix_missing_locations(tree)

    return ast.unparse(tree)


if __name__ == "__main__":

    sample_code = '''
def greet(name):
    print("Hello", name)

def square(x):
    return x * x
'''

    print("========== Original Code ==========\n")
    print(sample_code)

    rewritten = rewrite_code(sample_code)

    print("\n========== Rewritten Code ==========\n")
    print(rewritten)