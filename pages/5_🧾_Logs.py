
import streamlit as st
from utils import ensure_state
st.set_page_config(page_title="Logs", page_icon="🧾", layout="wide")
ensure_state(st.session_state)

st.markdown("## 🧾 Logs")
if st.session_state.logs:
    for line in st.session_state.logs[::-1]:
        st.write("•", line)
else:
    st.info("Noch keine Logs.")
