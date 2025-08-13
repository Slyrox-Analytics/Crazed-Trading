# pages/1_📊_Dashboard.py
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
)

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
ensure_state(st.session_state)

# ---- Scroll stabil halten (kein Autosprung)
html(
    """
<script>
(function(){
  const KEY='ct_dash_scrollY';
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

st.markdown(f"### 📊 Dashboard  ·  `{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC`")
st.caption("Aktueller Kurs & PnL. Optionaler TradingView-Chart ohne API-Key.")

top1, top2 = st.columns(2)
use_live = top1.toggle("Echter BTC-Preis", value=True)
auto = top2.toggle("Auto-Refresh", value=True)

ref = st.slider("Refresh (ms)", 1200, 5000, 2000, step=100)

# --- TradingView (optional)
st.markdown("#### TradingView-Chart (Beta)")
tv_on = st.toggle("Chart anzeigen", value=True)
if tv_on:
    c1, c2, c3 = st.columns([2, 1, 1])
    symbol = c1.text_input("Symbol", "BINANCE:BTCUSDT")
    tf = c2.selectbox("Timeframe", ["1", "3", "5", "15", "30", "60", "120", "240", "D", "W", "M"], index=2)
    h = c3.slider("Höhe (px)", 300, 1200, 680, step=10)
    full = st.toggle("Fullscreen-Höhe (75vh)", value=False)
    height_css = "75vh" if full else f"{h}px"
    html(
        f"""
<div style="height:{height_css}; margin-bottom:12px;">
  <iframe
    src="https://s.tradingview.com/widgetembed/?symbol={symbol}&interval={tf}&hidesidetoolbar=1&symboledit=1&saveimage=0&hideideas=1&theme=dark"
    style="width:100%; height:100%; border:0; border-radius:8px;"></iframe>
</div>
""",
        height=10,
    )

ph = st.empty()

# sanfter Loop: hält Scroll stabil
loops = 10 if auto else 1
for _ in range(loops):
    # Preis holen/simulieren
    if use_live:
        px, src = fetch_btc_spot_multi()
        if px is not None:
            push_price(st.session_state, px)
            st.session_state.last_live_src = src
    else:
        simulate_next_price(st.session_state, 0.0014)

    # Fills auswerten, wenn Bot läuft
    if st.session_state.bot.get("running", False):
        process_fills(st.session_state, current_price(st.session_state))

    price = current_price(st.session_state)
    equity, realized, unrealized = update_equity(st.session_state)

    with ph.container():
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Preis", f"{price:,.2f}")
        k2.metric("Equity (USDT)", f"{equity:,.2f}")
        k3.metric("Realized PnL", f"{realized:,.2f}")
        k4.metric("Unrealized PnL", f"{unrealized:,.2f}")

        # kleine Verlaufslinie
        y = st.session_state.price_series.tail(200)["price"]
        fig = go.Figure(go.Scatter(y=y, mode="lines", line=dict(width=2)))
        fig.update_layout(height=240, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

        st.caption(f"Live-Quelle: {st.session_state.get('last_live_src','bitstamp')}")

    if loops > 1:
        time.sleep(ref / 1000.0)