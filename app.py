"""
HVTS.AI Studio - Binance Futures Multi-Timeframe Signal Dashboard
==================================================================
Run:  streamlit run app.py
"""

import base64
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data_feed import fetch_all_tickers, fetch_bundles_threaded, get_top_symbols_by_volume
from indicators import (
    ZONE_COLORS, SIGNAL_COLORS, composite_oracle, gmma_signal, pivot_zone,
    williams_r, macd, crt, smc, vwap, rvol, normalize_signal, get_signal_color
)

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except Exception:
    HAS_AUTOREFRESH = False

APP_DIR = Path(__file__).parent
LOGO_PATH = APP_DIR / "assets" / "hvts_logo.png"

# ============================================================================
# PAGE CONFIG
# ============================================================================
st.set_page_config(
    page_title="HVTS.AI Studio",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# DESIGN TOKENS / THEME
# ============================================================================
BG = "#070a14"
SURFACE = "#0e1424"
SURFACE_2 = "#141b30"
BORDER = "#232c48"
TEXT = "#e9edf7"
TEXT_DIM = "#8a93ab"
CYAN = "#22d3ee"
PURPLE = "#8b7bff"
GREEN = "#1fd67a"
RED = "#f5455c"
GOLD = "#f2b84b"

def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()

LOGO_B64 = _b64(LOGO_PATH) if LOGO_PATH.exists() else ""

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {{
    font-family: 'JetBrains Mono', monospace;
}}
.stApp {{
    background:
        radial-gradient(ellipse 1200px 600px at 15% -10%, rgba(139,123,255,0.10), transparent 60%),
        radial-gradient(ellipse 1000px 500px at 90% 0%, rgba(34,211,238,0.08), transparent 55%),
        {BG};
}}
#MainMenu, footer, header {{visibility: hidden;}}
.block-container {{ padding-top: 1.2rem; max-width: 1400px; }}

/* ---- Header band ---- */
.hvts-header {{
    display: flex; align-items: center; gap: 18px;
    padding: 18px 26px; margin-bottom: 18px;
    background: linear-gradient(135deg, {SURFACE} 0%, {SURFACE_2} 100%);
    border: 1px solid {BORDER}; border-radius: 14px;
    box-shadow: 0 0 0 1px rgba(34,211,238,0.03), 0 8px 30px rgba(0,0,0,0.35);
    position: relative; overflow: hidden;
}}
.hvts-header::after {{
    content:""; position:absolute; top:0; right:0; width:280px; height:100%;
    background: radial-gradient(circle at 100% 0%, rgba(139,123,255,0.16), transparent 65%);
    pointer-events:none;
}}
.hvts-logo {{
    width: 56px; height: 56px; border-radius: 12px;
    box-shadow: 0 0 24px rgba(34,211,238,0.35);
    flex-shrink: 0;
}}
.hvts-title-wrap {{ display:flex; flex-direction:column; gap:2px; }}
.hvts-title {{
    font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 26px;
    letter-spacing: 0.5px; margin:0; line-height:1.1;
    background: linear-gradient(90deg, #ffffff 10%, {CYAN} 55%, {PURPLE} 100%);
    -webkit-background-clip: text; background-clip: text; color: transparent;
}}
.hvts-subtitle {{ font-size: 12.5px; color: {TEXT_DIM}; letter-spacing: 0.4px; margin:0;}}
.hvts-live-pill {{
    margin-left: auto; display:flex; align-items:center; gap:8px;
    background: rgba(31,214,122,0.09); border: 1px solid rgba(31,214,122,0.35);
    color: {GREEN}; padding: 7px 14px; border-radius: 999px; font-size: 12px; font-weight:600;
    white-space: nowrap;
}}
.hvts-dot {{ width:8px; height:8px; border-radius:50%; background:{GREEN};
    box-shadow: 0 0 8px {GREEN}; animation: pulse 1.6s ease-in-out infinite; }}
@media (prefers-reduced-motion: reduce) {{ .hvts-dot {{ animation: none; }} }}
@keyframes pulse {{ 0%,100% {{ opacity:1; transform:scale(1);}} 50% {{opacity:.45; transform:scale(0.75);}} }}

/* ---- KPI cards ---- */
.kpi-row {{ display:flex; gap:14px; margin-bottom: 20px; flex-wrap:wrap; }}
.kpi-card {{
    flex:1; min-width:150px; background:{SURFACE}; border:1px solid {BORDER};
    border-radius: 12px; padding: 14px 16px; position:relative;
}}
.kpi-label {{ font-size: 10.5px; color:{TEXT_DIM}; text-transform:uppercase; letter-spacing:1px; margin-bottom:6px;}}
.kpi-value {{ font-family:'Space Grotesk', sans-serif; font-size: 26px; font-weight:700; color:{TEXT}; line-height:1;}}
.kpi-accent-top {{ position:absolute; top:0; left:14px; right:14px; height:2px; border-radius:2px; }}

/* ---- Section labels ---- */
.hvts-section-title {{
    font-family:'Space Grotesk', sans-serif; font-weight:700; font-size:15px;
    color:{TEXT}; margin: 6px 0 10px 2px; letter-spacing:0.3px;
    display:flex; align-items:center; gap:8px;
}}
.hvts-section-title .bar {{ width:4px; height:16px; background:linear-gradient(180deg,{CYAN},{PURPLE}); border-radius:2px; }}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{ gap: 4px; }}
.stTabs [data-baseweb="tab"] {{
    background: {SURFACE}; border:1px solid {BORDER}; border-radius: 10px 10px 0 0;
    padding: 8px 18px; color:{TEXT_DIM}; font-size: 13px; font-weight:600;
}}
.stTabs [aria-selected="true"] {{ color:{CYAN} !important; border-bottom: 2px solid {CYAN}; }}

/* Sidebar */
section[data-testid="stSidebar"] {{ background: {SURFACE}; border-right: 1px solid {BORDER}; }}

/* Dataframe */
[data-testid="stDataFrame"] {{ border:1px solid {BORDER}; border-radius: 10px; overflow:hidden; }}

.hvts-caption {{ color:{TEXT_DIM}; font-size:11.5px; margin-top: 2px; }}
</style>
""", unsafe_allow_html=True)

# ============================================================================
# SIDEBAR CONTROLS
# ============================================================================
with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=64)
    st.markdown("### HVTS.AI Studio")
    st.caption("Binance Futures · Signal Control Room")
    st.markdown("---")

    st.markdown("**Universe**")
    universe_mode = st.radio(
        "Symbol source", ["Top by 24h Volume", "Custom Watchlist"],
        label_visibility="collapsed",
    )
    if universe_mode == "Top by 24h Volume":
        top_n = st.slider("Number of symbols", 10, 80, 30, step=5)
        custom_symbols = None
    else:
        default_watchlist = "BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, XRP/USDT, DOGE/USDT"
        raw = st.text_area("Symbols (comma-separated)", value=default_watchlist, height=80)
        custom_symbols = [s.strip().upper() for s in raw.split(",") if s.strip()]
        top_n = None

    min_volume = st.number_input(
        "Min 24h volume (USDT)", min_value=0, value=1_000_000, step=100_000, format="%d"
    )

    st.markdown("---")
    st.markdown("**Refresh**")
    auto_refresh = st.toggle("Auto-refresh", value=True)
    refresh_secs = st.select_slider(
        "Interval", options=[30, 60, 90, 120, 180, 300], value=60,
        disabled=not auto_refresh,
    )
    force_refresh = st.button("🔄 Refresh now", use_container_width=True)

    st.markdown("---")
    st.markdown("**Trading style weighting**")
    style_focus = st.select_slider(
        "Emphasis", options=["Day", "Balanced", "Position"], value="Balanced",
        help="Tilts the composite HVTS Score toward faster or slower timeframes.",
    )

if auto_refresh and HAS_AUTOREFRESH:
    st_autorefresh(interval=refresh_secs * 1000, key="hvts_autorefresh")

if force_refresh:
    fetch_all_tickers.clear()
    st.cache_data.clear()

# ============================================================================
# HEADER
# ============================================================================
now = datetime.now()
next_refresh = now + timedelta(seconds=refresh_secs if auto_refresh else 0)

logo_html = f'<img class="hvts-logo" src="data:image/png;base64,{LOGO_B64}"/>' if LOGO_B64 else ""
header_html = (
'<div class="hvts-header">'
f'{logo_html}'
'<div class="hvts-title-wrap">'
'<p class="hvts-title">HVTS.AI STUDIO</p>'
'<p class="hvts-subtitle">BINANCE FUTURES · MULTI-TIMEFRAME SIGNAL INTELLIGENCE FOR DAY · SWING · POSITION TRADING</p>'
'</div>'
f'<div class="hvts-live-pill"><span class="hvts-dot"></span>LIVE · {now.strftime("%H:%M:%S")}</div>'
'</div>'
)
st.markdown(header_html, unsafe_allow_html=True)

# ============================================================================
# DATA PIPELINE
# ============================================================================
@st.cache_data(ttl=280, show_spinner=False)
def build_master_table(symbols: tuple, min_volume: float) -> pd.DataFrame:
    tickers = fetch_all_tickers()
    if not tickers:
        return pd.DataFrame()

    ticker_lookup = {}
    for raw_sym, data in tickers.items():
        norm = raw_sym[:-5] if raw_sym.endswith(":USDT") else raw_sym
        ticker_lookup[norm] = data

    bundles = fetch_bundles_threaded(list(symbols))

    rows = []
    for sym in symbols:
        tdata = ticker_lookup.get(sym, {})
        price = tdata.get("last") or tdata.get("mark") or 0
        volume = tdata.get("quoteVolume", 0) or 0
        if not price or volume < min_volume:
            continue

        frames = bundles.get(sym, {})
        f15, f30, f1h, f4h, f1d, f1w = (
            frames.get("15m"), frames.get("30m"), frames.get("1h"),
            frames.get("4h"), frames.get("1d"), frames.get("1w"),
        )
        if f1d is None or f1h is None:
            continue

        ath = float(f1d["high"].max()) if f1d is not None and len(f1d) else price
        zone, discount = pivot_zone(price, ath)

        gmma_1h, _ = gmma_signal(f1h)
        gmma_4h, _ = gmma_signal(f4h)
        gmma_1d, _ = gmma_signal(f1d)
        gmma_1w, _ = gmma_signal(f1w)

        day_o = composite_oracle(f15, f30, fib_lb_fast=20, fib_lb_slow=12, poly_lb_fast=40, poly_lb_slow=24) if f15 is not None and f30 is not None else None
        swing_o = composite_oracle(f1h, f4h, fib_lb_fast=24, fib_lb_slow=20, poly_lb_fast=40, poly_lb_slow=30) if f1h is not None and f4h is not None else None
        pos_o = composite_oracle(f1d, f1w, fib_lb_fast=30, fib_lb_slow=20, poly_lb_fast=40, poly_lb_slow=24) if f1d is not None and f1w is not None else None

        # --- Advanced indicators (H4) ---
        macd_h4 = macd(f4h) if f4h is not None else "neutral"
        williams_h4 = williams_r(f4h) if f4h is not None else "neutral"
        crt_h4 = crt(f4h) if f4h is not None else "neutral"
        smc_h4 = smc(f4h) if f4h is not None else "neutral"
        vwap_h4 = vwap(f4h) if f4h is not None else "neutral"
        rvol_h4 = rvol(f4h) if f4h is not None else 1.0

        def sc(o):
            return o.net_score if o else 0.0

        def sig(o):
            return o.signal if o else "NEUTRAL"

        def conf(o):
            return o.confidence if o else 0.0

        rows.append({
            "Symbol": sym,
            "Price": price,
            "Volume": volume,
            "ATH": ath,
            "Zone": zone,
            "Discount%": discount,
            "GMMA_1H": gmma_1h, "GMMA_4H": gmma_4h, "GMMA_1D": gmma_1d, "GMMA_1W": gmma_1w,
            "Day_Signal": sig(day_o), "Day_Score": sc(day_o), "Day_Conf": conf(day_o),
            "Swing_Signal": sig(swing_o), "Swing_Score": sc(swing_o), "Swing_Conf": conf(swing_o),
            "Position_Signal": sig(pos_o), "Position_Score": sc(pos_o), "Position_Conf": conf(pos_o),
            # Advanced indicators
            "MACD_H4": macd_h4,
            "WilliamsR_H4": williams_h4,
            "CRT_H4": crt_h4,
            "SMC_H4": smc_h4,
            "VWAP_H4": vwap_h4,
            "RVOL_H4": rvol_h4,
        })

    df = pd.DataFrame(rows)
    return df


def composite_hvts_score(row, style_focus: str) -> float:
    weights = {
        "Day": (0.55, 0.30, 0.15),
        "Balanced": (0.33, 0.34, 0.33),
        "Position": (0.15, 0.30, 0.55),
    }[style_focus]
    return (
        weights[0] * row["Day_Score"]
        + weights[1] * row["Swing_Score"]
        + weights[2] * row["Position_Score"]
    )


def action_call(row) -> str:
    deep_zone = row["Zone"] in ("Accumulation Zone", "Extreme Discount")
    rich_zone = row["Zone"] == "Above Buy Zone"
    hvts = row["HVTS_Score"]
    if hvts >= 0.5 and deep_zone:
        return "🟢 High-Conviction Long"
    if hvts >= 0.5 and rich_zone:
        return "🟡 Bullish, but extended"
    if hvts >= 0.25:
        return "🟢 Constructive"
    if hvts <= -0.5:
        return "🔴 Avoid / Short bias"
    if hvts <= -0.25:
        return "🟠 Weakening"
    return "⚪ Stand aside"


with st.spinner("Scanning Binance Futures market..."):
    tickers_preview = fetch_all_tickers()
    if universe_mode == "Top by 24h Volume":
        symbols = get_top_symbols_by_volume(tickers_preview, min_volume, top_n) if tickers_preview else []
    else:
        symbols = custom_symbols or []

    df = build_master_table(tuple(symbols), float(min_volume)) if symbols else pd.DataFrame()

if df.empty:
    st.warning(
        "No symbols matched your filters yet, or the market data feed is still warming up. "
        "Try lowering the minimum volume, choosing more symbols, or clicking **Refresh now**."
    )
    st.stop()

df["HVTS_Score"] = df.apply(lambda r: composite_hvts_score(r, style_focus), axis=1)
df["Action"] = df.apply(action_call, axis=1)
df = df.sort_values("HVTS_Score", ascending=False).reset_index(drop=True)

# ============================================================================
# KPI STRIP
# ============================================================================
total_syms = len(df)
strong_bull = int((df["HVTS_Score"] >= 0.5).sum())
strong_bear = int((df["HVTS_Score"] <= -0.5).sum())
deep_value = int(df["Zone"].isin(["Accumulation Zone", "Extreme Discount"]).sum())
avg_conf = df[["Day_Conf", "Swing_Conf", "Position_Conf"]].mean().mean()

kpis = [
    ("Symbols Scanned", f"{total_syms}", CYAN),
    ("Strong Bullish", f"{strong_bull}", GREEN),
    ("Strong Bearish", f"{strong_bear}", RED),
    ("Deep-Value Zone", f"{deep_value}", GOLD),
    ("Avg Confidence", f"{avg_conf:.0f}%", PURPLE),
]
cards_html = '<div class="kpi-row">'
for label, value, color in kpis:
    cards_html += (
        '<div class="kpi-card">'
        f'<div class="kpi-accent-top" style="background:{color};"></div>'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        '</div>'
    )
cards_html += "</div>"
st.markdown(cards_html, unsafe_allow_html=True)

st.markdown(
    f'<p class="hvts-caption">Last scan {now.strftime("%Y-%m-%d %H:%M:%S")}'
    + (f" · next auto-refresh ~{next_refresh.strftime('%H:%M:%S')}" if auto_refresh else " · auto-refresh paused")
    + f" · universe: {universe_mode} · style emphasis: {style_focus}</p>",
    unsafe_allow_html=True,
)

# ============================================================================
# STYLING HELPERS FOR TABLES
# ============================================================================
def style_signal_col(val):
    color = SIGNAL_COLORS.get(val, TEXT_DIM)
    return f"color:{color}; font-weight:700;"

def style_gmma_col(val):
    if val == "bullish":
        return f"color:{GREEN}; font-weight:600;"
    if val == "bearish":
        return f"color:{RED}; font-weight:600;"
    return f"color:{TEXT_DIM};"

def style_zone_col(val):
    color = ZONE_COLORS.get(val, TEXT_DIM)
    return f"color:{color}; font-weight:600;"

def style_action_col(val):
    if "Long" in val or "Constructive" in val:
        return f"color:{GREEN}; font-weight:700;"
    if "Avoid" in val or "Weakening" in val:
        return f"color:{RED}; font-weight:700;"
    if "extended" in val:
        return f"color:{GOLD}; font-weight:700;"
    return f"color:{TEXT_DIM};"

def style_advanced_signal_col(val):
    """Style for advanced indicator signals (MACD, Williams, CRT, SMC, VWAP)."""
    if val in ["bullish", "oversold_bullish"]:
        return f"color:{GREEN}; font-weight:600;"
    elif val in ["bearish", "overbought_bearish"]:
        return f"color:{RED}; font-weight:600;"
    return f"color:{TEXT_DIM};"

def style_rvol_col(val):
    if val >= 1.5:
        return f"color:{GREEN}; font-weight:600;"
    elif val >= 1.2:
        return f"color:{GOLD}; font-weight:500;"
    else:
        return f"color:{TEXT_DIM};"

def base_table_style(styler):
    return (
        styler
        .format({
            "Price": "${:,.4f}", "Volume": "${:,.0f}", "ATH": "${:,.4f}",
            "Discount%": "{:.1f}%",
            "Day_Conf": "{:.0f}%", "Swing_Conf": "{:.0f}%", "Position_Conf": "{:.0f}%",
            "HVTS_Score": "{:+.2f}",
            "RVOL": "{:.2f}x",
        })
        .set_properties(**{"background-color": SURFACE, "color": TEXT, "border-color": BORDER})
        .set_table_styles([
            {"selector": "th", "props": [("background-color", SURFACE_2), ("color", TEXT_DIM),
                                          ("font-size", "11px"), ("text-transform", "uppercase")]}
        ])
    )

# ============================================================================
# TABS
# ============================================================================
tab_day, tab_swing, tab_pos, tab_matrix, tab_deep, tab_advanced = st.tabs(
    ["🔥 Day Trading", "📈 Swing Trading", "🧭 Position Trading", "🗂 Full Matrix", "🔍 Symbol Deep Dive", "📊 Advanced Signals"]
)

with tab_day:
    st.markdown('<div class="hvts-section-title"><span class="bar"></span>Day Trading — M15/M30 Oracle, confirmed by H1 GMMA</div>', unsafe_allow_html=True)
    day_df = df.sort_values("Day_Score", ascending=False)[
        ["Symbol", "Price", "Volume", "Day_Signal", "Day_Conf", "GMMA_1H", "Zone", "Action"]
    ].rename(columns={"Day_Signal": "Signal", "Day_Conf": "Confidence"})
    styler = base_table_style(day_df.style).format({"Confidence": "{:.0f}%"}).map(style_signal_col, subset=["Signal"]) \
        .map(style_gmma_col, subset=["GMMA_1H"]).map(style_zone_col, subset=["Zone"]).map(style_action_col, subset=["Action"])
    st.dataframe(styler, use_container_width=True, height=560, hide_index=True)

with tab_swing:
    st.markdown('<div class="hvts-section-title"><span class="bar"></span>Swing Trading — H1/H4 Oracle, confirmed by H4 & Daily GMMA</div>', unsafe_allow_html=True)
    swing_df = df.sort_values("Swing_Score", ascending=False)[
        ["Symbol", "Price", "Volume", "Swing_Signal", "Swing_Conf", "GMMA_4H", "GMMA_1D", "Zone", "Action"]
    ].rename(columns={"Swing_Signal": "Signal", "Swing_Conf": "Confidence"})
    styler = base_table_style(swing_df.style).format({"Confidence": "{:.0f}%"}).map(style_signal_col, subset=["Signal"]) \
        .map(style_gmma_col, subset=["GMMA_4H", "GMMA_1D"]).map(style_zone_col, subset=["Zone"]).map(style_action_col, subset=["Action"])
    st.dataframe(styler, use_container_width=True, height=560, hide_index=True)

with tab_pos:
    st.markdown('<div class="hvts-section-title"><span class="bar"></span>Position Trading — Daily/Weekly Oracle, ATH Discount Zone gating</div>', unsafe_allow_html=True)
    pos_df = df.sort_values("Position_Score", ascending=False)[
        ["Symbol", "Price", "Volume", "Position_Signal", "Position_Conf", "GMMA_1D", "GMMA_1W", "Zone", "Discount%", "Action"]
    ].rename(columns={"Position_Signal": "Signal", "Position_Conf": "Confidence"})
    styler = base_table_style(pos_df.style).format({"Confidence": "{:.0f}%"}).map(style_signal_col, subset=["Signal"]) \
        .map(style_gmma_col, subset=["GMMA_1D", "GMMA_1W"]).map(style_zone_col, subset=["Zone"]).map(style_action_col, subset=["Action"])
    st.dataframe(styler, use_container_width=True, height=560, hide_index=True)

with tab_matrix:
    st.markdown('<div class="hvts-section-title"><span class="bar"></span>Full Signal Matrix — every timeframe, ranked by HVTS Composite Score</div>', unsafe_allow_html=True)
    matrix_df = df[[
        "Symbol", "Price", "Volume", "Zone", "GMMA_1H", "GMMA_4H", "GMMA_1D", "GMMA_1W",
        "Day_Signal", "Swing_Signal", "Position_Signal", "HVTS_Score", "Action",
    ]].rename(columns={"Day_Signal": "Day", "Swing_Signal": "Swing", "Position_Signal": "Position"})
    styler = base_table_style(matrix_df.style) \
        .map(style_signal_col, subset=["Day", "Swing", "Position"]) \
        .map(style_gmma_col, subset=["GMMA_1H", "GMMA_4H", "GMMA_1D", "GMMA_1W"]) \
        .map(style_zone_col, subset=["Zone"]).map(style_action_col, subset=["Action"]) \
        .background_gradient(subset=["HVTS_Score"], cmap="RdYlGn", vmin=-1, vmax=1)
    st.dataframe(styler, use_container_width=True, height=620, hide_index=True)
    st.download_button(
        "⬇️ Export Full Matrix (CSV)",
        data=df.to_csv(index=False).encode(),
        file_name=f"hvts_ai_studio_matrix_{now.strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )

with tab_deep:
    st.markdown('<div class="hvts-section-title"><span class="bar"></span>Symbol Deep Dive</div>', unsafe_allow_html=True)
    sel_symbol = st.selectbox("Select symbol", df["Symbol"].tolist())
    row = df[df["Symbol"] == sel_symbol].iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Price", f"${row['Price']:,.4f}")
    c2.metric("24h Volume", f"${row['Volume']:,.0f}")
    c3.metric("Zone", row["Zone"])
    c4.metric("HVTS Score", f"{row['HVTS_Score']:+.2f}", delta=row["Action"])

    gcol1, gcol2, gcol3 = st.columns(3)
    for gcol, label, sig_col, conf_col in [
        (gcol1, "Day Trading", "Day_Signal", "Day_Conf"),
        (gcol2, "Swing Trading", "Swing_Signal", "Swing_Conf"),
        (gcol3, "Position Trading", "Position_Signal", "Position_Conf"),
    ]:
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=row[conf_col],
            number={"suffix": "%", "font": {"color": TEXT, "size": 26}},
            title={"text": f"{label}<br><span style='font-size:13px;color:{SIGNAL_COLORS.get(row[sig_col], TEXT_DIM)}'>{row[sig_col]}</span>", "font": {"color": TEXT_DIM, "size": 13}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": TEXT_DIM},
                "bar": {"color": SIGNAL_COLORS.get(row[sig_col], CYAN)},
                "bgcolor": SURFACE, "borderwidth": 0,
                "steps": [
                    {"range": [0, 30], "color": SURFACE_2},
                    {"range": [30, 60], "color": "#1a2138"},
                    {"range": [60, 100], "color": "#20283f"},
                ],
            },
        ))
        fig.update_layout(height=220, margin=dict(l=20, r=20, t=60, b=10),
                           paper_bgcolor="rgba(0,0,0,0)", font_color=TEXT)
        gcol.plotly_chart(fig, use_container_width=True)

    # Advanced indicators summary
    st.markdown("#### Advanced Indicators (H4)")
    adv_cols = st.columns(6)
    adv_cols[0].metric("MACD", row["MACD_H4"].upper())
    adv_cols[1].metric("Williams %R", row["WilliamsR_H4"].replace("_", " ").title())
    adv_cols[2].metric("CRT", row["CRT_H4"].upper())
    adv_cols[3].metric("SMC", row["SMC_H4"].upper())
    adv_cols[4].metric("VWAP", row["VWAP_H4"].upper())
    adv_cols[5].metric("RVOL", f"{row['RVOL_H4']:.2f}x")

    # Candlestick with GMMA + ATH zone bands
    from data_feed import fetch_ohlcv
    chart_tf = st.select_slider("Chart timeframe", options=["15m", "1h", "4h", "1d"], value="4h")
    cdf = fetch_ohlcv(sel_symbol, chart_tf, 300)
    if cdf is not None:
        fig2 = go.Figure(data=[go.Candlestick(
            x=cdf.index, open=cdf["open"], high=cdf["high"], low=cdf["low"], close=cdf["close"],
            increasing_line_color=GREEN, decreasing_line_color=RED, name=sel_symbol,
        )])
        for p, c in [(20, CYAN), (60, PURPLE)]:
            fig2.add_trace(go.Scatter(
                x=cdf.index, y=cdf["close"].ewm(span=p, adjust=False).mean(),
                line=dict(color=c, width=1.4), name=f"EMA{p}",
            ))
        ath_val = row["ATH"]
        for frac, zname in [(0.75, "Accumulation"), (0.90, "Extreme")]:
            fig2.add_hline(y=ath_val * (1 - frac), line_dash="dot",
                            line_color=TEXT_DIM, opacity=0.5,
                            annotation_text=zname, annotation_font_color=TEXT_DIM)
        fig2.update_layout(
            height=480, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=SURFACE,
            font_color=TEXT, xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", y=1.05),
            margin=dict(l=10, r=10, t=30, b=10),
        )
        fig2.update_xaxes(gridcolor=BORDER)
        fig2.update_yaxes(gridcolor=BORDER)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Chart data unavailable for this symbol/timeframe right now.")

with tab_advanced:
    st.markdown('<div class="hvts-section-title"><span class="bar"></span>Advanced H4 Indicators — MACD, Williams %R, CRT, SMC, VWAP & RVOL</div>', unsafe_allow_html=True)
    adv_df = df[[
        "Symbol", "Price", "Volume", "Zone",
        "MACD_H4", "WilliamsR_H4", "CRT_H4", "SMC_H4", "VWAP_H4", "RVOL_H4",
        "Action"
    ]].rename(columns={
        "MACD_H4": "MACD",
        "WilliamsR_H4": "Williams %R",
        "CRT_H4": "CRT",
        "SMC_H4": "SMC",
        "VWAP_H4": "VWAP",
        "RVOL_H4": "RVOL"
    })
    styler = base_table_style(adv_df.style) \
        .map(style_advanced_signal_col, subset=["MACD", "Williams %R", "CRT", "SMC", "VWAP"]) \
        .map(style_rvol_col, subset=["RVOL"]) \
        .map(style_zone_col, subset=["Zone"]) \
        .map(style_action_col, subset=["Action"])
    st.dataframe(styler, use_container_width=True, height=560, hide_index=True)

st.markdown(
    f'<p class="hvts-caption" style="text-align:center; margin-top:24px;">'
    f"HVTS.AI Studio · Public Binance Futures market data only, no API keys required · "
    f"Signals are analytical output, not financial advice.</p>",
    unsafe_allow_html=True,
)