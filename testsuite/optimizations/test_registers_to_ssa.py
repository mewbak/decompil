from testsuite.utils import *
from testsuite import material

from decompil import interpreter
from decompil.interpreter import LiveValue
from decompil.optimizations.registers_to_ssa import RegistersToSSA


@standard_testcase
def test_empty(ctx, func, bld):
    material.build_empty(ctx, func)
    material.test_empty(ctx, func)

    RegistersToSSA.process_function(func)
    material.test_empty(ctx, func)


@standard_testcase
def test_simple_rstore(ctx, func, bld):
    """
    Test that a simple store still affects the target register after
    optimization.
    """
    material.build_simple_rstore(ctx, func, 42)
    material.test_simple_rstore(ctx, func, 42)

    RegistersToSSA.process_function(func)
    material.test_simple_rstore(ctx, func, 42)


@standard_testcase
def test_load_and_store(ctx, func, bld):
    """Test for chained register load and store."""
    value_before = bld.build_rload(ctx.reg_a)
    value_after = bld.build_add(value_before, ctx.reg_a.type.create(1))
    bld.build_rstore(ctx.reg_a, value_after)
    bld.build_ret()

    run_before_and_after_optimization(
        func, RegistersToSSA,
        {ctx.reg_a: LiveValue(ctx.reg_a.type, 1)},
        {ctx.reg_a: LiveValue(ctx.reg_a.type, 2)}
    )


@standard_testcase
def test_simple_phi(ctx, func, bld):
    material.build_simple_phi(ctx, func)
    material.test_simple_phi(ctx, func)

    RegistersToSSA.process_function(func)
    material.test_simple_phi(ctx, func)


@standard_testcase
def test_simple_loop(ctx, func, bld):
    material.build_simple_loop(ctx, func)
    material.test_simple_loop(ctx, func)

    RegistersToSSA.process_function(func)
    material.test_simple_loop(ctx, func)
