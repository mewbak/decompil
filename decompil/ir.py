from pygments.token import *

from decompil import utils

class Context:

    def __init__(self, pointer_width):
        self.functions = {}

        self.pointer_width = pointer_width

        self.void_type = VoidType(self)
        self.boolean_type = IntType(self, 1)
        self.byte_type = IntType(self, 8)
        self.half_type = IntType(self, 16)
        self.word_type = IntType(self, 32)
        self.double_type = IntType(self, 64)

    def create_int_type(self, width):
        return IntType(self, width)

    def create_pointer_type(self, pointed):
        return PointerType(self, pointed)

    def create_function(self, address):
        func = Function(self, address)
        self.functions[address] = func
        return func

    def format(self):
        if self.functions:
            result = []
            for i, func in enumerate(self.functions.values()):
                if i > 0:
                    result.append((Text, '\n'))
                result.extend(func.format())
            return result
        else:
            return [(Comment, '; Empty context'),]


class Function:

    def __init__(self, context, address):
        self.context = context
        self.address = address
        self.basic_blocks = [
            BasicBlock(self)
        ]

        self.return_type = context.void_type
        self.arg_types = []

    def create_entry_basic_block(self):
        """
        Create an empty basic block and make it the entry point for this
        function.
        """
        bb = BasicBlock(self)
        self.basic_blocks.insert(0, bb)
        return bb

    def create_basic_block(self):
        bb = BasicBlock(self)
        self.basic_blocks.append(bb)
        return bb

    def replace_value(self, old_value, new_value):
        for bb in self:
            bb.replace_value(old_value, new_value)

    def __iter__(self):
        return iter(self.basic_blocks)

    def __getitem__(self, idx):
        return self.basic_blocks.__getitem__(idx)

    @property
    def entry(self):
        return self.basic_blocks[0]

    def format(self):
        # TODO: return type and argument types.
        result = [
            (Name.Function, 'sub_{:x}'.format(self.address)),
            (Punctuation, '()'),
            (Text, ' '),
            (Punctuation, '{'),
            (Text, '\n'),
        ]
        for i, bb in enumerate(self.basic_blocks):
            if i > 0:
                result.append((Text, '\n'))
            result.extend(bb.format())
        result.extend([(Punctuation, '}'), (Text, '\n')])
        return result


class BasicBlock:

    def __init__(self, function):
        self.function = function
        self.instructions = []
        self.predecessors = set()

    def insert(self, index, insn):
        self.instructions.insert(index, insn)
        for succ in self.get_successors(True):
            succ.add_predecessor(self)

    def replace(self, index, insn):
        old_insn = self.instructions[index]
        self.instructions[index] = insn
        # TODO: if affecting the last instruction, update the predecessor cache
        # of successors.

    def remove(self, index):
        # TODO: same as for replace
        self.instructions.pop(index)

    def replace_value(self, old_value, new_value):
        def helper(value):
            return new_value if value == old_value else value
        for insn in self:
            insn.map_inputs(helper)

    @property
    def successors(self):
        return self.get_successors(False)

    def get_successors(self, allow_incomplete):
        if len(self.instructions) == 0:
            assert allow_incomplete
            return []

        last_insn = self.instructions[-1]
        if last_insn.kind == JUMP:
            return [last_insn.destination]
        elif last_insn.kind == BRANCH:
            return [last_insn.dest_true, last_insn.dest_false]
        elif last_insn.kind in (RET, UNDEF):
            return []
        else:
            assert allow_incomplete
            return []

    def __iter__(self):
        return iter(self.instructions)

    def __getitem__(self, idx):
        return self.instructions.__getitem__(idx)

    def __len__(self):
        return len(self.instructions)

    def add_predecessor(self, bb):
        self.predecessors.add(bb)

    @property
    def context(self):
        return self.function.context

    @property
    def name(self):
        for i, bb in enumerate(self.function.basic_blocks):
            if bb == self:
                return '%bb_{}'.format(i)
        assert False

    def __repr__(self):
        return '<BasicBlock {}>'.format(self.name)

    def format(self):
        indentation = (Text, '    ')

        result = self.format_label() + [
            (Punctuation, ':'),
            (Text, '\n')
        ]
        if self.predecessors:
            result.extend([
                indentation,
                (Comment, '; Predecessors: {}'.format(', '.join(sorted(
                    pred.name for pred in self.predecessors
                )))),
                (Text, '\n'),
            ])

        current_origin = None
        for insn in self.instructions:
            if insn.origin != current_origin:
                current_origin = insn.origin
                result.extend([
                    indentation,
                    (Comment, '; {}'.format(current_origin)),
                    (Text, '\n'),
                ])
            result.append(indentation)
            result.extend(insn.format())
            result.append((Text, '\n'))
        return result

    def format_label(self):
        return [(Name.Label, self.name)]

    def __repr__(self):
        return '<BasicBlock {}>'.format(self.format_label()[0][1])


