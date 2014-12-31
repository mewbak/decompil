from collections import namedtuple

from decompil import ir, optimizations
from decompil.analysis.predecessors import get_predecessors


# Holder for the pattern matching below (see
# BinaryPhiToSelect.match_if_pattern). We are looking for an IF/THEN(/ELSE)
# basic blocks pattern corresponding to some PHI node.
PatternMatch = namedtuple('PatternMatch',
    # A ComputingInstruction that evaluates the IF condition.
    'condition'
    # When reaching the PHI node, these are the predecessor basic blocks
    # corresponding to the decision made at the condition.
    ' then_pred_bb'
    ' else_pred_bb'
)


class BinaryPhiToSelect(optimizations.Optimization):
    """
    Turn as many PHI nodes with two inputs into SELECT ones as possible.

    Note that this pass makes the IR invalid as a true SSA representation: the
    resulting SELECT nodes reference values defined in basic blocks that don't
    dominate them.
    """

    # TODO: maybe allow this pass only in FORM_EXPR mode and create SELECT
    # nodes only when they don't violate SSA.

    @classmethod
    def process_function(cls, function):
        self = cls(function)
        self._process()

    def __init__(self, function):
        self.function = function
        self.predecessors = get_predecessors(function)

    def _process(self):
        # We are lazy here and don't traverse instructions in depth.
        assert self.function.form == ir.Function.FORM_PURE

        for bb in self.function:
            # We work only on PHI nodes that have two inputs, so we need
            # exactly two predecessors.
            predecessors = self.predecessors[bb]
            if len(predecessors) != 2:
                continue

            # Look for an IF pattern.
            pred_left, pred_right = predecessors
            match = (
                self.match_if_pattern(pred_left, pred_right)
                or self.match_if_pattern(pred_right, pred_left)
            )
            if not match:
                continue

            # Now, precess PHI nodes in `bb`.
            for i, insn in enumerate(bb):
                if insn.kind != ir.PHI:
                    continue

                # Associate values to THEN/ELSE edges.
                then_value = else_value = None
                for orig_bb, value in insn.pairs:
                    if orig_bb == match.then_pred_bb:
                        then_value = value
                    elif orig_bb == match.else_pred_bb:
                        else_value = value
                assert then_value and else_value

                # Finally replace the PHI nodes with a SELECT one!
                select_node = ir.SelectInstruction(
                    self.function, match.condition, then_value, else_value,
                    origin=insn.origin,
                )
                bb.replace(i, select_node)
                self.function.replace_value(
                    insn.as_value, select_node.as_value)

    def match_if_pattern(self, left, right):
        """
        Match an IF/THEN(/ELSE) pattern. If there is a match, return a
        PatternMatch instance. Return None otherwise.

        Given some basic block, `left` and `right` must be its two
        predecessors. Their order matters, so one should also try to match
        after switching them.
        """
        left_preds = self.predecessors[left]
        right_preds = self.predecessors[right]

        # Assume `left` is the THEN basic block.
        if len(left_preds) != 1:
            return None
        left_pred = list(left_preds)[0]
        origin_bb = left_pred

        if not (
            # If the following is true, there is no ELSE basic block.
            left_pred == right
            # Otherwise, if the following is true we have an ELSE basic block.
            or (len(right_preds) == 1 and left_pred == list(right_preds)[0])
        ):
            return None

        cond_branch = origin_bb[-1]
        if cond_branch.kind != ir.BRANCH:
            return None

        return PatternMatch(cond_branch.condition, left, right)
