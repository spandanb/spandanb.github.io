"""
use jinja to generate site pages

"""
import os
import yaml
import itertools

from collections import namedtuple, defaultdict
from jinja2 import Environment, FileSystemLoader
from typing import List

import textparser
import treeparser
import treediff

###  Config
SELF_PATH = os.path.dirname(os.path.realpath(__file__))
TEMPLATE_DIR = os.path.join(SELF_PATH, r"..\templates")
OUTPUT_DIR = os.path.join(SELF_PATH, r"..")
CONTENT_DIR = os.path.join(SELF_PATH, r"..\content")
IMG_DIR = os.path.join(SELF_PATH, r"..\img")
# IMG_CONTENT_DIR is where images produced by me are stored
IMG_CONTENT_DIR = os.path.join(SELF_PATH, r"..\pics")
INDEX_FILE = os.path.join(SELF_PATH, r"..\index.html")
# determines whether intermediate output files are stored
DEBUG = False
# on listing pages, I show the first line of content
# truncate the line if longer limit
PREVIEW_LINE_LIMIT = 135
"""
Notes
the yaml files may be sensitive to tab characters

Random:
    it's cool I get to implement a crude JQuery, DOM, etc.
    -have some tests
    - this should be above all easy to maintain

TODO:
    - perhaps DEBUG should be like log levels
    - ensure, no tabs (including in .yaml files)
    - jinja should throw exception on unspecified vars

"""

"""
Design Decisions:
- Transforming trees vs text:
Everything can be expressed via jinja templates.
But, this is not very elegant, since every bit of html that can change
has to be controlled via variable. The alternative is to
apply tranformations on a tree. Transforming a tree is easier
because, one can specify which node to find, and transform.
I've opted for this when possible. But this does mean the tree
has to be searchable and updatable.
"""

### Data Structs/Classes


class CMetadata:
    """
    Content metadata
    """

    def __init__(
        self,
        title: str,
        date: str,
        section: str,
        content_id: str,
        template_id: str,
        image_id: str = "",
        image_attribution: str = "",
    ):
        self.title = title
        self.date = date
        self.section = section
        self.content_id = content_id
        self.template_id = template_id
        self.image_id = image_id
        self.image_attribution = image_attribution

    def __repr__(self):
        return f"CM[{self.__dict__}]"

    def get_contentpath(self):
        return os.path.join(CONTENT_DIR, self.section, self.content_id)


class ICMetadata:
    """
    Image Content metadata
    """

    def __init__(
        self, title: str, date: str, section: str, image_id: str, subtext: str
    ):
        self.title = title
        self.date = date
        self.section = section
        self.image_id = image_id
        self.subtext = subtext

    def __repr__(self):
        return f"ICM[{self.__dict__}]"

    def get_contentpath(self):
        return os.path.join(IMG_CONTENT_DIR, self.image_id)


class LMetadata:
    """
    listing metadata
    """

    def __init__(
        self,
        section: str,
        section_title: str,
        template_id: str,
        subtext: str = "",
        image_content: bool = False,
    ):
        # section has no whitespace - unique id
        self.section = section
        # actual title, with whitespace and capitalization
        self.section_title = section_title
        self.template_id = template_id
        self.subtext = subtext
        self.image_content = image_content

    def __repr__(self):
        return f"LM[{self.__dict__}]"


class ValidationError(Exception):
    """
    Generic exception raised on validation failure
    """


### Utils


def get_relpath(fpath: str, refpath=OUTPUT_DIR) -> str:
    """
    get `fpath` relative to `refpath`
    """
    return os.path.relpath(fpath, refpath)


def flatten(iterable: List) -> List:
    """
    flatten a 2-d iterable object
    """
    return [subitem for item in iterable for subitem in item]


def decorate_path(filepath: str, dec: str) -> str:
    """
    example: "foo.html", "meow" -> foo-meow.html
    """
    fpath, ext = os.path.splitext(filepath)
    return f"{fpath}-{dec}{ext}"


def read_all(filepath: str) -> str:
    """Read entire file as string"""
    with open(filepath, encoding="utf-8") as fp:
        return fp.read()


