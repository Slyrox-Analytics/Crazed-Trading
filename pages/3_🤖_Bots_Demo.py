
import streamlit as st, plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
from utils import (
    ensure_state, BotConfig, price_to_grid_levels, rebuild_grid_orders,
    simulate_next_price, current_price, realized_unrealized, process_fills,
    insight_expected_tp_pnl, update_equity
)

st.set_page_config(page_title="Bot-Demo", page_icon="🤖", layout="wide")
ensure_state(st.session_state)

st.markdown("## 🤖 Bot-Demo (ohne API)")
st.caption("Erstelle einen Demo-Bot. **Grid-Linien sichtbar**. Range & Grids während des Laufens anpassbar.")

cfg: BotConfig = st.session_state.bot["config"]
col1, col2, col3, col4 = st.columns(4)
cfg.side = col1.selectbox("Richtung", ["Long","Short","Neutral"], index=2)
cfg.margin = col2.number_input("Margin (USDT)", min_value=1000.0, value=100000.0, step=1000.0)
cfg.leverage = col3.slider("Leverage", 1, 125, 10)
cfg.grid_count = col4.slider("Grids", 4, 40, 8)

c5, c6 = st.columns(2)
cfg.range_min = c5.number_input("Range Min", min_value=10.0, value=60000.0, step=10.0, format="%.2f")
cfg.range_max = c6.number_input("Range Max", min_value=20.0, value=64000.0, step=10.0, format="%.2f")
cfg.step_shift = st.slider("Grid verschieben (Stepgröße)", 1.0, 1000.0, 50.0, step=1.0)

# Controls
cA, cB, cC, cD, cE = st.columns([1,1,1,1,1])
if cA.button("Start", type="primary"):
    st.session_state.bot["running"] = True
    rebuild_grid_orders(st.session_state)
if cB.button("Stop"):
    st.session_state.bot["running"] = False
if cC.button("Grid ⬆️"):
    delta = cfg.step_shift
    cfg.range_min += delta; cfg.range_max += delta
    rebuild_grid_orders(st.session_state)
if cD.button("Grid ⬇️"):
    delta = cfg.step_shift
    cfg.range_min -= delta; cfg.range_max -= delta
    rebuild_grid_orders(st.session_state)
if cE.button("Rebuild Grid"):
    rebuild_grid_orders(st.session_state)

# Auto-tick toggle + interval
t1, t2, t3 = st.columns([1,1,2])
auto = t1.toggle("Auto-Tick", value=True, help="Simuliert Preisbewegung automatisch in Intervallen.")
interval = t2.slider("Intervall (ms)", 800, 4000, 1500, step=100)
if auto and st.session_state.bot["running"]:
    st_autorefresh(interval=interval, limit=None, key="auto_tick_bot")
    new = simulate_next_price(st.session_state, vol=0.0012)
    process_fills(st.session_state, new)
elif t3.button("➡️ Nächster Tick (manuell)"):
    new = simulate_next_price(st.session_state, vol=0.0012)
    if st.session_state.bot["running"]:
        process_fills(st.session_state, new)

# Metrics FIRST
price = current_price(st.session_state)
equity, r, u = update_equity(st.session_state)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Preis", f"{price:,.2f}")
m2.metric("Equity (USDT)", f"{equity:,.2f}")
m3.metric("Realized PnL", f"{r:,.2f}")
m4.metric("Unrealized PnL", f"{u:,.2f}")

insight = insight_expected_tp_pnl(st.session_state)
with st.expander("Nächste Grid-TP Vorschau", expanded=True):
    if insight:
        st.table({
            "Avg Entry":[f"{insight['avg_entry']:.2f}"],
            "Next TP":[f"{insight['next_tp']:.2f}"],
            "Distance":[f"{insight['distance']:.2f}"],
            "Qty":[f"{insight['qty']:.4f}"],
            "Expected PnL (after fees)":[f"{insight['expected_pnl_at_tp']:.2f}"]
        })
    else:
        st.info("Kein aktiver Avg Entry – warte auf den ersten Fill.")

# Chart with distinct styles: Long (green solid), Short (red dot), Price (yellow)
levels = list(price_to_grid_levels(cfg))
mid = (cfg.range_min + cfg.range_max) / 2.0

# Determine long/short groups depending on side
long_levels = []
short_levels = []
if cfg.side == "Long":
    long_levels = [float(L) for L in levels if L < mid]
elif cfg.side == "Short":
    short_levels = [float(L) for L in levels if L > mid]
else:
    long_levels = [float(L) for L in levels if L < mid]
    short_levels = [float(L) for L in levels if L > mid]

fig = go.Figure()
fig.add_trace(go.Scatter(
    y=st.session_state.price_series["price"],
    x=list(range(len(st.session_state.price_series))),
    mode="lines",
    name="Preis",
    line=dict(width=2)
))

for L in long_levels:
    fig.add_hline(y=L, line=dict(color="#00ff88", width=1.8, dash="solid"),
                  annotation_text="Long", annotation_position="right")
for L in short_levels:
    fig.add_hline(y=L, line=dict(color="#ff4d4d", width=1.8, dash="dot"),
                  annotation_text="Short", annotation_position="right")

fig.add_hline(y=price, line=dict(color="#ffd700", width=2.8, dash="solid"),
              annotation_text=f"Price {price:.2f}", annotation_position="right")

fig.update_layout(height=460, margin=dict(l=10,r=10,t=30,b=10))
st.plotly_chart(fig, use_container_width=True)

# Quick views
with st.expander("Offene Orders", expanded=False):
    if st.session_state.bot["open_orders"]:
        st.dataframe(st.session_state.bot["open_orders"], use_container_width=True, hide_index=True)
    else:
        st.caption("Keine offenen Orders.")
with st.expander("Logs", expanded=False):
    if st.session_state.logs:
        for line in st.session_state.logs[::-1]:
            st.write("•", line)
    else:
        st.caption("Noch keine Logs.")

st.caption("Legende: Long-Grids = grün/solid • Short-Grids = rot/dot • Preis = gelb")