class Type:
    def __init__(self, context, width):
        self.context = context
        self.width = width

    def format(self):
        raise NotImplementedError()


class VoidType(Type):
    def __init__(self, context):
        super(VoidType, self).__init__(context, None)

    def __eq__(self, other):
        return isinstance(other, VoidType)

    def format(self):
        return [(Keyword.Type, 'void')]


class IntType(Type):
    def __init__(self, context, width):
        super(IntType, self).__init__(context, width)
        assert width > 0

    def create(self, i):
        assert -(2 ** (self.width - 1)) <= i < 2 ** self.width - 1
        return Value(self, i)

    def __eq__(self, other):
        return isinstance(other, IntType) and self.width == other.width

    def format(self):
        return [(Keyword.Type, 'i{}'.format(self.width))]


class PointerType(Type):
    def __init__(self, context, pointed):
        super(PointerType, self).__init__(context, context.pointer_width)
        self.pointed = pointed

    def __eq__(self, other):
        return isinstance(other, PointerType) and self.pointed == other.pointed

    def format(self):
        return self.pointed.format() + [(Punctuation, '*')]


class FunctionType(Type):
    def __init__(self, context, return_type, arg_types):
        super(FunctionType, self).__init__(context, self.context.pointer_width)
        self.return_type == return_type
        self.arg_types == self.arg_types

    @property
    def width(self):
        return self.context.pointer_size

    def __eq__(self, other):
        return (
            isinstance(other, FunctionType)
            and self.return_type == other.return_type
            and self.arg_types == other.arg_types
        )

    def format(self):
        result = self.return_type.format() + [(Punctuation, '(')]
        for i, arg_type in enumerate(self.arg_types):
            if i > 0:
                result.extend([(Punctuation, ','), (Text, ' ')])
            result.extend(arg_type.format())
        result.append((Punctuation, ')'))
        return result


class Value:
    def __init__(self, type, value):
        self.type = type
        self.value = value

        assert (
            isinstance(value, int)
            or isinstance(value, ComputingInstruction)
        )

    def __eq__(self, other_value):
        return self.value == other_value.value

    def format(self):
        if isinstance(self.value, int):
            return self.type.format() + [
                (Text, ' '), (Number.Hex, hex(self.value))
            ]
        else:
            return [(Name.Variable, self.value.name)]

    def __repr__(self):
        return '<Value {}>'.format(utils.format_to_str(self))

    def __eq__(self, other):
        return self.type == other.type and self.value == other.value


class Register:
    def format(self):
        raise NotImplementedError()


class BaseInstruction:

    def __init__(self, function, kind, origin=None):
        self.function = function
        self.kind = kind
        self.origin = origin

    @property
    def context(self):
        return self.function.context

    @property
    def name(self):
        i = 0
        for bb in self.function.basic_blocks:
            for insn in bb.instructions:
                if insn == self:
                    return '%{}'.format(i)
                i += 1
        # assert False
        return '%??? ({})'.format(type(self).__name__)

    @property
    def type(self):
        raise NotImplementedError()

    @property
    def as_value(self):
        type = self.type
        assert type != self.context.void_type
        return Value(type, self)

    def map_inputs(self, func):
        # TODO: since this enables the outer world to modify inputs, it would
        # be greate to be able to perform validation afterwards.
        raise NotImplementedError()

    @property
    def inputs(self):
        result = []
        def helper(value):
            result.append(value)
            return value
        self.map_inputs(helper)
        return result

    def format_instruction(self):
        # TODO: remove this
        print(repr(self))
        raise NotImplementedError()

    def format(self):
        fmt_insn = self.format_instruction()
        if self.type != self.context.void_type:
            return [
                (Name.Variable, self.name),
                (Text, ' '),
                (Operator, '='),
                (Text, ' '),
            ] + fmt_insn
        else:
            return fmt_insn


(
    # Control flow instruction kinds (5)
    JUMP, BRANCH, CALL, RET, PHI,

    # Conversions (4)
    ZEXT, SEXT, TRUNC, BITCAST,
    # Arithmetic (5)
    ADD, SUB, MUL, SDIV, UDIV,
    # Bitwise (6)
    LSHL, LSHR, ASHR, AND, OR, XOR,
    # Concatenation (1)
    CAT,
    # Comparisons (10)
    EQ, NE, SLE, SLT, SGE, SGT, ULE, ULT, UGE, UGT,

    # Memory (2)
    LOAD, STORE,
    # Registers (2)
    RLOAD, RSTORE,

    # Misc (2)
    SELECT, COPY,

    # Undefined (1)
    UNDEF,
) = range (5 + 4 + 5 + 1 + 6 + 10 + 2 + 2 + 2 + 1)


