
import streamlit as st
from utils import ensure_state
st.set_page_config(page_title="Orders", page_icon="📜", layout="wide")
ensure_state(st)

st.markdown("## 📜 Orders")
st.caption("Offene Grid-Orders (vereinfacht).")

if st.bot["open_orders"]:
    st.dataframe(st.bot["open_orders"], use_container_width=True, hide_index=True)
else:
    st.info("Keine offenen Orders.")
