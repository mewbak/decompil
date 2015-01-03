#! /usr/bin/env python3
import argparse
import subprocess
import sys

import pygments
from pygments.formatters import get_formatter_by_name
from pygments.styles import get_style_by_name

import decompil.builder
from decompil.disassemblers import EntryDisassembler
from decompil.optimizations import (
    binary_phi_to_select,
    copy_elimination,
    dead_code_elimination,
    merge_basic_block_sequences,
    registers_to_ssa,
    strip_unused_branches,
    to_expr,
)
from decompil.utils import function_to_dot
import gcdsp


parser = argparse.ArgumentParser(description='Decode a GCDSP ROM')

# Mandatory arguments
parser.add_argument(
    'rom-file', type=argparse.FileType('rb'),
    help='ROM file'
)
parser.add_argument(
    'offset', type=lambda x: int(x, 16),
    help='Decoding entry point'
)

# Options
parser.add_argument(
    '--verbose', '-v', action='store_true',
    help='Display progression (useful for debugging)'
)
parser.add_argument(
    '--dumps', '-d', choices=('text', 'dot'), nargs='+',
    default=['text'],
    help='Format to use for dumps (default: only text)'
)
parser.add_argument(
    '--all-steps', '-a', action='store_true',
    help='Whether to dump all steps (default: only the final result)'
)
parser.add_argument(
    '--style', '-s', default='native', type=get_style_by_name,
    help='Pygments style to use for code highlighting'
)
parser.add_argument(
    '--dot-format', default=None, choices=('png', 'svg', 'pdf'),
    help='If provided, invoke dot to produce the graph output'
)
parser.add_argument(
    '--dpi', default=None, type=int,
    help='When invoking dot, specifies a DPI for its output'
)

text_formatter = get_formatter_by_name('text')


def main(args):
    context = gcdsp.Context()

    decoder = gcdsp.Decoder(getattr(args, 'rom-file'))
    EntryDisassembler(context, decoder, args.offset).process()

    opt_pipeline = [
        registers_to_ssa.RegistersToSSA,
        copy_elimination.CopyElimination,
        dead_code_elimination.DeadCodeElimination,
        binary_phi_to_select.BinaryPhiToSelect,
        to_expr.ToExpr,
        strip_unused_branches.StripUnusedBranches,
        merge_basic_block_sequences.MergeBasicBlockSequences,
        to_expr.ToExpr,
    ]

    def output_stage(name, function):
        if 'dot' in args.dumps:
            dot_document = function_to_dot(function, style=args.style)
            if args.dot_format:
                dot_args = ['dot',
                    '-T{}'.format(args.dot_format),
                    '-o' '{}.{}'.format(name, args.dot_format),
                ]
                if args.dpi is not None:
                    dot_args.append('-Gdpi={}'.format(args.dpi))
                dot = subprocess.Popen(dot_args, stdin=subprocess.PIPE)
                dot.communicate(dot_document.encode('utf-8'))
            else:
                with open('{}.dot'.format(name), 'w') as f:
                    f.write(dot_document)
                    f.write('\n')
        if 'text' in args.dumps:
            with open('{}.ll'.format(name), 'w') as f:
                f.write(pygments.format(function.format(), text_formatter))
                f.write('\n')

    for func in context.functions.values():
        func_name = '{:x}'.format(func.address)
        if args.all_steps:
            output_stage('{}-0-original'.format(func_name), func)

        for i, opt in enumerate(opt_pipeline, 1):
            if args.verbose:
                print('Running {}'.format(opt.__name__))
            opt.process_function(func)
            if args.all_steps:
                output_stage(
                    '{}-{}-{}'.format(func_name, i, opt.__name__), func)

    if not args.all_steps:
        output_stage('{}-final'.format(func_name), func)


if __name__ == '__main__':
    main(parser.parse_args())
