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
    '''`
    unspecified whether it's open-and closed or just closed
    '''
    pass


class OpenClosedNode(Node):
    pass


class ClosedNode(Node):
    '''
    represents a self closing tag
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
    '''
    def __init__(self, comment):
        super().__init__('COMMENT')
        self.comment = comment


### Processing

class TreeParser(HTMLParser):
    '''
    Parses HTML text into a DOM tree
    
    Using a stack based parser doesn't work
    since html 5 allows standalone
    non-self-closing tags, i.e. since these
    tags look like start tag, they can only be
    distinguished from standard opening tags
    if you know the standard.

    The new algorithm is to:
        - store a list of start tags seens so far
        - on endtag, find the starttag 
            - since html nesting is proper, any unclosed tags
               in list of tags must be standalone
    '''

    def __init__(self):
        '''
        '''
        super().__init__()
        # root of tree
        self.root = RootNode()
        # list of nodes seen so far
        self.nodes = []
        # dict of tagname -> list of idx/position in self.nodes
        self.tagpos = defaultdict(list)
        
        # index nodes by tag and attrs
        self.id_idx = {}  # id -> Node
        self.tag_idx = defaultdict(list)

    def update_indices(self, node: Node):
        # not indexing on tag
        
        # index attrs
        for key, value in node.attrs:
            # index by Id
            if key == 'id':
                self.id_idx[value] = node
        
        self.tag_idx[node.tag].append(node)
        
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
        convert standalone nodes to ClosedNode
        '''
        result = []
        for node in nodes:
            if isinstance(node, UnspecifiedNode):
                result.append(ClosedNode(tag=node.tag, attrs=node.attrs))
                self.update_indices(node)
                # print(f'CN: {result[-1]}')
            else:
                result.append(node)
        return result

    def finalize(self):
        # whatever is left must be children of root
        for node in self.nodes:
            self.root.children.append(node)

    '''
    transformation API below
    
    the current API supports id based mutation
    to build a generic API would require exposing
    a generic way to search and mutate nodes
    
    namely, search on id, attr, and tag is sufficient
    
    '''
    def add_class_by_id(self, objectid: str, classname: str):
        '''
        Add class to node with objectid
        TODO: remove/replace with new API
        '''
        node = self.id_idx[objectid]
        newval = classname
        classidx = -1
        for idx, (key, value) in enumerate(node.attrs):
            # TODO: does case-sensitivity matter here
            if key == 'class':
                newval = f'{value} {classname}'
                classidx = idx
                break
        # class attr exists; update it
        if classidx != -1:            
            node.attrs[classidx] = ('class', newval)
        else:
            node.attrs.append('class', newval)

    def set_attr_by_id(self, objectid: str, attrname: str, attrval: str):
        '''
        set `attrname` on node with `objectid` value `attrval`
        either deprecate the implementation or
            atleast remove this implementation
        TODO: remove/replace with new API
        '''
        # test and replace with below 
        # node = self.find_node_with_id(objectid)
        # self.set_attr(node, attrname, attrval)
        
        node = self.id_idx[objectid]
        attridx = -1
        for idx, (key, value) in enumerate(node.attrs):
            if key == attrname:
                attridx = idx
                break
        # if attr not found, set it
        if attridx == -1:
            node.attrs.append((attrname, attrval))
        else:
            node.attrs[attridx] = (attrname, attrval)

        
    def set_attr(self, node, attrname, attrval):
        attridx = -1
        for idx, (key, value) in enumerate(node.attrs):
            if key == attrname:
                print(f'attrname is "{attrname}"')
                attridx = idx
                break
        # if attr not found, add it
        if attridx == -1:
            node.attrs.append((attrname, attrval))
        else:
            node.attrs[attridx] = (attrname, attrval)
 
    def find_node_with_id(self, objectid) -> Node:
        '''
        ID must be unique
        '''
        return self.id_idx[objectid]

    def find_nodes_with_fn(self, match_fn, node=None, descend=True)->list:
        '''        
        find descendent node that matches `match_fn`. All search includes
        `rootnode` and it's children
 
        Arguments:
            match_fn(Function):
            rootnode(Node): node whose descendents to search; if none start at tree root
            descend: determines whether search scoped to children of `rootnode` or all descendents
        '''
        if node is None:
            node = self.root

        # do a shallow search
        if not descend:           
            return [match_fn(item) for item in ([node] + node.children)]
        
        # do a BFS 
        matches = []
        queue = deque()
        queue.append(node)
        while queue:
            item = queue.popleft()
            # if item.tag == 'a': print(f'item is {item}')
            if match_fn(item):
                matches.append(item)
            queue.extend(item.children)
                
        return matches
                
    def find_nodes_with_attr(self, attrname, attrval, node=None, descend=True):
        def match_fn(node):
            '''return True node contains attrname with attrval'''
            for attr, val in node.attrs:
                if attrs == attrname:
                    if val == attrval:
                        return True
            return False
        return find_nodes_with_fn(match_fn, node, descend)
    
    def find_nodes_with_tag(self, tag, node=None, descend=True):
        def match_fn(node):
            '''return True if node tag matches'''
            return node.tag == tag
        return self.find_nodes_with_fn(match_fn, node, descend)
        

class TreePrinter:

    def __init__(self, root):
        self.root = root

    def format_node(self, node: Node, is_starttag=True):
        '''
        convert node to html text
        '''
        return self.format_starttag(node) if is_starttag else self.format_endtag(node)

    def format_endtag(self, node):
        '''
        '''
        if isinstance(node, (RootNode, ClosedNode)):
            return ''
        return f'</{node.tag}>'

    def format_starttag(self, node):
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

    def format_attrs(self, attrs):
        '''
        attrs is a list of the form [(k1, v1)...(kn, vn)]
        '''
        if attrs is None:
            return ''
        res = []
        for (key, value) in attrs:
            res.append(f'{key}="{value}"')
        return ' '.join(res)

    def to_str(self, node: Node, result: list):
        '''
        recursive to_str
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

    def mk_doc(self):
        result = []
        self.to_str(self.root, result)
        return ''.join(result)



def mk_tree(filepath):
    fpath, fext = os.path.splitext(filepath)
    outfilepath = f'{fpath}-rtrip.{fext}'

    parser = TreeParser()
    with open(filepath, encoding='utf-8') as fp:
        parser.feed(fp.read())
    parser.finalize()
    
    # apply transforms
    parser.add_class_by_id('nav-item-essays', 'active')

    printer = TreePrinter(parser.root)
    with open(outfilepath, 'w', encoding='utf-8') as fp:
        result = printer.mk_doc()
        fp.write(result)

    print(f'Read {filepath}; Writing to {outfilepath}')



if __name__ == '__main__':
    #filepath = r'C:\Users\spand\universe\personal_website2\art-listing-generated.html'
    filepath = r'C:\Users\spand\universe\html_parser\hello2.html'
    mk_tree(filepath)
