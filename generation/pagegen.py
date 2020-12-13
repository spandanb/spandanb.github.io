'''
use jinja to generate site pages

'''
import re
import os
import yaml

from collections import namedtuple, OrderedDict, defaultdict
from jinja2 import Environment, FileSystemLoader, select_autoescape

import textparser
import treeparser

###  Config
SELF_PATH = os.path.dirname(os.path.realpath(__file__))
TEMPLATE_DIR = os.path.join(SELF_PATH, r'..\templates')
OUTPUT_DIR = os.path.join(SELF_PATH, r'..')
CONTENT_DIR = os.path.join(SELF_PATH, r'..\content')
IMG_DIR = os.path.join(SELF_PATH, r'..\img')
# IMG_CONTENT_DIR is where images produced by me are stored
IMG_CONTENT_DIR = os.path.join(SELF_PATH, r'..\pics')
# determines whether intermediate output files are stored
DEBUG = False
# on listing pages, I show the first line of content
# truncate the line if longer limit
PREVIEW_LINE_LIMIT = 135
'''
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

'''

'''
Design Decisions:
- Transforming trees vs text: 
Everything can be expressed via jinja templates.
But, this is not very elegant, since every bit of html that can change
has to be controlled via variable. The alternative is to 
apply tranformations on a tree. Transforming a tree is easier
because, one can specify which node to find, and transform. 
I've opted for this when possible. But this does mean the tree
has to be searchable and updatable.
'''

### DataStructs

class CMetadata:
    '''
    Content metadata
    '''
    def __init__(self, title: str, date: str, section: str, content_id: str, template_id: str,
                 image_id: str = '', image_attribution: str = ''):
       self.title = title
       self.date = date
       self.section = section
       self.content_id = content_id
       self.template_id = template_id
       self.image_id = image_id
       self.image_attribution = image_attribution

    def __repr__(self):
         return f'CM[{self.__dict__}]'

    def get_contentpath(self):
        return os.path.join(CONTENT_DIR, self.section, self.content_id)


class ICMetadata:
    '''
    Image Content metadata
    '''
    def __init__(self, title: str, date: str, section: str, image_id: str, subtext: str):
       self.title = title
       self.date = date
       self.section = section
       self.image_id = image_id
       self.subtext = subtext

    def __repr__(self):
         return f'ICM[{self.__dict__}]'

    def get_contentpath(self):
        return os.path.join(IMG_CONTENT_DIR, self.image_id)


class LMetadata:
    '''
    listing metadata
    '''
    def __init__(self, section: str, section_title: str, template_id: str, subtext: str='', image_content: bool=False):

        '''
        section is a no-whitespace, lowercase id
        section_name is case-, whitespace- sensitive displayed name
        '''
        self.section = section
        self.section_title = section_title
        self.template_id = template_id
        self.subtext = subtext
        self.image_content = image_content

    def __repr__(self):
         return f'LM[{self.__dict__}]'


### Utils

def get_relpath(fpath, refpath=OUTPUT_DIR):
    return os.path.relpath(fpath, refpath)


def decorate_path(filepath, dec):
    '''
    foo.html, 'meow' -> foo-meow.html
    '''
    fpath, ext = os.path.splitext(filepath)
    return f'{fpath}-{dec}{ext}'


def read_all(filepath)->str:
    with open(filepath, encoding='utf-8') as fp:
        return fp.read()


def get_line(content_path, maxlen=float('inf'))-> str:
    '''
    get first line of file
    '''
    result = ''
    with open(content_path, encoding='utf-8') as fp:
        for line in fp:
            result = line
            break
    # truncate line if needed
    if len(result) > maxlen:
        result = f'{result[:maxlen]} ... '
    return result


def get_lines(content_path)-> list:
    '''
    get all lines at filepath
    '''
    lines = []
    with open(content_path, encoding='utf-8') as fp:
        lines = fp.readlines()
    return lines


### Content Generation


