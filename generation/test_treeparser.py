import pytest
import treeparser as tp


def test_simple_html_roundtrip():
    """
    do a simple roundtrip of html text -> tree -> text
    """
    parser = tp.TreeParser()
    parser.feed("<html><body>foo</body></html>")
    tree = parser.finalize()
    # modify tree
    root = tree.get_root(as_qmnode=True)
    root.descendent("body").set_attr("class", "fooclass")
    # print tree
    printer = tp.TreePrinter()
    expected = '<html><body class="fooclass">foo</body></html>'
    actual = printer.mk_doc(root.node)
    assert expected == actual, "test fail"


def test_malformed_html_missing_starttag():
    """
    do a simple roundtrip of html text -> tree -> text
    """
    parser = tp.TreeParser()
    with pytest.raises(tp.MissingStartTag):
        parser.feed("<html>foo</body></html>")
        parser.finalize()
