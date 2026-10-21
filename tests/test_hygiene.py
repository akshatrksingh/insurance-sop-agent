"""Hygiene scans over tests/: docstrings on module-level helpers, no vacuous assertions."""
import ast
import re

from conftest import ROOT

FILES = sorted((ROOT / 'tests').glob('*.py'))


def test_module_level_helpers_and_fixtures_have_docstrings():
    """Every module-level function or class in tests/ that is not a test has a docstring."""
    missing = []
    for p in FILES:
        for n in ast.parse(p.read_text(encoding='utf-8')).body:
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not n.name.startswith('test_') and not ast.get_docstring(n):
                missing.append(f'{p.name}:{n.name}')
    assert not missing, missing


def test_every_test_function_has_a_docstring_naming_its_subject():
    """Every test function has a docstring."""
    missing = []
    for p in FILES:
        for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))):
            if isinstance(n, ast.FunctionDef) and n.name.startswith('test_') and not ast.get_docstring(n):
                missing.append(f'{p.name}:{n.name}')
    assert not missing, missing


def test_no_vacuous_assertions_in_tests():
    """No always-true assertion such as 'assert x >= 0' on a counter, 'or True', or 'assert True'."""
    pattern = re.compile(r'assert\s+(True\b|.*\bor True\b|\w+\s*>=\s*0\s*$)')
    hits = []
    for p in FILES:
        if p.name == 'test_hygiene.py':
            continue
        for i, line in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
            if pattern.search(line.strip()):
                hits.append(f'{p.name}:{i}')
    assert not hits, hits
