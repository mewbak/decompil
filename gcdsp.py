import collections
import inspect
import struct

from pygments.token import *

import builder
import disassemblers
import ir


class Context(ir.Context):

    def __init__(self):
        super(Context, self).__init__(16)
        self.pointer_type = self.create_pointer_type(self.half_type)
        self.init_registers()

    def init_registers(self):
        self.registers = regs = [
            # 0x00-0x03
            Register(self, 'ar0', 16),
            Register(self, 'ar1', 16),
            Register(self, 'ar2', 16),
            Register(self, 'ar3', 16),

            # 0x04-0x07
            Register(self, 'ix0', 16),
            Register(self, 'ix1', 16),
            Register(self, 'ix2', 16),
            Register(self, 'ix3', 16),

            # 0x08-0xb
            Register(self, 'r08', 16),
            Register(self, 'r09', 16),
            Register(self, 'r0a', 16),
            Register(self, 'r0b', 16),

            # 0x0c-0x0f
            # TODO: something special?
            Register(self, 'st0', 16),
            Register(self, 'st1', 16),
            Register(self, 'st2', 16),
            Register(self, 'st3', 16),

            # 0x10-0x11
            # TODO: handle 8-bit overflow
            Register(self, 'ac0.h', 16),
            Register(self, 'ac1.h', 16),

            # 0x12-0x13
            Register(self, 'config', 16),
            Register(self, 'sr', 16),

            # 0x14-0x17
            Register(self, 'prod.l', 16),
            Register(self, 'prod.m1', 16),
            # TODO: handle 8-bit overflow
            Register(self, 'prod.h', 16),
            Register(self, 'prod.m2', 16),

            # 0x18-0x1b
            Register(self, 'ax0.l', 16),
            Register(self, 'ax1.l', 16),
            Register(self, 'ax0.h', 16),
            Register(self, 'ax1.h', 16),

            # 0x1c-0x1f
            Register(self, 'ac0.l', 16),
            Register(self, 'ac1.l', 16),
            Register(self, 'ac0.m', 16),
            Register(self, 'ac1.m', 16),
        ]

        self.wr_registers = [
            Register(self, 'wr{}'.format(i), 16) for i in range(4)
        ]

        self.addr_to_wr = {
            self.registers[0x00]: self.wr_registers[0x00],
            self.registers[0x01]: self.wr_registers[0x01],
            self.registers[0x02]: self.wr_registers[0x02],
            self.registers[0x03]: self.wr_registers[0x03],
        }

        self.long_accumulators = [
            Register(self, 'ac0', 40, [
                (regs[0x10], 32), (regs[0x1e], 16), (regs[0x1c], 0)
            ]),
            Register(self, 'ac1', 40, [
                (regs[0x11], 32), (regs[0x1f], 16), (regs[0x1d], 0)
            ]),
        ]
        self.short_accumulators = [
            Register(self, 'acs0', 24, [(regs[0x10], 16), (regs[0x1e], 0)]),
            Register(self, 'acs1', 24, [(regs[0x11], 16), (regs[0x1f], 0)]),
        ]
        self.extra_acculumators = [
            Register(self, 'ax0', 32, [(regs[0x1a], 16), (regs[0x18], 0)]),
            Register(self, 'ax1', 32, [(regs[0x1b], 16), (regs[0x19], 0)]),
        ]
        self.prod_register = Register(self, 'prod', 40, [
            (regs[0x14], 32),
            (regs[0x15], 16), (regs[0x17], 16),
            (regs[0x16], 16),
        ])


class Register(ir.Register):
    def __init__(self, context, name, width, components=None):
        self.context = context
        self.type = context.create_int_type(width)
        self.name = name
        self.components = components

    def build_load(self, builder):
        if self.components is None:
            return builder.build_rload(self)
        else:
            result = None
            for reg, shift in self.components:
                val = builder.build_zext(
                    self.type, builder.build_rload(reg)
                )
                if shift:
                    val = builder.build_shl(val, self.type.create(shift))

                if result:
                    result = builder.build_add(result, val)
                else:
                    result = val
            return result

    def build_store(self, builder, value):
        assert value.type == self.type
        if self.components is None:
            builder.build_rstore(self, value)
        else:
            for reg, shift in self.components:
                if shift:
                    val = builder.build_lshl(value, value.type.create(shift))
                val = builder.build_trunc(reg.type, val)
                builder.build_rstore(reg, val)

    def build_load_comp(self, builder):
        return [
            builder.build_rload(reg)
            for reg, _ in self.components
        ]

    def build_store_comp(self, builder, *values):
        assert len(values) == len(self.components)
        for value, (reg, _) in zip(values, self.components):
            builder.build_rstore(reg, value)

    def format(self):
        return [(Name.Variable, '${}'.format(self.name))]