def generate_content(metadata: CMetadata)->str:
    '''
    generate content for file specified in
    Assumptions:
        -
    '''
    # convert text content to html block
    content_path = metadata.get_contentpath()

    # note these transformations are order dependenent
    text = get_lines(content_path)
    block = textparser.text_to_html(text)

    # configure jinja environment
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        # disabled because this escapes all the html
        # autoescape=select_autoescape(['html'])
    )
    # find template
    template = env.get_template(metadata.template_id)

    # render template
    image_location = get_relpath(os.path.join(IMG_DIR, metadata.image_id))
    rendered = template.render(title=metadata.title,
                date=metadata.date, body=block,
                image_location=image_location,
                image_attribution=metadata.image_attribution,
                is_content_page=True)

    # content_id is: <foo>.txt
    baseid, _ = os.path.splitext(metadata.content_id)
    # write output
    if DEBUG:
        output_filepath = os.path.join(OUTPUT_DIR, f'{baseid}-generated.html')
    else:
        output_filepath = os.path.join(OUTPUT_DIR, f'{baseid}.html')
    print(f'writing {metadata.section} {baseid} to {output_filepath}')
    with open(output_filepath, 'w', encoding='utf-8') as fp:
        fp.write(rendered)
    return output_filepath


def generate_content_listing(metadata: LMetadata, items: list):
    '''
    generate a specific listing page
    '''
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    # find template
    template = env.get_template(metadata.template_id)

    # represents how an item will be viewed
    ItemView = namedtuple('ItemView', 'title teaser')

    # transform items into listings
    listings = []
    for item in items:
        content_path = item.get_contentpath()
        teaser = get_line(content_path, maxlen=PREVIEW_LINE_LIMIT)
        listings.append(ItemView(item.title, teaser))

    # if subtext is unset, make it empty
    # TODO: maybe the subtext element in the listing should be ommitted?
    if not metadata.subtext:
        metadata.subtext = ''

    rendered = template.render(section_title=metadata.section_title,
                               subtext=metadata.subtext,
                               listings=listings)
    if DEBUG:
        output_filepath = os.path.join(OUTPUT_DIR, f'{metadata.section}-listing-generated.html')
    else:
        output_filepath = os.path.join(OUTPUT_DIR, f'{metadata.section}-listing.html')
    print(f'writing listing {metadata.section} to {output_filepath} with {len(items)} items')
    with open(output_filepath, 'w', encoding='utf-8') as fp:
        fp.write(rendered)
    return output_filepath


def generate_image_listing(metadata: LMetadata, items: list):
    '''
    similar to generate_listings, but handles images
    '''
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template(metadata.template_id)

    ItemView = namedtuple('ItemView', 'title subtext rel_location')
    listing = []
    for item in items:
        subtext = f'{item.subtext}, {item.date}'
        relloc = get_relpath(item.get_contentpath())
        listing.append(ItemView(item.title, subtext, relloc))

    print(f'generate_image_listing {metadata.section} listing={listing}')

    if not metadata.subtext:
        metadata.subtext = ''

    rendered = template.render(section_title=metadata.section_title,
                               subtext=metadata.subtext,
                               listing=listing)
    if DEBUG:
        output_filepath = os.path.join(OUTPUT_DIR, f'{metadata.section}-listing-generated.html')
    else:
        output_filepath = os.path.join(OUTPUT_DIR, f'{metadata.section}-listing.html')
    print(f'writing listing {metadata.section} to {output_filepath} with {len(items)} items')
    with open(output_filepath, 'w', encoding='utf-8') as fp:
        fp.write(rendered)
    return output_filepath


def generate_all_content(content_file: str):
    '''
    generate all content files
    '''
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


def generate_listings(listings_file: str, content_file: str, img_content_file: str):
    '''
    Generate all the listings file
    listings of images don't have children content files
    '''
    content = None
    with open(content_file) as fp:
        content = yaml.safe_load(fp)
    img_content = None
    with open(img_content_file) as fp:
        img_content = yaml.safe_load(fp)

    listings = None
    with open(listings_file) as fp:
        listings = yaml.safe_load(fp)

    results = {} # section -> filepath
    for section, props in listings.items():
        if props is None:
            print(f'Skipping listing generation for section: "{section}"; empty props')
            continue

        lmetadata = LMetadata(section=section, **props)
        if lmetadata.image_content:
            listing  = [ICMetadata(section=section, **item) for item in img_content.get(section, [])]
            results[section] = generate_image_listing(lmetadata, listing)
        else:
            listing = [CMetadata(section=section, **item) for item in content.get(section,[])]
            results[section] = generate_content_listing(lmetadata, listing)
    return results


