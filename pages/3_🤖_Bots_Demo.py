# pages/3_Bots_Demo.py
# Bot-Demo: stabiles Scrollen, PnL-Demo (Ticks/Auto-Fill/Force Cross),
# neutrale Aufteilung dynamisch, große Grid-Visualisierung

from __future__ import annotations

import random
import time
from datetime import datetime

import plotly.graph_objects as go
import streamlit as st
from streamlit.components.v1 import html

# -- utils aus deinem Projekt:
from utils import (
    ensure_state,
    BotConfig,
    price_to_grid_levels,
    rebuild_grid_orders,
    simulate_next_price,
    current_price,
    process_fills,
    update_equity,
    fetch_btc_spot_multi,
    push_price,
)

# optionale utils (falls vorhanden)
try:
    from utils import neutral_split_levels  # bevorzugt
except Exception:
    neutral_split_levels = None  # Fallback

try:
    from utils import force_cross_nearest  # Demo-PnL helper
except Exception:
    force_cross_nearest = None

st.set_page_config(page_title="Bot-Demo", page_icon="🤖", layout="wide")
ensure_state(st.session_state)

BUILD = "v23-" + datetime.utcnow().strftime("%Y%m%d-%H%M%S") + "Z"
st.markdown(f"### Bot-Demo · Build `{BUILD}`")
st.caption("Soft-Refresh, stabiles Scrollen, PnL-Demo & Grid-Linien.")

# --- Scroll-Stabilisierung (verhindert 'nach oben springen' bei Rerender)
html(
    """
<script>
(function(){
  const key='ct_scrollY';
  const y=sessionStorage.getItem(key);
  if(y){window.scrollTo(0, parseFloat(y));}
  window.addEventListener('scroll', ()=>sessionStorage.setItem(key, window.scrollY));
})();
</script>
""",
    height=0,
)

# --- Bot-Config Controls
cfg: BotConfig = st.session_state.bot["config"]
c1, c2, c3, c4 = st.columns(4)
cfg.side = c1.selectbox("Richtung", ["Long", "Short", "Neutral"], index=2)
cfg.margin = c2.number_input("Margin (USDT)", 1000.0, step=1000.0, value=100000.0)
cfg.leverage = c3.slider("Leverage", 1, 125, 10)
cfg.grid_count = c4.slider("Grids", 4, 60, 12)

cc5, cc6 = st.columns(2)
cfg.range_min = cc5.number_input("Range Min", value=60000.0, step=10.0, format="%.2f")
cfg.range_max = cc6.number_input("Range Max", value=64000.0, step=10.0, format="%.2f")
cfg.step_shift = st.slider("Grid verschieben (Stepgröße)", 1.0, 1000.0, 50.0, step=1.0)

with st.expander("⚙️ Schnell anpassen"):
    w = st.slider("Breite um Preis (%)", 1, 20, 8)
    if st.button("Center Grid auf Preis", use_container_width=True):
        p = current_price(st.session_state)
        span = p * (w / 100)
        cfg.range_min = round(p - span / 2, 2)
        cfg.range_max = round(p + span / 2, 2)
        rebuild_grid_orders(st.session_state)
        st.success("Grid zentriert.")

# --- Aktionen
r = st.columns([1, 1, 1, 1, 1, 1.2, 1.2, 1.2, 1.4])
if r[0].button("Start", type="primary"):
    st.session_state.bot["running"] = True
    st.session_state["scroll_to_chart"] = True  # einmalig zum Chart springen
    rebuild_grid_orders(st.session_state)

if r[1].button("Stop"):
    st.session_state.bot["running"] = False

if r[2].button("Grid ⬆️"):
    d = cfg.step_shift
    cfg.range_min += d
    cfg.range_max += d
    rebuild_grid_orders(st.session_state)

if r[3].button("Grid ⬇️"):
    d = cfg.step_shift
    cfg.range_min -= d
    cfg.range_max -= d
    rebuild_grid_orders(st.session_state)

if r[4].button("Rebuild Grid"):
    rebuild_grid_orders(st.session_state)

if r[5].button("Tick (1x)"):
    simulate_next_price(st.session_state, 0.0015)
    process_fills(st.session_state, current_price(st.session_state))

if r[6].button("10 Ticks"):
    for _ in range(10):
        simulate_next_price(st.session_state, 0.0020)
        process_fills(st.session_state, current_price(st.session_state))

if r[7].button("100 Ticks"):
    for _ in range(100):
        simulate_next_price(st.session_state, 0.0035)
        process_fills(st.session_state, current_price(st.session_state))

if r[8].button("⚡ Force Cross (Demo-PnL)"):
    if force_cross_nearest is not None:
        force_cross_nearest(
            st.session_state, "down" if cfg.side != "Short" else "up"
        )
        process_fills(st.session_state, current_price(st.session_state))
    else:
        st.warning("force_cross_nearest() fehlt in utils.py – Demo-PnL nicht möglich.")

