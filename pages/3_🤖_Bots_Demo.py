# pages/3_🤖_Bots_Demo.py
from __future__ import annotations

import time
from datetime import datetime

import plotly.graph_objects as go
import streamlit as st
from streamlit.components.v1 import html

from utils import (
    ensure_state,
    current_price,
    simulate_next_price,
    fetch_btc_spot_multi,
    push_price,
    process_fills,
    update_equity,
    build_grid,
    force_cross,
)

st.set_page_config(page_title="Bot-Demo", page_icon="🤖", layout="wide")
ensure_state(st.session_state)

# --- Scroll stabilisieren (kein Hochspringen bei Rerun)
html(
    """
<script>
(function(){
  const KEY='ct_bot_scrollY';
  const y=sessionStorage.getItem(KEY);
  if(y){window.scrollTo(0, parseFloat(y));}
  let t;
  window.addEventListener('scroll', ()=>{
    clearTimeout(t);
    t=setTimeout(()=>sessionStorage.setItem(KEY, window.scrollY), 90);
  });
})();
</script>
""",
    height=0,
)

st.markdown("## 🤖 Bot-Demo (ohne API)")

# ---------------- Controls ----------------
c1, c2, c3 = st.columns(3)
mode = c1.selectbox("Richtung", ["Neutral", "Long", "Short"], index=0)
st.session_state.bot["mode"] = mode.lower()

margin = c2.number_input("Margin (USDT)", min_value=1000.0, value=100000.0, step=1000.0)
leverage = c3.slider("Leverage", 1, 125, 10)
grids = st.slider("Grids", 4, 60, 12)

r1, r2 = st.columns(2)
rmin = r1.number_input("Range Min", value=117000.0, step=50.0, format="%.2f")
rmax = r2.number_input("Range Max", value=123000.0, step=50.0, format="%.2f")

st.session_state.bot.update(
    {"range_min": rmin, "range_max": rmax, "grids": grids}
)
build_grid(st.session_state.bot)

st.markdown("### Aktionen")

act1, act2, act3, act4, act5, act6 = st.columns(6)
if act1.button("Start", type="primary"):
    st.session_state.bot["running"] = True
if act2.button("Stop"):
    st.session_state.bot["running"] = False
if act3.button("Grid ⬆"):
    st.session_state.bot["grids"] = min(60, st.session_state.bot["grids"] + 1)
    build_grid(st.session_state.bot)
if act4.button("Grid ⬇"):
    st.session_state.bot["grids"] = max(4, st.session_state.bot["grids"] - 1)
    build_grid(st.session_state.bot)
if act5.button("Rebuild Grid"):
    build_grid(st.session_state.bot)
if act6.button("⚡ Force Cross (Demo-PnL)", use_container_width=True):
    force_cross(st.session_state)

# Run/Auto-Update
b1, b2, b3, b4 = st.columns([1, 1, 2, 2])
use_live = b1.toggle("Echter BTC-Preis", value=True)
auto_soft = b2.toggle("Auto-Tick (soft)", value=True)
tick_speed = st.slider("Refresh (ms)", 1200, 5000, 2500, step=100)

# Statuszeile
status = "RUNNING" if st.session_state.bot.get("running") else "STOPPED"
st.success(f"Status: {status}") if status == "RUNNING" else st.warning(f"Status: {status}")

# ---------------- Tick / Preisversorgung ----------------
loops = 20 if auto_soft else 1   # weicher Autoloop ohne Scrollsprung
for _ in range(loops):
    if use_live:
        px, src = fetch_btc_spot_multi()
        if px is not None:
            push_price(st.session_state, px)
            st.session_state.last_live_src = src
        else:
            simulate_next_price(st.session_state)
    else:
        simulate_next_price(st.session_state)

    if st.session_state.bot.get("running"):
        process_fills(st.session_state, current_price(st.session_state))

    if loops > 1:
        time.sleep(tick_speed / 1000.0)

# ---------------- KPIs ----------------
p = current_price(st.session_state)
equity, realized, unrealized = update_equity(st.session_state)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Preis", f"{p:,.2f}")
k2.metric("Equity (USDT)", f"{equity:,.2f}")
k3.metric("Realized PnL", f"{realized:,.2f}")
k4.metric("Unrealized PnL", f"{unrealized:,.2f}")

st.caption(f"Live-Quelle: {st.session_state.get('last_live_src','bitstamp')}")

# ---------------- Chart mit Grid-Linien ----------------
def grid_figure():
    df = st.session_state.price_series.tail(220)
    fig = go.Figure()

    # Preis
    fig.add_trace(
        go.Scatter(
            x=df["ts"], y=df["price"], mode="lines", name="Preis", line=dict(width=2)
        )
    )

    # Long-Grids (grün)
    for lv in st.session_state.bot["grid"]["long"]:
        fig.add_hline(y=lv, line=dict(color="#00e676", width=1.5))

    # Short-Grids (rot, dotted)
    for lv in st.session_state.bot["grid"]["short"]:
        fig.add_hline(y=lv, line=dict(color="#ff5252", width=1.5, dash="dot"))

    # Mid (gelb)
    mid = (st.session_state.bot["range_min"] + st.session_state.bot["range_max"]) / 2
    fig.add_hline(y=mid, line=dict(color="#ffde59", width=2))

    fig.update_layout(height=420, margin=dict(l=8, r=8, t=4, b=4), legend=dict(orientation="h"))
    return fig

st.plotly_chart(grid_figure(), use_container_width=True)

# ---------------- Orders / Logs ----------------
tabs = st.tabs(["📈 Chart", "📋 Orders", "✅ Fills / Logs"])

with tabs[1]:
    st.dataframe(
        pd.DataFrame(st.session_state.orders).tail(100),
        use_container_width=True,
        height=260,
    )

with tabs[2]:
    st.dataframe(
        pd.DataFrame(st.session_state.fills).tail(100),
        use_container_width=True,
        height=300,
    )