NAMES = {
    JUMP: 'jump',
    BRANCH: 'branch',
    CALL: 'call',
    RET: 'ret',

    PHI: 'phi',

    ZEXT: 'zext',
    SEXT: 'sext',
    TRUNC: 'trunc',
    BITCAST: 'bitcast',

    ADD: 'add',
    SUB: 'sub',
    MUL: 'mul',
    SDIV: 'sdiv',
    UDIV: 'udiv',

    LSHL: 'lshl',
    LSHR: 'lshr',
    ASHR: 'ashr',
    AND: 'and',
    OR: 'or',
    XOR: 'xor',
    CAT: 'cat',

    EQ: 'eq',
    NE: 'ne',
    SLE: 'sle',
    SLT: 'slt',
    SGE: 'sge',
    SGT: 'sgt',
    ULE: 'ule',
    ULT: 'ult',
    UGE: 'uge',
    UGT: 'ugt',

    LOAD: 'load',
    STORE: 'store',
    RLOAD: 'rload',
    RSTORE: 'rstore',

    COPY: 'copy',
    SELECT: 'select',

    UNDEF: 'undef',
}


class ControlFlowInstruction(BaseInstruction):
    KINDS = (JUMP, BRANCH, CALL, RET)

    def __init__(self, function, kind, *operands, **kwargs):
        super(ControlFlowInstruction, self).__init__(function, kind, **kwargs)
        assert kind in self.KINDS

        if kind == JUMP:
            self.destination, = operands

        elif kind == BRANCH:
            self.condition, self.dest_true, self.dest_false = operands
            assert self.condition.type == self.context.boolean_type

        elif kind == CALL:
            self.callee = operands[0]
            assert isinstance(self.callee.type, FunctionType)
            self.args = list(operands[1:])
            assert (
                self.callee.type.arg_types == [arg.type for arg in self.args]
            )

        elif kind == RET:
            if self.function.return_type == self.context.void_type:
                assert len(operands) == 0
            else:
                self.return_value = operands,
                assert self.return_value.type == self.function.type.return_type

    @property
    def type(self):
        if self.kind == CALL:
            return self.callee.type
        else:
            return self.context.void_type

    def map_inputs(self, func):
        if self.kind == BRANCH:
            self.condition = func(self.condition)
        elif self.kind == CALL:
            self.callee = func(self.callee)
            for i, arg in enumerate(self.args):
                self.args[i] = func(self.args[i])
        elif (
            self.kind == RET
            and self.function.return_type != self.context.void_type
        ):
            self.return_value = func(self.return_value)

    def format_instruction(self):
        if self.kind == JUMP:
            return [
                (Operator.Word, 'jump'),
                (Text, ' '),
            ] + self.destination.format_label()

        elif self.kind == BRANCH:
            return [
                (Operator.Word, 'branch'),
                (Text, ' '),
                (Keyword, 'if'),
                (Text, ' '),
            ] + self.condition.format() + [
                (Text, ' '),
                (Keyword, 'then'),
                (Text, ' '),
            ] + self.dest_true.format_label() + [
                (Text, ' '),
                (Keyword, 'else'),
                (Text, ' '),
            ] + self.dest_false.format_label()

        elif self.kind == CALL:
            result = [(Operator.word, 'call')]
            result.extend(self.type.format())
            result.append((Text, ' '))
            result.extend(self.callee.format())
            result.append((Punctuation, '('))
            for i, arg in enumerate(self.args):
                if i > 0:
                    result.extend([(Punctuation, ','), (Text, ' ')])
                result.extend(arg.format())
            result.append((Punctuation, ')'))
            return result

        elif self.kind == RET:
            result = [(Operator.Word, 'ret')]
            if self.function.return_type != self.context.void_type:
                result.append((Text, ' '))
                result.extend(self.return_value.format())
            return result


class ComputingInstruction(BaseInstruction):
    KINDS = ()


