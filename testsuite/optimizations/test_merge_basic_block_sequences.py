from testsuite.utils import *
from testsuite import material

from decompil import interpreter
from decompil.interpreter import LiveValue
from decompil.optimizations.merge_basic_block_sequences import (
    MergeBasicBlockSequences,
)


@standard_testcase
def test_nop(ctx, func, bld):
    """Test correctness with a single basic block."""
    material.build_simple_rstore(ctx, func, 1)

    run_before_and_after_optimization(
        func, MergeBasicBlockSequences,
        {},
        {ctx.reg_a: LiveValue(ctx.reg_a.type, 1)}
    )
    assert len(func) == 1


@standard_testcase
def test_sequence_2(ctx, func, bld):
    """Test correctness and completeness with two chained basic blocks."""
    bb_next = bld.create_basic_block()

    a_val = bld.build_rload(ctx.reg_a)
    bld.build_jump(bb_next)

    bld.position_at_end(bb_next)
    bld.build_rstore(ctx.reg_b, bld.build_add(a_val, a_val.type.create(1)))
    bld.build_ret()

    run_before_and_after_optimization(
        func, MergeBasicBlockSequences,
        {ctx.reg_a: LiveValue(ctx.reg_a.type, 1)},
        {ctx.reg_a: LiveValue(ctx.reg_a.type, 1),
         ctx.reg_b: LiveValue(ctx.reg_a.type, 2)},
    )
    assert len(func) == 1


@standard_testcase
def test_sequence_3(ctx, func, bld):
    """Test correctness and completeness with three chained basic blocks."""
    bb_next = bld.create_basic_block()
    bb_end = bld.create_basic_block()

    a_val = bld.build_rload(ctx.reg_a)
    bld.build_jump(bb_next)

    bld.position_at_end(bb_next)
    b_val = bld.build_add(a_val, a_val.type.create(1))
    bld.build_jump(bb_end)

    bld.position_at_end(bb_end)
    bld.build_rstore(ctx.reg_b, b_val)
    bld.build_ret()

    run_before_and_after_optimization(
        func, MergeBasicBlockSequences,
        {ctx.reg_a: LiveValue(ctx.reg_a.type, 1)},
        {ctx.reg_a: LiveValue(ctx.reg_a.type, 1),
         ctx.reg_b: LiveValue(ctx.reg_a.type, 2)},
    )
    assert len(func) == 1


@standard_testcase
def test_reverse_sequence_3(ctx, func, bld):
    """
    Test correctness and completeness with three chained basic blocks.

    The pecularity of this testcase is that basic blocks are not created in the
    "execution order". This was known to trigger invalid instructions
    scheduling in the merged basic block.
    """
    bb_end = bld.create_basic_block()
    bb_next = bld.create_basic_block()

    a_val = bld.build_rload(ctx.reg_a)
    bld.build_jump(bb_next)

    bld.position_at_end(bb_next)
    b_val = bld.build_add(a_val, a_val.type.create(1))
    bld.build_jump(bb_end)

    bld.position_at_end(bb_end)
    bld.build_rstore(ctx.reg_b, b_val)
    bld.build_ret()

    run_before_and_after_optimization(
        func, MergeBasicBlockSequences,
        {ctx.reg_a: LiveValue(ctx.reg_a.type, 1)},
        {ctx.reg_a: LiveValue(ctx.reg_a.type, 1),
         ctx.reg_b: LiveValue(ctx.reg_a.type, 2)},
    )
    assert len(func) == 1
