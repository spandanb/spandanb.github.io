import itertools
import os

from collections import defaultdict

from typing import List, Dict
from collections.abc import Iterable


import treediff
import treeparser

### Utils


def flatten(iterable: Iterable) -> List:
    """
    flatten a 2-d iterable object
    """
    return [subitem for item in iterable for subitem in item]


class ValidationError(Exception):
    """
    Generic exception raised on validation failure
    """

### Run Validations


def run_validations(
    listing_fpaths: dict,
    content_fpaths: dict,
    index_fpath: str,
    listing_trees: dict,
    content_trees: dict,
    index_tree: treeparser.Tree
):
    """
    Apply validations to generated files.

    TODO: break each validation into it's own function

    Currently applying:
    1) ensure files aren't empty
    2) index file and a generated file navbar only differ in 'active' class
    3) validate all generated files have a unique filename
    4)

    Thoughts:
    - perhaps have a diff mode
    - validate DOM tree- i.e. do all nodes closes
        -- hmm, this should be something exposed by treeparser

    Arguments:
        NB: the structure of all the different maps is the same
            as the yaml files, i.e.
            `listint_<T>` have the structure section -> object and
            `content_<T>` have the structure section -> [object] and

        listing_fpaths: maps section to filepath
        content_fpaths: maps section to list of filepaths
        listing_trees: tree
        content_trees
        content_datamap: the map of the section -> [CMetadata]
        image_content_datamap: the map of section -> [ICMetadata]
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
    # uncomment to pretty print diff
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

    # validations: all sections should have a reverse-chronological order
#    vname = "content order reverse chronological"
#    print(f"Applying validation: {vname}")
#    for section, items in itertools.chain(content_datamap.items(), image_content_datamap.items()):
#        print(f"validating {vname} {section}")
#        for idx, metadata in enumerate(items):
#            # a subsequent item has a newer date; order is broken
#            print(metadata.date, items[idx-1].date)
#            if idx > 0 and (metadata.date > items[idx-1].date):
#                raise ValidationError(f"Section '{section}' not in reverse-chronological order at index '{idx}'")
