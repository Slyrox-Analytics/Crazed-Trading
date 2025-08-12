
import streamlit as st
from utils import ensure_state, BotConfig
st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")
ensure_state(st)

st.markdown("## ⚙️ Settings")
st.caption("Baseline-Parameter & Darstellung (Demo).")

cfg: BotConfig = st.bot["config"]
st.json({
    "side": cfg.side,
    "margin": cfg.margin,
    "leverage": cfg.leverage,
    "grid_count": cfg.grid_count,
    "range_min": cfg.range_min,
    "range_max": cfg.range_max
})
st.success("In der Demo werden Einstellungen im Session-State gehalten.")
