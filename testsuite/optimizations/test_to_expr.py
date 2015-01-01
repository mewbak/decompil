from testsuite.utils import *

from decompil import interpreter
from decompil.interpreter import LiveValue
from decompil.optimizations.to_expr import ToExpr


@standard_testcase
def test_inline_loads(ctx, func, bld):
    """Test that the ToExpr pass does not move LOAD/RLOAD operations."""
    a_val = bld.build_rload(ctx.reg_a)
    bld.build_rstore(ctx.reg_a, a_val.type.create(0))
    bld.build_rstore(ctx.reg_b, a_val)

    # The optimization should not move the RLOAD instruction, even though it is
    # used only once: while reaching its use, the corresponding register value
    # has changed.
    run_before_and_after_optimization(
        func, ToExpr,
        {ctx.reg_a: LiveValue(ctx.reg_a.type, 1)},
        {ctx.reg_a: LiveValue(ctx.reg_a.type, 0),
         ctx.reg_b: LiveValue(ctx.reg_a.type, 1)}
    )
