"""Palette contrast per FRONTEND_GUIDELINES section 3 (Tier 1)."""
import tomllib

import pytest

from conftest import ROOT
from insurance_claims.ui.theme import GLASS_ALPHA, TOKENS

EXPECTED = {
    'backdrop': '#E8EAEF', 'glow_warm': '#FFD9BF', 'glow_cool': '#C9D7F2', 'glass': '#FFFFFF',
    'ink': '#1D1D1F', 'ink_secondary': '#68686D', 'action': '#0066CC',
    'verified': '#1B7437', 'caution': '#A64B00', 'hairline': '#1D1D1F',
}


def rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lum(c):
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (f(x) for x in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def effective_glass():
    g, b = rgb(TOKENS['glass']), rgb(TOKENS['backdrop'])
    return tuple(round(GLASS_ALPHA * gc + (1 - GLASS_ALPHA) * bc) for gc, bc in zip(g, b))


def test_tokens_match_guideline_values():
    """FRONTEND section 3: token values and GLASS_ALPHA."""
    for k, v in EXPECTED.items():
        assert TOKENS[k].upper() == v, k
    assert GLASS_ALPHA == 0.70


PAIRS = [(fg, bg) for fg in ('ink', 'ink_secondary', 'verified', 'caution') for bg in ('glass', 'backdrop')]


@pytest.mark.parametrize('fg,bg', PAIRS)
def test_palette_contrast_at_least_4_5(fg, bg, record_property):
    """Palette contrast: text on effective glass and backdrop >= 4.5:1."""
    bgc = effective_glass() if bg == 'glass' else rgb(TOKENS['backdrop'])
    r = ratio(rgb(TOKENS[fg]), bgc)
    record_property(f'contrast_{fg}_on_{bg}', f'{r:.2f}')
    assert r >= 4.5


def test_palette_contrast_white_on_action(record_property):
    """Palette contrast: white on action >= 4.5:1."""
    r = ratio((255, 255, 255), rgb(TOKENS['action']))
    record_property('contrast_white_on_action', f'{r:.2f}')
    assert r >= 4.5


def test_config_toml_theme_matches_tokens():
    """FRONTEND section 3: .streamlit/config.toml theme values."""
    t = tomllib.loads((ROOT / '.streamlit' / 'config.toml').read_text())['theme']
    assert t['base'] == 'light'
    assert t['primaryColor'].upper() == TOKENS['action']
    assert t['backgroundColor'].upper() == TOKENS['backdrop']
    assert t['textColor'].upper() == TOKENS['ink']
    assert t['secondaryBackgroundColor'].upper() == '#F6F7F9'
    assert t['font'] == 'sans serif'


def test_config_toml_theme_text_contrast():
    """Palette contrast: config.toml text on background and secondary background >= 4.5."""
    t = tomllib.loads((ROOT / '.streamlit' / 'config.toml').read_text())['theme']
    for bg in ('backgroundColor', 'secondaryBackgroundColor'):
        assert ratio(rgb(t['textColor']), rgb(t[bg])) >= 4.5
