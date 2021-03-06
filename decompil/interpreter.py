import sys

from decompil import ir, utils


class LiveValue:
    def __init__(self, type, value=None):
        assert value is None or isinstance(value, int)
        assert isinstance(type, (ir.IntType, ir.PointerType, ir.FunctionType))
        self.type = type
        if value is not None:
            self.value = value & (2 ** type.width - 1)
        else:
            self.value = None

    @property
    def is_undef(self):
        return self.value is None

    @property
    def as_signed(self):
        assert not self.is_undef
        if self.value & 2 ** (self.type.width - 1):
            return self.value | (-1 ^ (2 ** self.type.width - 1))
        else:
            return self.value

    @property
    def as_unsigned(self):
        assert not self.is_undef
        return self.value

    @classmethod
    def from_value(self, value):
        return LiveValue(value.type, value.value)

    def __eq__(self, other):
        return (self.type, self.value) == (other.type, other.value)

    def __repr__(self):
        return '<LiveValue {} {}>'.format(
            utils.format_to_str(self.type),
            'undef' if self.is_undef else self.value
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

        # Mapping: int (pointers) -> LiveValue (pointed values)
        # TODO: handle a real memory space, with "unaligned" accesses, etc.
        self.memory = {}
        # Next address ALLOCA will return. TODO: not sure it is a good idea
        # since generated numbers may conflict with "statically allocated
        # storage". Anyway, this interpreter is for testing synthetic
        # testcases, so maybe we can live with it.
        self.next_addr = 1

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
            return LiveValue.from_value(ir_value)

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
        addr_value = self.get_value(insn.source)
        addr = addr_value.as_unsigned

        # Currently, we handle only ALLOCA'd pointers.
        assert addr in self.memory
        slot = self.memory[addr]
        assert slot.type == addr_value.type.pointed

        return slot

    def handle_store(self, insn):
        addr_value = self.get_value(insn.destination)
        addr = addr_value.as_unsigned

        # Currently, we handle only ALLOCA'd pointers.
        assert (
            addr in self.memory
            and self.memory[addr].type == addr_value.type.pointed
        )
        self.memory[addr] = LiveValue.from_value(insn.value)

    def handle_rload(self, insn):
        return self.registers.get(insn.source, LiveValue(insn.source.type))

    def handle_rstore(self, insn):
        self.registers[insn.destination] = self.get_value(insn.value)

    def handle_alloca(self, insn):
        addr = self.next_addr
        self.next_addr += 1

        self.memory[addr] = LiveValue(insn.stored_type)
        return LiveValue(insn.stored_type.pointer, addr)

    def handle_select(self, insn):
        cond = self.get_value(insn.condition)
        return insn.true_value if cond.value else insn.false_value

    def handle_copy(self, insn):
        return self.get_value(insn.value)

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
        ir.ALLOCA: handle_alloca,

        ir.COPY: handle_copy,

        ir.UNDEF: handle_undef,
    }


def run(function, registers):
    interp = Interpreter(function, registers)
    interp.process()
    return interp.return_value
