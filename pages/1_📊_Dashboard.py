
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from utils import ensure_state, current_price, simulate_next_price, realized_unrealized, fetch_btc_spot_multi, push_price

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
ensure_state(st.session_state)

st.markdown("## 📊 Dashboard")
st.caption("Aktueller Kurs & PnL-Übersicht. Echtpreis optional (mehrere Quellen).")

left, right = st.columns([2,1])
with left:
    c0, c1 = st.columns([1,1])
    use_live = c0.toggle("Echter BTC-Preis", value=True)
    live = c1.toggle("Auto-Refresh", value=True)
    if live:
        st_autorefresh(interval=1500, limit=None, key="auto_refresh_dash")
        if use_live:
            px_live, src = fetch_btc_spot_multi()
            push_price(st.session_state, px_live if px_live is not None else current_price(st.session_state))
            if px_live is not None:
                st.session_state.last_live_src = src
        else:
            simulate_next_price(st.session_state, vol=0.0008)
    else:
        if st.button("➡️ Nächster Tick"):
            if use_live:
                px_live, src = fetch_btc_spot_multi()
                push_price(st.session_state, px_live if px_live is not None else current_price(st.session_state))
                if px_live is not None:
                    st.session_state.last_live_src = src
            else:
                simulate_next_price(st.session_state, vol=0.0008)

    px = current_price(st.session_state)
    st.button(f"💸 Aktueller Kurs: **{px:,.2f}**", use_container_width=True)
    st.line_chart(st.session_state.price_series.tail(120), y="price", height=160)
    st.caption(f"Live-Quelle: {st.session_state.get('last_live_src', '…')}")

with right:
    r, u = realized_unrealized(st.session_state)
    st.metric("Realized PnL", f"{r:,.2f}")
    st.metric("Unrealized PnL", f"{u:,.2f}")