def get_line(content_path: str, maxlen: int = 1000) -> str:
    """
    get first line from file at `content_path`
    return atmost `maxlen` characters of first line
    """
    result = ""
    with open(content_path, encoding="utf-8") as fp:
        for line in fp:
            result = line
            break
    # truncate line if needed
    if len(result) > maxlen:
        result = f"{result[:maxlen]} ... "
    return result


def get_lines(content_path: str) -> List:
    """
    get all lines at filepath
    """
    lines = []
    with open(content_path, encoding="utf-8") as fp:
        lines = fp.readlines()
    return lines


### Content Generation


def generate_content(metadata: CMetadata) -> str:
    """
    generate content for file specified in `metadata`
    and write output to output file. Returns output-filepath
    """
    # convert text content to html block
    content_path = metadata.get_contentpath()

    text = get_lines(content_path)
    block = textparser.text_to_html(text)

    # configure jinja environment
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    # find template
    template = env.get_template(metadata.template_id)

    # render template
    image_location = get_relpath(os.path.join(IMG_DIR, metadata.image_id))
    rendered = template.render(
        title=metadata.title,
        date=metadata.date,
        body=block,
        image_location=image_location,
        image_attribution=metadata.image_attribution,
        is_content_page=True,
    )

    # content_id is: <foo>.txt
    baseid, _ = os.path.splitext(metadata.content_id)
    # write output
    if DEBUG:
        output_filepath = os.path.join(OUTPUT_DIR, f"{baseid}-generated.html")
    else:
        output_filepath = os.path.join(OUTPUT_DIR, f"{baseid}.html")
    print(f"writing {metadata.section} {baseid} to {output_filepath}")
    with open(output_filepath, "w", encoding="utf-8") as fp:
        fp.write(rendered)
    return output_filepath


def generate_content_listing(metadata: LMetadata, items: list) -> str:
    """
    generate a specific listing page and return output filepath
    """
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    # find template
    template = env.get_template(metadata.template_id)

    # represents how an item will be viewed
    ItemView = namedtuple("ItemView", "title teaser")

    # transform items into listings
    listings = []
    for item in items:
        content_path = item.get_contentpath()
        teaser = get_line(content_path, maxlen=PREVIEW_LINE_LIMIT)
        listings.append(ItemView(item.title, teaser))

    # if subtext is unset, make it empty
    # TODO: maybe the subtext element in the listing should be ommitted?
    if not metadata.subtext:
        metadata.subtext = ""

    rendered = template.render(
        section_title=metadata.section_title,
        subtext=metadata.subtext,
        listings=listings,
    )
    if DEBUG:
        output_filepath = os.path.join(
            OUTPUT_DIR, f"{metadata.section}-listing-generated.html"
        )
    else:
        output_filepath = os.path.join(OUTPUT_DIR, f"{metadata.section}-listing.html")
    print(
        f"writing listing {metadata.section} to {output_filepath} with {len(items)} items"
    )
    with open(output_filepath, "w", encoding="utf-8") as fp:
        fp.write(rendered)
    return output_filepath


def generate_image_listing(metadata: LMetadata, items: list) -> str:
    """
    similar to generate_listings, but handles images
    """
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template(metadata.template_id)

    ItemView = namedtuple("ItemView", "title subtext rel_location")
    listing = []
    for item in items:
        subtext = f"{item.subtext}, {item.date}"
        relloc = get_relpath(item.get_contentpath())
        listing.append(ItemView(item.title, subtext, relloc))

    print(f"generate_image_listing {metadata.section} listing={listing}")

    if not metadata.subtext:
        metadata.subtext = ""

    rendered = template.render(
        section_title=metadata.section_title, subtext=metadata.subtext, listing=listing
    )
    if DEBUG:
        output_filepath = os.path.join(
            OUTPUT_DIR, f"{metadata.section}-listing-generated.html"
        )
    else:
        output_filepath = os.path.join(OUTPUT_DIR, f"{metadata.section}-listing.html")
    print(
        f"writing listing {metadata.section} to {output_filepath} with {len(items)} items"
    )
    with open(output_filepath, "w", encoding="utf-8") as fp:
        fp.write(rendered)
    return output_filepath


