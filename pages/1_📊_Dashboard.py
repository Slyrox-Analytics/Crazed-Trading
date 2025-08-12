
import streamlit as st
import plotly.graph_objects as go
from utils import ensure_state, current_price, fetch_btc_spot_multi, push_price, update_equity

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
ensure_state(st.session_state)

st.markdown("# Dashboard")
st.caption("Aktueller Kurs & PnL-Übersicht. Echtpreis optional (mehrere Quellen).")

c1, c2 = st.columns(2)
use_live = c1.toggle("Echter BTC-Preis", value=True)
auto = c2.toggle("Auto-Refresh", value=True)
ms = st.slider("Refresh (ms)", 1200, 5000, 2000, step=100)

# Soft refresh — no page rerun, no scroll jump
placeholder = st.empty()
loops = 1 if not auto else 8  # draw a few steps per run

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

    import time
    if auto: time.sleep(ms/1000.0)
