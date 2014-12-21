import sys

import pygments
from pygments.formatters import get_formatter_by_name

import decompil.builder
from decompil.disassemblers import EntryDisassembler
from decompil.optimizations import (
    copy_elimination,
    dead_code_elimination,
    registers_to_ssa,
)
from decompil.utils import function_to_dot
import gcdsp


prog0 = (0x0cd3, 0x0d61)
prog1 = (0x0d62, 0x0d6a)

formatter = get_formatter_by_name('terminal256', style='native')

context = gcdsp.Context()
first, last = prog1

with open(sys.argv[1], 'rb') as fp:
    decoder = gcdsp.Decoder(fp)

    # fp.seek(2 * first)
    # for address, insn in decoder.iter_insns(first):
    #     if address > last:
    #         break
    #     print(insn)

    EntryDisassembler(context, decoder, first).process()

    # func = context.create_function(first)
    # bld = builder.Builder()
    # bld.position_at_entry(func)

opt_pipeline = [
    registers_to_ssa.RegistersToSSA,
    copy_elimination.CopyElimination,
    dead_code_elimination.DeadCodeElimination,
]


def output_dot(name, function):
    with open('{}.dot'.format(name), 'w') as f:
        f.write(function_to_dot(function))
        f.write('\n')


for func in context.functions.values():
    func_name = '{:x}'.format(func.address)
    output_dot('{}-0-original'.format(func_name), func)
    for i, opt in enumerate(opt_pipeline, 1):
        opt.process_function(func)
        output_dot('{}-{}-{}'.format(func_name, i, opt.__name__), func)
