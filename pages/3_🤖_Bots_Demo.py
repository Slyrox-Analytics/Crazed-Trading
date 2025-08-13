# pages/3_Bots_Demo.py
from __future__ import annotations

import random, time
from datetime import datetime

import plotly.graph_objects as go
import streamlit as st
from streamlit.components.v1 import html

# ---- aus utils deines Projekts (vorhanden):
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

# ---------------------------------------------
# Seitentitel + State
# ---------------------------------------------
st.set_page_config(page_title="Bot-Demo", page_icon="🤖", layout="wide")
ensure_state(st.session_state)

# kleine Build-Markierung
BUILD = "fix-CT-" + datetime.utcnow().strftime("%Y%m%d-%H%M%S") + "Z"
st.markdown(f"#### 🤖 Bot-Demo  ·  `{BUILD}`")
st.caption("Stabiles Scrollen, PnL-Fix (Demo-Fills) & optionaler TradingView-Chart.")

# ---------------------------------------------
# Scroll-Fix (keine Sprünge bei Rerender)
# ---------------------------------------------
html(
    """
<script>
(function(){
  const KEY='ct_scrollY';
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

# ---------------------------------------------
# UI – Config
# ---------------------------------------------
cfg: BotConfig = st.session_state.bot["config"]

c1,c2,c3,c4 = st.columns(4)
cfg.side     = c1.selectbox("Richtung", ["Long","Short","Neutral"], index=2)
cfg.margin   = c2.number_input("Margin (USDT)", 1000.0, step=1000.0, value=100000.0)
cfg.leverage = c3.slider("Leverage", 1, 125, 10)
cfg.grid_count = c4.slider("Grids", 4, 60, 12)

c5,c6 = st.columns(2)
cfg.range_min = c5.number_input("Range Min", value=60000.0, step=10.0, format="%.2f")
cfg.range_max = c6.number_input("Range Max", value=64000.0, step=10.0, format="%.2f")

cfg.step_shift = st.slider("Grid verschieben (Stepgröße)", 1.0, 1000.0, 50.0, step=1.0)

with st.expander("⚙️ Schnell anpassen / Center"):
    band = st.slider("Breite um Preis (%)", 1, 20, 8)
    if st.button("Center Grid auf aktuellen Preis", use_container_width=True):
        p = current_price(st.session_state)
        span = p*(band/100)
        cfg.range_min = round(p - span/2, 2)
        cfg.range_max = round(p + span/2, 2)
        rebuild_grid_orders(st.session_state)
        st.success("Grid zentriert & neu aufgebaut.")

# ---------------------------------------------
# Helper: erzwinge Fill (Demo-PnL) ohne utils-Änderung
# ---------------------------------------------
def _force_cross(direction: str):
    p  = current_price(st.session_state)
    lv = list(price_to_grid_levels(cfg))
    if not lv:
        rebuild_grid_orders(st.session_state)
        lv = list(price_to_grid_levels(cfg))
        if not lv:
            return

    # nächstgelegte Grid-Linie
    level = min(lv, key=lambda L: abs(L - p))
    eps = max(0.01, (cfg.range_max - cfg.range_min) * 1e-6)

    if direction == "down":
        push_price(st.session_state, level + 2*eps)
        process_fills(st.session_state, current_price(st.session_state))
        push_price(st.session_state, level - 2*eps)
        process_fills(st.session_state, current_price(st.session_state))
    else:
        push_price(st.session_state, level - 2*eps)
        process_fills(st.session_state, current_price(st.session_state))
        push_price(st.session_state, level + 2*eps)
        process_fills(st.session_state, current_price(st.session_state))

# ---------------------------------------------
# Aktionen (oberes Buttonband)
# ---------------------------------------------
b = st.columns([1,1,1,1,1,1.1,1.1,1.1,1.4])
if b[0].button("Start", type="primary"):
    st.session_state.bot["running"] = True
    rebuild_grid_orders(st.session_state)  # garantiert Orders da
    st.session_state["scroll_to_chart"] = True

if b[1].button("Stop"):
    st.session_state.bot["running"] = False

if b[2].button("Grid ⬆️"):
    d = cfg.step_shift
    cfg.range_min += d; cfg.range_max += d
    rebuild_grid_orders(st.session_state)

if b[3].button("Grid ⬇️"):
    d = cfg.step_shift
    cfg.range_min -= d; cfg.range_max -= d
    rebuild_grid_orders(st.session_state)

if b[4].button("Rebuild Grid"):
    rebuild_grid_orders(st.session_state)

if b[5].button("Tick (1x)"):
    simulate_next_price(st.session_state, 0.0018)
    process_fills(st.session_state, current_price(st.session_state))

if b[6].button("10 Ticks"):
    for _ in range(10):
        simulate_next_price(st.session_state, 0.0022)
        process_fills(st.session_state, current_price(st.session_state))

if b[7].button("100 Ticks"):
    for _ in range(100):
        simulate_next_price(st.session_state, 0.0032)
        process_fills(st.session_state, current_price(st.session_state))

# Demo-PnL: erzwungener Cross
if b[8].button("⚡ Force Cross (Demo-PnL)"):
    _force_cross("down" if cfg.side != "Short" else "up")

# ---------------------------------------------
# Laufzeit-Optionen
# ---------------------------------------------
o1,o2,o3,o4 = st.columns([1,1,2,1])
use_live  = o1.toggle("Echter BTC-Preis", value=True)
auto_soft = o2.toggle("Auto-Update (soft)", value=True)
refresh_ms = o3.slider("Refresh (ms)", 1200, 5000, 2500, step=100)
auto_fill = o4.toggle("Auto-Fill (Demo)", value=False)

# TradingView (optional im Bot)
tv_on = st.toggle("TradingView-Chart (Beta)", value=False, help="Optionaler Candles-Chart direkt in der Bot-Seite")
if tv_on:
    tva, tvb = st.columns([2,1])
    sym = tva.text_input("Symbol", "BINANCE:BTCUSDT")
    tf  = tvb.selectbox("Timeframe", ["1","3","5","15","30","60","120","240","D","W","M"], index=2)
    h   = st.slider("Höhe (px)", 300, 1200, 680, step=10)
    full = st.toggle("Fullscreen-Höhe (75vh)", value=False)
    height_css = "75vh" if full else f"{h}px"
    html(
        f"""
<div style="height:{height_css};">
  <iframe
    src="https://s.tradingview.com/widgetembed/?symbol={sym}&interval={tf}&hidesidetoolbar=1&symboledit=1&saveimage=0&hideideas=1&theme=dark"
    style="width:100%; height:100%; border:0;"></iframe>
</div>
""",
        height=10,  # Container baut seine Höhe im div selbst
    )

# ---------------------------------------------
# Soft-Loop (nur Chart & KPIs) – hält Scroll stabil
# ---------------------------------------------
ph = st.empty()

cycles = 1 if not (auto_soft and st.session_state.bot["running"]) else 12
for _ in range(cycles):
    # Preis-Feed
    if use_live:
        px, src = fetch_btc_spot_multi()
        if px is not None:
            push_price(st.session_state, px)
            st.session_state.last_live_src = src
    else:
        simulate_next_price(st.session_state, 0.0016)

    # Demo-AutoFill (damit PnL sicher sichtbar wird)
    if st.session_state.bot["running"] and auto_fill and random.random() < 0.15:
        _force_cross("down" if cfg.side != "Short" else "up")

    # Fills auswerten
    if st.session_state.bot["running"]:
        process_fills(st.session_state, current_price(st.session_state))

    # Fallback: wenn keine Orders vorhanden → neu aufbauen
    if not st.session_state.bot.get("orders"):
        rebuild_grid_orders(st.session_state)

    # KPIs & Render
    price = current_price(st.session_state)
    equity, realized, unrealized = update_equity(st.session_state)

    with ph.container():
        st.markdown('<div id="chart-anchor"></div>', unsafe_allow_html=True)

        k1,k2,k3,k4 = st.columns(4)
        k1.metric("Preis", f"{price:,.2f}")
        k2.metric("Equity (USDT)", f"{equity:,.2f}")
        k3.metric("Realized PnL", f"{realized:,.2f}")
        k4.metric("Unrealized PnL", f"{unrealized:,.2f}")

        # kleine Sparkline
        y = st.session_state.price_series.tail(240)["price"]
        spark = go.Figure(go.Scatter(y=y, mode="lines", line=dict(width=2)))
        spark.update_layout(height=110, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(spark, use_container_width=True)
        st.caption(f"Live-Quelle: {st.session_state.get('last_live_src','...')}")

        # Grid-Chart
        levels = list(price_to_grid_levels(cfg))
        mid = (cfg.range_min + cfg.range_max)/2
        if cfg.side == "Long":
            longs  = [L for L in levels if L < mid]
            shorts = []
        elif cfg.side == "Short":
            longs  = []
            shorts = [L for L in levels if L > mid]
        else:
            # Neutral dynamisch am Preis trennen (nicht 50/50)
            longs  = [L for L in levels if L < price]
            shorts = [L for L in levels if L > price]

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(y=st.session_state.price_series["price"],
                       x=list(range(len(st.session_state.price_series))),
                       mode="lines", name="Preis", line=dict(width=2)))
        for L in longs:
            fig.add_hline(y=float(L), line=dict(color="#00ff88",width=1.8,dash="solid"),
                          annotation_text="Lo", annotation_position="right")
        for L in shorts:
            fig.add_hline(y=float(L), line=dict(color="#ff4d4d",width=1.8,dash="dot"),
                          annotation_text="Sh", annotation_position="right")
        fig.add_hline(y=float(price), line=dict(color="#ffd700",width=2.8),
                      annotation_text=f"Price {price:.2f}", annotation_position="right")
        fig.update_layout(height=540, margin=dict(l=8,r=8,t=24,b=8))
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("🔎 Debug: Orders & Fills"):
            st.write("Open Orders:", st.session_state.bot.get("orders"))
            st.write("Fills:", st.session_state.bot.get("fills"))

        # einmalig nach Start zum Chart springen
        if st.session_state.get("scroll_to_chart"):
            html(
                """
<script>
const el=document.getElementById('chart-anchor');
if(el){ el.scrollIntoView({behavior:'smooth', block:'start'}); }
</script>
""",
                height=0,
            )
            st.session_state["scroll_to_chart"] = False

    if cycles > 1:
        time.sleep(refresh_ms/1000.0)
```0