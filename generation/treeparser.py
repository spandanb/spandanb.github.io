'''
parse html document into a tree
modify document
write document

ideally preserve whitespace
ideally preserve comments in generated html

I realize that I'm going to end up implementing a really crude
DOM and jquery, but that's kind of the point
'''
import os.path
from html.parser import HTMLParser
from collections import deque, namedtuple, defaultdict

### Data structs

class Node:
    '''
    DOM node corresponding to html element
    '''
    def __init__(self, tag, attrs=None):
        self.tag = tag
        self.attrs = attrs
        self.children = []

    def __repr__(self):
        return f'Node({self.tag}, attrs={self.attrs})'


class RootNode(Node):
    '''
    '''
    def __init__(self):
        super().__init__('ROOT')
        self.doctype = None


class UnspecifiedNode(Node):
    '''
    TODO: Rename to UndeterminedNode
    unspecified whether it's open-and closed or just closed
    '''
    pass


class OpenClosedNode(Node):
    '''
    A node with an open and closed tag, e.g. <p></p>
    '''
    pass


class ClosedNode(Node):
    '''
    represents a self closing tag
    <img\>
    '''
    def __init__(self, *args, closing_marker=False, **kwargs):
        '''
        `closing_marker` True refers to to a self-closing tag, e.g. <img \>
                         False refers to a standalone tag <meta>
        '''
        self.closing_marker = closing_marker
        super().__init__(*args, **kwargs)


class DataNode(ClosedNode):
    '''
    handle these like self-enclosing tags
    '''
    def __init__(self, data):
        super().__init__('DATA')
        self.data = data


class CommentNode(ClosedNode):
    '''
    represents a comment
    '''
    def __init__(self, comment):
        super().__init__('COMMENT')
        self.comment = comment


### Processing Functions

def find_nodes_with_fn(match_fn, node, descend=True, single=False)->list:
    '''
    find descendent node that matches `match_fn`. All search includes
    `rootnode` and it's children

    Arguments:
        match_fn(Function):
        rootnode(Node): node whose descendents to search; if none start at tree root
        descend: determines whether search scoped to children of `node` or all descendents
        single(bool): if true, return first result else return all results
    '''
    maxdepth = float('inf')
    if not descend:
        maxdepth = 1

    # do a BFS
    matches = []  # result set
    queue = deque()
    NodeDepth = namedtuple('NodeDepth', 'node depth')
    queue.append(NodeDepth(node, 0))
    while queue:
        item, depth = queue.popleft()
        if match_fn(item):
            matches.append(item)
        # handle request for first element only
        if len(matches) > 0 and single:
            return matches

        if depth + 1 <= maxdepth:
            # only process upto maxdepth; i.e. don't need to add anything beyond maxdepth
            next_gen = [NodeDepth(child, depth+1) for child in item.children]
            queue.extend(next_gen)

    return matches


def find_nodes_with_attr(node, attr, descend=True):
    '''
    find nodes with matching attr
    '''
    match_fn = lambda node: any(key for key, val in node.attrs if key == attr)
    find_nodes_with_fn(match_fn, node, descend)


def find_nodes_with_attrval(node, attr, attrval, descend=True):
    '''
    find nodes contains matching attribute (`attrname`)
    with corresponding value (`attrval`)
    '''
    def match_fn(node):
        for attr, val in node.attrs:
            if attr == attr:
                if val == attrval:
                    return True
        return False
    return find_nodes_with_fn(match_fn, node, descend)


def find_nodes_with_tag(node, tag, descend=True):
    '''
    find nodes with matching tag
    '''
    match_fn = lambda node: node.tag == tag
    return find_nodes_with_fn(match_fn, node, descend)

### Processing



