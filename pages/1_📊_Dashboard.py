
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from utils import ensure_state, current_price, realized_unrealized, fetch_btc_spot_multi, push_price, simulate_next_price, fetch_binance_klines
import plotly.graph_objects as go

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
ensure_state(st.session_state)

st.markdown("## 📊 Dashboard")
st.caption("Aktueller Kurs & PnL-Übersicht. Echtpreis & Candle-Chart (Binance) ohne API-Key.")

c0, c1, c2 = st.columns([1,1,1])
use_live = c0.toggle("Echter BTC-Preis", value=True)
auto = c1.toggle("Auto-Refresh", value=True)
interval = c2.slider("Refresh (ms)", 1000, 6000, 2000, step=250)

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
    tf = st.selectbox("Timeframe", ["1m","5m","15m","1h"], index=1, help="Binance-Kerzen")
    candles = fetch_binance_klines(tf, 180)
    if candles is not None:
        fig = go.Figure(data=[go.Candlestick(
            x=candles["t"], open=candles["o"], high=candles["h"], low=candles["l"], close=candles["c"]
        )])
        fig.update_layout(height=300, margin=dict(l=0,r=10,t=10,b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Konnte Candles nicht laden – zeige Sparkline.")
        y = st.session_state.price_series.tail(300)["price"]
        fig = go.Figure(go.Scatter(y=y, mode="lines"))
        fig.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)

    # aktuelle Kursanzeige
    px = current_price(st.session_state)
    st.button(f"💸 Aktueller Kurs: **{px:,.2f}**", use_container_width=True)
    st.caption(f"Live-Quelle: {st.session_state.get('last_live_src', '…')}")

with right:
    r, u = realized_unrealized(st.session_state)
    st.metric("Realized PnL", f"{r:,.2f}")
    st.metric("Unrealized PnL", f"{u:,.2f}")