def generate_all_content(content_file: str) -> dict:
    """
    generate all content files
    """
    content = None
    with open(content_file) as fp:
        content = yaml.safe_load(fp)
    contentfiles = defaultdict(list)
    for section, items in content.items():
        # print(f'Processing section: {section}')
        for item in items:
            metadata = CMetadata(section=section, **item)
            generated = generate_content(metadata)
            contentfiles[section].append(generated)

    return contentfiles


def generate_listings(
    listings_file: str, content_file: str, img_content_file: str
) -> dict:
    """
    Generate all the listings file
    listings of images don't have children content files
    """
    content = None
    with open(content_file) as fp:
        content = yaml.safe_load(fp)
    img_content = None
    with open(img_content_file) as fp:
        img_content = yaml.safe_load(fp)

    listings = None
    with open(listings_file) as fp:
        listings = yaml.safe_load(fp)

    results = {}  # section -> filepath
    for section, props in listings.items():
        if props is None:
            print(f'Skipping listing generation for section: "{section}"; empty props')
            continue

        lmetadata = LMetadata(section=section, **props)
        if lmetadata.image_content:
            listing = [
                ICMetadata(section=section, **item)
                for item in img_content.get(section, [])
            ]
            results[section] = generate_image_listing(lmetadata, listing)
        else:
            listing = [
                CMetadata(section=section, **item) for item in content.get(section, [])
            ]
            results[section] = generate_content_listing(lmetadata, listing)
    return results


def construct_trees(
    listing_fpaths: dict, content_fpaths: dict, index_fpath: str
) -> tuple:
    """
    Creates tree for each listing and content file.
    The return structure is same as the argument structure
    """
    # section name -> tree
    ltrees = {}
    # section name -> [tree]
    ctrees = defaultdict(list)
    # parser
    tparser = treeparser.TreeParser()

    # create trees for listing files
    for (section, filepath) in listing_fpaths.items():
        # read file to tree
        tparser.feed(read_all(filepath))
        tree = tparser.finalize()
        ltrees[section] = tree

    # create trees for content files
    for section, filepaths in content_fpaths.items():
        for idx, filepath in enumerate(filepaths):
            tparser.feed(read_all(filepath))
            tree = tparser.finalize()
            ctrees[section].append(tree)

    # create index.html tree
    tparser.feed(read_all(index_fpath))
    itree = tparser.finalize()

    return ltrees, ctrees, itree


def transform_html(
    listing_fpaths: dict, content_fpaths: dict, listing_trees: dict, content_trees: dict
) -> None:
    """
    express transformations on a DOM tree. Some transformations, e.g.
    add class "active" on a class are easier expressed on a tree, than as
    transformations applied on text.
    Arguments:
        listing_fpaths(dict): dict[section]-> listing_path
        content_fpaths(dict): dict[section]-> [content_paths]
    Returns:
        dict: section -> tree
    """

    # handle listing files
    for section, filepath in listing_fpaths.items():
        # lookup tree
        tree = listing_trees[section]

        # set active on nav item
        node = tree.find_node_with_id(f"nav-item-{section}")
        node.add_class("active")

        # enrich see more link on listing page
        # by creating a link to the referenced content page
        # this assumes content_paths are in same order as on listing
        node = tree.find_node_with_id("listing-container")
        for i, desc_node in enumerate(node.descendents(tag="a")):
            content_path = (content_fpaths.get(section, []))[i]
            link = get_relpath(content_path)
            desc_node.set_attr("href", link)

        # write output
        outfilepath = decorate_path(filepath, "mutated") if DEBUG else filepath
        print(f"transforming {section} at {filepath} to {outfilepath}")
        # import pdb; pdb.set_trace()
        printer = treeparser.TreePrinter(tree.get_root(as_qmnode=False))
        with open(outfilepath, "w", encoding="utf-8") as fp:
            result = printer.mk_doc()
            fp.write(result)

    # handle content files
    for section, filepaths in content_fpaths.items():
        for idx, filepath in enumerate(filepaths):
            # lookup tree
            tree = content_trees[section][idx]

            # set navbar active
            node = tree.find_node_with_id(f"nav-item-{section}")
            node.add_class("active")

            # set prev, next links
            # set prev
            if idx != 0:
                prev_fpath = get_relpath(filepaths[idx - 1])
                if DEBUG:
                    # if DEBUG, intermediate files are preserved
                    # temporarily to test on mutated file
                    # hence, set link to correct file
                    prev_fpath = decorate_path(prev_fpath, "mutated")

                tree.find_node_with_id("prev_link").set_attr("href", prev_fpath)
            # set next
            if idx != len(filepaths) - 1:
                next_fpath = get_relpath(filepaths[idx + 1])
                if DEBUG:
                    next_fpath = decorate_path(next_fpath, "mutated")
                tree.find_node_with_id("next_link").set_attr("href", next_fpath)

            # get output filepath
            outfilepath = decorate_path(filepath, "mutated") if DEBUG else filepath
            print(f"transforming {section} at {filepath} to {outfilepath}")
            # printer = parser.TreePrinter(tparser.root)
            printer = treeparser.TreePrinter(tree.get_root(as_qmnode=False))
            with open(outfilepath, "w", encoding="utf-8") as fp:
                result = printer.mk_doc()
                fp.write(result)


