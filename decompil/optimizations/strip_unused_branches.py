from collections import namedtuple

from decompil import ir, optimizations
from decompil.analysis.predecessors import get_predecessors
from decompil.analysis.utils import get_inlined_insns


# Holder for the pattern matching below (see
# StripUnusedBranches.match_if_pattern). We are looking for an IF/THEN(/ELSE)
# basic block pattern corresponding to some BRANCH node.
PatternMatch = namedtuple('PatternMatch', 'then_bb else_bb next_bb')


class StripUnusedBranches(optimizations.Optimization):
    """
    Remove branches and merge basic blocks when destination basic blocks are
    empty and no PHI node references them.
    """

    @classmethod
    def process_function(cls, function):
        self = cls(function)
        self._process()

    def __init__(self, function):
        self.function = function
        self.predecessors = get_predecessors(function)

    def _process(self):
        # Set of indices for basic blocks to remove.
        to_remove = set()

        for i, bb in enumerate(self.function):
            # Match all basic blocks that ends with a (conditional) BRANCH...
            last_insn = bb[-1]
            last_insn_index = len(bb) - 1
            if last_insn.kind != ir.BRANCH:
                continue
            dest_true, dest_false = last_insn.dest_true, last_insn.dest_false

            # ... that form an IF/THEN(/ELSE) pattern.
            match = (
                self.match_if_pattern(dest_true, dest_false)
                or self.match_if_pattern(dest_false, dest_true)
            )
            if not match:
                continue

            # Before removing the THEN/ELSE basic blocks, make sure they do not
            # compute anything[1] and that they are not referenced by PHI
            # nodes.
            # [1] The last instruction of a basic block is always a control
            # flow instruction. If there was a match, we know it's a JUMP so
            # if there is only 1 instruction, it does not compute anything.
            if not (
                (len(match.then_bb) == 1
                    and not self.is_referenced(match.then_bb))
                and (
                    match.else_bb is None
                    or (len(match.else_bb) == 1
                        and not self.is_referenced(match.else_bb)))
            ):
                continue

            # Remove empty basic blocks and reduce the BRANCH to a simple JUMP.
            to_remove.add(match.then_bb.index)
            if match.else_bb:
                to_remove.add(match.else_bb.index)
            bb.replace(last_insn_index, ir.ControlFlowInstruction(
                self.function, ir.JUMP, match.next_bb, origin=last_insn.origin)
            )

            # TODO: we probably leave here simply chained basic blocks: the new
            # JUMP instructions are often the only predecessor of
            # `match.next_bb`. A pass that merges such patterns would be great.

        # As usual, remove basic blocks at the end to preserve index validity
        # during computations/iterations.
        for i in reversed(sorted(to_remove)):
            self.function.remove(i)


    def is_referenced(self, bb):
        """Return whether `bb` is referenced by a PHI node."""

        def is_referenced_in_insn(root_insn):
            """
            Return whether `bb` is referenced by a PHI node in `insn` and all
            the inlined instructions it contains.
            """
            for insn in get_inlined_insns(root_insn):
                if insn.kind == ir.PHI:
                    for orig_bb, _ in insn.pairs:
                        if bb == orig_bb:
                            return True
            else:
                return False

        return any(
            any(is_referenced_in_insn(insn) for insn in succ_bb)
            for succ_bb in bb.successors
        )


    def match_if_pattern(self, left, right):
        """
        Match an IF/THEN(/ELSE) pattern. IF there is a match, return a
        PatternMatch instance. Return None otherwise.

        Given some BRANCH node, `left` and `right` must be its two destination
        basic blocks. Their order matters so one shoudlr also try to match
        after switching them.
        """

        # Assume `left` is the THEN basic block.
        if len(self.predecessors[left]) != 1 or len(left.successors) != 1:
            return None
        then_bb = left
        next_bb = list(left.successors)[0]

        # Look for an ELSE-less pattern...
        if next_bb == right:
            else_bb = None
        # ... for a complete one...
        elif (
            len(self.predecessors[right]) == 1
            and len(right.successors) == 1
            and list(right.successors)[0] == next_bb
        ):
            else_bb = right
        # ... or abort.
        else:
            return None

        return PatternMatch(then_bb, else_bb, next_bb)
