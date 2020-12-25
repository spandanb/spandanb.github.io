# Personal Website Generator

## Generation
python -m venv virtenv
../virtenv/Scripts/Activate
cd <ROOT>/jgeneration
python pagegen.py

## Before Committing Code
- pytest
- black
- flake8
- mypy

## Running tests
pytest <test_filename>

## Troubleshooting
- if website doesn't update, try pushing an empty commit
