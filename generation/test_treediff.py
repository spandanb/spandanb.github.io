from treediff import compare, UpdateAttrib
from treeparser import TreeParser


def diff_text(text0, text1):
    parser = TreeParser()

    parser.feed(text0)
    tree = parser.finalize()
    root0 = tree.get_root(as_qmnode=True)

    parser.feed(text1)
    tree = parser.finalize()
    root1 = tree.get_root(as_qmnode=True)
    diff = compare(root0, root1)
    return diff


def test_update_attrib():
    text0 = '<html class="foo"></html>'
    text1 = '<html class="bar"></html>'

    diff = diff_text(text0, text1)

    # print(diff)
    # pretty_print_diff(diff)
    assert len(diff) == 1
    assert isinstance(diff[0], UpdateAttrib)
    assert diff[0].old_value == "foo"
    assert diff[0].new_value == "bar"


def test_other():
    # text0 = '<html><body class="man">foo</body></html>'
    # text1 = '<html><body class="poo">food</body></html>'

    # text0 = '<html class="foo" id="meID">body1</html>'
    # text1 = '<html class="bar">body1</html>'

    text0 = '<html class="foo"><div>body0</div></html>'
    text1 = '<html class="foo"><span>body0</span></html>'

    diff = diff_text(text0, text1)
    # TODO: assertions
