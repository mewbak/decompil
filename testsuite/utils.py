import functools

import nose.tools
from pygments.token import *

from decompil import builder, ir


class Register(ir.Register):
    def __init__(self, context, name):
        super(Register, self).__init__()
        self.type = context.create_int_type(32)
        self.name = name

    def format(self):
        return [(Name.Variable, self.name)]

    def __repr__(self):
        return '<Register {} {}>'.format(
            ''.join(text for _, text in self.type.format()),
            self.name
        )


class Context(ir.Context):
    def __init__(self):
        super(Context, self).__init__(32)
        self.reg_a = Register(self, 'ra')
        self.reg_b = Register(self, 'rb')
        self.reg_c = Register(self, 'rc')
        self.reg_d = Register(self, 'rd')


@nose.tools.nottest
def standard_testcase(func):
    @functools.wraps(func)
    def wrapper():
        ctx = Context()
        func_obj = ctx.create_function(0)
        bld = builder.Builder()
        bld.position_at_end(func_obj.entry)
        return func(ctx, func_obj, bld)
    return wrapper
