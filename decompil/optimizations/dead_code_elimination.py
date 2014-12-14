from decompil import ir, optimizations


class DeadCodeElimination(optimizations.Optimization):
    """
    Remove all unused instructions and basic blocks.
    """

    @classmethod
    def process_function(cls, function):
        self = cls(function)
        self._process()

    def __init__(self, function):
        self.function = function
        self.used_instructions = set()

    def _process(self):
        # First pass: compute the set of all used instructions. These are the
        # instructions that either:
        #  - return no value;
        #  - return a value that is used by another used instruction.
        for basic_block in self.function:
            for insn in basic_block:
                if not isinstance(insn, ir.ComputingInstruction):
                    self.mark_used(insn)

        # Second pass: remove all instructions that are not used.
        for basic_block in self.function:
            to_remove = []
            for i, insn in enumerate(basic_block):
                if insn not in self.used_instructions:
                    to_remove.append(i)
            for i in reversed(to_remove):
                basic_block.remove(i)

        # TODO: remove unused basic blocks

    def mark_used(self, insn):
        if insn in self.used_instructions:
            return
        self.used_instructions.add(insn)
        for value in insn.inputs:
            if isinstance(value.value, ir.ComputingInstruction):
                self.mark_used(value.value)
