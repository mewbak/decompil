from collections import defaultdict

from decompil import ir


def get_predecessors(func, allow_incomplete=False):
    """Compute and return all basic block predecessors as a mapping."""

    predecessors = defaultdict(set)
    for bb in func:
        for succ in bb.get_successors(allow_incomplete):
            predecessors[succ].add(bb)
    return predecessors
