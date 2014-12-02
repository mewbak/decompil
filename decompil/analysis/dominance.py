import collections
import itertools


class Tree:
    """General tree with both parent and children links."""

    class Node:
        def __init__(self, value, parent):
            self.value = value
            self.parent = parent
            self.children = set()

        def add(self, child):
            self.children.add(child)

    def __init__(self):
        self.root = None
        self.nodes = {}

    def __contains__(self, value):
        return value in self.nodes

    def add(self, value, parent=None):
        # Create the new node itself.
        assert value not in self.nodes
        node = self.Node(value, parent)
        self.nodes[value] = node

        # Then link its parent and it.
        if parent is None:
            assert self.root is None
            self.root = node
        else:
            self.nodes[parent].add(value)

    def get_ancestors(self, value):
        ancestor = self.nodes[value].parent
        while ancestor:
            yield ancestor
            ancestor = self.nodes[ancestor].parent

    def is_ancestor(self, value, ancestor):
        return any(a == ancestor for a in self.get_ancestors(value))

    def get_parent(self, value):
        return self.nodes[value].parent

    def get_children(self, value):
        return self.nodes[value].children


def parent_links_to_tree(parents):
    """Convert a mapping: node -> parent into a Tree."""
    tree = Tree()

    def helper(node, parent):
        """
        Add `node` to `tree` as child of `parent` if it's not there already.
        """
        if node not in tree:
            # Before we can add `node`, we have to make sure `parent` is
            # already there.
            if parent:
                helper(parent, parents[parent])
            tree.add(node, parent)

    for node, parent in parents.items():
        helper(node, parent)

    return tree


def get_dfs_spanning_tree(func):
    dfs_tree = Tree()
    dfs_numbers = {}
    next_dfs_number = iter(itertools.count(0))

    def build_helper(basic_block, parent=None):
        if basic_block in dfs_numbers:
            return
        dfs_tree.add(basic_block, parent)
        dfs_numbers[basic_block] = next(next_dfs_number)
        for succ in basic_block.successors:
            build_helper(succ, basic_block)

    build_helper(func.entry)
    return dfs_tree, dfs_numbers


def get_dominator_tree(func):
    """Return the dominance tree for basic blocks in func.

    This tree is a dictionnary that maps basic blocks to their parent (their
    immediate dominator).
    """
    # Implementation is based on Modern Compiler Implementation, Andew W.
    # Appel, Chapter 19 Static Single-Assignment Form, algorithms 19.9 and
    # 19.10 (naive versions).

    dfs_tree, dfs_numbers = get_dfs_spanning_tree(func)
    # Mapping: basic block -> its immediate dominator. Once completely built,
    # we can build the dominator tree from it.
    imm_dominators = {}

    # Mapping: basic block -> semidominator
    semidominators = {}
    # Mapping: basic_block -> ??? TODO
    ancestors = {}
    # Mapping: basic_block -> ??? TODO
    buckets = collections.defaultdict(set)
    # Mapping: basic_block -> ??? TODO
    same_dominators = {}

    def ancestor_with_lowest_semi_no(basic_block):
        result = basic_block
        while result not in ancestors:
            bb_semi = semidominators.get(basic_block, None)
            result_semi = semidominators.get(result, None)
            if (dfs_numbers.get(bb_semi, 0)
                < dfs_numbers.get(result_semi, 0)
            ):
                result = basic_block
            result = ancestors[result]
        return result

    basic_blocks_dfs_order = list(sorted(
        (dfs_number, basic_block)
        for basic_block, dfs_number in dfs_numbers.items()
    ))

    for i, basic_block in reversed(basic_blocks_dfs_order):
        if i == 0:
            imm_dominators[basic_block] = None
            continue
        parent = dfs_tree.get_parent(basic_block)

        # Compute the semi-dominator for basic_block.
        semi_candidate = parent
        semi_candidate_number = dfs_numbers[semi_candidate]

        for pred in basic_block.predecessors:
            s = (
                pred
                if dfs_numbers[pred] <= i else
                semidominators.get(ancestor_with_lowest_semi_no(pred), None)
            )
            s_no = dfs_numbers[s]
            if s_no < semi_candidate_number:
                semi_candidate, semi_candidate_number = s, s_no

        semidominators[basic_block] = semi_candidate
        buckets[semi_candidate].add(basic_block)
        ancestors[basic_block] = parent

        for bb in buckets[parent]:
            y = ancestor_with_lowest_semi_no(bb)
            if semidominators[y] == semidominators[bb]:
                imm_dominators[bb] = parent
            else:
                same_dominators[bb] = y
        buckets[parent] = set()

    for i, basic_block in basic_blocks_dfs_order[1:]:
        try:
            same_dom = same_dominators[basic_block]
        except KeyError:
            pass
        else:
            imm_dominators[basic_block] = imm_dominators[same_dom]

    return parent_links_to_tree(imm_dominators)


def get_dominance_frontiers(func):
    """Return a mapping: basic_block -> dominance frontier."""
    # Implementation is based on Modern Compiler Implementation, Andew W.
    # Appel, Chapter 19 Static Single-Assignment Form.

    result = {}
    dom_tree = get_dominator_tree(func)

    def process_node(basic_block):
        df = set()
        # First compute DF_local[basic_block].
        for bb in basic_block.successors:
            if dom_tree.get_parent(bb) != basic_block:
                df.add(bb)
        for bb in dom_tree.get_children(basic_block):
            process_node(bb)
            # Compute DF_up[bb].
            for bb_front in result[bb]:
                if not dom_tree.is_ancestor(bb_front, basic_block):
                    df.add(bb_front)
        result[basic_block] = df

    process_node(func.entry)
    return dom_tree, result
