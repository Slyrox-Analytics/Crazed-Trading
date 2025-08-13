# pages/1_Dashboard.py
from __future__ import annotations
import streamlit as st
from streamlit.components.v1 import html
from utils import ensure_state, fetch_btc_spot_multi, push_price, current_price, update_equity

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
ensure_state(st.session_state)

st.markdown("## Dashboard")

live, auto = st.columns(2)
use_live = live.toggle("Echter BTC-Preis", value=True)
auto_refresh = auto.toggle("Auto-Refresh", value=True)
speed = st.slider("Refresh (ms)", 1200, 5000, 2000, step=100)

if auto_refresh:
    px, src = fetch_btc_spot_multi()
    if px is not None:
        push_price(st.session_state, px); st.session_state.last_live_src = src

eq, r, u = update_equity(st.session_state)
c1,c2,c3 = st.columns(3)
c1.metric("Aktueller Kurs", f"{current_price(st.session_state):,.2f}")
c2.metric("Realized PnL", f"{r:,.2f}")
c3.metric("Unrealized PnL", f"{u:,.2f}")
st.caption(f"Live-Quelle: {st.session_state.get('last_live_src','bitstamp')}")

st.markdown("### TradingView-Chart (Beta)")
sym = st.selectbox("Symbol", ["BINANCE:BTCUSDT","BITSTAMP:BTCUSD","BYBIT:BTCUSDT","COINBASE:BTCUSD"], index=0)
tf = st.selectbox("Timeframe", ["1","3","5","15","30","60","240","D"], index=2)
h = st.slider("Höhe (px)", 300, 1200, 680)

html(f"""
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
  "backgroundColor": "transparent",
  "allow_symbol_change": true
 }});
</script>
""", height=h)