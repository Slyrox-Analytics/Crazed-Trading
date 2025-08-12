
import streamlit as st
from utils import ensure_state, current_price, simulate_next_price, realized_unrealized
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
ensure_state(st.session_state)

left, right = st.columns([1,1])

with left:
    st.markdown("## 📊 Dashboard")
    st.caption("Aktueller Demo-Kurs (Random Walk) und PnL-Übersicht.")
    live = st.toggle("Live-Modus (Auto-Refresh)", value=True, help="Simuliert Live-Kurs via Random Walk.")
    if live:
        st_autorefresh(interval=1200, limit=None, key="auto_refresh_dash")
        px = simulate_next_price(st.session_state, vol=0.0008)
    else:
        if st.button("➡️ Nächster Tick", use_container_width=True):
            px = simulate_next_price(st.session_state, vol=0.0008)
        else:
            px = current_price(st.session_state)
    st.button(f"💸 Aktueller Kurs: **{px:,.2f}**", use_container_width=True)
    r, u = realized_unrealized(st.session_state)
    st.metric("Realized PnL", f"{r:,.2f}")
    st.metric("Unrealized PnL", f"{u:,.2f}")

with right:
    st.markdown("### Quick Actions")
    c1, c2, c3 = st.columns(3)
    if c1.button("Bot-Demo öffnen", use_container_width=True):
        st.switch_page("pages/3_🤖_Bots_Demo.py")
    if c2.button("Orders ansehen", use_container_width=True):
        st.switch_page("pages/4_📜_Orders.py")
    if c3.button("Logs ansehen", use_container_width=True):
        st.switch_page("pages/5_🧾_Logs.py")
