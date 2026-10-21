"""LANG-02: banned phrases and patterns from FRONTEND_GUIDELINES section 8 in UI strings, prompts and rendered UI."""
import ast
import re

import pytest

from apphelpers import EMOJI, all_text, make_app
from conftest import ROOT

BANNED_WORDS = ['please', 'successfully', 'simply', 'just', 'seamless', 'robust', 'pivotal', 'leverage', 'delve',
                'tapestry', 'moreover', 'furthermore', 'certainly', 'great question', "it's important to note",
                'it is important to note', 'ensuring', 'highlighting']
PATTERNS = {
    'exclamation mark': re.compile(r'!'),
    'emoji': EMOJI,
    'not X but Y': re.compile(r'\bnot\b[^.?!\n]{0,40}\bbut\b', re.I),
    'trailing -ing clause': re.compile(r',\s+(?!and\b|pending\b)\w+ing\b'),
    'arrow glyph': re.compile('[←-⇿]|&[lr]arr;|->|=>'),
    'bold-label bullet': re.compile(r'^\s*[-*]\s+\*\*[^*]+\*\*', re.M),
}


def hits_in(text):
    """Names of banned words and patterns found in text."""
    found = [w for w in BANNED_WORDS if re.search(r'(?<![\w])' + re.escape(w) + r'(?![\w])', text, re.I)]
    return found + [n for n, rx in PATTERNS.items() if rx.search(text)]


def ui_string_constants():
    """(file, line, text) for each non-docstring, non-CSS string constant in app.py and insurance_claims/ui/*.py."""
    out = []
    for p in [ROOT / 'app.py'] + sorted((ROOT / 'insurance_claims' / 'ui').glob('*.py')):
        tree = ast.parse(p.read_text(encoding='utf-8'))
        docs = {id(n.body[0].value) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
                and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], 'value', None), ast.Constant)}
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs:
                if '{' in n.value and ';' in n.value:
                    continue
                if len(n.value.split()) >= 2:
                    out.append((p.name, n.lineno, n.value))
    return out


def test_lang_02_ui_string_constants_have_no_banned_phrases():
    """LANG-02: UI string constants contain no banned phrase or pattern."""
    strings_ = ui_string_constants()
    assert len(strings_) >= 10
    bad = [f'{f}:{ln} {hits_in(t)}' for f, ln, t in strings_ if hits_in(t)]
    assert not bad, bad


@pytest.mark.parametrize('prompt', sorted((ROOT / 'insurance_claims' / 'prompts').glob('*.txt')), ids=lambda p: p.name)
def test_lang_02_prompts_have_no_banned_phrases(prompt):
    """LANG-02: each prompt file contains no banned phrase or pattern."""
    bad = []
    for i, line in enumerate(prompt.read_text(encoding='utf-8').splitlines(), 1):
        if hits_in(line):
            bad.append(f'{prompt.name}:{i} {hits_in(line)}')
    assert not bad, bad


def test_lang_02_rendered_ui_has_no_banned_phrases(fake_backend):
    """LANG-02: the rendered page (empty state and after a turn) has no banned phrase or pattern."""
    at = make_app().run()
    at.chat_input[0].set_value('hello').run()
    text = re.sub(r'<style>.*?</style>', '', all_text(at), flags=re.S)
    text = re.sub(r'<[^>]+>', ' ', text)
    assert hits_in(text) == []