class QMNode:
    '''
    Queryable-Modifiable Node:
    represents a node, that can be queryied for descendenants matching certain
    properties or values.
    Creating a node class allows expressing API, like:
       - root.descendents(tag="foo").child().parent().child(text_equals)
    Chaining is achieved by wrapping returning results in this class
    '''
    def __init__(self, node: Node, tree, return_qmnode: bool=True):
        self.node = node
        # store ref to tree
        self._tree = tree
        # whether return objects should be wrapped as QMNode
        # TODO: is this needed?
        self.return_qmnode = return_qmnode

    def wrap_results(self, result: list, single: bool=True):
        '''
        utility method to wrap the results
        depending on specificed `return_qmnode`
        `single` determines whether return is scalar or list
        '''
        if not self.return_qmnode or len(result) == 0:
            return result
        # wrap only if specified
        if single:
            return QMNode(result[0], self._tree) if len(result) == 1 else None
        else:
            return [QMNode(node, self._tree) for node in result]

    def parent(self):
        '''
        return parent node
        '''
        return QMNode(self._tree.get_parent(self.node))

    def child(self, tag=None, attr=None, attrval=None):
        result = Tree.find_nodes(self.node, tag=tag, attr=attr, attrval=attrval, descend=False, single=True)
        return self.wrap_results(result, single=True)

    def children(self, tag=None, attr=None, attrval=None):
        '''
        '''
        result = Tree.find_nodes(self.node, tag=tag, attr=attr, attrval=attrval, descend=False, single=False)
        return self.wrap_results(result, single=False)

    def descendent(self, tag=None, attr=None, attrval=None):
        '''
        '''
        result = Tree.find_nodes(self.node, tag=tag, attr=attr, attrval=attrval, descend=True, single=True)
        return self.wrap_results(result, single=True)

    def descendents(self, tag=None, attr=None, attrval=None):
        '''
        '''
        result = Tree.find_nodes(self.node, tag=tag, attr=attr, attrval=attrval, descend=True, single=False)
        return self.wrap_results(result, single=False)

    def get_attr_index(self, attr):
        '''
        get the index to attr 
        '''
        for idx, (key, value) in enumerate(self.node.attrs):
            if key == attr:
                return idx
        return -1
    
    def get_attr(self, attr: str, notfound=None):
        '''
        get attr value
        '''
        attridx = self.get_attr_index(attr)
        if attridx == -1:
            return notfound
        key, value  = self.node.attrs[attridx]
        return value

    def set_attr(self, attr, attrval):
        '''
        set attr
        '''
        attridx = self.get_attr_index(attr)
        # if attr not found, add it
        if attridx == -1:
            self.node.attrs.append((attr, attrval))
        else:
            self.node.attrs[attridx] = (attr, attrval)
        
    def set_class(self, classname):
        '''
        this will remove any existing classes
        and set class=`classname`
        '''
        self.set_attr("class", classname)

    def add_class(self, classname):
        '''
        this will add a class to existing classes
        '''
        attridx = self.get_attr_index("class")
        if attridx == -1:
            self.node.attrs.append((attr, attrval))
        else:
            # check if the classname exists
            _, value = self.node.attrs[attridx]
            curr_classes = set(value.split())
            # add if the class isn't already applied
            if classname not in curr_classes:
                new_classes = f'{value} {classname}'
                self.node.attrs[attridx] = ("class", new_classes)

class Tree:
    '''
    Represents the DOM corresponding to the
    parsed text. Contains the search API
    '''
    def __init__(self, root, id_idx: dict, parent_idx: dict):
        self.root = root
        self.id_idx = id_idx
        self.parent_idx = parent_idx

    def get_parent(self, node):
        return self.parent_idx[node]

    def get_root(self, as_qmnode: bool=True):
        if as_qmnode:
            return QMNode(self.root, self)
        return self.root

    def find_node_with_id(self, objectid, as_qmnode: bool = True) -> Node:
        '''
        ID must be unique
        '''
        node = self.id_idx.get(objectid, None)
        if as_qmnode and node is not None:
            return QMNode(node, self)
        return node

    @staticmethod
    def find_nodes(node, tag=None, attr=None, attrval=None, descend=True, single=False)->list:
        '''
        Assumption: I will either do find on ID or another attr; but not both
        hence static method;

        supports three search params:
            - tag
            - attrname and attrval
            - attrval

        root.find(tag="foo", )
        root.find_all(tag="foo")

        root.descendents(tag="foo").child().parent().child(text_equals)

        '''
        if (tag is not None) and (attr is not None):
            # only support one search parameter
            raise NotImplementedError(f"Only single parameter-search supported;In node search both tag ({tag}) and attr ({attr}) val ({attrval}) set")

        matches = []
        if tag is not None:
            matches = find_nodes_with_tag(node, tag)
        elif attr is not None and attrval is not None:
            matches = find_nodes_with_attrval(node, attr, attrval)
        elif attr is not None:
            matches = find_nodes_with_attr(node, attr)
        else:
            # no filter condition; get all nodes
            matches = find_nodes_with_fn(node, lambda node: True)
        return matches


