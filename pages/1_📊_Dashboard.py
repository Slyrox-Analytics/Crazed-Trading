# pages/1_Dashboard.py
# Build v23 – große/flexible TradingView-Einbettung, Autorefresh (optional)

import time
import streamlit as st
import plotly.graph_objects as go
from streamlit.components.v1 import html

# --- erwartete utils ---
try:
    from utils import (
        ensure_state, current_price, fetch_btc_spot_multi,
        push_price, update_equity
    )
except Exception as e:
    st.error(
        "Konnte aus utils nicht alles importieren. Erwartet: "
        "ensure_state, current_price, fetch_btc_spot_multi, push_price, update_equity\n\n"
        f"Fehler: {e}"
    )
    st.stop()

# Autorefresh ist optional (falls Paket installiert)
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
ensure_state(st.session_state)

BUILD_TAG = "v23"

st.markdown(f"### Dashboard — Build: `{BUILD_TAG}`")
st.caption("Aktueller Kurs & PnL-Übersicht. Echtpreis (mehrere Quellen) + TradingView-Chart.")

# --- Steuerung oben ---
c1, c2 = st.columns(2)
use_live = c1.toggle("Echter BTC-Preis", value=True)
auto     = c2.toggle("Auto-Refresh", value=True)
ms       = st.slider("Refresh (ms)", 1200, 5000, 2000, step=100)

# Optionaler Autorefresh über Paket, falls vorhanden
if auto and st_autorefresh is not None:
    st_autorefresh(interval=ms, key="dash_autorefresh_v23")

# --- Preis-Update (einmal pro Run) ---
if use_live:
    px, src = fetch_btc_spot_multi()
    if px is not None:
        push_price(st.session_state, px)
        st.session_state.last_live_src = src

# Equity/PnL berechnen + aktuellem Preis
equity, realized, unrealized = update_equity(st.session_state)
price = current_price(st.session_state)

# --- obere Metriken + Sparkline ---
c_left, c_r1, c_r2 = st.columns([2, 1, 1])
with c_left:
    st.info(f"🔌 Live-Quelle: **{st.session_state.get('last_live_src', '…')}**")
    y = st.session_state.price_series.tail(200)["price"]
    fig = go.Figure(go.Scatter(y=y, mode="lines"))
    fig.update_layout(height=220, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
with c_r1:
    st.metric("Realized PnL", f"{realized:,.2f}")
with c_r2:
    st.metric("Unrealized PnL", f"{unrealized:,.2f}")

# --- TradingView-Chart ---
st.markdown("### TradingView-Chart (Beta)")

tv_on = st.toggle("Chart anzeigen", value=True)
cl1, cl2, cl3, cl4 = st.columns([2, 1, 1, 1])
symbol = cl1.text_input("Symbol", value="BINANCE:BTCUSDT")
tf     = cl2.selectbox("Timeframe", ["1","3","5","15","30","60","120","240","D","W"], index=2)
height = cl3.slider("Höhe (px)", 300, 1200, 720, step=20)
fullscreen = cl4.toggle("Fullscreen (75vh)", value=False)

if tv_on:
    height_css = "75vh" if fullscreen else f"{height}px"
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
    html(tv, height=0, scrolling=False)