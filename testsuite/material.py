import functools

from decompil import builder, interpreter
from decompil.interpreter import LiveValue


def with_builder(func):
    @functools.wraps(func)
    def wrapper(ctx, func_obj, *args, **kwargs):
        bld = builder.Builder()
        bld.position_at_end(func_obj.entry)
        return func(ctx, func_obj, bld, *args, **kwargs)
    return wrapper


@with_builder
def build_empty(ctx, func, bld):
    # ret
    bld.build_ret()


def test_empty(ctx, func):
    regs = {}
    assert interpreter.run(func, regs) is None
    assert not regs


@with_builder
def build_simple_rstore(ctx, func, bld, i):
    # rstore 42 to $reg_a
    # ret
    value = ctx.reg_a.type.create(i)
    bld.build_rstore(ctx.reg_a, value)
    bld.build_ret()


def test_simple_rstore(ctx, func, i):
    regs = {}
    interpreter.run(func, regs)
    assert regs == {ctx.reg_a: LiveValue(ctx.reg_a.type, i)}


@with_builder
def build_simple_phi(ctx, func, bld):
    # %bb_0:
    #   %0 = rload $reg_a
    #   %1 = %0 != 0
    #   branch if %1 then %bb_1 else %bb_2
    # %bb_1:
    #   %2 = rload $reg_b
    #   jump to %bb_3
    # %bb_2:
    #   %3 = rload $reg_c
    #   jump to %bb_3
    # %bb_3:
    #   %4 = phi %bb_1 => %2, %bb_2 => %3
    #   rstore %4 to %reg_d
    #   ret

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


def test_simple_phi(ctx, func):
    base_regs = {
        ctx.reg_b: LiveValue(ctx.reg_b.type, 1),
        ctx.reg_c: LiveValue(ctx.reg_c.type, 2),
    }
    regs = dict(base_regs)
    regs[ctx.reg_a] = LiveValue(ctx.reg_b.type, 1)
    interpreter.run(func, regs)
    assert regs == {
        ctx.reg_a: LiveValue(ctx.reg_a.type, 1),
        ctx.reg_b: base_regs[ctx.reg_b],
        ctx.reg_c: base_regs[ctx.reg_c],
        ctx.reg_d: base_regs[ctx.reg_b],
    }

    regs = dict(base_regs)
    regs[ctx.reg_a] = LiveValue(ctx.reg_b.type, 0)
    interpreter.run(func, regs)
    assert regs == {
        ctx.reg_a: LiveValue(ctx.reg_a.type, 0),
        ctx.reg_b: base_regs[ctx.reg_b],
        ctx.reg_c: base_regs[ctx.reg_c],
        ctx.reg_d: base_regs[ctx.reg_c],
    }


@with_builder
def build_simple_loop(ctx, func, bld):
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


def test_simple_loop(ctx, func):
    regs = {ctx.reg_a: LiveValue(ctx.reg_a.type, 0)}
    interpreter.run(func, regs)
    assert regs == {
        ctx.reg_a: LiveValue(ctx.reg_a.type, 0),
        ctx.reg_b: LiveValue(ctx.reg_b.type, 1),
    }

    regs = {ctx.reg_a: LiveValue(ctx.reg_a.type, 1)}
    interpreter.run(func, regs)
    assert regs == {
        ctx.reg_a: LiveValue(ctx.reg_a.type, 1),
        ctx.reg_b: LiveValue(ctx.reg_b.type, 2),
    }

    regs = {ctx.reg_a: LiveValue(ctx.reg_a.type, 2)}
    interpreter.run(func, regs)
    assert regs == {
        ctx.reg_a: LiveValue(ctx.reg_a.type, 2),
        ctx.reg_b: LiveValue(ctx.reg_b.type, 4),
    }