class TreeParser(HTMLParser):
    '''
    Parses HTML text into a DOM tree

    Using a stack based parser doesn't work since html 5 allows standalone
    non-self-closing tags, i.e. since these tags look like start tag,
    they can only be distinguished from standard opening tags via the spec.

    The current algorithm is to:
        - store a list of start tag nodes seens so far (`self.nodes`)
        - on endtag, use the `tagpos` index to find the starttag
        - the start and end form a opening-closing tag pair
        - nodes in between are children, which are coalesced in `coalesce`
          i.e. added as children
        - at the end, any remaining children must be children of root
    '''

    def __init__(self):
        '''
        '''
        super().__init__()
        self._init()

    def _init(self):
        '''
        custom init function that can be used to reset parser
        '''
        # root of tree
        self.root = RootNode()
        # these are used to construct the tree
        # list of nodes seen so far
        self.nodes = []
        # dict of tagname -> list of idx/position in self.nodes
        self.tagpos = defaultdict(list)

        # index nodes by id
        # can't construct global indices, e.g. on class, tag
        # since, the search semantics is that it's scoped; to filter
        # to children of the scoping node, would require the search
        self.id_idx = {}
        self.parent_idx = {}
        self.output_tree = None  # the DOM tree that the parser produces

    def update_indices(self, node: Node):
        # index id
        for key, value in node.attrs:
            # index by Id
            if key == 'id':
                self.id_idx[value] = node

        for child in node.children:
            self.parent_idx[child] = node

    def handle_starttag(self, tag, attrs):
        # print(f'handling STARTTAG {tag}; attrs={attrs}')
        node = UnspecifiedNode(tag, attrs)
        self.nodes.append(node)
        idx = len(self.nodes) - 1
        self.tagpos[tag].append(idx)

    def handle_endtag(self, tag):
        # print(f'handling ENDTAG {tag}')
        # if this doesn't exist -> closing tag without opening tag -> malformed html
        starttag_idx = self.tagpos[tag].pop()

        node = self.nodes[starttag_idx]
        # construct specific node
        node = OpenClosedNode(tag, node.attrs)
        node.children = self.coalesce(self.nodes[starttag_idx+1:])
        # drop everything upto starttag_idx
        self.nodes = self.nodes[:starttag_idx]
        self.nodes.append(node)
        self.update_indices(node)

    def handle_startendtag(self, tag, attrs):
        node = ClosedNode(tag, attrs=attrs, closing_marker=True)
        self.nodes.append(node)
        self.update_indices(node)

    def handle_data(self, data: str):
        '''handle data
        '''
        node = DataNode(data)
        self.nodes.append(node)

    def handle_decl(self, decl: str):
        self.root.doctype = decl

    def handle_comment(self, comment: str):
        node = CommentNode(comment)
        self.nodes.append(node)

    def coalesce(self, nodes: list):
        '''
        aggregate op invoked by parent node, on children `nodes`/
        convert standalone nodes to ClosedNode
        '''
        result = []
        for node in nodes:
            # this node hasn't been closed; we can definitively say this is
            # stanalone, i.e. ClosedNode
            if isinstance(node, UnspecifiedNode):
                result.append(ClosedNode(tag=node.tag, attrs=node.attrs))
                self.update_indices(node)
            else:
                result.append(node)
        return result

    def finalize(self)->Tree:
        '''
        perform any finalization operations and return
        Tree that is generated from parse.
        '''
        # perform finalize operation
        # any remaining nodes must be children of root, since
        # we never explicitly encounter the end, we need to do
        # it when requester implicitly commits tree has been read

        # condition makes operation idempotent
        # Note: this operation can only be called once
        for node in self.nodes:
            self.root.children.append(node)
        result = Tree(self.root, self.id_idx, self.parent_idx)
        # reset all internal data structure
        self._init()
        return result


class TreePrinter:
    '''
    handle printing tree
    '''
    def __init__(self, root):
        self.root = root

    def format_node(self, node: Node, is_starttag=True)-> str:
        '''
        convert node to html text
        '''
        return self.format_starttag(node) if is_starttag else self.format_endtag(node)

    def format_endtag(self, node)->str:
        '''
        '''
        if isinstance(node, (RootNode, ClosedNode)):
            return ''
        return f'</{node.tag}>'

    def format_starttag(self, node)->str:
        '''
        '''
        if isinstance(node, RootNode):
            return f'<!{node.doctype}>' if node.doctype else ''
        if isinstance(node, CommentNode):
            return f'<!-- { node.comment} -->'
        if isinstance(node, DataNode):
            return node.data

        attrs = self.format_attrs(node.attrs)
        if attrs == '':
            return f'<{node.tag}>'
        else:
            return f'<{node.tag} {attrs}>'

    def format_attrs(self, attrs)->str:
        '''
        attrs is a list of the form [(k1, v1)...(kn, vn)]
        '''
        if attrs is None:
            return ''
        res = []
        for (key, value) in attrs:
            res.append(f'{key}="{value}"')
        return ' '.join(res)

    def to_str(self, node: Node, result: list)->None:
        '''
        recursive to_str
        in-place modifies `result` object
        '''
        # handle start tag formatting
        text = self.format_node(node, True)
        result.append(text)

        # handle children
        for child in node.children:
            self.to_str(child, result)

        # handle end tag
        # self-closed and data nodes don't have a closing tag or children
        # endtag will be empty
        text = self.format_node(node, False)
        result.append(text)

    def mk_doc(self)-> str:
        result = []
        self.to_str(self.root, result)
        return ''.join(result)


