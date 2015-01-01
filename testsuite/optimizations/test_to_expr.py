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


@standard_testcase
def test_inline_multiple_sub_insns(ctx, func, bld):
    """
    Test that the ToExpr pass does not inline an instruction when it is
    referenced twice from the same expression.
    """
    a_val = bld.build_rload(ctx.reg_a)
    tmp1 = bld.build_add(a_val, a_val.type.create(1))
    tmp2 = bld.build_mul(tmp1, tmp1.type.create(2))
    tmp3 = bld.build_mul(tmp1, tmp2)
    bld.build_rstore(ctx.reg_b, tmp3)
    bld.build_rstore(ctx.reg_c, tmp3)

    # A first pass should turn the above into:
    #   %0 = rload reg_a
    #   %1 = %0 + 1
    #   %2 = %1 * (%1 * 2)
    #   rstore %2 to reg_b
    #   rstore %2 to reg_c
    # But the second pass should not be able to inline %0 into %1.
    for _ in range(2):
        ToExpr.process_function(func)
        # TODO: from decompil.utils import format_to_str
        # TODO: print(format_to_str(func.entry))
        assert len(func.entry) == 5
