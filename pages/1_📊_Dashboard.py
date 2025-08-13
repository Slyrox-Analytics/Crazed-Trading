# pages/1_Dashboard.py
from __future__ import annotations
import streamlit as st
from streamlit.components.v1 import html
from streamlit_autorefresh import st_autorefresh

from utils import ensure_state, fetch_btc_spot_multi, push_price, current_price, update_equity

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
ensure_state(st.session_state)

st.markdown("## Dashboard")
st.caption("Aktueller Kurs & PnL-Übersicht. Echtpreis optional (mehrere Quellen).")

# -------------------- Steuerleiste --------------------
colA, colB = st.columns(2)
use_live = colA.toggle("Echter BTC-Preis", value=True)
auto = colB.toggle("Auto-Refresh", value=True)

speed = st.slider("Refresh (ms)", 1200, 5000, 2000, step=100)

# Auto-Refresh auslösen (neu rendert die Seite in dem Intervall)
if auto:
    st_autorefresh(interval=speed, key="dash_autorefresh")

# Live-Preis ziehen (ein Request pro Render)
if use_live:
    px, src = fetch_btc_spot_multi()
    if px is not None:
        push_price(st.session_state, px)
        st.session_state.last_live_src = src

# -------------------- KPIs --------------------
p = current_price(st.session_state)
equity, realized, unrealized = update_equity(st.session_state)

k1, k2, k3 = st.columns(3)
k1.metric("Aktueller Kurs", f"{p:,.2f}")
k2.metric("Realized PnL", f"{realized:,.2f}")
k3.metric("Unrealized PnL", f"{unrealized:,.2f}")
st.caption(f"Live-Quelle: {st.session_state.get('last_live_src', 'bitstamp')}")

st.markdown("### TradingView-Chart (Beta)")
show_tv = st.toggle("Chart anzeigen", value=True)

sym = st.selectbox(
    "Symbol",
    ["BINANCE:BTCUSDT", "BITSTAMP:BTCUSD", "BYBIT:BTCUSDT", "COINBASE:BTCUSD"],
    index=0,
)
tf = st.selectbox("Timeframe", ["1", "3", "5", "15", "30", "60", "240", "D"], index=2)
h = st.slider("Höhe (px)", 300, 1200, 680)

if show_tv:
    html(
        f"""
<div class="tradingview-widget-container">
  <div id="tv_chart"></div>
</div>
<script src="https://s3.tradingview.com/tv.js"></script>
<script>
  new TradingView.widget({{
    "container_id": "tv_chart",
    "autosize": true,
    "symbol": "{sym}",
    "interval": "{tf}",
    "timezone": "Etc/UTC",
    "theme": "dark",
    "style": "1",
    "locale": "de_DE",
    "hide_top_toolbar": false,
    "allow_symbol_change": true,
    "backgroundColor": "transparent"
  }});
</script>
        """,
        height=h,
    )
else:
    st.info("TradingView ist ausgeblendet. Schalte **„Chart anzeigen“** ein, um den Chart zu sehen.")