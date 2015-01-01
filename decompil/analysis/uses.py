from collections import defaultdict

from decompil import ir
from decompil.analysis.utils import get_inlined_insns


def get_uses(func):
    """
    Return the uses of all computing instructions in `func` as a mapping
    (computing instructions -> set of instructions using it).
    """

    uses = defaultdict(set)
    for bb in func:
        for insn in bb:
            for sub_insn in get_inlined_insns(insn):
                for value in sub_insn.inputs:
                    input = value.value
                    if isinstance(input, ir.ComputingInstruction):
                        uses[input].add(sub_insn)
    return uses
