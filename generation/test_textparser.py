from textparser import enrich_links, enrich_subheadings


def test():
    lines = ["hello world http://docs.python.com"]
    lines = enrich_links(lines)
    expected = ["hello world <a href=http://docs.python.com>http://docs.python.com</a>"]
    assert lines == expected, "enrich link result doesn't match"

    lines = ["foo", "#subheading", "bar"]
    lines = enrich_subheadings(lines)
    expected = ["foo", "<h3>subheading</h3>", "bar"]

    assert lines == expected, "enrich subheadings result doesn't match"
