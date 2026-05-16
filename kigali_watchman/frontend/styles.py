"""
KIRA Frontend: Unified Style System
Centralized CSS and theme definitions for clean, consistent UI.
"""

THEME = {
    "primary": "#22c55e",
    "secondary": "#3b82f6",
    "danger": "#ef4444",
    "warning": "#eab308",
    "dark_bg": "#071428",
    "card_bg": "#0b2b4a",
    "border": "#15344f",
    "text_light": "#ffffff",
    "text_muted": "#cbd5e1",
    "success": "#22c55e",
    "error": "#ef4444",
    "info": "#3b82f6",
}

# Combined emblem SVG (URL-encoded where needed when inserted into data URI)
EMBLEM_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'>"
    "<rect x='40' y='70' width='120' height='60' rx='8' fill='%23ffffff' opacity='0.12'/>"
    "<rect x='146' y='82' width='6' height='36' fill='%23ffffff' opacity='0.12'/>"
    "<circle cx='100' cy='36' r='18' fill='%23ffd166' opacity='0.12'/>"
    "<path d='M10 150 C40 130 80 160 120 140 C160 120 200 150 240 140' "
    "transform='translate(-20,0)' fill='none' stroke='%23ffffff' stroke-width='6' "
    "stroke-linecap='round' opacity='0.12'/>"
    "</svg>"
)

GLOBAL_CSS = """
<style>
/* === Global Styles === */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body, .main {
  background: __DARK_BG__;
  color: __TEXT_LIGHT__;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

/* Large, subtle background emblem (combined hydro/battery/solar icon) */
body::before {
  content: "";
  position: fixed;
  inset: 0;
  background-image: url("data:image/svg+xml;utf8,__EMBLEM__");
  background-repeat: no-repeat;
  background-position: center top 10%;
  background-size: 56%;
  opacity: 1;
  pointer-events: none;
  z-index: 0;
}

h1, h2, h3, h4, h5, h6 {
  color: __TEXT_LIGHT__;
  font-weight: 600;
  letter-spacing: -0.02em;
}

a { color: __PRIMARY__; text-decoration: none; }
a:hover { text-decoration: underline; opacity: 0.8; }

.auth-container {
  max-width: 450px;
  margin: 60px auto;
  padding: 40px;
  background: linear-gradient(135deg, __CARD_BG__ 0%, #1e293b 100%);
  border: 1px solid __BORDER__;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  animation: slideIn 0.6s ease-out;
}

@keyframes slideIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }

.form-group { margin-bottom: 20px; }
.form-group label { display:block; margin-bottom:8px; font-weight:500; color: __TEXT_LIGHT__; font-size:0.95rem; }
.form-group input, .form-group select { width:100%; padding:12px 14px; border:1px solid __BORDER__; border-radius:8px; background: rgba(15,23,42,0.5); color: __TEXT_LIGHT__; font-size:0.95rem; transition: all 0.3s ease; }
.form-group input:focus, .form-group select:focus { outline:none; border-color: __PRIMARY__; box-shadow: 0 0 0 3px rgba(34,197,94,0.1); }
.form-group input::placeholder { color: __TEXT_MUTED__; }

.btn { padding:12px 16px; border:none; border-radius:8px; font-weight:600; font-size:0.95rem; cursor:pointer; transition: all 0.3s ease; letter-spacing:0.5px; text-transform:uppercase; }
.btn-primary { background: linear-gradient(135deg, __PRIMARY__ 0%, #16a34a 100%); color: white; width:100%; margin-top:8px; }
.btn-primary:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(34,197,94,0.3); }
.btn-secondary { background: transparent; color: __PRIMARY__; border:1px solid __PRIMARY__; width:100%; }
.btn-secondary:hover { background: rgba(34,197,94,0.1); }

.metric-card { background: linear-gradient(135deg, __CARD_BG__ 0%, #1e293b 100%); border:1px solid __BORDER__; border-radius:12px; padding:18px; margin:8px 0; transition: all 0.3s ease; }
.metric-card:hover { border-color: __PRIMARY__; box-shadow: 0 8px 16px rgba(34,197,94,0.1); transform: translateY(-4px); }
.metric-value { font-size:1.8rem; font-weight:700; color: __PRIMARY__; }
.metric-label { font-size:0.85rem; color: __TEXT_MUTED__; text-transform:uppercase; letter-spacing:0.5px; }

.status-badge { display:inline-block; padding:4px 10px; border-radius:20px; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; }
.status-ok { background: rgba(34,197,94,0.2); color: __SUCCESS__; }
.status-warning { background: rgba(234,179,8,0.2); color: __WARNING__; }
.status-error { background: rgba(239,68,68,0.2); color: __ERROR__; }

.brand-header { display:flex; align-items:center; gap:12px; margin-bottom:8px; }
.brand-icon { font-size:1.8rem; }
.brand-title { font-size:1.2rem; font-weight:700; color: __TEXT_LIGHT__; }
.brand-subtitle { font-size:0.85rem; color: __TEXT_MUTED__; }

.divider { height:1px; background: linear-gradient(to right, transparent, __BORDER__, transparent); margin:20px 0; }

.link-text { color: __TEXT_MUTED__; font-size:0.9rem; }
.link-text strong { color: __PRIMARY__; cursor:pointer; transition: color 0.3s ease; }
.link-text strong:hover { opacity:0.8; }

.tab-container { display:flex; gap:8px; margin-bottom:20px; border-bottom:1px solid __BORDER__; }
.tab { padding:12px 16px; background:transparent; border:none; color: __TEXT_MUTED__; font-weight:600; cursor:pointer; border-bottom:3px solid transparent; transition: all 0.3s ease; }
.tab.active { color: __PRIMARY__; border-bottom-color: __PRIMARY__; }
.tab:hover { color: __TEXT_LIGHT__; }

@media (max-width:768px) { .auth-container { margin:30px 16px; padding:24px; } h1 { font-size:1.5rem; } .metric-card { padding:12px; } }

</style>
"""

# Inject theme values into the CSS placeholders
GLOBAL_CSS = GLOBAL_CSS.replace("__DARK_BG__", THEME['dark_bg'])
GLOBAL_CSS = GLOBAL_CSS.replace("__TEXT_LIGHT__", THEME['text_light'])
GLOBAL_CSS = GLOBAL_CSS.replace("__PRIMARY__", THEME['primary'])
GLOBAL_CSS = GLOBAL_CSS.replace("__CARD_BG__", THEME['card_bg'])
GLOBAL_CSS = GLOBAL_CSS.replace("__BORDER__", THEME['border'])
GLOBAL_CSS = GLOBAL_CSS.replace("__TEXT_MUTED__", THEME['text_muted'])
GLOBAL_CSS = GLOBAL_CSS.replace("__SUCCESS__", THEME['success'])
GLOBAL_CSS = GLOBAL_CSS.replace("__ERROR__", THEME['error'])
GLOBAL_CSS = GLOBAL_CSS.replace("__INFO__", THEME['info'])
GLOBAL_CSS = GLOBAL_CSS.replace("__WARNING__", THEME['warning'])
GLOBAL_CSS = GLOBAL_CSS.replace("__EMBLEM__", EMBLEM_SVG)


def get_status_badge_html(status: str, text: str = None) -> str:
    """Generate a status badge HTML element."""
    if text is None:
        text = status.upper()
    status_map = {"ok": "status-ok", "warning": "status-warning", "error": "status-error"}
    css_class = status_map.get(status.lower(), "status-ok")
    return f'<span class="status-badge {css_class}">{text}</span>'
