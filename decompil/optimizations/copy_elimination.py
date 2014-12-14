from decompil import ir, optimizations


class CopyElimination(optimizations.Optimization):
    """
    Replace all uses of values computed by COPY instructions with the original
    value.
    """

    @staticmethod
    def get_original_value(value):
        """
        For value computed by a CopyInstruction, return the original value.
        Return the value itself otherwise.
        """
        while isinstance(value.value, ir.CopyInstruction):
            insn = value.value
            value = insn.value
        return value

    @classmethod
    def process_function(cls, function):
        for basic_block in function:
            for insn in basic_block:
                insn.map_inputs(cls.get_original_value)
