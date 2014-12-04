import sys

from decompil import ir, utils


class LiveValue:
    def __init__(self, type, value):
        assert isinstance(value, int)
        assert isinstance(type, (ir.IntType, ir.PointerType, ir.FunctionType))
        self.type = type
        self.value = value & (2 ** type.width - 1)

    @property
    def as_signed(self):
        if self.value & 2 ** (self.type.width - 1):
            return self.value | (-1 ^ (2 ** self.type.width - 1))
        else:
            return self.value

    @property
    def as_unsigned(self):
        return self.value

    def __eq__(self, other):
        return (self.type, self.value) == (other.type, other.value)

    def __repr__(self):
        return '<LiveValue {} {}>'.format(
            utils.format_to_str(self.type), self.value
        )


class Interpreter:

    def __init__(self, function, registers):
        self.context = function.context
        self.function = function
        self.return_value = None

        # Mapping: register -> current register live value
        self.registers = registers

        # Mapping: ComputingInstruction -> last live value
        # TODO: remove values as they it becomes invalid to used them.
        self.values = {}

        self.last_bb = None
        self.current_bb = function.entry

        self.process()

    def print_regs(self, outf=sys.stdout):
        regs = {reg.name: value.value for reg, value in self.registers.items()}
        for reg in sorted(regs):
            print('{}: {}'.format(reg, regs[reg]), end=', ', file=outf)
        print('', file=outf)

    def process(self):
        next_bb = None

        while self.current_bb:
            for insn in self.current_bb:
                if isinstance(insn, ir.ControlFlowInstruction):
                    ctrl_flow = self.HANDLERS[insn.kind](self, insn)
                    next_bb = ctrl_flow
                    if not next_bb:
                        break
                elif isinstance(insn, ir.ComputingInstruction):
                    self.values[insn] = self.HANDLERS[insn.kind](self, insn)
                else:
                    self.HANDLERS[insn.kind](self, insn)

            self.last_bb = self.current_bb
            self.current_bb = next_bb

    def get_value(self, ir_value):
        if isinstance(ir_value.value, ir.ComputingInstruction):
            return self.values[ir_value.value]
        else:
            return LiveValue(ir_value.type, ir_value.value)

    def handle_jump(self, insn):
        return insn.destination

    def handle_branch(self, insn):
        cond = self.get_value(insn.condition)
        return insn.dest_true if cond.value else insn.dest_false

    def handle_call(self, insn):
        raise NotImplementedError()

    def handle_ret(self, insn):
        if insn.type != self.context.void_type:
            self.return_value = self.get_value(insn.return_value)
        return None

    def handle_phi(self, insn):
        for basic_block, value in insn.pairs:
            if basic_block == self.last_bb:
                return self.get_value(value)
        else:
            assert False

    def handle_zext(self, insn):
        return LiveValue(
            insn.dest_type,
            self.get_value(insn.value).as_unsigned
        )

    def handle_sext(self, insn):
        return LiveValue(
            insn.dest_type,
            self.get_value(insn.value).as_signed
        )

    def handle_trunc(self, insn):
        return LiveValue(
            insn.dest_type,
            self.get_value(insn.value).as_unsigned
        )

    def handle_bitcast(self, insn):
        return LiveValue(
            insn.dest_type,
            self.get_value(insn.value).as_unsigned
        )

    def handle_add(self, insn):
        left = self.get_value(insn.left).as_unsigned
        right = self.get_value(insn.right).as_unsigned
        return LiveValue(insn.type, left + right)

    def handle_sub(self, insn):
        left = self.get_value(insn.left).as_unsigned
        right = self.get_value(insn.right).as_unsigned
        return LiveValue(insn.type, left - right)

    def handle_mul(self, insn):
        left = self.get_value(insn.left).as_unsigned
        right = self.get_value(insn.right).as_unsigned
        return LiveValue(insn.type, left * right)

    def handle_sdiv(self, insn):
        left = self.get_value(insn.left).as_signed
        right = self.get_value(insn.right).as_signed
        return LiveValue(insn.type, left // right)

    def handle_udiv(self, insn):
        left = self.get_value(insn.left).as_unsigned
        right = self.get_value(insn.right).as_unsigned
        return LiveValue(insn.type, left // right)

    def handle_lshl(self, insn):
        left = self.get_value(insn.left).as_unsigned
        right = self.get_value(insn.right).as_unsigned
        return LiveValue(insn.type, left << right)

    def handle_lshr(self, insn):
        left = self.get_value(insn.left).as_unsigned
        right = self.get_value(insn.right).as_unsigned
        return LiveValue(insn.type, left >> right)

    def handle_ashr(self, insn):
        left = self.get_value(insn.left).as_signed
        right = self.get_value(insn.right).as_unsigned
        return LiveValue(insn.type, left >> right)

    def handle_and(self, insn):
        left = self.get_value(insn.left).as_unsigned
        right = self.get_value(insn.right).as_unsigned
        return LiveValue(insn.type, left & right)

    def handle_or(self, insn):
        left = self.get_value(insn.left).as_unsigned
        right = self.get_value(insn.right).as_unsigned
        return LiveValue(insn.type, left | right)

    def handle_xor(self, insn):
        left = self.get_value(insn.left).as_unsigned
        right = self.get_value(insn.right).as_unsigned
        return LiveValue(insn.type, left ^ right)

    def handle_cat(self, insn):
        raise NotImplementedError()

    def handle_eq(self, insn):
        left = self.get_value(insn.left).as_unsigned
        right = self.get_value(insn.right).as_unsigned
        return LiveValue(insn.type, left == right)

    def handle_ne(self, insn):
        left = self.get_value(insn.left).as_unsigned
        right = self.get_value(insn.right).as_unsigned
        return LiveValue(insn.type, left != right)

    def handle_sle(self, insn):
        left = self.get_value(insn.left).as_signed
        right = self.get_value(insn.right).as_signed
        return LiveValue(insn.type, left <= right)

    def handle_slt(self, insn):
        left = self.get_value(insn.left).as_signed
        right = self.get_value(insn.right).as_signed
        return LiveValue(insn.type, left < right)

    def handle_sge(self, insn):
        left = self.get_value(insn.left).as_signed
        right = self.get_value(insn.right).as_signed
        return LiveValue(insn.type, left >= right)

    def handle_sgt(self, insn):
        left = self.get_value(insn.left).as_signed
        right = self.get_value(insn.right).as_signed
        return LiveValue(insn.type, left > right)

    def handle_ule(self, insn):
        left = self.get_value(insn.left).as_unsigned
        right = self.get_value(insn.right).as_unsigned
        return LiveValue(insn.type, left <= right)

    def handle_ult(self, insn):
        left = self.get_value(insn.left).as_unsigned
        right = self.get_value(insn.right).as_unsigned
        return LiveValue(insn.type, left < right)

    def handle_uge(self, insn):
        left = self.get_value(insn.left).as_unsigned
        right = self.get_value(insn.right).as_unsigned
        return LiveValue(insn.type, left >= right)

    def handle_ugt(self, insn):
        left = self.get_value(insn.left).as_unsigned
        right = self.get_value(insn.right).as_unsigned
        return LiveValue(insn.type, left > right)

    def handle_load(self, insn):
        raise NotImplementedError()

    def handle_store(self, insn):
        raise NotImplementedError()

    def handle_rload(self, insn):
        return self.registers[insn.source]

    def handle_rstore(self, insn):
        self.registers[insn.destination] = self.get_value(insn.value)

    def handle_undef(self, insn):
        raise NotImplementedError()

    HANDLERS = {
        ir.JUMP: handle_jump,
        ir.BRANCH: handle_branch,
        ir.CALL: handle_call,
        ir.RET: handle_ret,

        ir.PHI: handle_phi,

        ir.ZEXT: handle_zext,
        ir.SEXT: handle_sext,
        ir.TRUNC: handle_trunc,
        ir.BITCAST: handle_bitcast,

        ir.ADD: handle_add,
        ir.SUB: handle_sub,
        ir.MUL: handle_mul,
        ir.SDIV: handle_sdiv,
        ir.UDIV: handle_udiv,

        ir.LSHL: handle_lshl,
        ir.LSHR: handle_lshr,
        ir.ASHR: handle_ashr,
        ir.AND: handle_and,
        ir.OR: handle_or,
        ir.XOR: handle_xor,
        ir.CAT: handle_cat,

        ir.EQ: handle_eq,
        ir.NE: handle_ne,
        ir.SLE: handle_sle,
        ir.SLT: handle_slt,
        ir.SGE: handle_sge,
        ir.SGT: handle_sgt,
        ir.ULE: handle_ule,
        ir.ULT: handle_ult,
        ir.UGE: handle_uge,
        ir.UGT: handle_ugt,

        ir.LOAD: handle_load,
        ir.STORE: handle_store,
        ir.RLOAD: handle_rload,
        ir.RSTORE: handle_rstore,

        ir.UNDEF: handle_undef,
    }


def run(function, registers):
    interp = Interpreter(function, registers)
    interp.process()
    return interp.return_value
