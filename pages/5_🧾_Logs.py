
import streamlit as st
from utils import ensure_state
st.set_page_config(page_title="Logs", page_icon="🧾", layout="wide")
ensure_state(st)

st.markdown("## 🧾 Logs")
if st.logs:
    for line in st.logs[::-1]:
        st.write("•", line)
else:
    st.info("Noch keine Logs.")
