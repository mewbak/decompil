from decompil import ir, optimizations
from decompil.analysis.uses import get_uses
from decompil.analysis.utils import get_inlined_insns


class ToExpr(optimizations.Optimization):

    @classmethod
    def process_function(cls, function):
        # Inline all computing instructions whose result is used only once.
        uses = get_uses(function)

        for bb in function:
            # Inlining is done in two steps: tag the instruction as such and
            # remove it from its basic block.
            to_remove = []
            for i, insn in enumerate(bb):
                # Do not inline:
                #   - instructions that are used more than once;
                #   - LOAD/RLOAD ones;
                #   - PHI ones when it would violate the SSA rules.
                # TODO: for LOAD/RLOAD instruction, *maybe* it would be
                # interesting to enable inlining when we know the register has
                # not changed at the destination.
                if len(uses[insn]) != 1 or insn.kind in (ir.LOAD, ir.RLOAD):
                    continue
                consumer = list(uses[insn])[0]

                phi_nodes = cls.get_phi_nodes(insn)
                if any(
                    cls.get_container_bb(function, node) != bb
                    for node in phi_nodes
                ):
                    continue

                insn.inline = True
                to_remove.append(i)

            for i in reversed(to_remove):
                bb.remove(i)

        function.form = function.FORM_EXPR

    @classmethod
    def get_container_bb(cls, function, insn):
        """
        Return the basic block that contains `insn`. Don't dive into
        expressions.
        """
        for bb in function:
            if insn in bb:
                return bb
        else:
            assert False

    @classmethod
    def get_phi_nodes(cls, insn):
        """
        Return all PHI nodes inlined in `insn` (root instruction included).
        """
        return set(
            insn for insn in get_inlined_insns(insn)
            if insn.kind == ir.PHI
        )
