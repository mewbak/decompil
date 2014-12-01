import collections


from pygments.token import *


from decompil import builder, ir, optimizations
from decompil.analysis.dominance import get_dominance_frontiers


class DummyPhiArgument(ir.ComputingInstruction):
    def __init__(self, function, register):
        super(DummyPhiArgument, self).__init__(function, None)
        self.register = register

    @property
    def type(self):
        return self.register.type

    def format(self):
        return [(Keyword, 'dummy'), (Text, ' ')] + self.register.format()


class RegistersToSSA(optimizations.Optimization):

    @staticmethod
    def is_reg_barrier(insn):
        """
        Return whether insn is a register barrier.

        A register barrier is an instruction that can read or write registers.
        Hence, before register barriers, stores must occur and after them, load
        must occur.
        """
        return insn.kind in (ir.CALL, ir.RET, ir.UNDEF)

    @classmethod
    def get_store_sites(cls, function):
        """
        Return a mapping: register -> set of basic blocks in which a value is
        stored in this register.
        """
        store_sites = collections.defaultdict(set)

        for basic_block in function:
            for insn in basic_block:
                if insn.kind == ir.RSTORE:
                    store_sites[insn.destination].add(basic_block)
        return store_sites

    @classmethod
    def process_function(cls, function):
        self = cls(function)
        self._process()

    def __init__(self, function):
        self.function = function
        self.bld = builder.Builder()

        # Mapping: register -> set of all basic blocks that store a value in
        # this register.
        self.store_sites = None
        # Reverse mapping for it (i.e. basic block -> set of all registers
        # affected by this basic block).
        self.stored_registers = None

        # Mapping: register -> stack of values to use when loading the register
        # (at some specific point, take the top).  Initialized in _process and
        # really used in transform_reg_insns.
        self.def_stacks = collections.defaultdict(list)

        self.dom_tree = None

    def _process(self):
        self.store_sites = self.get_store_sites(self.function)
        self.stored_registers = collections.defaultdict(set)

        # Introduce load instructions at a new entry point and force the
        # assumption that they are all initialized at this point. This way,
        # other register loads that are not dominated by a corresponding
        # register store will inherit these values.
        old_entry = self.function.entry
        new_entry = self.function.create_entry_basic_block()
        self.bld.position_at_end(new_entry)
        for register, reg_store_sites in self.store_sites.items():
            self.def_stacks[register].append(self.bld.build_rload(register))
            reg_store_sites.add(new_entry)
            for ss in reg_store_sites:
                self.stored_registers[ss].add(register)
        self.bld.build_jump(old_entry)

        # Force registers reloading after barrier instructions.
        for basic_block in self.function:
            # If some basic block contains a barrier instruction, consider it
            # as a store site so that its sucessors will have to transmit
            # new values of registers after it.
            for insn in basic_block:
                if self.is_reg_barrier(insn):
                    for register in self.store_sites:
                        self.store_sites[register].add(basic_block)
                        self.stored_registers[basic_block].add(register)
                    break

        # Enter the regular renaming algorithm...
        self.dom_tree, dom_frontiers = get_dominance_frontiers(self.function)

        # For each register, create phi nodes in basic blocks that need some.
        for register, reg_store_sites in self.store_sites.items():
            self.create_phi_nodes(register, reg_store_sites, dom_frontiers)

        # Now perform the renaming itself. Skip the new entry point: it does
        # not need renaming (most importantly, it's invalid to rename it).
        for basic_block in self.dom_tree.get_children(new_entry):
            self.transform_reg_insns(basic_block)

    def create_phi_nodes(self, register, store_sites, dom_frontiers):
        """
        Create phi nodes with `register` DummyPhiArgument inputs in all the
        transitive dominance frontier of basic blocks in `reg_store_sites`.
        """
        visited_bb = set()

        # As long as we have definition (store or phi node) sites to process...
        queue = set(store_sites)
        while queue:
            store_site = queue.pop()
            # Create phi nodes in nodes that belong to their dominance frontier
            # and remember them. Do this transitively.
            for basic_block in dom_frontiers[store_site]:
                if basic_block not in visited_bb:
                    self.bld.position_at_start(basic_block)
                    self.bld.build_phi([
                        (
                            bb_pred,
                            DummyPhiArgument(self.function, register).as_value
                        )
                        for bb_pred in basic_block.predecessors
                    ])
                    visited_bb.add(basic_block)
                    if register not in self.stored_registers[basic_block]:
                        queue.add(basic_block)

    def transform_reg_insns(self, basic_block):
        def_introduced = collections.defaultdict(lambda: 0)
        def introduce_def(reg, value):
            self.def_stacks[reg].append(value)
            def_introduced[reg] += 1

        # First, process load/stores in this basic block.
        # This is done in two passes: 1) analyse the basic block to list
        # operations to perform on it, 2) actually perform these operations
        # (one cannot iterate on a container and modifying it at the same
        # time!).

        # List of tuples: (index, operation, instruction?) used to modify a
        # basic block after analysis. `index` is the index in the basic block
        # of the instruction to remove. `operation` is True when inserting an
        # instruction and `False` when removing one. If inserting an operation,
        # `instruction` is the BaseInstruction subclass instance to insert;
        # it's None otherwise.
        basic_block_operations = []

        for i, insn in enumerate(basic_block):
            if insn.kind == ir.RLOAD and insn.source in self.def_stacks:
                # Transform register loads into mere copies of the related
                # register store value.
                new_insn = ir.CopyInstruction(
                    basic_block.function,
                    self.def_stacks[insn.source][-1]
                )
                basic_block.replace(i, new_insn)
                # TODO: for efficiency purposes, instead of looking for the old
                # value in the whole function, we could instead do so only in
                # the children from the dominator tree and their successors:
                # these are the only places where it is legitimate to reference
                # the value.
                basic_block.function.replace_value(
                    insn.as_value, new_insn.as_value
                )

            elif insn.kind == ir.RSTORE:
                # Remove register stores but remember the association between
                # the corresponding register and value.
                introduce_def(insn.destination, insn.value)
                basic_block_operations.append((i, False, None))

            elif self.is_reg_barrier(insn):
                # Actually store values in registers before register barriers.
                for reg, value_stacks in self.def_stacks.items():
                    new_insn = ir.StoreInstruction(
                        basic_block.function, ir.RSTORE,
                        reg, value_stacks[-1]
                    )
                    basic_block_operations.append((i, True, new_insn))
                # If the instruction can return, reload registers afterwards.
                if insn.kind not in (ir.RET, ir.UNDEF):
                    for register in self.def_stacks:
                        new_insn = ir.LoadInstruction(
                            basic_block.function, ir.RLOAD, register
                        )
                        basic_block_operations.append((i + 1, True, new_insn))
                        introduce_def(register, new_insn.as_value)

        # Perform operations on basic blocks. In order to keep remaining
        # operations valid at each iterations, process bigger indexes first.
        for i, operation, insn in reversed(basic_block_operations):
            if operation:
                basic_block.insert(i, insn)
            else:
                basic_block.remove(i)

        # Propagate the corresponding values to the phi nodes in the
        # successors.
        for bb_succ in basic_block.successors:
            for insn in bb_succ:
                register = self.search_dummy_arg(basic_block, insn)
                if register:
                    insn.set_value(basic_block, self.def_stacks[register][-1])

        # Recurse down the dominator tree.
        for dom_child in self.dom_tree.get_children(basic_block):
            self.transform_reg_insns(dom_child)

        # Hide all definitions created here from the caller.
        for register, def_count in def_introduced.items():
            self.def_stacks[register] = self.def_stacks[register][:-def_count]

    def search_dummy_arg(self, bb, insn):
        """
        Look for a DummyPhiArgument in `insn` associated to `bb`. If `insn` is
        a PHI node and there is one, return the corresponding register.
        Otherwise, return None.
        """
        if isinstance(insn, ir.PhiInstruction):
            for prev_bb, prev_value in insn.pairs:
                if prev_bb == bb:
                    if isinstance(prev_value.value, DummyPhiArgument):
                        return prev_value.value.register
                    else:
                        return None
        return None