class BaseDecoder:
    name               = None
    opcode             = None
    opcode_mask        = None
    operands_format    = None

    def decode(self, context, disassembler, builder):
        raise NotImplementedError()

    def decode_operands(self, context):
        return [op.extract(context, self) for op in self.operands_format]

class Instruction(BaseDecoder):
    have_extra_operand = False
    is_extended        = False

    def __init__(self, address, opcode, extra_operand=None, extension=None):
        self.address = address
        self.opcode_value = opcode
        self.extension = extension
        assert self.is_extended == (extension is not None)
        assert self.have_extra_operand == (extra_operand is not None)
        if self.extension:
            self.extension.instruction = self

    def __repr__(self):
        ext = (
            ' ({})'.format(self.extension.name)
            if self.extension else
            ''
        )
        return '{:04x}: {}{}'.format(
            self.address, self.name, ext
        )


class InstructionExtension(BaseDecoder):
    def __init__(self, opcode):
        self.opcode_value = opcode
        # When accepting an extension, instructions should set the following
        # field:
        self.instruction = None

    def __repr__(self):
        return '{:04x}: {} (extension)'.format(
            self.address, self.name
        )


instructions = []
instruction_extensions = []
def _init_tables():
    import gcdsp_decoders

    def helper(table, cls):
        for obj_name in dir(gcdsp_decoders):
            obj = getattr(gcdsp_decoders, obj_name)
            if not (
                inspect.isclass(obj)
                and issubclass(obj, cls)
                and obj != cls
            ):
                continue
            assert (obj.opcode & ~obj.opcode_mask) == 0
            table.append(obj)

    helper(instructions, Instruction)
    helper(instruction_extensions, InstructionExtension)
_init_tables()


def load_insns():
    import gcdsp_decoders

    def default_decoder(self, context, disassembler, builder):
        builder.build_undef()
        disassembler.stop_basic_block()

    def decode_operands(self, context):
        result = []
        for _, size, addend, rshift, mask in self.operands_format:
            operand = (self.opcode & mask) >> rshift
            result.append(self.opcode & mask + addend)
        return result

    Insn = collections.namedtuple(
        'Insn', 'name opcode mask size unused0 operands is_extended unused1'
    )

    for insn in gcdsp_decoders.opcodes:
        insn = Insn(*insn)
        insn_decoder = getattr(
            gcdsp_decoders,
            'decode_{}'.format(insn.name.lower()),
            default_decoder,
        )
        instructions.append(
            type(insn.name, (Instruction, ), {
                'name': insn.name,
                'opcode': insn.opcode,
                'opcode_mask': insn.mask,
                'have_extra_operand': insn.size == 2,
                'is_extended': insn.is_extended,
                'decode': insn_decoder,
                'decode_operands': decode_operands,
                'operands_format': insn.operands
            })
        )

    for ext in gcdsp_decoders.opcodes_ext:
        ext = Insn(*ext)
        instruction_extensions.append(
            type(ext.name, (InstructionExtension, ), {
                'name': ext.name,
                'opcode': ext.opcode,
                'opcode_mask': ext.mask,
                'decode': insn_decoder,
                'decode_operands': decode_operands,
                'operands_format': insn.operands
            })
        )
load_insns()


class Decoder(disassemblers.BaseDecoder):

    def __init__(self, fp):
        self.fp = fp

    def parse_insn(self, disassembler, builder, address):

        opcode = self.get_word(address)
        next_address = address + 1
        if opcode is None:
            return None
        insn_pat = self.lookup(opcode, instructions)

        # Parse the extra operand, if any.
        if insn_pat.have_extra_operand:
            extra_operand = self.get_word(address + 1)
            next_address += 1
            if extra_operand is None:
                raise ValueError('Incomplete file')
        else:
            extra_operand = None

        # Parse the instruction extension, if any.
        if insn_pat.is_extended:
            ext_pat = self.lookup(opcode, instruction_extensions)
            ext = ext_pat(opcode)
        else:
            ext = None

        insn = insn_pat(address, opcode, extra_operand, ext)
        # Always decode the extension first (if any).
        if insn.is_extended:
            insn.extension.decode(disassembler.context, disassembler, builder)
            # TODO: remove this once all extensions are supported.
            if disassembler.must_stop_basic_block:
                return next_address
        insn.decode(disassembler.context, disassembler, builder)

        return next_address

    def iter_insns(self, address):
        while True:
            address, insn = self.parse_insn(address)
            if insn is None:
                break
            else:
                yield address, insn

    def get_word(self, address):
        self.fp.seek(2 * address)
        word = self.fp.read(2)
        if len(word) == 0:
            return None
        elif len(word) == 2:
            return struct.unpack('>H', word)[0]
        else:
            raise ValueError('Incomplete file')

    def lookup(self, opcode, pattern_set):
        for pat in pattern_set:
            if opcode & pat.opcode_mask == pat.opcode:
                return pat
        else:
            raise ValueError('Invalid opcode: {:04x}'.format(opcode))
