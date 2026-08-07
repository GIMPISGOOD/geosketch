"""脚本作用域与用户函数。"""

MISSING = object()


class UserFunction:
    def __init__(self, name, params, body, closure_scope):
        self.name = name
        self.params = params
        self.body = body
        self.closure_scope = closure_scope


class Scope:
    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent

    def find(self, name):
        if name in self.vars:
            return self.vars[name]

        if self.parent is not None:
            return self.parent.find(name)

        return MISSING

    def set_local(self, name, value):
        self.vars[name] = value

    def set_global(self, name, value):
        root = self

        while root.parent is not None:
            root = root.parent

        root.vars[name] = value

    def get_global_scope(self):
        root = self

        while root.parent is not None:
            root = root.parent

        return root