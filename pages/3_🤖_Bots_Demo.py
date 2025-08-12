
import streamlit as st, plotly.graph_objects as go
from utils import ensure_state, BotConfig, price_to_grid_levels, rebuild_grid_orders, simulate_next_price, current_price, realized_unrealized, process_fills

st.set_page_config(page_title="Bot-Demo", page_icon="🤖", layout="wide")
ensure_state(st)

st.markdown("## 🤖 Bot-Demo (ohne API)")
st.caption("Erstelle einen Demo-Bot. **Grid-Linien sichtbar**. Range & Grids während des Laufens anpassbar.")

cfg: BotConfig = st.bot["config"]
col1, col2, col3, col4 = st.columns(4)
cfg.side = col1.selectbox("Richtung", ["Long","Short","Neutral"], index=2)
cfg.margin = col2.number_input("Margin (USDT)", min_value=1000.0, value=100000.0, step=1000.0)
cfg.leverage = col3.slider("Leverage", 1, 125, 10)
cfg.grid_count = col4.slider("Grids", 4, 40, 8)

c5, c6 = st.columns(2)
cfg.range_min = c5.number_input("Range Min", min_value=10.0, value=60000.0, step=10.0, format="%.2f")
cfg.range_max = c6.number_input("Range Max", min_value=20.0, value=64000.0, step=10.0, format="%.2f")
cfg.step_shift = st.slider("Grid verschieben (Stepgröße)", 1.0, 1000.0, 50.0, step=1.0)

cA, cB, cC, cD, cE = st.columns([1,1,1,1,1])
if cA.button("Start", type="primary"):
    st.bot["running"] = True
    rebuild_grid_orders(st)
if cB.button("Stop"):
    st.bot["running"] = False
if cC.button("Grid ⬆️"):
    delta = cfg.step_shift
    cfg.range_min += delta; cfg.range_max += delta
    rebuild_grid_orders(st)
if cD.button("Grid ⬇️"):
    delta = cfg.step_shift
    cfg.range_min -= delta; cfg.range_max -= delta
    rebuild_grid_orders(st)
if cE.button("Rebuild Grid"):
    rebuild_grid_orders(st)

cT1, cT2 = st.columns([1,1])
if cT1.button("➡️ Nächster Tick"):
    new = simulate_next_price(st, vol=0.0012)
    if st.bot["running"]:
        process_fills(st, new)
price = current_price(st)

levels = price_to_grid_levels(cfg)
fig = go.Figure()
fig.add_trace(go.Scatter(y=st.price_series["price"], x=list(range(len(st.price_series))), mode="lines", name="Preis"))
for L in levels:
    fig.add_hline(y=float(L), line_dash="dot", line_width=1, opacity=0.6)
fig.add_hline(y=price, line_width=2, line_dash="solid", annotation_text=f"Price {price:.2f}", annotation_position="right")

fig.update_layout(height=450, margin=dict(l=10,r=10,t=30,b=10), template="plotly_dark")
st.plotly_chart(fig, use_container_width=True)

r, u = realized_unrealized(st)
st.metric("Realized PnL", f"{r:,.2f}")
st.metric("Unrealized PnL", f"{u:,.2f}")

st.caption("**Hinweis:** In dieser Demo sind Fees & Positions vereinfacht. Fill-Logik: Cross bei Grid-Linie.")
