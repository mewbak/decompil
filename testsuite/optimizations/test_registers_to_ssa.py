from testsuite.utils import *

from decompil import interpreter
from decompil.interpreter import LiveValue
from decompil.optimizations.registers_to_ssa import RegistersToSSA


@standard_testcase
def test_empty(ctx, func, bld):
    bld.build_ret()

    RegistersToSSA.process_function(func)
    regs = {}
    assert interpreter.run(func, regs) is None
    assert not regs


@standard_testcase
def test_simple_rstore(ctx, func, bld):
    """
    Test that a simple store still affects the target register after
    optimization.
    """
    value = ctx.reg_a.type.create(42)
    bld.build_rstore(ctx.reg_a, value)
    bld.build_ret()

    run_before_and_after_optimization(
        func, RegistersToSSA,
        {}, {ctx.reg_a: LiveValue.from_value(value)}
    )
