# Personal Website Generator

## Generation
python -m venv virtenv
../virtenv/Scripts/Activate
cd <ROOT>/jgeneration
python pagegen.py

### Adding new/updating section
- Ensure generation/sections.yaml and contents.yaml have entries for new section
- Ensure index.html is pointing to new listings file
- Ensure templates/head.yaml.json is pointing to new listings file

## Before Committing Code
- pytest
- black
- flake8
- mypy

## Running tests
pytest <test_filename>

## Troubleshooting
- if website doesn't update, try pushing an empty commit


