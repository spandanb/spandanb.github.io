'''
use jinja to generate site pages

'''
import os
import yaml

from collections import namedtuple, OrderedDict, defaultdict
from dataclasses import dataclass
from jinja2 import Environment, FileSystemLoader, select_autoescape

import treeparser as parser

###  Config
SELF_PATH = os.path.dirname(os.path.realpath(__file__))
TEMPLATE_DIR = os.path.join(SELF_PATH, r'..\jtemplates')
OUTPUT_DIR = os.path.join(SELF_PATH, r'..')
CONTENT_DIR = os.path.join(SELF_PATH, r'..\content')
IMG_DIR = os.path.join(SELF_PATH, r'..\img')
# IMG_CONTENT_DIR is where images produced by me are stored
IMG_CONTENT_DIR = os.path.join(SELF_PATH, r'..\pics')
# determines whether intermediate output files are stored
DEBUG = False

'''
Notes
the yaml files may be sensitive to tab characters

Random:
    it's cool I get to implement a crude JQuery, DOM, etc.
    -have some tests
    - this should be above all easy to maintain

TODO:
    - ensure, no tabs (including in .yaml files)
    - jinja should throw exception on unspecified vars

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
    
    def get_relpath(self):
        '''
        get path relative to OUTPUT_DIR
        '''
        return os.path.relpath(self.get_contentpath(), OUTPUT_DIR)


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

def get_relpath(fpath):
    return os.path.relpath(fpath, OUTPUT_DIR)


def decorate_path(filepath, dec):
    '''
    foo.html, 'meow' -> foo-meow.html
    '''
    fpath, ext = os.path.splitext(filepath)
    return f'{fpath}-{dec}{ext}'


def read_all(filepath)->str:
    with open(filepath, encoding='utf-8') as fp:
        return fp.read()


def get_line(content_path)-> str:
    '''
    get first line of file
    '''
    with open(content_path, encoding='utf-8') as fp:
        for line in fp:
            return line
    return ''


def get_lines(content_path)-> list:
    '''
    get all lines at filepath
    '''
    lines = []
    with open(content_path, encoding='utf-8') as fp:
        lines = fp.readlines()
    return lines


### Content Generation

def text_to_html(lines: list):
    '''
    Converts item at `content_path` (text file)
    to html and writes to `output_path`

    replaces a\nb with a<br>b
    replaces a\n(\n)+b  with a<br><br>b

    Arguments:
        text: list[str]
    '''

    output = []
    for line in lines:
        stripped = line.strip()
        if len(stripped) > 0:
            output.append(stripped)
            output.append('<br>')
        else:  # len(stripped) == 0
            # we never want more than 2 contigiuous <br> elements
            if len(output) >= 2 and output[-1] == '<br>' and output[-2] == '<br>':
                continue
            output.append('<br>')

    # \n just so it's also human readable
    output = '<p>\n' + '\n'.join(output) + '\n</p>'
    return output


def generate_content(metadata: CMetadata)->str:
    '''
    generate content for file specified in
    Assumptions:
        -
    '''
    # convert text content to html block
    content_path = metadata.get_contentpath()
    block = text_to_html(get_lines(content_path))

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

    # content_id is: *.jinja.html
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
        teaser = get_line(content_path)
        listings.append(ItemView(item.title, teaser))
    
    # if subtext is unset, make it empty
    # TODO: maybe there element in the listing should be ommitted?
    if not metadata.subtext:
        metadata.subtext = ''

    rendered = template.render(section_title=metadata.section_title,
                               subtext=metadata.subtext,
                               listings=listings)
    if DEBUG:
        output_filepath = os.path.join(OUTPUT_DIR, f'{metadata.section}-listing-generated.html')
    else:
        output_filepath = os.path.join(OUTPUT_DIR, f'{metadata.section}-listing.html')
    print(f'writing listing {metadata.section} to {output_filepath}')
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
        relloc = item.get_relpath()
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
    print(f'writing listing {metadata.section} to {output_filepath}')
    with open(output_filepath, 'w', encoding='utf-8') as fp:
        fp.write(rendered)
    return output_filepath
    

def generate_all_content(content_file):
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


def generate_listings(listings_file, content_file, img_content_file):
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
        # CONSIDER: custom load into custom class, e.g. LMetadata
        listings = yaml.safe_load(fp)

    results = {} # section -> filepath
    for section, props in listings.items():
        if props is None:
            continue

        lmetadata = LMetadata(section=section, **props)
        if lmetadata.image_content:
            listing  = [ICMetadata(section=section, **item) for item in img_content.get(section, [])]
            results[section] = generate_image_listing(lmetadata, listing)
        else:
            listing = [CMetadata(section=section, **item) for item in content.get(section,[])]
            results[section] = generate_content_listing(lmetadata, listing)
    return results


def enrich_seemore_link(tparser, content_fpaths:list):
    '''
    create link on listing article teasers to content page
    '''
    container = tparser.find_node_with_id("listing-container")
    anchors = tparser.find_nodes_with_tag('a', container, descend=True)
    for i, anch in enumerate(anchors):
        # this relies on content_paths being in same order as listing
        link = get_relpath(content_fpaths[i])
        tparser.set_attr(anch, 'href', link)


def transform_html(listing_fpaths, content_fpaths):
    '''
    express other transformations on html best expressed
    as transformations on a tree
    '''
    for (section, filepath) in listing_fpaths.items():
        # read file to tree
        tparser = parser.TreeParser()
        tparser.feed(read_all(filepath))
        tparser.finalize()
        # apply transform 0 - set navbar active
        tparser.add_class_by_id(f'nav-item-{section}', 'active')
        
        # transform 1 - set see more link from listing to content pages
        # we'll rely on the ordering of the content
        enrich_seemore_link(tparser, content_fpaths.get(section, []))
        
        # write output
        outfilepath = decorate_path(filepath, 'mutated') if DEBUG else filepath
        print(f'transforming {section} at {filepath} to {outfilepath}')
        
        printer = parser.TreePrinter(tparser.root)
        with open(outfilepath, 'w', encoding='utf-8') as fp:
            result = printer.mk_doc()
            fp.write(result)


    # handle content files
    for section, filepaths in content_fpaths.items():
        for idx, filepath in enumerate(filepaths):
            tparser = parser.TreeParser()
            tparser.feed(read_all(filepath))
            tparser.finalize()

            # apply transform 0 - set navbar active
            tparser.add_class_by_id(f'nav-item-{section}', 'active')
                                   
            # apply transform 1 - set prev, next
            # set prev
            if idx != 0:    
                prev_fpath = get_relpath(filepaths[idx-1])        
                if DEBUG:
                    # if DEBUG, intermediate files are preserved
                    # temporarily to test on mutated file
                    # hence, set link to correct file
                    prev_fpath = decorate_path(prev_fpath, 'mutated')
                tparser.set_attr_by_id('prev_link', 'href', prev_fpath)
            # set next
            if idx != len(filepaths)-1:
                next_fpath = get_relpath(filepaths[idx+1])        
                if DEBUG:
                    next_fpath = decorate_path(next_fpath, 'mutated')
                tparser.set_attr_by_id('next_link', 'href', next_fpath)
                    
            # get output filepath
            outfilepath = decorate_path(filepath, 'mutated') if DEBUG else filepath
            print(f'transforming {section} at {filepath} to {outfilepath}')            
            printer = parser.TreePrinter(tparser.root)
            with open(outfilepath, 'w', encoding='utf-8') as fp:
                result = printer.mk_doc()
                fp.write(result)


if __name__ == "__main__":
    # determines whether intermediate files are written out separately
    DEBUG = False
    dir_path = os.path.dirname(os.path.realpath(__file__))
    content_file = os.path.join(dir_path, './content.yaml')
    image_content_file = os.path.join(dir_path, './image_content.yaml')
    listings_file = os.path.join(dir_path, './sections.yaml')

    cfiles = generate_all_content(content_file)
    lfiles = generate_listings(listings_file, content_file, image_content_file)
    #print_contents(content_file)
    transform_html(lfiles, cfiles)


