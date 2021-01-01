"""
static website generation pipeline
"""
import os
import yaml
import itertools

from collections import namedtuple, defaultdict
from jinja2 import Environment, FileSystemLoader

from typing import List, Union, Dict
from collections.abc import Iterable

# local imports
import textparser
import treeparser
import treediff

###  Config
## Config source and output of generation
SELF_PATH = os.path.dirname(os.path.realpath(__file__))
TEMPLATE_DIR = os.path.join(SELF_PATH, r"..\templates")
OUTPUT_DIR = os.path.join(SELF_PATH, r"..")
CONTENT_DIR = os.path.join(SELF_PATH, r"..\content")
IMG_DIR = os.path.join(SELF_PATH, r"..\img")
# IMG_CONTENT_DIR is where images produced by me are stored
IMG_CONTENT_DIR = os.path.join(SELF_PATH, r"..\pics")
INDEX_FILE = os.path.join(SELF_PATH, r"..\index.html")

## Config Generation pipeline
# whether intermediate files are stored; for normal run set `True`
INTERMEDIATE_FILES = False
# whether to apply validations
APPLY_VALIDATIONS = True

## Config controlling generated page styling
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

- settable filename:
The way the filename is generated, it can be overriden through
an external actor; this makes the code non-functional, since
the it can have non-deterministic outcome. To make the code functionally cleaner
I would have to re-write the generation function to have side effects, i.e.
write to file, and that would ruin the original design goal of code simplicity.

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

    @classmethod
    def from_file(cls, filepath: str) -> dict:
        """
        read content file and returns dict: section -> [files]
        """
        content = load_yaml(filepath)
        contentfiles = defaultdict(list)
        for section, items in content.items():
            for item in items:
                metadata = cls(section=section, **item)
                contentfiles[section].append(metadata)
        return contentfiles


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

    @classmethod
    def from_file(cls, filepath: str) -> dict:
        """
        read yaml file and return data structure mimicking structure of file
        i.e. section -> LMetadata
        """
        content = load_yaml(filepath)
        contentfiles = defaultdict(list)
        for section, items in content.items():
            for item in items:
                metadata = cls(section=section, **item)
                contentfiles[section].append(metadata)
        return contentfiles


