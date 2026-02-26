"""
app.py — Interface web Streamlit pour visualiser les notes Real Madrid.

Lancer avec : streamlit run app.py
"""

import base64
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Configuration de la page
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Notes Real Madrid 2025-2026",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("output")
DATA_FILE = OUTPUT_DIR / "data.json"
STATS_FILE = OUTPUT_DIR / "stats.json"
FOTMOB_FILE = OUTPUT_DIR / "fotmob_data.json"

COMPETITION_ICONS: dict[str, str] = {}  # plus d'icônes

COLOR_SCALE = {
    "high": "#22c55e",
    "mid":  "#f59e0b",
    "low":  "#ef4444",
}

@st.cache_resource
def _load_logo_b64() -> str:
    """Charge le logo JDR en base64 (mis en cache pour la session)."""
    path = Path("logo-jdr.jpg")
    if path.exists():
        return base64.b64encode(path.read_bytes()).decode()
    return ""


# Palette Real Madrid — or en tête, puis couleurs distinctives
MADRID_PALETTE = [
    "#c9a227", "#3b82f6", "#ef4444", "#22c55e",
    "#8b5cf6", "#f97316", "#06b6d4", "#ec4899",
]


# ---------------------------------------------------------------------------
# CSS — Thème Bernabéu Noir
# ---------------------------------------------------------------------------

def inject_css() -> None:
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:ital,wght@0,300;0,400;0,500;1,300&family=Outfit:wght@300;400;500;600&display=swap');

/* ─── Variables ─────────────────────────────── */
:root {
    --bg:          #04080f;
    --surface:     #07101c;
    --card:        #0c1624;
    --elevated:    #111e30;
    --gold:        #c9a227;
    --gold-bright: #dbb84a;
    --gold-dim:    rgba(201,162,39,0.08);
    --gold-mid:    rgba(201,162,39,0.25);
    --gold-glow:   rgba(201,162,39,0.13);
    --royal:       #1c3a6e;
    --text:        #e6e0d0;
    --text-2:      #8fa0b2;
    --muted:       #445566;
    --border:      #152338;
    --border-2:    #1e3050;
    --green:       #22c55e;
    --amber:       #f59e0b;
    --red:         #ef4444;
    --r:           3px;
}

/* ─── Reset ─────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }
::selection { background: rgba(201,162,39,0.2); color: var(--text); }

::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(201,162,39,0.35); }

/* ─── App Layout ─────────────────────────────── */
body,
.stApp,
.stAppViewContainer,
[data-testid="stAppViewContainer"] {
    background-color: var(--bg) !important;
    background-image:
        radial-gradient(ellipse 100% 40% at 50% 0%, rgba(28,58,110,0.28) 0%, transparent 65%),
        radial-gradient(ellipse 50% 30% at 0% 100%, rgba(10,20,40,0.4) 0%, transparent 60%) !important;
    font-family: 'Outfit', sans-serif !important;
    color: var(--text) !important;
}
.stApp > header { display: none !important; }
#MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden !important; }
.block-container {
    padding-top: 0.5rem !important;
    padding-left: 2.5rem !important;
    padding-right: 2.5rem !important;
    max-width: 100% !important;
}
section[data-testid="stVerticalBlock"] > div > div { gap: 0.5rem !important; }

