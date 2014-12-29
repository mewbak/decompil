from collections import defaultdict

from decompil import ir


def get_uses(func):
    """
    Return the uses of all computing instructions in `func` as a mapping
    (computing instructions -> set of instructions using it).
    """

    uses = defaultdict(set)
    for bb in func:
        for insn in bb:
            for value in insn.inputs:
                input = value.value
                if isinstance(input, ir.ComputingInstruction):
                    uses[input].add(insn)
    return uses
