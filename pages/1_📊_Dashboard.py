
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from utils import ensure_state, current_price, simulate_next_price, realized_unrealized, fetch_btc_spot, push_price

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
ensure_state(st.session_state)

st.markdown("## 📊 Dashboard")
st.caption("Aktueller Kurs & PnL-Übersicht. Optional echter BTC-Preis (Binance) mit Sparkline.")

left, right = st.columns([2,1])
with left:
    c0, c1 = st.columns([1,1])
    use_live = c0.toggle("Echter BTC-Preis", value=True, help="Binance Spot BTCUSDT (kein Key nötig)")
    live = c1.toggle("Auto-Refresh", value=True, help="Aktualisiert den Kurs automatisch.")
    if live:
        st_autorefresh(interval=1500, limit=None, key="auto_refresh_dash")
        if use_live:
            px_live = fetch_btc_spot()
            push_price(st.session_state, px_live if px_live is not None else current_price(st.session_state))
        else:
            simulate_next_price(st.session_state, vol=0.0008)
    else:
        if st.button("➡️ Nächster Tick"):
            if use_live:
                px_live = fetch_btc_spot()
                push_price(st.session_state, px_live if px_live is not None else current_price(st.session_state))
            else:
                simulate_next_price(st.session_state, vol=0.0008)

    px = current_price(st.session_state)
    st.button(f"💸 Aktueller Kurs: **{px:,.2f}**", use_container_width=True)
    st.line_chart(st.session_state.price_series.tail(120), y="price", height=160)

with right:
    r, u = realized_unrealized(st.session_state)
    st.metric("Realized PnL", f"{r:,.2f}")
    st.metric("Unrealized PnL", f"{u:,.2f}")

st.divider()
c1, c2, c3 = st.columns(3)
if c1.button("Bot-Demo öffnen", use_container_width=True):
    st.switch_page("pages/3_🤖_Bots_Demo.py")
if c2.button("Orders ansehen", use_container_width=True):
    st.switch_page("pages/4_📜_Orders.py")
if c3.button("Logs ansehen", use_container_width=True):
    st.switch_page("pages/5_🧾_Logs.py")