class PhiInstruction(ComputingInstruction):
    KINDS = (PHI, )

    def __init__(self, function, pairs, **kwargs):
        super(PhiInstruction, self).__init__(function, PHI, **kwargs)

        self.pairs = pairs
        self.return_type = None

        assert len(self.pairs) > 0
        basic_blocks = set()
        for basic_block, value in self.pairs:
            bb_id = id(basic_block)
            assert bb_id not in basic_blocks
            assert basic_block.function == self.function
            if self.return_type is None:
                self.return_type = value.type
            else:
                # Allow no value yet since during phi nodes constructions, all
                # required values may not be available yet.
                assert value is None or value.type == self.return_type
        # ... But there must be at least one value available.
        assert self.return_type is not None

    def set_value(self, basic_block, value):
        assert value.type == self.return_type
        for i, (bb, _) in enumerate(self.pairs):
            if bb == basic_block:
                self.pairs[i] = (bb, value)
                break
        else:
            assert False

    @property
    def type(self):
        return self.return_type

    def map_inputs(self, func):
        for i, (basic_block, value) in enumerate(self.pairs):
            self.pairs[i] = (basic_block, func(value))

    def format_instruction(self):
        result = [(Operator.Word, 'phi'), (Text, ' ')]
        for i, (bb, value) in enumerate(self.pairs):
            if i > 0:
                result.extend([(Punctuation, ','), (Text, ' ')])
            result.extend(bb.format_label())
            result.extend([(Text, ' '), (Punctuation, '=>'), (Text, ' ')])
            result.extend(value.format())
        return result


class ConversionInstruction(ComputingInstruction):
    KINDS = (ZEXT, SEXT, TRUNC, BITCAST)

    def __init__(self, function, kind, dest_type, value, **kwargs):
        super(ConversionInstruction, self).__init__(function, kind, **kwargs)

        self.dest_type, self.value = dest_type, value
        if kind == BITCAST:
            assert value.type.width == dest_type.width
        else:
            assert (
                isinstance(self.value.type, IntType)
                and isinstance(self.dest_type, IntType)
            )

        if kind in (ZEXT, SEXT):
            assert self.value.type.width <= self.dest_type.width
        elif kind == TRUNC:
            assert self.value.type.width >= self.dest_type.width
        elif kind == BITCAST:
            pass
        else:
            assert False

    @property
    def type(self):
        return self.dest_type

    def map_inputs(self, func):
        self.value = func(self.value)

    def format_instruction(self):
        result = [(Operator.Word, NAMES[self.kind]), (Text, ' ')]
        result.extend(self.value.format()),
        result.extend([(Text, ' '), (Keyword, 'to'), (Text, ' ')])
        result.extend(self.dest_type.format())
        return result


class BinaryInstruction(ComputingInstruction):
    KINDS = (
        ADD, SUB, MUL, SDIV, UDIV,
        LSHL, LSHR, ASHR, AND, OR, XOR,
    )

    OPERATOR_IMAGES = {
        ADD:   '+',
        SUB:   '-',
        MUL:   '*',
        SDIV:  '/s',
        UDIV:  '/u',

        LSHL:  '<<',
        LSHR:  '>>u',
        ASHR:  '>>s',
        AND:   '&',
        OR:    '|',
        XOR:   '^',
    }

    def __init__(self, function, kind, left, right, **kwargs):
        super(BinaryInstruction, self).__init__(function, kind, **kwargs)
        assert (
            kind in (LSHL, LSHR, ASHR)
            or (
                kind in (
                    ADD, SUB, MUL, SDIV, UDIV, AND, OR, XOR
                )
                and left.type == right.type
            )
        )
        self.left = left
        self.right = right

    @property
    def type(self):
        return self.left.type

    def map_inputs(self, func):
        self.left = func(self.left)
        self.right = func(self.right)

    def format_instruction(self):
        return self.left.format() + [
            (Text, ' '),
            (Operator, self.OPERATOR_IMAGES[self.kind]),
            (Text, ' '),
        ] + self.right.format()


class ConcatenateInstruction(ComputingInstruction):
    KINDS = (CAT, )

    def __init__(self, function, *operands, **kwargs):
        super(ConcatenateInstruction, self).__init__(function, CAT, **kwargs)
        assert len(operands) > 0
        self.operands = operands

        width = 0
        for op in self.operands:
            assert isinstance(op.type, IntType)
            width += op.type.width

        self.return_type = IntType(width)

    @property
    def type(self):
        return self.return_type

    def map_inputs(self, func):
        self.operands = func(self.operands)


