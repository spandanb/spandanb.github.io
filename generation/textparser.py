"""
handle all the custom text transformations to convert
text content into
"""
import re
from typing import List


def insert_footnote_links(lines: List[str]) -> List[str]:
    """
    transforms footnotes in the text. (inplace modifes `lines`)
    If the content has footnotes, it's seperated by
    a line like ___\n. Footnotes are marked as [n] in the content
    and referenced below the separator by [n]. Footnotes are the last lines of content

    To make the footnote a link, transform the line containing
    the first [n] into <a href="footnote-n">[n]</a>
    the second [n], e.g. [n]foobar.. -> <span id="footnote-n">[n]foobar</span>

    e.g.
    foo bar [1] car
    ---
    [1]

    =>
    foo bar <a href="foot-note1">[1]</a> car
    ---
    <span>[1]


    """
    # update markers in content body
    fnnum = 1
    # since i'll in-place modify `lines` don't use
    # an iterator over lines; rather iterate manually using an index
    lineno = 0
    while lineno < len(lines):
        # find marker
        marker = f"[{fnnum}]"
        anchor = f'<a href="#footnote-{fnnum}">[{fnnum}]</a>'

        while lineno < len(lines):
            line = lines[lineno]
            # match found
            if marker in line:
                # replace
                newline = line.replace(marker, anchor)
                lines[lineno] = newline
                # search next footnote num
                fnnum += 1
                break
            else:
                lineno += 1

    # update footnote refs underneath
    FOOTNOTE_DIVIDER = "________________\n"
    # if there are footnotes, they are bottom n lines; iterate from the bottom
    lineno = len(lines) - 1
    while lineno >= 0:
        # don't use an iterator over lines, since I'll be modifying it
        line = lines[lineno]
        if line == FOOTNOTE_DIVIDER:
            break
        match = re.match(r"\[([0-9]+)\](.*)", line)
        if match is None:
            # there are no footnotes
            break
        footnum, fnbody = match.groups()
        lines[lineno] = f'<span id="footnote-{footnum}">{line}</span>'

        lineno -= 1
    return lines


def enrich_links(lines: List[str]) -> List[str]:
    """
    convert all http(s) text to self link
    i.e. foo bar https... car -> foo bar <a href="#https...">https...</a>
    """
    # url regex pattern source: https://stackoverflow.com/a/3809435
    URL_PATTERN = r"https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)"

    lineidx = 0
    while lineidx < len(lines):
        line = lines[lineidx]
        # each line may have multiple matches
        # when we do a replace, we also add any filler chars
        # from the position of previous url match
        prevend = 0
        # collect all chunks
        bucket = []
        for match in re.finditer(URL_PATTERN, line):
            start, end = match.start(), match.end()
            # print(f'match found: {line[start:end]}')
            # append content before match
            bucket.append(line[prevend:start])
            # get this url
            url = line[start:end]
            # append anchor tag
            anchor = f"<a href={url}>{url}</a>"
            bucket.append(anchor)
            # store end idx
            prevend = end
        # last chunk is from prevend to end of line
        bucket.append(line[prevend:])

        if len(bucket) > 1:
            # some replacements happened
            newline = "".join(bucket)
            lines[lineidx] = newline

        lineidx += 1

    return lines


def enrich_subheadings(lines):
    """
    convert a line that starts with # to a header
    e.g.

    # foobar -> <h3> foobar </h3>
    """
    lineidx = 0
    while lineidx < len(lines):
        line = lines[lineidx]
        if line.startswith("#"):
            newline = f"<h3>{line[1:]}</h3>"
            lines[lineidx] = newline
        lineidx += 1
    return lines


def lines_to_chunks(lines: List[str]) -> str:
    """
    Transforms lines of text into space separated
    chunks

    - replaces a\nb with a<br>b
    - replaces a\n(\n)+b  with a<br><br>b

    Arguments:
        text: list[str]
    """

    output = []
    for line in lines:
        stripped = line.strip()
        if len(stripped) > 0:
            output.append(stripped)
            output.append("<br>")
        else:  # len(stripped) == 0
            # we never want more than 2 contiguous <br> elements
            if len(output) >= 2 and output[-1] == "<br>" and output[-2] == "<br>":
                continue
            output.append("<br>")

    # \n to make more human-readable
    return "<p>\n" + "\n".join(output) + "\n</p>"


def text_to_html(lines: List[str]) -> str:
    """
    Apply various transforms to convert
    list of lines to list of html.
    These transformations are not indenpendent, so ordering matters.
    """
    lines = insert_footnote_links(lines)
    lines = enrich_links(lines)
    lines = enrich_subheadings(lines)
    # call this last; all the rest manipulate text as unmarked text
    return lines_to_chunks(lines)
