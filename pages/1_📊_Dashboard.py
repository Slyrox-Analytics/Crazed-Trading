
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from utils import ensure_state, current_price, realized_unrealized, fetch_btc_spot_multi, push_price, simulate_next_price, fetch_candles_multi
import plotly.graph_objects as go
import streamlit.components.v1 as components

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
ensure_state(st.session_state)

st.markdown("## 📊 Dashboard")
st.caption("Aktueller Kurs & PnL-Übersicht. Wahlweise TradingView-Widget oder interne Candles (Binance/Bitstamp).")

c0, c1, c2 = st.columns([1,1,1])
use_live = c0.toggle("Echter BTC-Preis", value=True)
auto = c1.toggle("Auto-Refresh", value=True)
interval = c2.slider("Refresh (ms)", 1000, 6000, 2000, step=250)

tv = st.toggle("TradingView-Chart (Beta)", value=True, help="Original TradingView Widget einbetten")

if auto or use_live:
    st_autorefresh(interval=interval, limit=None, key="dash_refresh")
    if use_live:
        px, src = fetch_btc_spot_multi()
        push_price(st.session_state, px if px is not None else current_price(st.session_state))
        if px is not None: st.session_state.last_live_src = src
    else:
        simulate_next_price(st.session_state, vol=0.0008)

left, right = st.columns([2,1])
with left:
    if tv:
        theme = "dark"
        sym = st.selectbox("Symbol", ["BINANCE:BTCUSDT", "BITSTAMP:BTCUSD", "COINBASE:BTCUSD"], index=0)
        height = st.slider("Höhe (px)", 300, 800, 420, step=20)
        html = f'''
        <div class="tradingview-widget-container">
          <div id="tradingview_crazed"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
          <script type="text/javascript">
          new TradingView.widget({{
              "width": "100%",
              "height": "{height}",
              "symbol": "{sym}",
              "interval": "5",
              "timezone": "Etc/UTC",
              "theme": "{theme}",
              "style": "1",
              "locale": "de_DE",
              "toolbar_bg": "rgba(0, 0, 0, 0)",
              "enable_publishing": false,
              "hide_top_toolbar": false,
              "allow_symbol_change": true,
              "container_id": "tradingview_crazed"
          }});
          </script>
        </div>
        '''
        components.html(html, height=height+10, scrolling=True)
    else:
        tf = st.selectbox("Timeframe", ["1m","5m","15m","1h"], index=1, help="Candles aus Binance, Fallback Bitstamp")
        candles = fetch_candles_multi(tf, 180)
        if candles is not None and len(candles):
            fig = go.Figure(data=[go.Candlestick(
                x=candles["t"], open=candles["o"], high=candles["h"], low=candles["l"], close=candles["c"]
            )])
            fig.update_layout(height=360, margin=dict(l=0,r=10,t=10,b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Konnte Candles nicht laden – zeige Sparkline.")
            y = st.session_state.price_series.tail(300)["price"]
            fig = go.Figure(go.Scatter(y=y, mode="lines"))
            fig.update_layout(height=360, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)

    px = current_price(st.session_state)
    st.button(f"💸 Aktueller Kurs: **{px:,.2f}**", use_container_width=True)
    st.caption(f"Live-Quelle: {st.session_state.get('last_live_src', '…')}")

with right:
    r, u = realized_unrealized(st.session_state)
    st.metric("Realized PnL", f"{r:,.2f}")
    st.metric("Unrealized PnL", f"{u:,.2f}")
