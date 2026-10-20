"""CP0 scans: LANG-01, NFR-05, coding-guideline hygiene."""
import ast
import re
import sys

import pytest

from conftest import ROOT, text_files

DASHES = ('\u2014', '\u2013')
ALLOWED = {'streamlit', 'pydantic', 'openai', 'pytest'}


def _repo_files():
    return list(text_files())


def test_lang_01_no_em_or_en_dash_in_repo_text():
    """LANG-01: no em/en dash in app code, prompts, README, docs, config."""
    hits = []
    for p in _repo_files():
        for n, line in enumerate(p.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
            if any(d in line for d in DASHES):
                hits.append(f'{p.relative_to(ROOT)}:{n}')
    assert not hits, hits


def test_lang_01_no_dash_in_fixtures_is_reported_only():
    """LANG-01: fixtures are read-only; count dashes there for information."""
    fx = ROOT / 'insurance_claims' / 'fixtures'
    n = sum(f.read_text(encoding='utf-8').count(d) for f in fx.glob('*.json') for d in DASHES)
    assert n >= 0


@pytest.mark.parametrize('text', ['hello', 'hi there', 'what can you do', 'thanks'])
def test_lang_01_replies_have_no_dash(text):
    """LANG-01: replies with FakeLLM contain no em/en dash."""
    from insurance_claims.llm import FakeLLM
    from insurance_claims.orchestrator import handle_turn, new_session
    r = handle_turn(new_session(), text, FakeLLM())
    assert not any(d in r.reply for d in DASHES)


def test_lang_01_reply_filter_strips_dashes_from_llm_output():
    """LANG-01: replies are filtered in code, even if the LLM emits a dash."""
    from insurance_claims.llm import FakeLLM
    from insurance_claims.orchestrator import handle_turn, new_session

    class Dashy(FakeLLM):
        def reply(self, *a, **k):
            return 'Sure \u2014 one moment \u2013 thanks.'

    s = new_session()
    r = handle_turn(s, 'hello', Dashy())
    assert not any(d in r.reply for d in DASHES)
    assert not any(d in t for _, t in s.view().turns for d in DASHES)


def test_lang_01_ui_strings_have_no_dash():
    """LANG-01: rendered UI strings from view() contain no dash."""
    from insurance_claims.orchestrator import new_session
    v = new_session().view().model_dump_json()
    assert not any(d in v for d in DASHES)


def _code_and_test_files():
    """app.py, insurance_claims/ and tests/ Python files (docs, fixtures, ASSIGNMENT.md are excluded)."""
    files = [p for p in _repo_files() if p.suffix == '.py']
    return files + sorted((ROOT / 'tests').glob('*.py'))


def test_nfr_05_file_length_under_200_lines(record_property):
    """NFR-05 / CODING_GUIDELINES first no-go: code and test files stay under 200 lines."""
    sizes = {str(p.relative_to(ROOT)): len(p.read_text(encoding='utf-8').splitlines()) for p in _code_and_test_files()}
    longest = max(sizes.items(), key=lambda kv: kv[1])
    record_property('nfr_05_longest', f'{longest[0]} = {longest[1]} lines')
    over = {k: v for k, v in sizes.items() if v >= 200}
    assert not over, over


def _imports(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split('.')[0]


def test_nfr_05_only_listed_dependencies_imported():
    """NFR-05: third-party imports limited to streamlit, pydantic, openai, pytest."""
    bad = {}
    local = {p.stem for p in (ROOT / 'tests').glob('*.py')}
    for p in _code_and_test_files():
        for m in set(_imports(p)):
            if m in sys.stdlib_module_names or m in local or m in ('insurance_claims', 'app'):
                continue
            if m not in ALLOWED:
                bad.setdefault(str(p.relative_to(ROOT)), []).append(m)
    assert not bad, bad


def test_nfr_05_requirements_txt_lists_only_allowed():
    """NFR-05 / DEL-01: requirements.txt names only the listed dependencies."""
    lines = [l.strip() for l in (ROOT / 'requirements.txt').read_text().splitlines()]
    names = {re.split(r'[<>=!~\[; ]', l)[0].lower() for l in lines if l and not l.startswith('#')}
    assert names <= ALLOWED, names
    assert {'streamlit', 'pydantic', 'openai'} <= names


def test_guideline_no_requests_httpx_imports():
    """CODING_GUIDELINES: no raw HTTP libraries."""
    for p in _code_and_test_files():
        assert not ({'requests', 'httpx', 'httpx2', 'urllib3', 'aiohttp'} & set(_imports(p))), p


def test_guideline_no_print_calls():
    """CODING_GUIDELINES: no print() in product code or in tests."""
    hits = []
    for p in _code_and_test_files():
        for node in ast.walk(ast.parse(p.read_text(encoding='utf-8'))):
            if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'print':
                hits.append(f'{p.relative_to(ROOT)}:{node.lineno}')
    assert not hits, hits


def test_guideline_no_async_code():
    """CODING_GUIDELINES: synchronous code only."""
    hits = []
    for p in _repo_files():
        if p.suffix != '.py':
            continue
        for node in ast.walk(ast.parse(p.read_text(encoding='utf-8'))):
            if isinstance(node, (ast.AsyncFunctionDef, ast.Await)):
                hits.append(f'{p.relative_to(ROOT)}:{node.lineno}')
    assert not hits, hits


def test_guideline_init_files_empty_or_all_only():
    """CODING_GUIDELINES: __init__.py empty or only __all__."""
    for p in ROOT.rglob('__init__.py'):
        if 'goaly-venv' in p.parts:
            continue
        body = ast.parse(p.read_text(encoding='utf-8')).body
        for node in body:
            is_doc = isinstance(node, ast.Expr) and isinstance(getattr(node, 'value', None), ast.Constant)
            is_all = isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') == '__all__'
            assert is_doc or is_all, p


def test_guideline_no_utils_module():
    """CODING_GUIDELINES: no utils.py."""
    assert not [p for p in _repo_files() if p.name == 'utils.py']


def test_guideline_prompts_are_text_files():
    """CODING_GUIDELINES: prompts live in insurance_claims/prompts/ as text files."""
    d = ROOT / 'insurance_claims' / 'prompts'
    assert list(d.glob('*.txt'))


def test_guideline_single_quotes_style_report():
    """CODING_GUIDELINES: count of double-quoted string literals without a single quote ."""
    import io
    import tokenize
    hits = []
    for p in _code_and_test_files():
        for t in tokenize.generate_tokens(io.StringIO(p.read_text(encoding='utf-8')).readline):
            if t.type == tokenize.STRING and t.string.startswith('"') and not t.string.startswith('"""'):
                if "'" not in t.string[1:-1]:
                    hits.append(f'{p.name}:{t.start[0]}')
    assert not hits, hits


def test_tests_have_no_unused_imports():
    """Hygiene: no unused import in tests/."""
    hits = []
    for p in (ROOT / 'tests').glob('*.py'):
        tree = ast.parse(p.read_text(encoding='utf-8'))
        names = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    names[(a.asname or a.name).split('.')[0]] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                for a in node.names:
                    names[a.asname or a.name] = node.lineno
        used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
            n.value.id for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
        hits += [f'{p.name}:{ln} {n}' for n, ln in names.items() if n not in used and p.name != 'conftest.py']
    assert not hits, hits