class LMetadata:
    """
    TODO: rename S(ection)Metadata
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

    @classmethod
    def from_file(cls, filepath: str) -> dict:
        """
        read yaml file and return data structure mimicking structure of file
        i.e. section -> LMetadata
        """
        listings = load_yaml(filepath)
        result = {}
        for section, props in listings.items():
            if props is None:  # empty section
                continue
            result[section] = cls(section=section, **props)

        return result


class ValidationError(Exception):
    """
    Generic exception raised on validation failure
    """


### Utils


def load_yaml(filepath: str):
    """
    read yaml file
    """
    content = None
    with open(filepath) as fp:
        content = yaml.safe_load(fp)
    return content


def get_relpath(fpath: str, refpath=OUTPUT_DIR) -> str:
    """
    get `fpath` relative to `refpath`
    """
    return os.path.relpath(fpath, refpath)


def flatten(iterable: Iterable) -> List:
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

class FileManager:
    """
    file manager used to access files and get prev/next links
    this is initialized with content yaml maps. this makes
    the concerns somewhat mixed; but this is necessary given that I
    want to keep functions (individual components responsible for a part of the
    pipeline) capable of reading/generating/modifying/writing independently of
    other components. So you need this object with some state
    """

    def __init__(
        self, content: dict, output_dir=OUTPUT_DIR
    ):
        """"""
        # content map: section -> CMetadata
        self.content = content
        self.output_dir = output_dir

        self.decoration = ""

    def set_decoration(self, decoration: str):
        """
        This makes it more like FSM; this sets the mode of operation
        this also makes the path generation stateful
        """
        self.decoration = decoration

    def get_listing_filepath(self, section: str):
        decoration = f"-{self.decoration}" if self.decoration else ""
        return os.path.join(self.output_dir, f"{section}-listing{decoration}.html")

    def content_filepath_from_metadata(self, metadata: CMetadata) -> str:
        """
        generate filepath from metadata object
        """
        # content_id is: <foo>.txt
        baseid, _ = os.path.splitext(metadata.content_id)
        decoration = f"-{self.decoration}" if self.decoration else ""
        return os.path.join(self.output_dir, f"{baseid}{decoration}.html")

    def get_content_filepath(self, section, index) -> str:
        """
        get current content path from `section` and `index`
        """
        return self.content_filepath_from_metadata(self.content[section][index])

    def get_prev_content_path(self, section, index) -> str:
        """
        get the previous content path
        """
        if index > 0:
            return self.get_content_filepath(section, index - 1)
        return "#"

    def get_next_content_path(self, section, index) -> str:
        items = self.content[section]
        if index < len(items) - 1:
            return self.get_content_filepath(section, index + 1)
        return "#"


def generate_content(metadata: CMetadata, file_manager: FileManager) -> str:
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

    output_filepath = file_manager.content_filepath_from_metadata(metadata)
    print(f"writing {metadata.section} {metadata.content_id} to {output_filepath}")
    with open(output_filepath, "w", encoding="utf-8") as fp:
        fp.write(rendered)
    return output_filepath


def generate_content_listing(
    metadata: LMetadata, items: list, file_manager: FileManager
) -> str:
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
    output_filepath = file_manager.get_listing_filepath(metadata.section)
    with open(output_filepath, "w", encoding="utf-8") as fp:
        fp.write(rendered)
    return output_filepath


def generate_image_listing(
    metadata: LMetadata, items: list, file_manager: FileManager
) -> str:
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
    output_filepath = file_manager.get_listing_filepath(metadata.section)
    with open(output_filepath, "w", encoding="utf-8") as fp:
        fp.write(rendered)
    return output_filepath


def generate_all_content(content_file: str, file_manager: FileManager) -> dict:
    """
    generate all content files
    """
    contentfiles = defaultdict(list)
    content = CMetadata.from_file(content_file)
    for section, items in content.items():
        for metadata in items:
            generated = generate_content(metadata, file_manager)
            contentfiles[section].append(generated)

    return contentfiles


def generate_listings(
    listings_file: str,
    content_file: str,
    img_content_file: str,
    file_manager: FileManager,
) -> dict:
    """
    generate all listings
    NB: listing of images don't have children content files
    """
    listings = LMetadata.from_file(listings_file)
    content = CMetadata.from_file(content_file)
    img_content = ICMetadata.from_file(img_content_file)

    results = {}  # section -> filepath
    for section, lmetadata in listings.items():

        if lmetadata.image_content:
            img_listing = img_content.get(section, [])
            results[section] = generate_image_listing(
                lmetadata, img_listing, file_manager
            )
        else:
            content_listing = content.get(section, [])
            results[section] = generate_content_listing(
                lmetadata, content_listing, file_manager
            )

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
    content_fpaths: dict,
    listing_trees: dict,
    content_trees: dict,
    file_manager: FileManager,
):
    """
    express transformations on a DOM tree. Some transformations, e.g.
    add class "active" on a class are easier expressed on a tree, than as
    transformations applied on text.
    Arguments:
        listing_fpaths(dict): dict[section]-> listing_path
        content_fpaths(dict): dict[section]-> [content_paths]
    """
    printer = treeparser.TreePrinter()

    # handle listing files
    for section, tree in listing_trees.items():
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
        outfilepath = file_manager.get_listing_filepath(section)
        # print(f"transforming {section} at {filepath} to {outfilepath}")
        with open(outfilepath, "w", encoding="utf-8") as fp:
            result = printer.mk_doc(tree.get_root(as_qmnode=False))
            fp.write(result)

    # handle content files
    for section, trees in content_trees.items():
        for idx, tree in enumerate(trees):
            # lookup tree
            tree = content_trees[section][idx]

            # set navbar active
            node = tree.find_node_with_id(f"nav-item-{section}")
            node.add_class("active")

            # set prev, next links
            # set prev
            if idx != 0:
                prev_fpath = get_relpath(
                    file_manager.get_prev_content_path(section, idx)
                )
                tree.find_node_with_id("prev_link").set_attr("href", prev_fpath)
            # set next
            if idx != len(trees) - 1:
                next_fpath = get_relpath(
                    file_manager.get_next_content_path(section, idx)
                )
                tree.find_node_with_id("next_link").set_attr("href", next_fpath)

            # get output filepath
            outfilepath = file_manager.get_content_filepath(section, idx)
            print(f"transforming {section} to {outfilepath}")
            with open(outfilepath, "w", encoding="utf-8") as fp:
                result = printer.mk_doc(tree.get_root(as_qmnode=False))
                fp.write(result)


def validations(
    listing_fpaths: dict,
    content_fpaths: dict,
    index_fpath: str,
    listing_trees: dict,
    content_trees: dict,
    index_tree: treeparser.Tree,
):
    """
    Apply validations to generated files.

    Currently applying:
    1) ensure files aren't empty
    2) index file and a generated file navbar only differ in 'active' class
    3) validate all generated files have a unique filename

    Thoughts:
    - perhaps have a diff mode
    - validate DOM tree- i.e. do all nodes closes
        -- hmm, this should be something exposed by treeparser

    """

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

    # validation: no files being clobbered because of non-unique file names
    vname = "file names are unique"
    print(f"Applying validation: {vname}")
    counter: Dict[str, int] = defaultdict(int)
    for section, filepaths in content_fpaths.items():
        for filepath in filepaths:
            counter[filepath] += 1
            if counter[filepath] > 1:
                raise ValidationError(f"Non-unique filename '{filepath}'")


def driver():
    """
    generate pages
    handles config for:
        - whether to write intermediate files by manipulating output filename
        - whether to apply validations
    """
    dir_path = os.path.dirname(os.path.realpath(__file__))
    listings_file = os.path.join(dir_path, "./sections.yaml")
    content_file = os.path.join(dir_path, "./content.yaml")
    image_content_file = os.path.join(dir_path, "./image_content.yaml")

    listings = LMetadata.from_file(listings_file)
    content = CMetadata.from_file(content_file)
    image_content = ICMetadata.from_file(image_content_file)

    # construct file manager, which determines
    # the filenames used; this is intended to facilitate debugging
    # see design-decisions (settable filename)
    file_manager = FileManager(content)

    if INTERMEDIATE_FILES:
        file_manager.set_decoration("generated")

    print(f"{os.linesep}Generating listings...")
    # generate listings
    lfiles = generate_listings(
        listings_file, content_file, image_content_file, file_manager
    )  # section -> filepath

    print(f"{os.linesep}Generating content...")
    # generate content
    cfiles = generate_all_content(content_file, file_manager)  # section -> [filepaths]

    if INTERMEDIATE_FILES:
        file_manager.set_decoration("generated-mutated")

    # construct trees
    ltrees, ctrees, itree = construct_trees(lfiles, cfiles, INDEX_FILE)

    print(f"{os.linesep}Applying transformations...")
    # apply transform
    transform_html(cfiles, trees, ctrees, file_manager)

    if APPLY_VALIDATIONS:
        # apply validations
        print(f"{os.linesep}Applying validations...")
        validations(lfiles, cfiles, INDEX_FILE, ltrees, ctrees, itree)


if __name__ == "__main__":
    driver()
