"""
This module implements a diff algorithm
for calculating the diff between two DOM trees.
See: treediff.txt for notes
"""
from enum import Enum
from itertools import zip_longest

from treeparser import QMNode, DataNode, CommentNode, RootNode


class ValidationException(Exception):
    pass


class Relationship(Enum):
    """
    A path to an element in a tree is encoded
    as a list of subpaths, where each subpath is
    a child of the parent subpath.
    This enum, en
    """

    Child = 1
    # this is a terminal relationship, i.e. there
    # can't be any children of attr
    Attr = 2
    # special, only for root
    Null = 3


class UpdateBody:
    """
    represents a update-body diff operation
    """

    def __init__(self, path, new_body):
        self.path = path
        self.new_body = new_body

    def __repr__(self):
        return f'UpdateBody [path="{self.path}"; new_body="{self.new_body}"]'


class UpdateAttrib:
    """
    represents a update-attrib diff operation
    """

    def __init__(self, path, old_value, new_value):
        self.path = path
        self.old_value = old_value
        self.new_value = new_value  # str

    def __repr__(self):
        return (
            f'UpdateAttrib [path="{self.path}", "{self.old_value}->{self.new_value}"]'
        )


class AddAttrib:
    def __init__(self, path, value):
        self.path = path
        self.value = value

    def __repr__(self):
        return f'AddAttrib [path="{self.path}", "{self.value}"]'


class DelAttrib:
    def __init__(self, path):
        self.path = path

    def __repr__(self):
        return f'DelAttrib [path="{self.path}"]'


class AddNode:
    """
    # TODO: rename AddNode
    represents a add diff operation
    """

    def __init__(self, path, child_node, child_pos):
        self.path = path
        self.child_node = child_node
        self.child_pos = child_pos

    def __repr__(self):
        return f'AddNode [path="{self.path};  child={self.child_node}; ch_pos={self.child_pos}]'


class DelNode:
    """
    # TODO: rename DelNode
    represents a update-body del operation
    """

    def __init__(self, path):
        self.path = path

    def __repr__(self):
        return f'DelNode [path="{self.path}"]'


class PathElement:
    """
    represents a element in path
    """

    @classmethod
    def root_node(cls, rootnode):
        return cls(Relationship.Null, -1, rootnode)

    def __init__(self, relationship: Relationship, node, position: int = -1):
        """
        `relationship` is w.r.t. to parent node
        `positions` is position in child
        `node` is child; can be tag (
        """
        self.relationship = relationship
        self.node = node
        self.position = position

    def is_root(self):
        return isinstance(self.node, RootNode)

    def __repr__(self):
        if self.is_root():
            return "PNode(root)"
        elif self.relationship == Relationship.Child:
            return f"PNode(child[{self.position}], {self.node.tag})"
        elif self.relationship == Relationship.Attr:
            return f"PNode(Attr[{self.node}])"
        else:
            raise ValidationException("Unrecognized operation")


class TreePath:
    """
    represents a path to an element
    a `TreePath` is composed of many `PathElement` objects
    """

    def __init__(self):
        self.path = []

    def copy(self):
        """
        return a copy of the path
        """
        new_path = TreePath()
        new_path.path = self.path[:]
        return new_path

    def append(self, child_pnode):
        """
        append `child_pnode` to path
        """
        self.path.append(child_pnode)

    def unwrap(self):
        return self.path

    def tail(self):
        """return tail element"""
        return self.path[-1]

    def __repr__(self):
        pathrepr = r"/".join([repr(sub_path) for sub_path in self.path])
        return f"Path({pathrepr})"

    def get_childpath(self, child_node, child_pos):
        """
        return a new `TreePath` node
        with a child appended
        """
        # copy current path
        new_path = self.copy()
        # encode the newnode
        child_pnode = PathElement(Relationship.Child, child_node, child_pos)
        new_path.append(child_pnode)
        return new_path

    def get_attrpath(self, attr):
        """
        return a new `TreePath` node
        with a child appended
        """
        # copy current path
        new_path = self.copy()
        # encode the newnode
        child_pnode = PathElement(Relationship.Attr, attr)
        new_path.append(child_pnode)
        return new_path


### Utilities


def preorder_paths(node, path):
    """
    gets paths to all descendents rooted at `node`
    preorder, i.e. starting with the deepest descendents and going left->right, then node
    """
    # if node has child, descend
    for idx, child in enumerate(node.children):
        # if path isinstance `TreePath`
        child_path = path.get_childpath(child, idx)
        yield from preorder_paths(child, child_path)
    # all descendents exhausted
    yield path.copy()


def postorder_paths(node, path):
    """
    yield paths in node, descendents from left to right
    """
    yield path.copy()
    for idx, child in enumerate(node.children):
        child_path = path.get_childpath(child, idx)
        yield from postorder_paths(child, child_path)


def get_body(node):
    """
    return body of node
    """
    return getattr(node, "data", getattr(node, "comment", None))


### Comparison algorithm


