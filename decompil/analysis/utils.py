from decompil import ir


def get_inlined_insns(root_insn):
    """Return the set of all inlined instructions in `root_insn` (included)."""
    result = set()

    def helper(insn):
        result.add(insn)
        for input in insn.inputs:
            if (
                isinstance(input.value, ir.ComputingInstruction)
                and input.value.inline
            ):
                helper(input.value)

    helper(root_insn)
    return result
