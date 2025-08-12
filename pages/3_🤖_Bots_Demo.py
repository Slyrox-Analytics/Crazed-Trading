
import streamlit as st, plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
from utils import (
    ensure_state, BotConfig, price_to_grid_levels, rebuild_grid_orders,
    simulate_next_price, current_price, realized_unrealized, process_fills,
    insight_expected_tp_pnl, update_equity, fetch_btc_spot_multi, push_price,
    neutral_split_levels
)

st.set_page_config(page_title="Bot-Demo", page_icon="🤖", layout="wide")
ensure_state(st.session_state)

st.markdown("## 🤖 Bot-Demo (ohne API)")
st.caption("Erstelle einen Demo-Bot. Grid-Linien sichtbar. Range & Grids live anpassbar.")

cfg: BotConfig = st.session_state.bot["config"]
col1, col2, col3, col4 = st.columns(4)
cfg.side = col1.selectbox("Richtung", ["Long","Short","Neutral"], index=2)
cfg.margin = col2.number_input("Margin (USDT)", min_value=1000.0, value=100000.0, step=1000.0)
cfg.leverage = col3.slider("Leverage", 1, 125, 10)
cfg.grid_count = col4.slider("Grids", 4, 60, 12)

c5, c6 = st.columns(2)
cfg.range_min = c5.number_input("Range Min", min_value=10.0, value=60000.0, step=10.0, format="%.2f")
cfg.range_max = c6.number_input("Range Max", min_value=20.0, value=64000.0, step=10.0, format="%.2f")
cfg.step_shift = st.slider("Grid verschieben (Stepgröße)", 1.0, 1000.0, 50.0, step=1.0)

# Controls row
cA, cB, cC, cD, cE = st.columns([1,1,1,1,1])
if cA.button("Start", type="primary"):
    st.session_state.bot["running"] = True
    rebuild_grid_orders(st.session_state)
if cB.button("Stop"):
    st.session_state.bot["running"] = False
if cC.button("Grid ⬆️"):
    d = cfg.step_shift; cfg.range_min += d; cfg.range_max += d; rebuild_grid_orders(st.session_state)
if cD.button("Grid ⬇️"):
    d = cfg.step_shift; cfg.range_min -= d; cfg.range_max -= d; rebuild_grid_orders(st.session_state)
if cE.button("Rebuild Grid"):
    rebuild_grid_orders(st.session_state)

# Live + Refresh setup (decoupled from Auto-Tick)
t0, t1, t2, t3 = st.columns([1,1,1,2])
use_live = t0.toggle("Echter BTC-Preis", value=True)
auto_tick = t1.toggle("Auto-Tick (Sim)", value=False, help="Nur für Simulation nötig")
refresh = t2.slider("Refresh (ms)", 800, 4000, 1800, step=100)

if use_live or auto_tick:
    st_autorefresh(interval=refresh, limit=None, key="live_refresh")
    if use_live:
        px, src = fetch_btc_spot_multi()
        push_price(st.session_state, px if px is not None else current_price(st.session_state))
        if px is not None: st.session_state.last_live_src = src
    elif auto_tick:
        simulate_next_price(st.session_state, vol=0.0012)

    if st.session_state.bot["running"]:
        process_fills(st.session_state, current_price(st.session_state))

# Metrics + sparkline
price = current_price(st.session_state)
equity, r, u = update_equity(st.session_state)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Preis", f"{price:,.2f}")
m2.metric("Equity (USDT)", f"{equity:,.2f}")
m3.metric("Realized PnL", f"{r:,.2f}")
m4.metric("Unrealized PnL", f"{u:,.2f}")

# Sparkline
y = st.session_state.price_series.tail(120)["price"]
spark = go.Figure(go.Scatter(y=y, mode="lines", line=dict(width=2)))
spark.update_layout(height=110, margin=dict(l=0,r=0,t=0,b=0))
st.plotly_chart(spark, use_container_width=True)
st.caption(f"Live-Quelle: {st.session_state.get('last_live_src', '…')}")

# Tabs
tab_chart, tab_orders, tab_logs = st.tabs(["📈 Chart", "📜 Orders", "🧾 Logs"])

with tab_chart:
    levels = list(price_to_grid_levels(cfg))
    mid = (cfg.range_min + cfg.range_max) / 2.0

    # Determine which levels are Long/Short exactly like orders
    if cfg.side == "Long":
        long_levels = [float(L) for L in levels if L <= mid]
        short_levels = []
    elif cfg.side == "Short":
        long_levels = []
        short_levels = [float(L) for L in levels if L >= mid]
    else:
        buy_levels, sell_levels = neutral_split_levels(cfg, price)
        long_levels = buy_levels
        short_levels = sell_levels

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=st.session_state.price_series["price"],
        x=list(range(len(st.session_state.price_series))),
        mode="lines",
        name="Preis",
        line=dict(width=2)
    ))
    # draw all longs & shorts
    for L in long_levels:
        fig.add_hline(y=L, line=dict(color="#00ff88", width=1.8, dash="solid"),
                      annotation_text="Lo", annotation_position="right")
    for L in short_levels:
        fig.add_hline(y=L, line=dict(color="#ff4d4d", width=1.8, dash="dot"),
                      annotation_text="Sh", annotation_position="right")
    fig.add_hline(y=price, line=dict(color="#ffd700", width=2.8, dash="solid"),
                  annotation_text=f"Price {price:.2f}", annotation_position="right")
    fig.update_layout(height=520, margin=dict(l=10,r=10,t=30,b=10))
    st.plotly_chart(fig, use_container_width=True)

with tab_orders:
    if st.session_state.bot["open_orders"]:
        st.dataframe(st.session_state.bot["open_orders"], use_container_width=True, hide_index=True)
    else:
        st.info("Keine offenen Orders.")

with tab_logs:
    if st.session_state.logs:
        for line in st.session_state.logs[::-1]:
            st.write("•", line)
    else:
        st.info("Noch keine Logs.")
