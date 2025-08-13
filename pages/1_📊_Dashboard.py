# pages/1_Dashboard.py
# Dashboard: großer/flexibler TradingView-Chart + PnL + Live-Preis
# Hinweis: nutzt utils.ensure_state, fetch_btc_spot_multi, push_price, update_equity, current_price

from __future__ import annotations

import time
from datetime import datetime

import plotly.graph_objects as go
import streamlit as st
from streamlit.components.v1 import html

# -- utils-Funktionen aus deinem Projekt:
from utils import (
    ensure_state,
    fetch_btc_spot_multi,
    push_price,
    update_equity,
    current_price,
)

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
ensure_state(st.session_state)

BUILD = "v23-" + datetime.utcnow().strftime("%Y%m%d-%H%M%S") + "Z"
st.markdown(f"### Dashboard · Build `{BUILD}`")
st.caption("Aktueller Kurs & PnL-Übersicht. Echtpreis optional (mehrere Quellen).")

# --- Steuerelemente
c1, c2 = st.columns(2)
use_live = c1.toggle("Echter BTC-Preis", value=True)
auto = c2.toggle("Auto-Refresh", value=True)
ms = st.slider("Refresh (ms)", 1200, 5000, 2000, step=100)

st.markdown("#### TradingView-Chart (Beta)")
tv_on = st.toggle("Chart anzeigen", value=True)
cc1, cc2, cc3, cc4 = st.columns([2, 1, 1, 1])
symbol = cc1.text_input("Symbol", value="BINANCE:BTCUSDT")
tf = cc2.selectbox("Timeframe", ["1", "3", "5", "15", "30", "60", "120", "240", "D", "W"], index=2)
height_px = cc3.slider("Höhe (px)", 300, 1200, 720, step=20)
fullscreen = cc4.toggle("Fullscreen (75vh)", value=False)

# Platzhalter, damit bei Autorefresh die Komponenten in einem Container bleiben
frame = st.empty()

# Wie oft pro Aufruf rendern (soft auto-refresh)
loops = 1 if not auto else 8

for _ in range(loops):
    # Livepreis optional holen
    if use_live:
        px, src = fetch_btc_spot_multi()
        if px is not None:
            push_price(st.session_state, px)
            st.session_state.last_live_src = src

    # PnL/Equity berechnen und aktuellen Preis holen
    equity, realized, unrealized = update_equity(st.session_state)
    p = current_price(st.session_state)

    # Render
    with frame.container():
        m1, m2, m3 = st.columns([2, 1, 1])

        # kleine Sparkline mit Plotly, damit du Preisverlauf siehst
        with m1:
            st.info(f"🔌 Live-Quelle: **{st.session_state.get('last_live_src', '…')}**")
            y = st.session_state.price_series.tail(180)["price"]
            fig = go.Figure(go.Scatter(y=y, mode="lines"))
            fig.update_layout(height=220, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

        with m2:
            st.metric("Realized PnL", f"{realized:,.2f}")
        with m3:
            st.metric("Unrealized PnL", f"{unrealized:,.2f}")

        # TradingView (groß / fullscreen)
        if tv_on:
            height_css = "75vh" if fullscreen else f"{height_px}px"
            tv = f"""
<div class="tradingview-widget-container" style="height:{height_css};">
  <div id="tvchart" style="height:{height_css};"></div>
  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
  <script type="text/javascript">
    new TradingView.widget({{
      "autosize": true,
      "symbol": "{symbol}",
      "interval": "{tf}",
      "timezone": "Etc/UTC",
      "theme": "dark",
      "style": "1",
      "locale": "de_DE",
      "container_id": "tvchart"
    }});
  </script>
</div>
"""
            # height=0, damit die Komponente volle Höhe per CSS bekommt
            html(tv, height=0, scrolling=False)

    if auto:
        time.sleep(ms / 1000.0)