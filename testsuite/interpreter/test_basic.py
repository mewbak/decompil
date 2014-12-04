from testsuite.utils import *
from testsuite import material

from decompil import interpreter
from decompil.interpreter import LiveValue


@standard_testcase
def test_empty(ctx, func, bld):
    material.build_empty(ctx, func)
    material.test_empty(ctx, func)


@standard_testcase
def test_load_undef(ctx, func, bld):
    zero = ctx.reg_a.type.create(0)
    bld.build_rload(ctx.reg_a)
    bld.build_rstore(ctx.reg_a, zero)
    bld.build_ret()

    regs = {}
    interpreter.run(func, regs)
    assert regs == {ctx.reg_a: LiveValue.from_value(zero)}


@standard_testcase
def test_store_undef(ctx, func, bld):
    undef_value = bld.build_rload(ctx.reg_a)
    bld.build_rstore(ctx.reg_b, undef_value)
    bld.build_ret()

    regs = {}
    interpreter.run(func, regs)
    print(regs)
    assert regs == {ctx.reg_b: LiveValue(ctx.reg_a.type)}


@standard_testcase
def test_use_undef(ctx, func, bld):
    undef_value = bld.build_rload(ctx.reg_a)
    error_value = bld.build_add(undef_value, undef_value)
    bld.build_rstore(ctx.reg_b, error_value)
    bld.build_ret()
    try:
        interpreter.run(func, {})
    except AssertionError:
        pass
    else:
        assert False


# TODO: return values not handled yet.
# @standard_testcase
# def test_return_constant(ctx, func, bld):
#     value = ctx.byte_type.create(42)
#     bld.build_ret(value)
#     assert interpreter.run(func, {}) == value


@standard_testcase
def test_simple_rstore(ctx, func, bld):
    material.build_simple_rstore(ctx, func, 42)
    material.test_simple_rstore(ctx, func, 42)


@standard_testcase
def test_simple_phi(ctx, func, bld):
    material.build_simple_phi(ctx, func)
    material.test_simple_phi(ctx, func)


@standard_testcase
def test_loop(ctx, func, bld):
    material.build_simple_loop(ctx, func)
    material.test_simple_loop(ctx, func)


@standard_testcase
def test_asymetric_phi(ctx, func, bld):
    material.build_asymetric_phi(ctx, func)
    material.test_asymetric_phi(ctx, func)
