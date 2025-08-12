
import streamlit as st
import plotly.graph_objects as go
from streamlit.components.v1 import html
from utils import ensure_state, current_price, fetch_btc_spot_multi, push_price, update_equity

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
ensure_state(st.session_state)

st.markdown("# Dashboard")
st.caption("Aktueller Kurs & PnL-Übersicht. Echtpreis optional (mehrere Quellen).")

c1, c2 = st.columns(2)
use_live = c1.toggle("Echter BTC-Preis", value=True)
auto = c2.toggle("Auto-Refresh", value=True)
ms = st.slider("Refresh (ms)", 1200, 5000, 2000, step=100)

st.markdown("### TradingView-Chart (Beta)")
tv_on = st.toggle("Chart anzeigen", value=True)
cc1, cc2, cc3 = st.columns([2,1,1])
symbol = cc1.text_input("Symbol", value="BINANCE:BTCUSDT")
tf = cc2.selectbox("Timeframe", ["1", "3", "5", "15", "30", "60", "120", "240", "D", "W"], index=2)
h = cc3.slider("Höhe (px)", 300, 900, 420, step=10)

placeholder = st.empty()
loops = 1 if not auto else 8

for _ in range(loops):
    if use_live:
        px, src = fetch_btc_spot_multi()
        if px is not None:
            push_price(st.session_state, px)
            st.session_state.last_live_src = src

    eq, r, u = update_equity(st.session_state)
    p = current_price(st.session_state)

    with placeholder.container():
        m1, m2, m3 = st.columns([2,1,1])
        with m1:
            st.info(f"🔌 Live-Quelle: **{st.session_state.get('last_live_src','…')}**")
            y = st.session_state.price_series.tail(180)["price"]
            fig = go.Figure(go.Scatter(y=y, mode="lines"))
            fig.update_layout(height=220, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig, use_container_width=True)
        with m2:
            st.metric("Realized PnL", f"{r:,.2f}")
        with m3:
            st.metric("Unrealized PnL", f"{u:,.2f}")

        if tv_on:
            tv = f'''
<div class="tradingview-widget-container">
  <div id="tvchart"></div>
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
      "hide_top_toolbar": false,
      "hide_legend": false,
      "save_image": false,
      "container_id": "tvchart"
    }});
  </script>
</div>
'''
            html(tv, height=h, scrolling=False)

    import time
    if auto:
        time.sleep(ms/1000.0)
