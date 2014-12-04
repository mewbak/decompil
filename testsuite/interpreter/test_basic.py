from testsuite.utils import *

from decompil import interpreter
from decompil.interpreter import LiveValue


@standard_testcase
def test_empty(ctx, func, bld):
    bld.build_ret()
    assert interpreter.run(func, {}) is None


# TODO: return values not handled yet.
# @standard_testcase
# def test_return_constant(ctx, func, bld):
#     value = ctx.byte_type.create(42)
#     bld.build_ret(value)
#     assert interpreter.run(func, {}) == value


@standard_testcase
def test_simple_rstore(ctx, func, bld):
    value = LiveValue(ctx.reg_a.type, 42)
    bld.build_rstore(ctx.reg_a, value)
    bld.build_ret()

    regs = {}
    interpreter.run(func, regs)
    assert regs[ctx.reg_a] == value


@standard_testcase
def test_simple_phi(ctx, func, bld):
    bb_true = bld.create_basic_block()
    bb_false = bld.create_basic_block()
    bb_end = bld.create_basic_block()

    bld.build_branch(
        bld.build_ne(
            bld.build_rload(ctx.reg_a),
            ctx.reg_a.type.create(0)
        ),
        bb_true, bb_false
    )

    bld.position_at_end(bb_true)
    value_true = bld.build_rload(ctx.reg_b)
    bld.build_jump(bb_end)

    bld.position_at_end(bb_false)
    value_false = bld.build_rload(ctx.reg_c)
    bld.build_jump(bb_end)

    bld.position_at_end(bb_end)
    value_end = bld.build_phi([
        (bb_true, value_true),
        (bb_false, value_false),
    ])
    bld.build_rstore(ctx.reg_d, value_end)
    bld.build_ret()

    base_regs = {
        ctx.reg_b: LiveValue(ctx.reg_b.type, 1),
        ctx.reg_c: LiveValue(ctx.reg_c.type, 2),
    }
    regs = dict(base_regs)
    regs[ctx.reg_a] = LiveValue(ctx.reg_b.type, 1)
    interpreter.run(func, regs)
    assert regs[ctx.reg_d] == base_regs[ctx.reg_b]

    regs = dict(base_regs)
    regs[ctx.reg_a] = LiveValue(ctx.reg_b.type, 0)
    interpreter.run(func, regs)
    assert regs[ctx.reg_d] == base_regs[ctx.reg_c]


@standard_testcase
def test_loop(ctx, func, bld):
    bb_cond = bld.create_basic_block()
    bb_loop = bld.create_basic_block()
    bb_end = bld.create_basic_block()

    n = bld.build_rload(ctx.reg_a)
    i_start = ctx.reg_a.type.create(0)
    result_start = ctx.reg_a.type.create(1)
    bld.build_jump(bb_cond)

    bld.position_at_end(bb_cond)
    i_cond = bld.build_phi([
        (func.entry, i_start),
        (bb_loop,    None),
    ])
    result_cond = bld.build_phi([
        (func.entry, result_start),
        (bb_loop,    None),
    ])
    bld.build_branch(
        bld.build_ult(i_cond, n),
        bb_loop, bb_end
    )

    bld.position_at_end(bb_loop)
    i_loop = bld.build_add(i_cond, ctx.reg_a.type.create(1))
    result_loop = bld.build_mul(result_cond, ctx.reg_a.type.create(2))
    bld.build_jump(bb_cond)

    i_cond.value.set_value(bb_loop, i_loop)
    result_cond.value.set_value(bb_loop, result_loop)

    bld.position_at_end(bb_end)
    bld.build_rstore(ctx.reg_b, result_cond)
    bld.build_ret()

    regs = {ctx.reg_a: LiveValue(ctx.reg_a.type, 0)}
    interpreter.run(func, regs)
    assert regs[ctx.reg_b] == LiveValue(ctx.reg_b.type, 1)

    regs = {ctx.reg_a: LiveValue(ctx.reg_a.type, 1)}
    interpreter.run(func, regs)
    assert regs[ctx.reg_b] == LiveValue(ctx.reg_b.type, 2)

    regs = {ctx.reg_a: LiveValue(ctx.reg_a.type, 2)}
    interpreter.run(func, regs)
    assert regs[ctx.reg_b] == LiveValue(ctx.reg_b.type, 4)
