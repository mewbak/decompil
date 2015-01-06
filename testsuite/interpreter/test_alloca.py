from testsuite.utils import *
from testsuite import material

from decompil import interpreter
from decompil.interpreter import LiveValue


@standard_testcase
def test_basic(ctx, func, bld):
    """Test that ALLOCA + STORE + LOAD in a raw works properly."""
    var_addr = bld.build_alloca(ctx.reg_a.type)
    bld.build_store(var_addr, ctx.reg_a.type.create(0))
    bld.build_rstore(
        ctx.reg_b,
        bld.build_load(var_addr)
    )
    bld.build_ret()

    regs = {ctx.reg_a: LiveValue(ctx.reg_a.type, 0)}
    interpreter.run(func, regs)
    assert regs == {
        ctx.reg_a: LiveValue(ctx.reg_a.type, 0),
        ctx.reg_b: LiveValue(ctx.reg_a.type, 0),
    }


@standard_testcase
def test_same_alloca_twice(ctx, func, bld):
    """
    Test that one ALLOCA executed multiple times yields different pointers.
    """
    bb_loop_start = bld.create_basic_block()
    bb_loop_store_1 = bld.create_basic_block()
    bb_loop_store_2 = bld.create_basic_block()
    bb_loop_end = bld.create_basic_block()
    bb_end = bld.create_basic_block()
    i_reg = ctx.reg_a
    reg_1 = ctx.reg_b
    reg_2 = ctx.reg_c

    bld.build_rstore(i_reg, i_reg.type.create(2))
    bld.build_jump(bb_loop_start)

    bld.position_at_end(bb_loop_start)
    var_addr = bld.build_alloca(ctx.double_type)
    var_int  = bld.build_bitcast(reg_1.type, var_addr)
    bld.build_rstore(i_reg, bld.build_sub(
        bld.build_rload(i_reg),
        i_reg.type.create(1)
    ))
    bld.build_branch(
        bld.build_eq(bld.build_rload(i_reg), i_reg.type.create(0)),
        bb_loop_store_1, bb_loop_store_2
    )

    bld.position_at_end(bb_loop_store_1)
    bld.build_rstore(reg_1, var_int)
    bld.build_jump(bb_loop_end)

    bld.position_at_end(bb_loop_store_2)
    bld.build_rstore(reg_2, var_int)
    bld.build_jump(bb_loop_end)

    bld.position_at_end(bb_loop_end)
    bld.build_branch(
        bld.build_ugt(bld.build_rload(i_reg), i_reg.type.create(0)),
        bb_loop_start, bb_end
    )

    bld.position_at_end(bb_end)
    bld.build_ret()

    regs = {}
    interpreter.run(func, regs)
    assert set(regs) == {ctx.reg_a, ctx.reg_b, ctx.reg_c}
    assert regs[ctx.reg_a] == LiveValue(ctx.reg_a.type, 0)
    assert regs[ctx.reg_b] != regs[ctx.reg_c]
