
import streamlit as st
from pathlib import Path
from utils import ensure_state
st.set_page_config(page_title="Crazed-Trading", page_icon="💹", layout="wide")

st.markdown(Path("assets/custom.css").read_text(), unsafe_allow_html=True)
ensure_state(st.session_state)

col_logo, col_title = st.columns([1,3])
with col_logo:
    st.image("assets/logo.svg")
with col_title:
    st.markdown("### Willkommen bei")
    st.markdown("# **Crazed-Trading**")
    st.caption("Futures Grid-Bot — Demo ohne API, mit verschiebbaren Grids & anpassbarer Range")

st.divider()
st.markdown("#### Los geht's")
if st.button("🧠 Bot erstellen", type="primary", use_container_width=True):
    st.switch_page("pages/3_🤖_Bots_Demo.py")

st.markdown("")
st.markdown("**Tipp:** Oben über das Menü navigieren: Dashboard • Analyse • Bot-Demo • Orders • Logs • Settings")
