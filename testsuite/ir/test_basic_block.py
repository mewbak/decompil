import decompil.ir


def test_successor_incomplete():
    c = decompil.ir.Context(32)
    f = c.create_function(0)
    bb = f.create_basic_block()
    try:
        _ = bb.successors
    except AssertionError:
        return
    else:
        assert False, (
            "Getting an incomplete basic block's successors must raise"
            " an assertion error"
        )