def validations(
    listing_fpaths: dict,
    content_fpaths: dict,
    index_fpath: str,
    listing_trees: dict,
    content_trees: dict,
    index_tree: dict,
):
    """
    Apply validations to generated files.

    Currently applying:
    1) ensure files aren't empty
    2) index file and a generated file navbar only differ in 'active' class

    Thoughts:
    - perhaps have a diff mode
    - validate DOM tree- i.e. do all nodes closes
    """
    print("Applying validations....")

    # validation: ensure files are not empty
    vname = "files not empty"
    print(f"Applying validation: {vname}")
    # combine all files into one iterable
    filepaths = itertools.chain(
        listing_fpaths.values(), flatten(content_fpaths.values()), [index_fpath]
    )
    for filepath in filepaths:
        if os.path.getsize(filepath) == 0:
            raise ValidationError(f"file {filepath} is empty")

    # validation: index and generated should have identical navbar, except for active
    vname = "index matches generated"
    print(f"Applying validation: {vname}")
    # since navbar is generated from same template
    # need to only compare index with only one generated file
    # assuming there is one navbar
    # find navbar elements
    idx_nav = index_tree.get_root().descendent(tag="nav")
    gen_nav = next(iter(listing_trees.values())).get_root().descendent(tag="nav")
    # get page name
    gen_page = next(iter(listing_fpaths.values()))

    print(f"comparing {gen_page}, {index_fpath}")
    # get diff
    navdiff = treediff.compare(idx_nav, gen_nav)
    # treediff.pretty_print_diff(navdiff)
    for subdiff in navdiff:
        if isinstance(subdiff, treediff.UpdateAttrib):
            attrname = subdiff.path.tail().node
            if attrname == "class":
                classdiff = set(subdiff.old_value.split()).symmetric_difference(
                    set(subdiff.new_value.split())
                )
                # check that the only class is `active`
                if len(classdiff) != 1 or next(iter(classdiff)) != "active":
                    raise ValidationError(f"Unexpected change {subdiff}")
            else:
                raise ValidationError(f"Unexpected change {subdiff}")

        else:
            # this indicates something isn't as expected
            raise ValidationError(f"Unexpected change {subdiff}")


def driver():
    """
    generate pages
    """
    dir_path = os.path.dirname(os.path.realpath(__file__))
    content_file = os.path.join(dir_path, "./content.yaml")
    image_content_file = os.path.join(dir_path, "./image_content.yaml")
    listings_file = os.path.join(dir_path, "./sections.yaml")

    # section -> filepath
    lfiles = generate_listings(listings_file, content_file, image_content_file)
    # section -> [filepaths]
    cfiles = generate_all_content(content_file)
    # print_contents(content_file)

    # construct trees
    ltrees, ctrees, itree = construct_trees(lfiles, cfiles, INDEX_FILE)
    # apply transforms
    transform_html(lfiles, cfiles, ltrees, ctrees)
    # apply validations
    validations(lfiles, cfiles, INDEX_FILE, ltrees, ctrees, itree)


if __name__ == "__main__":
    # determines whether intermediate files are written out separately
    DEBUG = False
    print(f"DEBUG is {DEBUG}")
    driver()