/* ─── Sidebar ─────────────────────────────────── */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div {
    background: linear-gradient(180deg, #060f1c 0%, #04090f 100%) !important;
}
[data-testid="stSidebar"] {
    border-right: 1px solid var(--border) !important;
    box-shadow: 6px 0 32px rgba(0,0,0,0.55) !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span {
    color: var(--text-2) !important;
    font-family: 'Outfit', sans-serif !important;
}

/* ─── Select & Multiselect ───────────────────── */
[data-baseweb="select"] > div {
    background-color: var(--elevated) !important;
    border: 1px solid var(--border-2) !important;
    border-radius: var(--r) !important;
    min-height: 44px !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
[data-baseweb="select"] > div:hover {
    border-color: rgba(201,162,39,0.4) !important;
}
[data-baseweb="select"]:focus-within > div {
    border-color: var(--gold-mid) !important;
    box-shadow: 0 0 0 3px rgba(201,162,39,0.07) !important;
}
[data-baseweb="select"] > div > div {
    color: var(--text) !important;
    font-family: 'Outfit', sans-serif !important;
    font-size: 0.88rem !important;
}
[data-baseweb="tag"] {
    background-color: var(--gold-dim) !important;
    border: 1px solid var(--gold-mid) !important;
    border-radius: 2px !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 0.74rem !important;
}
[data-baseweb="tag"] span,
[data-baseweb="tag"] svg { color: var(--gold) !important; fill: var(--gold) !important; }
[data-baseweb="popover"] > div,
[data-baseweb="menu"] {
    background-color: var(--elevated) !important;
    border: 1px solid var(--border-2) !important;
    border-radius: var(--r) !important;
    box-shadow: 0 16px 48px rgba(0,0,0,0.65) !important;
}
[role="option"] {
    color: var(--text-2) !important;
    font-family: 'Outfit', sans-serif !important;
    font-size: 0.88rem !important;
    padding: 8px 14px !important;
    transition: background 0.15s !important;
}
[role="option"]:hover,
[role="option"][aria-selected="true"] { background-color: var(--gold-dim) !important; color: var(--text) !important; }
[data-testid="stSelectbox"] > div > div {
    background-color: var(--elevated) !important;
    border: 1px solid var(--border-2) !important;
    color: var(--text) !important;
    border-radius: var(--r) !important;
    min-height: 44px !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
[data-testid="stSelectbox"] > div > div:hover {
    border-color: rgba(201,162,39,0.4) !important;
}
[data-testid="stSelectbox"]:focus-within > div > div {
    border-color: var(--gold-mid) !important;
    box-shadow: 0 0 0 3px rgba(201,162,39,0.07) !important;
}
[data-testid="stMultiSelect"] label,
[data-testid="stSelectbox"] label {
    color: var(--muted) !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 0.63rem !important;
    letter-spacing: 0.2em !important;
    text-transform: uppercase !important;
}

/* ─── Buttons ─────────────────────────────────── */
.stButton > button {
    background: var(--gold-dim) !important;
    color: var(--gold) !important;
    border: 1px solid var(--gold-mid) !important;
    font-family: 'Bebas Neue', sans-serif !important;
    letter-spacing: 0.15em !important;
    font-size: 1rem !important;
    border-radius: var(--r) !important;
    padding: 0.4rem 1.2rem !important;
    transition: background 0.2s, color 0.2s, box-shadow 0.2s !important;
}
.stButton > button:hover {
    background: var(--gold) !important;
    color: var(--bg) !important;
    border-color: var(--gold) !important;
    box-shadow: 0 4px 20px rgba(201,162,39,0.28) !important;
}
[data-testid="stDownloadButton"] button {
    background: transparent !important;
    color: var(--muted) !important;
    border: 1px solid var(--border-2) !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 0.68rem !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    border-radius: var(--r) !important;
}
[data-testid="stDownloadButton"] button:hover {
    color: var(--gold) !important;
    border-color: var(--gold-mid) !important;
}

/* ─── Tabs ────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid var(--border) !important;
    gap: 0 !important;
    padding: 0 !important;
}
.stTabs [data-baseweb="tab-list"] button {
    background: transparent !important;
    color: var(--muted) !important;
    font-family: 'Bebas Neue', sans-serif !important;
    font-size: 1.08rem !important;
    letter-spacing: 0.14em !important;
    padding: 0.65rem 1.65rem !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    margin-bottom: -1px !important;
    transition: color 0.2s ease, background 0.2s ease !important;
}
.stTabs [data-baseweb="tab-list"] button:hover {
    color: var(--text-2) !important;
    background: rgba(201,162,39,0.04) !important;
}
.stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
    color: var(--gold) !important;
    border-bottom-color: var(--gold) !important;
    background: linear-gradient(180deg, rgba(201,162,39,0.06) 0%, transparent 100%) !important;
}
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }
.stTabs [data-baseweb="tab-panel"] { padding-top: 1.5rem !important; }

/* ─── Typography ─────────────────────────────── */
h1, h2, h3 {
    font-family: 'Bebas Neue', sans-serif !important;
    letter-spacing: 0.08em !important;
    color: var(--text) !important;
}
h2 {
    font-size: 1.6rem !important;
    border-bottom: 1px solid var(--border) !important;
    padding-bottom: 0.5rem !important;
    margin-bottom: 1.2rem !important;
    padding-left: 0.75rem !important;
    border-left: 3px solid var(--gold) !important;
    border-right: none !important;
    border-top: none !important;
}
h3 { font-size: 1.1rem !important; color: var(--muted) !important; }
p { color: var(--text-2) !important; font-family: 'Outfit', sans-serif !important; }
hr { border: none !important; border-top: 1px solid var(--border) !important; margin: 1.5rem 0 !important; }
.stCaptionContainer p {
    color: var(--muted) !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 0.67rem !important;
    letter-spacing: 0.1em !important;
}

/* ─── Slider ─────────────────────────────────── */
[data-testid="stSlider"] [role="slider"] {
    background-color: var(--gold) !important;
    border-color: var(--gold) !important;
    box-shadow: 0 0 10px rgba(201,162,39,0.45) !important;
}
[data-testid="stSlider"] p {
    color: var(--text-2) !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 0.8rem !important;
}

/* ─── Native Metrics (fallback) ──────────────── */
[data-testid="stMetric"] {
    background: linear-gradient(145deg, var(--card), var(--elevated)) !important;
    border: 1px solid var(--border) !important;
    border-top: 2px solid var(--gold) !important;
    padding: 1.2rem 1.4rem !important;
    border-radius: var(--r) !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3) !important;
}
[data-testid="stMetricLabel"] p {
    color: var(--muted) !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 0.6rem !important;
    letter-spacing: 0.2em !important;
    text-transform: uppercase !important;
}
[data-testid="stMetricValue"],
[data-testid="stMetricValue"] > div,
[data-testid="stMetricValue"] > div > div {
    color: var(--gold) !important;
    font-family: 'Bebas Neue', sans-serif !important;
    font-size: 2.2rem !important;
    letter-spacing: 0.03em !important;
}

/* ─── DataFrames ─────────────────────────────── */
[data-testid="stDataFrame"] {
    border: 1px solid var(--border-2) !important;
    border-radius: var(--r) !important;
    overflow: hidden !important;
    box-shadow: 0 4px 24px rgba(0,0,0,0.35) !important;
}
[data-testid="stDataFrame"] > div {
    border-radius: var(--r) !important;
}
[data-testid="stElementToolbarButton"] button {
    background: transparent !important;
    border-color: var(--border-2) !important;
    color: var(--muted) !important;
    border-radius: var(--r) !important;
}
[data-testid="stElementToolbarButton"] button:hover {
    color: var(--gold) !important;
    border-color: var(--gold-mid) !important;
}

/* ─── Alerts ─────────────────────────────────── */
[data-testid="stAlert"] {
    background-color: var(--card) !important;
    border-left-color: var(--gold) !important;
    border-radius: var(--r) !important;
}
[data-testid="stAlert"] p { color: var(--text-2) !important; }

/* ─── Checkbox ───────────────────────────────── */
[data-testid="stCheckbox"] {
    padding: 3px 0 !important;
}
[data-baseweb="checkbox"] span {
    color: var(--text-2) !important;
    font-family: 'Outfit', sans-serif !important;
    font-size: 0.875rem !important;
    line-height: 1.4 !important;
}
/* Checkbox visual — unchecked */
[data-baseweb="checkbox"] [role="checkbox"] {
    width: 16px !important;
    height: 16px !important;
    min-width: 16px !important;
    border: 1.5px solid var(--border-2) !important;
    border-radius: 3px !important;
    background-color: var(--elevated) !important;
    transition: border-color 0.15s ease, background-color 0.15s ease, box-shadow 0.15s ease !important;
}
[data-baseweb="checkbox"]:hover [role="checkbox"] {
    border-color: rgba(201,162,39,0.45) !important;
    box-shadow: 0 0 0 3px rgba(201,162,39,0.06) !important;
}
/* Checkbox visual — checked */
[data-baseweb="checkbox"] [role="checkbox"][aria-checked="true"] {
    background-color: var(--gold) !important;
    border-color: var(--gold) !important;
    box-shadow: 0 0 8px rgba(201,162,39,0.3) !important;
}

/* ─── Spinner ────────────────────────────────── */
.stSpinner > div > div { border-top-color: var(--gold) !important; }
.stSpinner p {
    color: var(--muted) !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 0.75rem !important;
}
[data-testid="stSidebar"] [data-testid="stAlert"] { border-radius: var(--r) !important; }

/* ══════════════════════════════════════════════
   HERO
══════════════════════════════════════════════ */
@keyframes fadeUp {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
}

.hero-wrap {
    position: relative;
    padding: 1.8rem 0 0;
    overflow: hidden;
}
.hero-bg-mark {
    position: absolute;
    top: -1rem;
    right: -0.5rem;
    font-family: 'Bebas Neue', sans-serif;
    font-size: clamp(5rem, 15vw, 13rem);
    color: rgba(201,162,39,0.027);
    letter-spacing: 0.06em;
    line-height: 1;
    user-select: none;
    pointer-events: none;
    white-space: nowrap;
}
.hero-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 0.65rem;
    font-family: 'DM Mono', monospace;
    font-size: 0.62rem;
    letter-spacing: 0.38em;
    color: var(--gold);
    text-transform: uppercase;
    margin-bottom: 0.55rem;
    animation: fadeUp 0.55s ease both;
}
.hero-eyebrow::before {
    content: '';
    display: inline-block;
    width: 22px;
    height: 1px;
    background: linear-gradient(to right, transparent, var(--gold));
    opacity: 0.55;
}
.hero-eyebrow::after {
    content: '';
    display: inline-block;
    width: 22px;
    height: 1px;
    background: linear-gradient(to left, transparent, var(--gold));
    opacity: 0.55;
}
.hero-title {
    font-family: 'Bebas Neue', sans-serif !important;
    font-size: clamp(3.2rem, 6vw, 5.8rem) !important;
    letter-spacing: 0.05em !important;
    color: var(--text) !important;
    line-height: 0.9 !important;
    margin: 0 !important;
    padding: 0 !important;
    animation: fadeUp 0.55s ease 0.08s both;
}
.hero-title-gold {
    color: var(--gold);
    display: block;
}
.hero-sub {
    font-family: 'DM Mono', monospace;
    font-size: 0.6rem;
    letter-spacing: 0.3em;
    color: var(--muted);
    text-transform: uppercase;
    margin-top: 0.7rem;
    display: block;
    animation: fadeUp 0.55s ease 0.16s both;
}
.hero-rule {
    height: 1px;
    background: linear-gradient(to right, var(--gold) 0%, rgba(201,162,39,0.18) 45%, transparent 100%);
    margin: 1.3rem 0 0;
}
.hero-rule::after {
    content: '';
    display: block;
    height: 1px;
    margin-top: 2px;
    background: linear-gradient(to right, rgba(201,162,39,0.1) 0%, transparent 40%);
}

/* ══════════════════════════════════════════════
   METRIC CARDS
══════════════════════════════════════════════ */
@keyframes shimmer {
    0%   { left: -60%; }
    100% { left: 130%; }
}

.metrics-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.85rem;
    margin: 1.6rem 0 0.6rem;
}
.m-card {
    position: relative;
    background: linear-gradient(145deg, var(--card) 0%, var(--elevated) 100%);
    border: 1px solid var(--border);
    border-top: 2px solid var(--gold);
    padding: 1.4rem 1.5rem 1.25rem;
    border-radius: var(--r);
    overflow: hidden;
    transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
    cursor: default;
}
.m-card::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse 75% 65% at 0% 100%, rgba(201,162,39,0.07), transparent 60%);
    pointer-events: none;
}
.m-card::after {
    content: '';
    position: absolute;
    top: 0;
    left: -60%;
    width: 30%;
    height: 100%;
    background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.022) 50%, transparent 100%);
    animation: shimmer 5s ease-in-out 0.8s infinite;
    pointer-events: none;
}
.m-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 14px 44px rgba(0,0,0,0.5), 0 0 0 1px rgba(201,162,39,0.14);
    border-color: rgba(201,162,39,0.3);
}
.m-ghost {
    position: absolute;
    bottom: -0.3rem;
    right: 0.8rem;
    font-family: 'Bebas Neue', sans-serif;
    font-size: 3.5rem;
    color: rgba(201,162,39,0.05);
    line-height: 1;
    letter-spacing: 0.05em;
    user-select: none;
    pointer-events: none;
}
.m-num {
    display: block;
    position: relative;
    font-family: 'Bebas Neue', sans-serif;
    font-size: 3.1rem;
    color: var(--gold);
    line-height: 1;
    letter-spacing: 0.02em;
    text-shadow: 0 0 28px rgba(201,162,39,0.18);
}
.m-label {
    display: block;
    position: relative;
    font-family: 'DM Mono', monospace;
    font-size: 0.57rem;
    color: var(--muted);
    letter-spacing: 0.28em;
    text-transform: uppercase;
    margin-top: 0.32rem;
}

