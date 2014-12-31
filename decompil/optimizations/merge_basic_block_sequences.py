from decompil import ir, optimizations
from decompil.analysis.predecessors import get_predecessors
from decompil.analysis.utils import get_inlined_insns


class MergeBasicBlockSequences(optimizations.Optimization):
    """Merge basic blocks that form sequences."""

    @classmethod
    def process_function(cls, function):
        self = cls(function)
        self._process()

    def __init__(self, function):
        self.function = function
        self.predecessors = get_predecessors(function)

        # Set of indices for basic blocks to remove.
        self.to_remove = set()

    def get_previous_in_sequence(self, bb):
        """
        Return the previous basic block in the sequence `bb` belongs to. Return
        None if it's the first node of this sequence.
        """
        if len(self.predecessors[bb]) != 1:
            return None
        pred = list(self.predecessors[bb])[0]
        if len(pred.successors) != 1:
            return None
        assert {pred} == self.predecessors[bb]
        return pred

    def _process(self):
        processed = set()

        for bb in self.function:
            if bb in processed:
                continue

            # Get the whole sequence `bb` belongs to and mark all basic blocks
            # as processed. There is nothing to do if `bb` is the only node in
            # the sequence.
            sequence = []
            while bb:
                sequence.append(bb)
                processed.add(bb)
                bb = self.get_previous_in_sequence(bb)
            if len(sequence) == 1:
                continue

            # Keep the sequence in some intuitive order (first in sequence =
            # first to be executed).
            sequence.reverse()

            # Strip all JUMP instructions between basic blocks to merge (so
            # keep the last one!).
            for bb in sequence[:-1]:
                bb.remove(len(bb) - 1)

            # Extract the only basic block we will keep afterwards.
            first_bb = sequence.pop(0)
            last_bb = sequence[-1]

            # Update the predecessors database so that the rest of the
            # algorithm works properly and update references to `last_bb` in
            # PHI nodes.
            for succ in last_bb.successors:
                preds = self.predecessors[succ]
                preds.remove(last_bb)
                preds.add(first_bb)

                for root_insn in succ:
                    for insn in get_inlined_insns(root_insn):
                        if insn.kind == ir.PHI:
                            insn.replace_predecessor(last_bb, first_bb)

            # While moving instructions to the first basic block, keep them in
            # the same order as in the sequence.
            for bb in reversed(sequence):
                for insn in bb:
                    first_bb.insert(len(first_bb), insn)
                self.to_remove.add(bb.index)

        # As usual, wait for the end to remove basic blocks in order to keep
        # data consistent during computations.
        for i in reversed(sorted(self.to_remove)):
            self.function.remove(i)
