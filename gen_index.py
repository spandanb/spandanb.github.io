#!/usr/bin/python
from __future__ import print_function

"""
Generates index.html from contents and index.template.html
"""

import yaml
from jinja2 import Template
import pdb

if __name__ == "__main__":
    #Read the content 
    with open('content.yaml', 'r') as stream:
        content = yaml.load(stream)

    #Read the template
    with open('index.template.html') as f:
        template = f.read()

    #Render the output 
    t = Template(template) 
    with open('index.html', 'w') as f:
        f.write(t.render(blogposts=content['blogposts'], projects=content['projects']))
