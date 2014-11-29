import builder


class BaseDecoder:

    def parse_insn(self, disassembler, builder, address):
        raise NotImplementedError()


class BaseDisassembler:

    def process(self):
        raise NotImplementedError()


class EntryDisassembler(BaseDisassembler):

    def __init__(self, context, decoder, entry):
        self.context = context
        self.decoder = decoder
        self.entry = entry

        self.current_function = None
        self.must_stop_basic_block = None

        self.pending_functions = None
        self.pending_basic_blocks = None

        self.processed_functions = None
        self.processed_basic_blocks = None

    def process(self):
        self.pending_functions = [self.entry]
        self.processed_basic_blocks = {}

        while self.pending_functions:
            address = self.pending_functions.pop(0)
            self.current_function = self.context.create_function(address)
            self.processed_basic_blocks[address] = self.current_function
            self.process_function(address, self.current_function)

    def process_function(self, address, function):
        self.pending_basic_blocks = [(address, function.entry)]
        self.processed_basic_blocks = set()

        bld = builder.Builder()

        while self.pending_basic_blocks:
            bb_addr, bb = self.pending_basic_blocks.pop(0)
            self.processed_basic_blocks.add(bb_addr)
            bld.position_at_end(bb)

            self.has_promised_bb = False
            self.must_stop_basic_block = False
            addr = bb_addr
            # Stop decoding this basic block as soon as the decoder requested
            # for another basic block: it means there is a branch.
            while not self.must_stop_basic_block:
                assert not self.has_promised_bb
                addr = self.decoder.parse_insn(self, bld, addr)
                if addr is None:
                    # We reached the end of the program...
                    bld.build_ret()
                    break

    def stop_basic_block(self):
        self.must_stop_basic_block = True

    def promise_function(self, address):
        try:
            return self.processed_functions[address]
        except KeyError:
            func = self.context.create_function(address)
            self.processed_functions[address] = func
            return func

    def promise_basic_block(self, address):
        self.has_promised_bb = True
        try:
            return self.processed_basic_blocks[address]
        except KeyError:
            bb = self.current_function.create_basic_block()
            self.processed_basic_blocks[address] = bb
            return bb