def transform_html(listing_fpaths: dict, content_fpaths: dict):
    '''
    express transformations on a DOM tree. Some transformations, e.g.
    add class "active" on a class are easier expressed on a tree, than as
    transformations applied on text.
    Arguments:
        listing_fpaths(dict): dict[section]-> listing_path
        content_fpaths(dict): dict[section]-> [content_paths]
    '''

    tparser = treeparser.TreeParser()
    # handle listing files
    for (section, filepath) in listing_fpaths.items():
        # read file to tree
        tparser.feed(read_all(filepath))
        tree = tparser.finalize()

        # set active on nav item
        node = tree.find_node_with_id(f'nav-item-{section}')
        node.set_class('active')

        # enrich see more link on listing page
        # by creating a link to the referenced content page
        # this assumes content_paths are in same order as on listing
        node = tree.find_node_with_id("listing-container")
        for i, desc_node in enumerate(node.descendents(tag='a')):
            content_path = (content_fpaths.get(section, []))[i]
            link = get_relpath(content_path)
            desc_node.set_attr('href', link)

        # write output
        outfilepath = decorate_path(filepath, 'mutated') if DEBUG else filepath
        print(f'transforming {section} at {filepath} to {outfilepath}')
        # import pdb; pdb.set_trace()
        printer = treeparser.TreePrinter(tree.get_root(as_qmnode=False))
        with open(outfilepath, 'w', encoding='utf-8') as fp:
            result = printer.mk_doc()
            fp.write(result)

    # handle content files
    for section, filepaths in content_fpaths.items():
        for idx, filepath in enumerate(filepaths):
            tparser.feed(read_all(filepath))
            tree = tparser.finalize()

            #set navbar active
            node = tree.find_node_with_id(f'nav-item-{section}')
            node.set_class('active')

            # set prev, next links
            # set prev
            if idx != 0:
                prev_fpath = get_relpath(filepaths[idx-1])
                if DEBUG:
                    # if DEBUG, intermediate files are preserved
                    # temporarily to test on mutated file
                    # hence, set link to correct file
                    prev_fpath = decorate_path(prev_fpath, 'mutated')

                tree.find_node_with_id('prev_link').set_attr('href', prev_fpath)
            # set next
            if idx != len(filepaths)-1:
                next_fpath = get_relpath(filepaths[idx+1])
                if DEBUG:
                    next_fpath = decorate_path(next_fpath, 'mutated')
                tree.find_node_with_id('next_link').set_attr('href', next_fpath)

            # get output filepath
            outfilepath = decorate_path(filepath, 'mutated') if DEBUG else filepath
            print(f'transforming {section} at {filepath} to {outfilepath}')
            # printer = parser.TreePrinter(tparser.root)
            printer = treeparser.TreePrinter(tree.get_root(as_qmnode=False))
            with open(outfilepath, 'w', encoding='utf-8') as fp:
                result = printer.mk_doc()
                fp.write(result)


def validations(listing_fpaths, content_fpaths):
    '''
    TODO: apply validations
    1) ensure files aren't empty
    2) perhaps have a diff mode
    3) validate DOM tree- i.e. do all nodes closes
    '''


if __name__ == "__main__":
    # determines whether intermediate files are written out separately
    DEBUG = False
    print(f'DEBUG is {DEBUG}')
    dir_path = os.path.dirname(os.path.realpath(__file__))
    content_file = os.path.join(dir_path, './content.yaml')
    image_content_file = os.path.join(dir_path, './image_content.yaml')
    listings_file = os.path.join(dir_path, './sections.yaml')

    cfiles = generate_all_content(content_file)
    lfiles = generate_listings(listings_file, content_file, image_content_file)
    #print_contents(content_file)
    transform_html(lfiles, cfiles)


