import collections
import functools

import nose.tools

from decompil import ir, builder
from decompil.analysis import dominance


Node = collections.namedtuple('Node', 'value children')

class Register(ir.Register):
    def __init__(self, context, name):
        super(Register, self).__init__()
        self.type = context.create_int_type(32)
        self.name = name

class Context(ir.Context):
    def __init__(self):
        super(Context, self).__init__(32)
        self.reg_a = Register(self, 'ra')
        self.reg_b = Register(self, 'rb')
        self.reg_c = Register(self, 'rc')
        self.reg_d = Register(self, 'rd')


def tree_to_nodes(tree):
    """
    Convert a decompil.analysis.Tree into a recursive Node structure.

    It makes it easier to write literals for trees in testcases.
    """
    def get_node(tree_node):
        return Node(
            tree_node.value,
            {n: get_node(tree.nodes[n]) for n in tree_node.children}
        )
    return get_node(tree.root)


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


@standard_testcase
def test_dominance_single(ctx, func, bld):
    bld.build_ret()

    rev_dom_tree = tree_to_nodes(dominance.get_dominator_tree(func))
    assert rev_dom_tree == Node(func.entry, {})


@standard_testcase
def test_dominance_chained_1(ctx, func, bld):
    bb = func.create_basic_block()
    bld.build_jump(bb)

    bld.position_at_end(bb)
    bld.build_ret()

    rev_dom_tree = tree_to_nodes(dominance.get_dominator_tree(func))
    assert rev_dom_tree == Node(func.entry, {
        bb: Node(bb, {}),
    })


@standard_testcase
def test_dominance_chained_2(ctx, func, bld):
    bb_A = func.create_basic_block()
    bb_B = func.create_basic_block()
    bld.build_jump(bb_A)

    bld.position_at_end(bb_A)
    bld.build_jump(bb_B)

    bld.position_at_end(bb_B)
    bld.build_ret()

    rev_dom_tree = tree_to_nodes(dominance.get_dominator_tree(func))
    assert rev_dom_tree == Node(func.entry, {
        bb_A: Node(bb_A, {
            bb_B: Node(bb_B, {}),
        }),
    })


@standard_testcase
def test_dominance_diamond(ctx, func, bld):
    bb_A = func.create_basic_block()
    bb_B = func.create_basic_block()
    bb_C = func.create_basic_block()
    reg_a_val = bld.build_rload(ctx.reg_a)
    bld.build_branch(
        bld.build_eq(reg_a_val, reg_a_val.type.create(0)),
        bb_A, bb_B
    )

    bld.position_at_end(bb_A)
    bld.build_jump(bb_C)

    bld.position_at_end(bb_B)
    bld.build_jump(bb_C)

    bld.position_at_end(bb_C)
    bld.build_ret()

    rev_dom_tree = tree_to_nodes(dominance.get_dominator_tree(func))
    assert rev_dom_tree == Node(func.entry, {
        bb_A: Node(bb_A, {}),
        bb_B: Node(bb_B, {}),
        bb_C: Node(bb_C, {}),
    })


@standard_testcase
def test_dominance_loop_simple(ctx, func, bld):
    bb_A = func.create_basic_block()
    bb_B = func.create_basic_block()
    bld.build_jump(bb_A)

    bld.position_at_end(bb_A)
    reg_a_val = bld.build_rload(ctx.reg_a)
    bld.build_branch(
        bld.build_eq(reg_a_val, reg_a_val.type.create(0)),
        bb_A, bb_B
    )

    bld.position_at_end(bb_B)
    bld.build_ret()

    rev_dom_tree = tree_to_nodes(dominance.get_dominator_tree(func))
    assert rev_dom_tree == Node(func.entry, {
        bb_A: Node(bb_A, {
            bb_B: Node(bb_B, {}),
        }),
    })