class ComparisonInstruction(ComputingInstruction):
    KINDS = (EQ, NE, SLE, SLT, SGE, SGT, ULE, ULT, UGE, UGT)

    OPERATOR_IMAGES = {
        EQ:  '==',
        NE:  '!=',
        SLE: '<=s',
        SLT: '<s',
        SGE: '>=s',
        SGT: '>s',
        ULE: '<=u',
        ULT: '<u',
        UGE: '>=u',
        UGT: '>u',
    }

    def __init__(self, function, kind, left, right, **kwargs):
        super(ComparisonInstruction, self).__init__(function, kind, **kwargs)
        assert kind in self.KINDS
        assert left.type == right.type
        self.left = left
        self.right = right

    @property
    def type(self):
        return self.context.boolean_type

    def map_inputs(self, func):
        self.left = func(self.left)
        self.right = func(self.right)

    def format_instruction(self):
        return self.left.format() + [
            (Text, ' '),
            (Operator, self.OPERATOR_IMAGES[self.kind]),
            (Text, ' '),
        ] + self.right.format()


class LoadInstruction(ComputingInstruction):
    KINDS = (LOAD, RLOAD)

    def __init__(self, function, kind, source, **kwargs):
        super(LoadInstruction, self).__init__(function, kind, **kwargs)
        self.source = source
        if kind == LOAD:
            assert isinstance(source.type, PointerType)
            self.return_type = source.type.pointed
        elif kind == RLOAD:
            assert isinstance(source, Register)
            self.return_type = source.type
        else:
            assert False

    @property
    def type(self):
        return self.return_type

    def map_inputs(self, func):
        if self.kind == LOAD:
            self.source = func(self.source)

    def format_instruction(self):
        result = [(Operator.Word, NAMES[self.kind]), (Text, ' ')]
        result.extend(self.source.type.format()),
        result.append((Text, ' '))
        result.extend(self.source.format())
        return result


class StoreInstruction(BaseInstruction):
    KINDS = (STORE, RSTORE)

    def __init__(self, function, kind, destination, value, **kwargs):
        super(StoreInstruction, self).__init__(function, kind, **kwargs)
        self.destination = destination
        self.value = value
        if kind == STORE:
            assert (
                isinstance(destination.type, PointerType)
                and destination.type.pointed == value.type
            )
        elif kind == RSTORE:
            assert (
                isinstance(destination, Register)
                and destination.type == value.type
            )
        else:
            assert False

    @property
    def type(self):
        return self.context.void_type

    def map_inputs(self, func):
        if self.kind == STORE:
            self.destination = func(self.destination)
        self.value = func(self.value)

    def format_instruction(self):
        result = [(Operator.Word, NAMES[self.kind]), (Text, ' ')]
        result.extend(self.value.format())
        result.extend([
            (Text, ' '),
            (Keyword, 'to'),
            (Text, ' ')
        ])
        result.extend(self.destination.type.format())
        result.append((Text, ' '))
        result.extend(self.destination.format())
        return result


class SelectInstruction(ComputingInstruction):
    KINDS = (SELECT, )

    def __init__(self, function, condition, true_value, false_value, **kwargs):
        super(SelectInstruction, self).__init__(function, SELECT, **kwargs)
        self.condition = condition

        assert (
            isinstance(condition.type, IntegerType)
            and condition.type.width == 1
        )
        assert true_value.type == false_value.type
        self.true_value = true_value
        self.false_value = false_value

    @property
    def type(self):
        return self.true_value.type

    def map_inputs(self, func):
        self.condition = func(self.condition)
        self.true_value = func(self.true_value)
        self.false_value = func(self.false_value)

    def format_instruction(self):
        result = [
            (Operator.Word, 'select'), (Text, ' '),
            (Keyword, 'if'), (Text, ' ')
        ]
        result.extend(self.condition.format())
        result.extend([(Text, ' '), (Keyword, 'then'), (Text, ' ')])
        result.extend(self.true_value.type.format())
        result.extend([(Text, ' '), (Keyword, 'else'), (Text, ' ')])
        result.extend(self.false_value.format())
        return result


class CopyInstruction(ComputingInstruction):
    KINDS = (COPY, )

    def __init__(self, function, value, **kwargs):
        super(CopyInstruction, self).__init__(function, COPY, **kwargs)
        self.value = value

    @property
    def type(self):
        return self.value.type

    def map_inputs(self, func):
        self.value = func(self.value)

    def format_instruction(self):
        return [
            (Keyword, 'copy'),
            (Text, ' '),
        ] + self.value.format()


class UndefInstruction(BaseInstruction):
    KINDS = (UNDEF, )

    def __init__(self, function, **kwargs):
        super(UndefInstruction, self).__init__(function, UNDEF, **kwargs)

    @property
    def type(self):
        return self.context.void_type

    def map_inputs(self, func):
        pass

    def format_instruction(self):
        return [(Operator.Word, '{}'.format(NAMES[self.kind]))]