# --- Laufzeit-Optionen
t0, t1, t2, t3 = st.columns([1, 1, 2, 1])
use_live = t0.toggle("Echter BTC-Preis", value=True)
auto = t1.toggle("Auto-Update (soft)", value=True)
refresh = t2.slider("Refresh (ms)", 1200, 5000, 2500, step=100)
auto_fill = t3.toggle("Auto-Fill (Demo)", value=False)

# Status-Badge
status = "RUNNING" if st.session_state.bot.get("running") else "PAUSED"
badge = "#21c36f" if status == "RUNNING" else "#555"
st.markdown(
    f'<div style="margin-top:-10px;margin-bottom:8px">'
    f'<span style="padding:4px 8px;border-radius:8px;background:{badge};color:white;'
    f'font-weight:600">Status: {status}</span></div>',
    unsafe_allow_html=True,
)

# Soft-Refresh-Schleife
ph = st.empty()
cycles = 1 if not (auto and st.session_state.bot["running"]) else 12

for _ in range(cycles):
    # Preisversorgung
    if use_live:
        px, src = fetch_btc_spot_multi()
        if px is not None:
            push_price(st.session_state, px)
            st.session_state.last_live_src = src
    else:
        simulate_next_price(st.session_state, 0.0015)

    # Demo-AutoFill (schneller PnL zum Testen)
    if st.session_state.bot["running"] and auto_fill and random.random() < 0.15:
        if force_cross_nearest is not None:
            force_cross_nearest(
                st.session_state, "down" if cfg.side != "Short" else "up"
            )

    # Fills verarbeiten wenn Bot läuft
    if st.session_state.bot["running"]:
        process_fills(st.session_state, current_price(st.session_state))

    # KPIs
    price = current_price(st.session_state)
    equity, realized, unrealized = update_equity(st.session_state)

    # Render
    with ph.container():
        st.markdown('<div id="chart-anchor"></div>', unsafe_allow_html=True)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Preis", f"{price:,.2f}")
        m2.metric("Equity (USDT)", f"{equity:,.2f}")
        m3.metric("Realized PnL", f"{realized:,.2f}")
        m4.metric("Unrealized PnL", f"{unrealized:,.2f}")

        # Sparkline (kurzer Verlauf)
        y = st.session_state.price_series.tail(250)["price"]
        spark = go.Figure(go.Scatter(y=y, mode="lines", line=dict(width=2)))
        spark.update_layout(height=110, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(spark, use_container_width=True)
        st.caption(f"Live-Quelle: {st.session_state.get('last_live_src', '…')}")

        # Grid-Linien berechnen
        levels = list(price_to_grid_levels(cfg))
        mid = (cfg.range_min + cfg.range_max) / 2.0

        if cfg.side == "Long":
            long_levels = [float(L) for L in levels if L < mid]
            short_levels = []
        elif cfg.side == "Short":
            long_levels = []
            short_levels = [float(L) for L in levels if L > mid]
        else:
            # Neutral: bevorzugt dynamisch über utils.neutral_split_levels(...)
            if neutral_split_levels is not None:
                buy, sell = neutral_split_levels(cfg, price, static=False)
                long_levels, short_levels = buy, sell
            else:
                # Fallback: 50/50
                half = len(levels) // 2
                long_levels = [float(L) for L in levels[:half]]
                short_levels = [float(L) for L in levels[half:]]

        # Hauptchart mit Grid-Linien
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                y=st.session_state.price_series["price"],
                x=list(range(len(st.session_state.price_series))),
                mode="lines",
                name="Preis",
                line=dict(width=2),
            )
        )
        for L in long_levels:
            fig.add_hline(
                y=L,
                line=dict(color="#00ff88", width=1.8, dash="solid"),
                annotation_text="Lo",
                annotation_position="right",
            )
        for L in short_levels:
            fig.add_hline(
                y=L,
                line=dict(color="#ff4d4d", width=1.8, dash="dot"),
                annotation_text="Sh",
                annotation_position="right",
            )
        fig.add_hline(
            y=price,
            line=dict(color="#ffd700", width=2.8, dash="solid"),
            annotation_text=f"Price {price:.2f}",
            annotation_position="right",
        )
        fig.update_layout(height=520, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

        # Debug: Orders/Fills einsehbar
        with st.expander("🔎 Debug: Orders & Fills"):
            st.write("Open Orders:", st.session_state.bot.get("orders"))
            st.write("Fills:", st.session_state.bot.get("fills"))

        # Nach "Start" einmal zum Chart-Anker springen
        if st.session_state.get("scroll_to_chart"):
            html(
                """
<script>
const el = document.getElementById('chart-anchor');
if (el) { el.scrollIntoView({behavior:'smooth', block:'start'}); }
</script>
""",
                height=0,
            )
            st.session_state["scroll_to_chart"] = False

    if cycles > 1:
        time.sleep(refresh / 1000.0)