/* ══════════════════════════════════════════════
   SIDEBAR
══════════════════════════════════════════════ */
.sidebar-head {
    padding: 1.3rem 0 0.8rem;
    text-align: center;
}
.sidebar-logo {
    display: block;
    width: 72px;
    height: 72px;
    margin: 0 auto 0.7rem;
    border-radius: 50%;
    object-fit: cover;
    box-shadow: 0 0 22px rgba(201,162,39,0.2), 0 0 0 1px rgba(201,162,39,0.15);
}
.sidebar-club {
    display: block;
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.35rem;
    letter-spacing: 0.28em;
    color: var(--gold);
    line-height: 1;
}
.sidebar-season {
    display: block;
    font-family: 'DM Mono', monospace;
    font-size: 0.55rem;
    letter-spacing: 0.3em;
    color: var(--muted);
    text-transform: uppercase;
    margin-top: 0.38rem;
}
.sidebar-divider {
    margin: 1rem 0;
    height: 1px;
    background: linear-gradient(to right, transparent, var(--border-2), transparent);
}
.sidebar-section-label {
    display: block;
    font-family: 'DM Mono', monospace;
    font-size: 0.56rem;
    letter-spacing: 0.24em;
    color: var(--muted);
    text-transform: uppercase;
    margin-bottom: 0.55rem;
}