def comp_classes(node1, node2):
    """
    return True if classes and tag match
    """
    return type(node1).__name__ == type(node2).__name__ and node1.tag == node2.tag


def comp_attrs(node1, node2):
    """
    compare attributes and return match (bool)
    and dicts representsing
    attributes to be added, deleted, modified, w.r.t. to node1,
    i.e. these changes applied to node1 will lead to
    same attrs as node2
    """
    add_ops = {}
    # only track attr name for del
    del_ops = set()  # attr
    mod_ops = {}  # attr -> (oldval, newval)

    attrs1 = dict(node1.attrs) if node1.attrs else {}
    attrs2 = dict(node2.attrs) if node2.attrs else {}
    # determine dels and mods
    for attr, val in attrs1.items():
        if attr not in attrs2:
            del_ops.add(attr)
        elif attrs2[attr] != val:
            newval = attrs2[attr]
            mod_ops[attr] = (val, newval)

    # determine adds
    for attr, val in attrs2.items():
        if attr not in attrs1:
            add_ops[attr] = val

    match = len(add_ops) == 0 and len(del_ops) == 0 and len(mod_ops) == 0
    return match, add_ops, del_ops, mod_ops


def comp_body(node1, node2):
    """
    True if both are DataNode and CommentNode and body is the same, False otherwise
    """
    if isinstance(node1, DataNode) and isinstance(node2, DataNode):
        return node1.data == node2.data
    if isinstance(node1, DataNode) or isinstance(node2, DataNode):
        # only one is a DataNode
        return False

    if isinstance(node1, CommentNode) and isinstance(node2, CommentNode):
        return node1.comment == node2.comment
    if isinstance(node1, CommentNode) or isinstance(node2, CommentNode):
        # only one is a CommentNode
        return False

    # doesn't have a body
    return True


def comp(node1, node2, path: TreePath, diff: list):
    """
    implement recursive compare
    """
    # compare class names/tags
    if not comp_classes(node1, node2):
        # classes/tags don't match
        # del descendents of node1 and then node1
        for sub_path in preorder_paths(node1, path):
            diff.append(DelNode(sub_path))

        # add node2 and then all its descendents
        for sub_path in postorder_paths(node2, path):
            child_pos = sub_path.tail().position
            child_node = sub_path.tail().node
            diff.append(AddNode(sub_path, child_node, child_pos))

    # same node type
    else:
        # compare attrs
        is_match, add_attrs, del_attrs, mod_attrs = comp_attrs(node1, node2)
        if not is_match:
            # add-attrib
            # a different diff element for each attribute change
            for attr, attrval in add_attrs.items():
                attr_path = path.get_attrpath(attr)
                diff.append(AddAttrib(attr_path, attr))
            # del attrib
            for attr in del_attrs:
                attr_path = path.get_attrpath(attr)
                diff.append(DelAttrib(attr_path))
            # update-attrib
            for attr, (oldval, newval) in mod_attrs.items():
                attr_path = path.get_attrpath(attr)
                diff.append(UpdateAttrib(attr_path, oldval, newval))

        # compare body
        if not comp_body(node1, node2):
            # update-text
            diff.append(UpdateBody(path.copy(), get_body(node2)))

    # compare children
    for idx, (child1, child2) in enumerate(zip_longest(node1.children, node2.children)):
        if child1 is None and child2 is None:
            pass  # noop
        elif child1 is None:
            # add child2 to as child of path at idx
            new_path = path.copy()
            # NB: the tree should not change when the diff is done
            # since the diff has references to the nodes
            diff.append(AddNode(new_path, child2, idx))
        elif child2 is None:
            # del child1
            new_path = path.get_childpath(child1, idx)
            diff.append(DelNode(new_path, child1))
        else:
            # both child1 and child2 are defined and have same path
            # NOTE: paths are always with respect to left hand side
            new_path = path.get_childpath(child1, idx)
            comp(child1, child2, new_path, diff)


def compare(root1, root2):
    """
    setup and invoke `comp`
    """
    # need to unwrap QMNodes
    if isinstance(root1, QMNode):
        root1 = root1.node
    if isinstance(root2, QMNode):
        root2 = root2.node

    diff = []
    path = TreePath()
    comp(root1, root2, path, diff)
    return diff


### main


def pretty_print_diff(diff):
    """
    helper for pretty printing diff
    """
    print("printing diff:")
    for operation in diff:
        if isinstance(operation, UpdateBody):
            print(f"update-body, {operation.path}, {operation.new_body}")
        elif isinstance(operation, AddAttrib):
            print(f"add-attrib, {operation.path}, {operation.value}")
        elif isinstance(operation, DelAttrib):
            print(f"del-attrib, {operation.path}")
        elif isinstance(operation, UpdateAttrib):
            print(f"update-attrib, {operation.path}, {operation.new_value}")
        elif isinstance(operation, AddNode):
            print(
                f"add, {operation.path}, {operation.child_pos}, {operation.child_node}"
            )
        elif isinstance(operation, DelNode):
            print(f"del, {operation.path}")
        else:
            print(f"ERROR: unrecognized op: {operation}")
