import inspect

import decompil.ir


class Builder:

    class Position:
        def __init__(self, basic_block, index):
            self.basic_bloc = basic_block
            self.index = index

    def __init__(self):
        _create_build_methods()
        self.basic_block = None
        self.index = None
        self.current_origin = None

    @property
    def position(self):
        if self.basic_block:
            return self.Position(self.basic_block, self.index)
        else:
            return None

    @property
    def current_basic_block(self):
        return self.basic_block

    def create_basic_block(self):
        return self.basic_block.function.create_basic_block()

    def set_position(self, position):
        self.basic_block = position.basic_block
        self.index = position.index

    def position_at_entry(self, function):
        self.basic_block = function.entry
        self.index = 0

    def position_at_end(self, basic_block):
        self.basic_block = basic_block
        self.index = len(basic_block.instructions)

    def insert_instruction(self, insn):
        assert self.position
        self.basic_block.insert(self.index, insn)
        self.index += 1

    def set_origin(self, origin):
        self.current_origin = origin


_build_method_created = False
def _create_build_methods():
    global _build_method_created

    if _build_method_created:
        return
    else:
        _build_method_created = True

    kind_to_cls = {}
    for names in dir(decompil.ir):
        obj = getattr(decompil.ir, names)
        if (
            inspect.isclass(obj)
            and issubclass(obj, decompil.ir.BaseInstruction)
            and obj != decompil.ir.BaseInstruction
        ):
            for kind in obj.KINDS:
                kind_to_cls[kind] = obj

    for kind, name in decompil.ir.NAMES.items():
        cls = kind_to_cls[kind]

        def create_build_method(cls, name, kind):

            def build(self, *operands, **kwargs):
                if 'origin' not in kwargs:
                    kwargs['origin'] = self.current_origin
                func = self.basic_block.function
                args = [func]
                if len(cls.KINDS) > 1:
                    args.append(kind)
                args.extend(operands)
                insn = cls(*args, **kwargs)
                self.insert_instruction(insn)
                if insn.type != func.context.void_type:
                    return insn.as_value

            return 'build_{}'.format(name), build

        method_name, method = create_build_method(
            kind_to_cls[kind], name, kind
        )
        setattr(Builder, method_name, method)