/* ══════════════════════════════════════════════
   FOOTER
══════════════════════════════════════════════ */
.footer-wrap { margin-top: 2.5rem; padding-bottom: 1.2rem; }
.footer-sep {
    height: 1px;
    background: linear-gradient(to right, transparent, var(--border-2), transparent);
    margin-bottom: 1rem;
}
.footer-text {
    text-align: center;
    font-family: 'DM Mono', monospace !important;
    font-size: 0.58rem !important;
    letter-spacing: 0.2em !important;
    color: var(--muted) !important;
    text-transform: uppercase !important;
}
.footer-text a {
    color: var(--gold) !important;
    text-decoration: none !important;
    transition: opacity 0.2s !important;
}
.footer-text a:hover { opacity: 0.75 !important; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers Plotly
# ---------------------------------------------------------------------------

def _hex_rgba(hex_color: str, alpha: float) -> str:
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    return f"rgba({r},{g},{b},{alpha})"


def apply_chart_theme(fig: go.Figure, title: str = "") -> go.Figure:
    """Applique le thème Bernabéu Noir à tout graphique Plotly."""
    layout: dict = dict(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#445566", family="DM Mono, monospace", size=11),
        margin=dict(l=40, r=16, t=58 if title else 28, b=36),
        legend=dict(
            bgcolor="rgba(11,18,30,0.92)",
            bordercolor="#1e3050",
            borderwidth=1,
            font=dict(color="#8fa0b2", family="DM Mono, monospace", size=10),
        ),
    )
    if title:
        layout["title"] = dict(
            text=title.upper(),
            font=dict(family="Bebas Neue, sans-serif", size=20, color="#e6e0d0"),
            x=0, xanchor="left", pad=dict(l=4, b=8),
        )
    fig.update_xaxes(gridcolor="#152338", linecolor="#1e3050", zerolinecolor="#1e3050", tickfont=dict(color="#445566", family="DM Mono, monospace", size=10))
    fig.update_yaxes(gridcolor="#152338", linecolor="#1e3050", zerolinecolor="#1e3050", tickfont=dict(color="#445566", family="DM Mono, monospace", size=10))
    fig.update_layout(**layout)
    return fig


# ---------------------------------------------------------------------------
# Chargement des données
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def load_data() -> tuple[list[dict], list[dict]]:
    articles, stats = [], []
    if DATA_FILE.exists():
        articles = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    if STATS_FILE.exists():
        stats = json.loads(STATS_FILE.read_text(encoding="utf-8"))
    return articles, stats


def flatten_to_df(articles: list[dict]) -> pd.DataFrame:
    rows = []
    for a in articles:
        for p in a.get("players", []):
            rows.append({
                "date": pd.to_datetime(a["date"]),
                "adversaire": a.get("opponent", "?"),
                "competition": a.get("competition", "Inconnue"),
                "joueur": p["name"],
                "note": p["note"],
                "url": a.get("url", ""),
                "titre": a.get("title", ""),
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("date")
        df["note"] = pd.to_numeric(df["note"], errors="coerce")
    return df


def stats_to_df(stats: list[dict]) -> pd.DataFrame:
    all_comps: set[str] = set()
    for s in stats:
        all_comps.update(s.get("par_competition", {}).keys())
    all_comps_sorted = sorted(all_comps)

    rows = []
    for s in stats:
        row = {
            "Joueur": s["player_name"],
            "Moy. globale": s["moyenne_globale"],
            "Moy. JDR": s.get("moyenne_jdr") or None,
            "Moy. FotMob": s.get("moyenne_fotmob") or None,
            "Matchs notés": s["nb_matchs"],
            "Non notés": s.get("nb_matchs_non_notes", 0),
            "Total": s.get("nb_matchs_total", s["nb_matchs"]),
            "Note min": s.get("note_min", "-"),
            "Note max": s.get("note_max", "-"),
            "Écart-type": s.get("ecart_type", 0.0),
            "Buts": s.get("total_goals", 0),
            "Passes D.": s.get("total_assists", 0),
        }
        for comp in all_comps_sorted:
            if comp in s.get("par_competition", {}):
                cd = s["par_competition"][comp]
                row[comp] = cd["moyenne"]
                row[f"{comp} (notés)"] = cd["nb_matchs"]
                row[f"{comp} (non notés)"] = cd.get("nb_non_notes", 0)
            else:
                row[comp] = None
                row[f"{comp} (notés)"] = 0
                row[f"{comp} (non notés)"] = 0
        rows.append(row)

    return pd.DataFrame(rows)


def stats_to_matches_df(stats: list[dict]) -> pd.DataFrame:
    """Flat DataFrame from stats detail_matchs — includes JDR, FotMob and combined notes."""
    rows = []
    for s in stats:
        for m in s.get("detail_matchs", []):
            rows.append({
                "date": pd.to_datetime(m["date"]),
                "adversaire": m.get("opponent") or "?",
                "competition": m.get("competition", "Inconnue"),
                "joueur": s["player_name"],
                "note": m.get("note"),
                "jdr_note": m.get("jdr_note"),
                "fotmob_note": m.get("fotmob_note"),
                "goals": m.get("goals", 0) or 0,
                "assists": m.get("assists", 0) or 0,
                "url": m.get("url", ""),
                "titre": m.get("title", ""),
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("date")
        for col in ("note", "jdr_note", "fotmob_note"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Coloration conditionnelle
# ---------------------------------------------------------------------------

def color_note(val) -> str:
    if pd.isna(val) or val is None:
        return ""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return ""
    if v >= 7:
        return f"background-color: {COLOR_SCALE['high']}22; color: {COLOR_SCALE['high']}"
    elif v >= 5:
        return f"background-color: {COLOR_SCALE['mid']}22; color: {COLOR_SCALE['mid']}"
    elif v > 0:
        return f"background-color: {COLOR_SCALE['low']}22; color: {COLOR_SCALE['low']}"
    return ""


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    logo_b64 = _load_logo_b64()
    logo_html = (
        f'<img src="data:image/jpeg;base64,{logo_b64}" class="sidebar-logo" alt="JDR">'
        if logo_b64
        else '<div style="width:72px;height:72px;margin:0 auto 0.7rem;border-radius:50%;'
             'border:1px solid rgba(201,162,39,0.25);background:rgba(201,162,39,0.06)"></div>'
    )
    st.sidebar.markdown(f"""
<div class="sidebar-head">
    {logo_html}
    <span class="sidebar-club">REAL MADRID</span>
    <span class="sidebar-season">Saison 2025 — 2026</span>
</div>
<div class="sidebar-divider"></div>
""", unsafe_allow_html=True)

    all_comps = sorted(df["competition"].unique()) if not df.empty else []
    all_players = sorted(df["joueur"].unique()) if not df.empty else []

    # Checkboxes par compétition
    st.sidebar.markdown(
        '<span class="sidebar-section-label">Compétitions</span>',
        unsafe_allow_html=True,
    )
    selected_comps = [
        comp for comp in all_comps
        if st.sidebar.checkbox(comp, value=True, key=f"comp_{comp}")
    ]

    st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

    selected_players = st.sidebar.multiselect(
        "Joueurs",
        options=all_players,
        default=[],
        placeholder="Tous les joueurs",
    )

    return selected_comps, selected_players


# ---------------------------------------------------------------------------
# Onglet 1 — Tableau général
# ---------------------------------------------------------------------------

def tab_tableau(stats: list[dict], selected_comps: list[str], selected_players: list[str]) -> None:
    st.header("Tableau général")

    if not stats:
        st.info("Aucune donnée disponible. Cliquez sur **Rafraîchir les données**.")
        return

    filtered_stats = stats
    if selected_players:
        filtered_stats = [s for s in filtered_stats if s["player_name"] in selected_players]

    df = stats_to_df(filtered_stats)

    if df.empty:
        st.warning("Aucun joueur trouvé avec les filtres sélectionnés.")
        return

    note_cols = [c for c in df.columns if "Moy." in c or (
        any(comp in c for comp in ["Liga", "Champions", "Coupe", "Super", "Intercontinental", "Amical"])
        and "notés" not in c
    )]

    ctrl1, ctrl2 = st.columns([2, 1])
    with ctrl1:
        sort_label = st.radio(
            "Trier par",
            options=["Combiné", "JDR", "FotMob"],
            horizontal=True,
            key="tab_sort_by",
        )
    sort_key = {"Combiné": "Moy. globale", "JDR": "Moy. JDR", "FotMob": "Moy. FotMob"}[sort_label]
    with ctrl2:
        min_matchs = st.slider("Min. matchs notés", 1, 20, 1, key="min_matchs_tab")

    df_sorted = df.copy()
    df_sorted[sort_key] = pd.to_numeric(df_sorted[sort_key], errors="coerce").fillna(0)
    df_sorted = df_sorted.sort_values(sort_key, ascending=False)
    df_filtered = df_sorted[df_sorted["Matchs notés"] >= min_matchs]

    st.caption(f"{len(df_filtered)} joueurs affichés · tri : {sort_label}")

    styled = df_filtered.style.applymap(color_note, subset=note_cols).format(
        {c: "{:.2f}" for c in note_cols if c in df_filtered.columns},
        na_rep="—",
    )
    st.dataframe(styled, use_container_width=True, height=600)

    csv = df_filtered.to_csv(index=False).encode("utf-8")
    st.download_button("Exporter CSV", csv, "notes_real_madrid.csv", "text/csv")


# ---------------------------------------------------------------------------
# Onglet 2 — Évolution temporelle
# ---------------------------------------------------------------------------

def tab_evolution(matches_df: pd.DataFrame, selected_players: list[str], selected_comps: list[str]) -> None:
    st.header("Évolution temporelle")

    if matches_df.empty:
        st.info("Aucune donnée disponible.")
        return

    mask = matches_df["competition"].isin(selected_comps)
    if selected_players:
        mask &= matches_df["joueur"].isin(selected_players)
    df_f = matches_df[mask].copy()

    if df_f.empty:
        st.warning("Aucune donnée pour les filtres sélectionnés.")
        return

    players_available = sorted(df_f["joueur"].unique())
    _trio = ["Kylian Mbappé", "Vinicius Jr", "Jude Bellingham"]
    if not selected_players:
        default_players = [p for p in _trio if p in players_available] or players_available[:3]
    else:
        default_players = [p for p in selected_players if p in players_available]

    players_choice = st.multiselect(
        "Joueurs à afficher",
        options=players_available,
        default=default_players,
        key="evo_players",
    )

    # Source + rolling controls
    sc1, sc2, sc3, sc4 = st.columns(4)
    show_combined = sc1.checkbox("Combiné", value=True, key="evo_combined")
    show_jdr     = sc2.checkbox("JDR",     value=True, key="evo_jdr")
    show_fotmob  = sc3.checkbox("FotMob",  value=True, key="evo_fotmob")
    show_rolling = sc4.checkbox("Moy. glissante (5M)", value=False, key="evo_rolling")

    if not players_choice:
        st.info("Sélectionnez au moins un joueur.")
        return
    if not (show_combined or show_jdr or show_fotmob):
        st.info("Cochez au moins une source.")
        return

    # (col, label, dash, marker_symbol, alpha_line)
    SERIES = [
        ("note",       "Combiné", "solid",  "circle",  1.0, show_combined),
        ("jdr_note",   "JDR",     "dash",   "square",  0.85, show_jdr),
        ("fotmob_note","FotMob",  "dot",    "diamond", 0.85, show_fotmob),
    ]

    df_plot = df_f[df_f["joueur"].isin(players_choice)].copy()
    fig = go.Figure()

    for idx, player in enumerate(players_choice):
        pdata = df_plot[df_plot["joueur"] == player].sort_values("date")
        if pdata.empty:
            continue
        color = MADRID_PALETTE[idx % len(MADRID_PALETTE)]

        for col, label, dash, sym, alpha, show in SERIES:
            if not show:
                continue
            y_vals = pdata[col]
            if y_vals.isna().all():
                continue
            is_main = col == "note"
            lcolor = color if is_main else _hex_rgba(color, 0.65)
            trace_name = player if is_main else f"{player} · {label}"
            fig.add_trace(go.Scatter(
                x=pdata["date"],
                y=y_vals,
                mode="lines+markers",
                name=trace_name,
                line=dict(color=lcolor, width=2 if is_main else 1.5, dash=dash),
                marker=dict(color=lcolor, size=7 if is_main else 6, symbol=sym,
                            line=dict(color=_hex_rgba(color, 0.35), width=2)),
                opacity=alpha,
                connectgaps=True,
                hovertemplate=(
                    f"<b>{player}</b> ({label})<br>"
                    "Date: %{x|%d/%m/%Y}<br>"
                    "Note: <b>%{y:.1f}/10</b><br>"
                    "Adversaire: %{customdata[0]}<br>"
                    "Compétition: %{customdata[1]}"
                    "<extra></extra>"
                ),
                customdata=pdata[["adversaire", "competition"]].values,
            ))

        if show_rolling:
            for r_col, r_label, _, _, _, r_show in SERIES:
                if not r_show or pdata[r_col].notna().sum() < 3:
                    continue
                rolling = pdata[r_col].rolling(window=5, min_periods=2).mean()
                r_color = color if r_col == "note" else _hex_rgba(color, 0.65)
                fig.add_trace(go.Scatter(
                    x=pdata["date"], y=rolling,
                    mode="lines",
                    name=f"{player} · {r_label} (moy. 5)",
                    line=dict(dash="longdash", width=1.2, color=r_color),
                    opacity=0.45, hoverinfo="skip",
                ))

    fig.update_layout(
        yaxis=dict(range=[0, 10.5], dtick=1),
        hovermode="x unified",
        height=520,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="#0c1624", bordercolor="#1e3050", font_family="DM Mono, monospace"),
    )
    apply_chart_theme(fig, "Évolution des notes")
    fig.update_xaxes(title_text="Date", title_font=dict(color="#445566", size=11))
    fig.update_yaxes(title_text="Note /10", title_font=dict(color="#445566", size=11))
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Onglet 3 — Comparaison joueurs
# ---------------------------------------------------------------------------

def tab_comparaison(stats: list[dict], selected_players: list[str], selected_comps: list[str]) -> None:
    st.header("Comparaison joueurs")

    if not stats:
        st.info("Aucune donnée disponible.")
        return

    all_players = sorted(s["player_name"] for s in stats)
    players_choice = st.multiselect(
        "Joueurs à comparer",
        options=all_players,
        default=(selected_players[:4] if selected_players else
                 [p for p in ["Kylian Mbappé", "Vinicius Jr", "Jude Bellingham"] if p in all_players]
                 or all_players[:3]),
        key="comp_players",
    )

    if not players_choice:
        st.info("Sélectionnez au moins un joueur.")
        return

    # Metric selector
    metric_label = st.radio(
        "Source de notes",
        options=["Combiné", "JDR", "FotMob"],
        horizontal=True,
        key="comp_metric",
    )
    metric_key = {"Combiné": "note", "JDR": "jdr_note", "FotMob": "fotmob_note"}[metric_label]

    comps_in_filter = set(selected_comps)
    all_comps_data: set[str] = set()
    for s in stats:
        if s["player_name"] in players_choice:
            for m in s.get("detail_matchs", []):
                comp = m.get("competition", "")
                if comp in comps_in_filter and m.get(metric_key) is not None:
                    all_comps_data.add(comp)
    comps_sorted = sorted(all_comps_data)

    if not comps_sorted:
        st.warning("Aucune compétition trouvée pour ces joueurs avec la source sélectionnée.")
        return

    # Helper: compute per-player, per-comp average for the chosen metric
    def _avg_per_comp(player_stats: dict, comp: str) -> tuple[float | None, int]:
        vals = [
            float(m[metric_key])
            for m in player_stats.get("detail_matchs", [])
            if m.get("competition") == comp and m.get(metric_key) is not None
        ]
        return (round(sum(vals) / len(vals), 2) if vals else None, len(vals))

    # Palette stable par joueur
    player_colors = {p: MADRID_PALETTE[i % len(MADRID_PALETTE)] for i, p in enumerate(players_choice)}

    col1, col2 = st.columns(2)

    # Bar chart groupé
    with col1:
        bar_data = []
        for s in stats:
            if s["player_name"] not in players_choice:
                continue
            for comp in comps_sorted:
                avg, n = _avg_per_comp(s, comp)
                if avg is not None:
                    bar_data.append({
                        "Joueur": s["player_name"],
                        "Compétition": comp,
                        "Moyenne": avg,
                        "Matchs": n,
                    })

        if bar_data:
            df_bar = pd.DataFrame(bar_data)
            fig_bar = px.bar(
                df_bar,
                x="Compétition",
                y="Moyenne",
                color="Joueur",
                barmode="group",
                range_y=[0, 10],
                hover_data=["Matchs"],
                color_discrete_map=player_colors,
                height=420,
            )
            fig_bar.update_layout(
                legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="center", x=0.5),
                bargap=0.2, bargroupgap=0.05,
                hoverlabel=dict(bgcolor="#0c1624", bordercolor="#1e3050", font_family="DM Mono, monospace"),
            )
            apply_chart_theme(fig_bar, f"Moyennes par compétition · {metric_label}")
            fig_bar.update_layout(margin=dict(b=72))
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Pas de données pour le graphique en barres.")

    # Radar chart
    with col2:
        radar_cats = comps_sorted + ["Régularité"]
        fig_radar = go.Figure()

        for s in stats:
            if s["player_name"] not in players_choice:
                continue
            color = player_colors[s["player_name"]]
            values = []
            for comp in comps_sorted:
                avg, _ = _avg_per_comp(s, comp)
                values.append(avg if avg is not None else 0)
            regularite = max(0, 10 - s.get("ecart_type", 0) * 2)
            values.append(regularite)
            values_closed = values + [values[0]]
            cats_closed = radar_cats + [radar_cats[0]]

            fig_radar.add_trace(go.Scatterpolar(
                r=values_closed, theta=cats_closed,
                fill="toself", name=s["player_name"],
                fillcolor=_hex_rgba(color, 0.1),
                line=dict(color=color, width=2), opacity=0.9,
            ))

        fig_radar.update_layout(
            polar=dict(
                bgcolor="rgba(0,0,0,0)",
                radialaxis=dict(
                    visible=True, range=[0, 10],
                    gridcolor="#152338", linecolor="#1e3050",
                    tickfont=dict(color="#445566", family="DM Mono", size=9), tickcolor="#445566",
                ),
                angularaxis=dict(
                    gridcolor="#152338", linecolor="#1e3050",
                    tickfont=dict(color="#8fa0b2", family="DM Mono", size=10),
                ),
            ),
            showlegend=True,
            legend=dict(orientation="h", yanchor="top", y=-0.08, xanchor="center", x=0.5),
            height=440,
            hoverlabel=dict(bgcolor="#0c1624", bordercolor="#1e3050", font_family="DM Mono, monospace"),
        )
        apply_chart_theme(fig_radar, f"Profil multi-compétition · {metric_label}")
        fig_radar.update_layout(margin=dict(b=72))
        st.plotly_chart(fig_radar, use_container_width=True)


# ---------------------------------------------------------------------------
# Onglet 4 — Détail par match
# ---------------------------------------------------------------------------

def tab_detail(matches_df: pd.DataFrame, selected_players: list[str], selected_comps: list[str]) -> None:
    st.header("Détail par match")

    if matches_df.empty:
        st.info("Aucune donnée disponible.")
        return

    # ── Ligne 1 : compétition + sélecteur de match ───────────────────────
    base = matches_df[matches_df["competition"].isin(selected_comps)].copy()
    comps_avail = sorted(base["competition"].unique())

    col1, col2 = st.columns([1, 2])
    with col1:
        comp_filter = st.selectbox(
            "Compétition",
            options=["Toutes"] + comps_avail,
            key="detail_comp",
        )
    if comp_filter != "Toutes":
        base = base[base["competition"] == comp_filter]

    # Build unique match labels sorted newest-first
    match_index = (
        base[["date", "adversaire", "competition"]]
        .drop_duplicates()
        .sort_values("date", ascending=False)
        .reset_index(drop=True)
    )
    if match_index.empty:
        st.info("Aucun match pour cette sélection.")
        return

    match_labels = [
        f"{r['date'].strftime('%d/%m/%Y')} — vs {r['adversaire']}  ({r['competition']})"
        for _, r in match_index.iterrows()
    ]
    with col2:
        selected_label = st.selectbox("Match", options=match_labels, key="detail_match")

    sel = match_index.iloc[match_labels.index(selected_label)]
    df_match = base[
        (base["date"] == sel["date"]) &
        (base["adversaire"] == sel["adversaire"]) &
        (base["competition"] == sel["competition"])
    ].copy()

    # ── Ligne 2 : sources + note minimale ────────────────────────────────
    sc1, sc2, sc3 = st.columns([1, 1, 2])
    show_jdr    = sc1.checkbox("JDR",    value=True, key="detail_jdr")
    show_fotmob = sc2.checkbox("FotMob", value=True, key="detail_fotmob")

    if show_jdr and show_fotmob:
        min_col, min_label = "note", "Combiné"
    elif show_jdr:
        min_col, min_label = "jdr_note", "JDR"
    else:
        min_col, min_label = "fotmob_note", "FotMob"

    note_min = sc3.slider(f"Note minimale ({min_label})", 0, 10, 0, key="detail_note_min")

    # Apply note-min filter on the relevant column
    df_match = df_match[
        (df_match[min_col] >= note_min) | df_match[min_col].isna()
    ]

    if df_match.empty:
        st.warning("Aucun joueur pour ces filtres.")
        return

    # ── Tableau ───────────────────────────────────────────────────────────
    cols_to_show = ["joueur"]
    rename_map   = {"joueur": "Joueur"}
    fmt          = {}
    color_subset = []

    if show_jdr:
        cols_to_show.append("jdr_note");  rename_map["jdr_note"] = "JDR"
        fmt["JDR"] = lambda x: "—" if pd.isna(x) else f"{x:.0f}"
        color_subset.append("JDR")
    if show_fotmob:
        cols_to_show.append("fotmob_note"); rename_map["fotmob_note"] = "FotMob"
        fmt["FotMob"] = lambda x: "—" if pd.isna(x) else f"{x:.1f}"
        color_subset.append("FotMob")
    if show_jdr and show_fotmob:
        cols_to_show.append("note"); rename_map["note"] = "Combiné"
        fmt["Combiné"] = lambda x: "—" if pd.isna(x) else f"{x:.2f}"
        color_subset.append("Combiné")

    # Add goals/assists if FotMob data present
    if show_fotmob:
        cols_to_show += ["goals", "assists"]
        rename_map.update({"goals": "Buts", "assists": "Passes D."})

    df_display = (
        df_match[cols_to_show]
        .rename(columns=rename_map)
        .sort_values("Joueur")
        .reset_index(drop=True)
    )

    st.caption(f"{len(df_display)} joueurs · {sel['date'].strftime('%d/%m/%Y')} vs {sel['adversaire']}")

    styled = df_display.style
    if color_subset:
        styled = styled.applymap(color_note, subset=color_subset)
    if fmt:
        styled = styled.format(fmt, na_rep="—")
    st.dataframe(styled, use_container_width=True, height=min(600, 55 + 35 * len(df_display)))

    # ── Résumé du match ───────────────────────────────────────────────────
    st.markdown("---")
    mc = st.columns(4)
    mc[0].metric("Joueurs", len(df_match))
    if show_jdr:
        jdr_v = df_match["jdr_note"].dropna()
        mc[1].metric("Moy. JDR", f"{jdr_v.mean():.2f}" if not jdr_v.empty else "—")
    if show_fotmob:
        fm_v = df_match["fotmob_note"].dropna()
        mc[2].metric("Moy. FotMob", f"{fm_v.mean():.2f}" if not fm_v.empty else "—")
    if show_jdr and show_fotmob:
        comb_v = df_match["note"].dropna()
        mc[3].metric("Moy. Combiné", f"{comb_v.mean():.2f}" if not comb_v.empty else "—")


# ---------------------------------------------------------------------------
# Onglet 5 — Profil joueur
# ---------------------------------------------------------------------------

def tab_profil_joueur(stats: list[dict]) -> None:
    st.header("Profil joueur")

    if not stats:
        st.info("Aucune donnée disponible.")
        return

    all_players = [s["player_name"] for s in stats]
    player_name = st.selectbox(
        "Joueur",
        options=all_players,
        key="profil_player",
    )

    player_data = next((s for s in stats if s["player_name"] == player_name), None)
    if not player_data:
        return

    # ── En-tête : photo + métriques ──────────────────────────────────────
    col_photo, col_stats = st.columns([1, 3])

    with col_photo:
        image_url = player_data.get("image_url")
        if image_url:
            st.markdown(
                f'<img src="{image_url}" style="width:140px;height:140px;object-fit:cover;'
                f'border-radius:50%;border:2px solid rgba(201,162,39,0.4);'
                f'box-shadow:0 0 28px rgba(201,162,39,0.18);display:block;margin:0 auto;">',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="width:140px;height:140px;border-radius:50%;background:rgba(201,162,39,0.06);'
                'border:2px solid rgba(201,162,39,0.2);display:flex;align-items:center;justify-content:center;'
                'margin:0 auto;font-family:DM Mono,monospace;color:#445566;font-size:0.7rem;letter-spacing:0.1em;">'
                'NO IMG</div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            f'<p style="text-align:center;font-family:Bebas Neue,sans-serif;font-size:1.1rem;'
            f'letter-spacing:0.12em;color:#c9a227;margin-top:0.7rem;">{player_name}</p>',
            unsafe_allow_html=True,
        )

    with col_stats:
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Moy. globale", f"{player_data['moyenne_globale']:.2f}")
        moy_jdr = player_data.get("moyenne_jdr", 0)
        moy_fm = player_data.get("moyenne_fotmob", 0)
        m2.metric("Moy. JDR", f"{moy_jdr:.2f}" if moy_jdr else "—")
        m3.metric("Moy. FotMob", f"{moy_fm:.2f}" if moy_fm else "—")
        m4.metric("Buts", player_data.get("total_goals", 0))
        m5.metric("Passes D.", player_data.get("total_assists", 0))
        yellows = player_data.get("total_yellow_cards", 0)
        reds = player_data.get("total_red_cards", 0)
        m6.metric("Cartons", f"{yellows}J / {reds}R")

        # Ligne 2 : matchs
        m7, m8, m9, _, _, _ = st.columns(6)
        m7.metric("Matchs notés", player_data["nb_matchs"])
        m8.metric("Non notés", player_data.get("nb_matchs_non_notes", 0))
        m9.metric("Total appars.", player_data.get("nb_matchs_total", player_data["nb_matchs"]))

    st.markdown("---")

    # ── Graphique : évolution JDR + FotMob + combiné ─────────────────────
    matches = player_data.get("detail_matchs", [])
    rated_matches = [m for m in matches if m.get("note") is not None or m.get("jdr_note") is not None or m.get("fotmob_note") is not None]

    if rated_matches:
        dates = [m["date"] for m in rated_matches]
        opponents = [m.get("opponent") or "?" for m in rated_matches]
        comps = [m.get("competition", "") for m in rated_matches]

        jdr_notes = [m.get("jdr_note") for m in rated_matches]
        fm_notes = [m.get("fotmob_note") for m in rated_matches]
        combined_notes = [m.get("note") for m in rated_matches]

        fig = go.Figure()

        # JDR
        if any(n is not None for n in jdr_notes):
            fig.add_trace(go.Scatter(
                x=dates, y=jdr_notes,
                mode="lines+markers",
                name="JDR",
                line=dict(color="#c9a227", width=2),
                marker=dict(color="#c9a227", size=7),
                connectgaps=True,
                hovertemplate="<b>JDR</b><br>%{x}<br>Note: <b>%{y}/10</b><extra></extra>",
            ))

        # FotMob
        if any(n is not None for n in fm_notes):
            fig.add_trace(go.Scatter(
                x=dates, y=fm_notes,
                mode="lines+markers",
                name="FotMob",
                line=dict(color="#3b82f6", width=2),
                marker=dict(color="#3b82f6", size=7),
                connectgaps=True,
                hovertemplate="<b>FotMob</b><br>%{x}<br>Note: <b>%{y:.1f}/10</b><extra></extra>",
            ))

        # Combined (dashed)
        if any(n is not None for n in combined_notes):
            fig.add_trace(go.Scatter(
                x=dates, y=combined_notes,
                mode="lines",
                name="Combiné",
                line=dict(color="#ffffff", width=1.5, dash="dot"),
                opacity=0.45,
                connectgaps=True,
                hovertemplate="<b>Combiné</b><br>%{x}<br>Note: <b>%{y:.2f}/10</b><extra></extra>",
                customdata=list(zip(opponents, comps)),
            ))

        fig.update_layout(
            yaxis=dict(range=[0, 10.5], dtick=1),
            hovermode="x unified",
            height=400,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hoverlabel=dict(bgcolor="#0c1624", bordercolor="#1e3050", font_family="DM Mono, monospace"),
        )
        apply_chart_theme(fig, f"Évolution des notes — {player_name}")
        fig.update_xaxes(title_text="Date", title_font=dict(color="#445566", size=11))
        fig.update_yaxes(title_text="Note /10", title_font=dict(color="#445566", size=11))
        st.plotly_chart(fig, use_container_width=True)

    # ── Par compétition (3 barres : JDR / FotMob / Combiné) ─────────────
    matches = player_data.get("detail_matchs", [])
    all_comps_p = sorted({m.get("competition", "") for m in matches if m.get("competition")})
    if all_comps_p:
        SOURCES_BAR = [
            ("Combiné", "note",        "#e6e0d0"),
            ("JDR",     "jdr_note",    "#c9a227"),
            ("FotMob",  "fotmob_note", "#3b82f6"),
        ]
        fig_bar = go.Figure()
        for src_name, src_key, src_color in SOURCES_BAR:
            avgs = []
            for comp in all_comps_p:
                vals = [float(m[src_key]) for m in matches
                        if m.get("competition") == comp and m.get(src_key) is not None]
                avgs.append(round(sum(vals) / len(vals), 2) if vals else None)
            fig_bar.add_trace(go.Bar(
                name=src_name,
                x=all_comps_p,
                y=avgs,
                marker_color=src_color,
                text=[f"{v:.2f}" if v is not None else "" for v in avgs],
                textposition="outside",
                hovertemplate=f"<b>{src_name}</b><br>%{{x}}<br>%{{y:.2f}}/10<extra></extra>",
            ))
        fig_bar.update_layout(
            barmode="group",
            yaxis=dict(range=[0, 11]),
            height=340,
            legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5),
            hoverlabel=dict(bgcolor="#0c1624", bordercolor="#1e3050", font_family="DM Mono, monospace"),
        )
        apply_chart_theme(fig_bar, "Moyenne par compétition · JDR / FotMob / Combiné")
        fig_bar.update_layout(margin=dict(b=60))
        st.plotly_chart(fig_bar, use_container_width=True)

    # ── Historique des matchs ─────────────────────────────────────────────
    if matches:
        st.subheader("Historique des matchs")
        rows = []
        for m in sorted(matches, key=lambda x: x["date"], reverse=True):
            jdr = m.get("jdr_note")
            fm = m.get("fotmob_note")
            note = m.get("note")
            rows.append({
                "Date": m["date"],
                "Adversaire": m.get("opponent") or "?",
                "Compétition": m.get("competition", ""),
                "JDR": jdr,
                "FotMob": round(fm, 1) if fm is not None else None,
                "Combiné": round(note, 2) if note is not None else None,
                "Buts": m.get("goals", 0) or 0,
                "Passes D.": m.get("assists", 0) or 0,
            })
        df_hist = pd.DataFrame(rows)
        styled = df_hist.style.applymap(color_note, subset=["JDR", "FotMob", "Combiné"]).format(
            {
                "JDR": lambda x: "—" if pd.isna(x) else f"{x:.0f}",
                "FotMob": lambda x: "—" if pd.isna(x) else f"{x:.1f}",
                "Combiné": lambda x: "—" if pd.isna(x) else f"{x:.2f}",
            },
            na_rep="—",
        )
        st.dataframe(styled, use_container_width=True, height=min(600, 45 + 35 * len(rows)))


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

def main() -> None:
    inject_css()

    articles, stats = load_data()

    if not articles:
        st.markdown("""
<div class="hero-wrap">
    <div class="hero-bg-mark">REAL MADRID</div>
    <span class="hero-eyebrow">Saison 2025 — 2026</span>
    <h1 class="hero-title">REAL MADRID<br><span class="hero-title-gold">Notes de Match</span></h1>
    <span class="hero-sub">Le Journal du Real · Analyse de performance</span>
    <div class="hero-rule"></div>
</div>
""", unsafe_allow_html=True)
        st.warning(
            "Aucune donnée trouvée. Cliquez sur **Rafraîchir les données** "
            "dans la barre latérale pour lancer le scraping."
        )
        df_empty = pd.DataFrame(columns=["competition", "joueur", "date", "note", "adversaire", "url", "titre"])
        render_sidebar(df_empty)
        return

    matches_df = stats_to_matches_df(stats)
    selected_comps, selected_players = render_sidebar(matches_df)

    # Hero
    st.markdown("""
<div class="hero-wrap">
    <div class="hero-bg-mark">REAL MADRID</div>
    <span class="hero-eyebrow">Saison 2025 — 2026</span>
    <h1 class="hero-title">REAL MADRID<br><span class="hero-title-gold">Notes de Match</span></h1>
    <span class="hero-sub">Le Journal du Real · FotMob · Analyse de performance</span>
    <div class="hero-rule"></div>
</div>
""", unsafe_allow_html=True)

    # Métriques globales
    n_articles = len(articles)
    n_players = matches_df["joueur"].nunique() if not matches_df.empty else 0
    avg_note = f"{matches_df['note'].mean():.2f}" if not matches_df.empty and matches_df["note"].notna().any() else "—"
    n_comps = matches_df["competition"].nunique() if not matches_df.empty else 0

    st.markdown(f"""
<div class="metrics-grid">
    <div class="m-card">
        <span class="m-ghost">ART</span>
        <span class="m-num">{n_articles}</span>
        <span class="m-label">Articles analysés</span>
    </div>
    <div class="m-card">
        <span class="m-ghost">JRS</span>
        <span class="m-num">{n_players}</span>
        <span class="m-label">Joueurs évalués</span>
    </div>
    <div class="m-card">
        <span class="m-ghost">MOY</span>
        <span class="m-num">{avg_note}</span>
        <span class="m-label">Moyenne générale</span>
    </div>
    <div class="m-card">
        <span class="m-ghost">CUP</span>
        <span class="m-num">{n_comps}</span>
        <span class="m-label">Compétitions</span>
    </div>
</div>
""", unsafe_allow_html=True)

    # Onglets
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Tableau général",
        "Évolution",
        "Comparaison",
        "Détail par match",
        "Profil joueur",
    ])

    mdf_filtered = matches_df[matches_df["competition"].isin(selected_comps)] if selected_comps else matches_df

    with tab1:
        tab_tableau(stats, selected_comps, selected_players)

    with tab2:
        tab_evolution(mdf_filtered, selected_players, selected_comps)

    with tab3:
        tab_comparaison(stats, selected_players, selected_comps)

    with tab4:
        tab_detail(mdf_filtered, selected_players, selected_comps)

    with tab5:
        tab_profil_joueur(stats)

    # Footer
    st.markdown("""
<div class="footer-wrap">
    <div class="footer-sep"></div>
    <p class="footer-text">
        Données · <a href="https://lejournaldureal.fr" target="_blank">lejournaldureal.fr</a>
        &nbsp;·&nbsp; <a href="https://www.fotmob.com" target="_blank">FotMob</a>
        &nbsp;·&nbsp; Saison 2025–2026
    </p>
</div>
""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
