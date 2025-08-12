
import streamlit as st
from utils import ensure_state
st.set_page_config(page_title="Orders", page_icon="📜", layout="wide")
ensure_state(st.session_state)

st.markdown("## 📜 Orders")
st.caption("Offene Grid-Orders (vereinfacht).")

if st.session_state.bot["open_orders"]:
    st.dataframe(st.session_state.bot["open_orders"], use_container_width=True, hide_index=True)
else:
    st.info("Keine offenen Orders.")
