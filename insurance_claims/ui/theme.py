"""Design tokens (Fog palette) and the one CSS block. All selectors live here."""

import streamlit as st

TOKENS: dict[str, str] = {
    'backdrop': '#E8EAEF',
    'glow_warm': '#FFD9BF',
    'glow_cool': '#C9D7F2',
    'glass': '#FFFFFF',
    'ink': '#1D1D1F',
    'ink_secondary': '#68686D',
    'action': '#0066CC',
    'verified': '#1B7437',
    'caution': '#A64B00',
    'hairline': '#1D1D1F',
}
GLASS_ALPHA = 0.70
HAIRLINE_ALPHA = 0.14
SURFACE = '#F6F7F9'
FONT_STACK = (
    '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI Variable", '
    '"Segoe UI", system-ui, sans-serif'
)


def _rgba(hex_color: str, alpha: float) -> str:
    """Convert a hex color to an rgba() string."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return f'rgba({r}, {g}, {b}, {alpha})'


def build_css() -> str:
    """Return the CSS text, built only from TOKENS."""
    t = TOKENS
    rule = _rgba(t['hairline'], HAIRLINE_ALPHA)
    return f"""
[data-testid="stAppViewContainer"] {{
  background-color: {t['backdrop']};
  background-image:
    radial-gradient(ellipse 60% 50% at 0% 0%, {t['glow_warm']} 0%, transparent 70%),
    radial-gradient(ellipse 60% 50% at 100% 100%, {t['glow_cool']} 0%, transparent 70%);
  background-attachment: fixed;
}}
html, body, [data-testid="stApp"] {{
  font-family: {FONT_STACK};
  font-size: 15px;
  color: {t['ink']};
}}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stSidebar"] {{ background: {SURFACE}; border-right: 1px solid {rule}; }}
.cs-title {{ font-size: 18px; font-weight: 600; }}
.cs-phase {{ font-size: 15px; color: {t['ink_secondary']}; }}
.cs-row {{
  display: grid; grid-template-columns: 72px 1fr; gap: 12px;
  padding: 12px 0; border-bottom: 1px solid {rule};
}}
.cs-who {{ font-size: 13px; font-weight: 600; color: {t['ink_secondary']}; }}
.cs-msg {{ font-size: 15px; line-height: 1.5; }}
.cs-event {{
  font-size: 13px; padding: 8px 12px; border-left: 3px solid {t['action']};
  border-bottom: 1px solid {rule};
}}
.cs-event.done {{ border-left-color: {t['verified']}; }}
.cs-event.handoff {{ border-left-color: {t['caution']}; }}
.cs-event.detail {{ color: {t['ink_secondary']}; }}
.cs-card {{
  background: {t['glass']}; border: 1px solid {rule}; border-radius: 6px;
  padding: 12px 16px; margin: 12px 0;
}}
.cs-card-subject {{ font-size: 15px; font-weight: 600; margin-bottom: 4px; }}
.cs-card-meta {{ font-size: 13px; color: {t['ink_secondary']}; margin-bottom: 8px; }}
.cs-card-body {{ font-size: 15px; line-height: 1.5; }}
.cs-empty {{ font-size: 15px; color: {t['ink_secondary']}; padding: 12px 0; }}
.cs-side-title {{ font-size: 15px; font-weight: 600; margin: 8px 0 4px; }}
.cs-note {{ font-size: 13px; color: {t['ink_secondary']}; margin-bottom: 8px; }}
.cs-side-row {{
  display: flex; justify-content: space-between; font-size: 13px;
  padding: 4px 0; border-bottom: 1px solid {rule};
  font-variant-numeric: tabular-nums;
}}
.cs-tone-good {{ color: {t['verified']}; }}
.cs-tone-warn {{ color: {t['caution']}; }}
.cs-phase-row {{ font-size: 15px; padding: 6px 0 0; }}
.cs-phase-row.current {{ font-weight: 600; color: {t['action']}; }}
.cs-phase-row.done {{ color: {t['verified']}; }}
.cs-phase-row.pending {{ color: {t['ink_secondary']}; }}
.cs-gate {{ font-size: 13px; padding-left: 22px; color: {t['ink_secondary']}; }}
.cs-gate.on {{ color: {t['verified']}; }}
[data-testid="stSidebar"] button, [data-testid="stMain"] button {{ border-radius: 6px; }}
""".strip()


def inject_css() -> None:
    """Inject the CSS block. If a selector stops matching, the UI still works unstyled."""
    st.markdown(f'<style>{build_css()}</style>', unsafe_allow_html=True)
