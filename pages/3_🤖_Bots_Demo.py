# pages/3_🤖_Bots_Demo.py
from __future__ import annotations
import time, pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit.components.v1 import html
from utils import (
    ensure_state, current_price, simulate_next_price, fetch_btc_spot_multi,
    push_price, process_fills, update_equity, build_grid, force_cross
)

st.set_page_config(page_title="Bot-Demo", page_icon="🤖", layout="wide")
ensure_state(st.session_state)

# Scroll-Fix
html("""
<script>
(function(){
 const KEY='ct_bot_scrollY'; const y=sessionStorage.getItem(KEY);
 if(y){window.scrollTo(0, parseFloat(y));}
 let t; window.addEventListener('scroll', ()=>{ clearTimeout(t); t=setTimeout(()=>sessionStorage.setItem(KEY, window.scrollY),100);});
})();
</script>
""", height=0)

st.markdown("## 🤖 Bot-Demo (ohne API)")

# Parameter
c1,c2,c3 = st.columns(3)
mode = c1.selectbox("Richtung", ["Neutral","Long","Short"], index=0).lower()
st.session_state.bot["mode"]=mode
c2.number_input("Margin (USDT)", 1000.0, value=100000.0, step=1000.0)
c3.slider("Grids", 4, 60, int(st.session_state.bot.get("grids",12)), key="grids_ui")

r1,r2 = st.columns(2)
st.session_state.bot["range_min"] = r1.number_input("Range Min", value=float(st.session_state.bot["range_min"]), step=50.0, format="%.2f")
st.session_state.bot["range_max"] = r2.number_input("Range Max", value=float(st.session_state.bot["range_max"]), step=50.0, format="%.2f")
st.session_state.bot["grids"] = int(st.session_state.grids_ui)
build_grid(st.session_state.bot)

st.markdown("### Aktionen")
a1,a2,a3,a4,a5,a6 = st.columns(6)
if a1.button("Start", type="primary"): st.session_state.bot["running"]=True
if a2.button("Stop"): st.session_state.bot["running"]=False
if a3.button("Grid ⬆"): st.session_state.bot["grids"]=min(60,st.session_state.bot["grids"]+1); build_grid(st.session_state.bot)
if a4.button("Grid ⬇"): st.session_state.bot["grids"]=max(4,st.session_state.bot["grids"]-1); build_grid(st.session_state.bot)
if a5.button("Rebuild Grid"): build_grid(st.session_state.bot)
if a6.button("⚡ Force Cross (Demo-PnL)"): force_cross(st.session_state)

b1,b2 = st.columns(2)
use_live = b1.toggle("Echter BTC-Preis", value=True)
auto_soft = b2.toggle("Auto-Update (soft)", value=True)
speed = st.slider("Refresh (ms)", 1200, 5000, 2500, step=100)

status = "RUNNING" if st.session_state.bot.get("running") else "STOPPED"
(st.success if status=="RUNNING" else st.warning)(f"Status: {status}")

# Ticks
loops = 20 if auto_soft else 1
for _ in range(loops):
    if use_live:
        px, src = fetch_btc_spot_multi()
        if px is not None:
            push_price(st.session_state, px); st.session_state.last_live_src=src
        else:
            simulate_next_price(st.session_state)
    else:
        simulate_next_price(st.session_state)
    if st.session_state.bot.get("running"):
        process_fills(st.session_state, current_price(st.session_state))
    if loops>1: time.sleep(speed/1000.0)

# KPIs
p = current_price(st.session_state)
equity, realized, unrealized = update_equity(st.session_state)
k1,k2,k3,k4 = st.columns(4)
k1.metric("Preis", f"{p:,.2f}")
k2.metric("Equity (USDT)", f"{equity:,.2f}")
k3.metric("Realized PnL", f"{realized:,.2f}")
k4.metric("Unrealized PnL", f"{unrealized:,.2f}")
st.caption(f"Live-Quelle: {st.session_state.get('last_live_src','bitstamp')}")

# Chart
def grid_fig():
    df = st.session_state.price_series.tail(240)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["ts"], y=df["price"], mode="lines", name="Preis", line=dict(width=2)))
    for lv in st.session_state.bot["grid"]["long"]:
        fig.add_hline(y=lv, line=dict(color="#00e676", width=1.5))
    for lv in st.session_state.bot["grid"]["short"]:
        fig.add_hline(y=lv, line=dict(color="#ff5252", width=1.5, dash="dot"))
    mid=(st.session_state.bot["range_min"]+st.session_state.bot["range_max"])/2
    fig.add_hline(y=mid, line=dict(color="#ffde59", width=2))
    fig.update_layout(height=420, margin=dict(l=8,r=8,t=4,b=4), legend=dict(orientation="h"))
    return fig
st.plotly_chart(grid_fig(), use_container_width=True)

t1,t2 = st.tabs(["📋 Orders", "✅ Fills / Logs"])
with t1:
    st.dataframe(pd.DataFrame(st.session_state.orders).tail(150), use_container_width=True, height=260)
with t2:
    st.dataframe(pd.DataFrame(st.session_state.fills).tail(150), use_container_width=True, height=300)