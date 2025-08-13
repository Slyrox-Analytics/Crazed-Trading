# pages/3_Bots_Demo.py
from __future__ import annotations
import random
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from utils import (
    ensure_state, rebuild_grid, process_tick,
    update_equity, current_price
)
from utils import push_price  # falls du manuell Preise testen willst
from utils import realized_unrealized

st.set_page_config(page_title="Bot-Demo", page_icon="🤖", layout="wide")
ensure_state(st.session_state)
bot = st.session_state.bot

st.markdown("## Bot-Demo (ohne API)")
left, right = st.columns([3,2])

# ----------- Setup -----------
with left:
    c1, c2, c3 = st.columns(3)
    bot.range_min = c1.number_input("Range Min", value=float(bot.range_min), step=100.0, format="%.2f")
    bot.range_max = c2.number_input("Range Max", value=float(bot.range_max), step=100.0, format="%.2f")
    bot.n_grids   = int(c3.slider("Grids", 4, 60, int(bot.n_grids)))
    bot.qty_per_order = st.slider("Qty pro Grid (BTC, Demo)", 0.0005, 0.01, float(bot.qty_per_order), step=0.0005)
    bot.mode = st.radio("Neutral-Modus", ["dynamic","static"], horizontal=True, index=0 if bot.mode=="dynamic" else 1)

    # Buttons
    b1, b2, b3, b4 = st.columns(4)
    if b1.button("Start", use_container_width=True): bot.running = True
    if b2.button("Stop",  use_container_width=True): bot.running = False
    if b3.button("Grid ⬆",use_container_width=True):  # preisnahe Grenzen verschieben
        bot.range_min += 50; bot.range_max += 50; rebuild_grid(bot, price=current_price(st.session_state))
    if b4.button("Grid ⬇",use_container_width=True):
        bot.range_min -= 50; bot.range_max -= 50; rebuild_grid(bot, price=current_price(st.session_state))

    if st.button("Rebuild Grid (neu)"):
        rebuild_grid(bot, price=current_price(st.session_state))

with right:
    refresh = st.slider("Refresh (ms)", 1200, 5000, 2500, step=100)
    soft_auto = st.toggle("Auto-Update (soft)", value=False)
    if soft_auto and bot.running:
        st_autorefresh(interval=refresh, key="bot_soft_tick")

# ----------- Kurs beschaffen / ticken -----------
# DU HAST BEREITS DEINEN Live-Feed: wenn du ihn nutzen willst,
# ruf process_tick(st, live_price) auf. Hier gibt's eine sehr
# kleine Demo-Bewegung per Zufall, falls kein Live-Feed aktiv ist.
if bot.running:
    # kleiner Random-Walk um die reale Preisspur nicht zu zerstören
    last = current_price(st.session_state)
    demo = last + random.uniform(-40, 40)
    process_tick(st.session_state, demo)

# ----------- KPIs -----------
p = current_price(st.session_state)
eq, R, U = update_equity(st.session_state)
top1, top2, top3 = st.columns(3)
top1.metric("Preis", f"{p:,.2f}")
top2.metric("Equity (USDT)", f"{eq:,.2f}")
top3.metric("Realized PnL",  f"{R:,.2f}")
st.metric("Unrealized PnL", f"{U:,.2f}")

# ----------- Chart ----------
ps = bot.price_series.tail(800)
fig = go.Figure()
fig.add_trace(go.Scatter(x=ps["ts"], y=ps["price"], name="Preis", mode="lines", line=dict(width=2)))

# Grid-Linien
for lvl, side in bot.grids:
    fig.add_hline(
        y=lvl,
        line_color="#00c853" if side=="long" else "#ff5252",
        line_dash="solid" if side=="long" else "dot",
        opacity=0.9
    )

# aktuelle Mid-Linie
mid = (bot.range_min + bot.range_max)/2
fig.add_hline(y=mid, line_color="#ffd54f", opacity=0.6, name="Mid")

fig.update_layout(height=420, margin=dict(l=10,r=10,t=10,b=10), showlegend=False)
st.plotly_chart(fig, use_container_width=True)

# ----------- Trades/Logs ----------
with st.expander("Trades (Demo-Fills)"):
    if bot.trades:
        st.dataframe(
            pd.DataFrame([t.__dict__ for t in bot.trades])[["ts","price","side","qty","realized"]],
            use_container_width=True, height=240
        )
    else:
        st.info("Noch keine Fills.")