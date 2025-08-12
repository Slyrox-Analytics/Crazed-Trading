
import streamlit as st, plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
from utils import (
    ensure_state, BotConfig, price_to_grid_levels, rebuild_grid_orders,
    simulate_next_price, current_price, realized_unrealized, process_fills,
    insight_expected_tp_pnl, update_equity, fetch_btc_spot_multi, push_price
)
import numpy as np

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
    delta = cfg.step_shift
    cfg.range_min += delta; cfg.range_max += delta
    rebuild_grid_orders(st.session_state)
if cD.button("Grid ⬇️"):
    delta = cfg.step_shift
    cfg.range_min -= delta; cfg.range_max -= delta
    rebuild_grid_orders(st.session_state)
if cE.button("Rebuild Grid"):
    rebuild_grid_orders(st.session_state)

# Live + Auto options
t0, t1, t2, t3 = st.columns([1,1,1,2])
use_live = t0.toggle("Echter BTC-Preis", value=True, help="Mehrere Quellen (Binance, Bitstamp, Coinbase)")
auto = t1.toggle("Auto-Tick", value=False, help="Aktiviere Autolauf (Scroll-Sprünge möglich)")
interval = t2.slider("Intervall (ms)", 800, 4000, 2000, step=100)

# Auto-fit range around price (default OFF to respect manual inputs)
f1, f2 = st.columns([1,1])
auto_fit = f1.toggle("Range auto an Preis anpassen", value=False)
fit_width = f2.slider("Breite um Preis (%)", 1, 15, 5)

# Tick logic (always update series on auto; manual via button)
if auto:
    st_autorefresh(interval=interval, limit=None, key="auto_tick_bot")
    if use_live:
        px_live, src = fetch_btc_spot_multi()
        new = push_price(st.session_state, px_live if px_live is not None else current_price(st.session_state))
        if px_live is not None:
            st.session_state.last_live_src = src
    else:
        new = simulate_next_price(st.session_state, vol=0.0012)
    if st.session_state.bot["running"]:
        process_fills(st.session_state, new)
elif t3.button("➡️ Nächster Tick (manuell)"):
    if use_live:
        px_live, src = fetch_btc_spot_multi()
        new = push_price(st.session_state, px_live if px_live is not None else current_price(st.session_state))
        if px_live is not None:
            st.session_state.last_live_src = src
    else:
        new = simulate_next_price(st.session_state, vol=0.0012)
    if st.session_state.bot["running"]:
        process_fills(st.session_state, new)

# Metrics
price = current_price(st.session_state)
equity, r, u = update_equity(st.session_state)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Preis", f"{price:,.2f}")
m2.metric("Equity (USDT)", f"{equity:,.2f}")
m3.metric("Realized PnL", f"{r:,.2f}")
m4.metric("Unrealized PnL", f"{u:,.2f}")

# Sparkline (letzte 120 Punkte) direkt unter den Metriken
y = st.session_state.price_series.tail(120)["price"]
spark = go.Figure(go.Scatter(y=y, mode="lines", line=dict(width=2)))
spark.update_layout(height=120, margin=dict(l=0,r=0,t=0,b=0))
st.plotly_chart(spark, use_container_width=True)
st.caption(f"Live-Quelle: {st.session_state.get('last_live_src', '…')}")

# Tabs to avoid scroll jumps
tab_chart, tab_orders, tab_logs = st.tabs(["📈 Chart", "📜 Orders", "🧾 Logs"])

with tab_chart:
    # Optionally auto-fit range to current price for clarity
    if auto_fit:
        width = max(0.0001, fit_width/100.0)
        cfg.range_min = price*(1.0 - width)
        cfg.range_max = price*(1.0 + width)
        rebuild_grid_orders(st.session_state)

    levels = list(price_to_grid_levels(cfg))
    mid = (cfg.range_min + cfg.range_max) / 2.0

    # Draw ALL levels including the one at/closest to mid
    epsilon = max(1e-9, (cfg.range_max - cfg.range_min) * 1e-6)
    # Find index of level closest to mid:
    mid_idx = int(np.argmin([abs(L - mid) for L in levels]))
    mid_level = float(levels[mid_idx])

    long_levels = [float(L) for i, L in enumerate(levels) if L < mid - epsilon or (i != mid_idx and cfg.side in ["Long","Neutral"] and L < mid)]
    short_levels = [float(L) for i, L in enumerate(levels) if L > mid + epsilon or (i != mid_idx and cfg.side in ["Short","Neutral"] and L > mid)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=st.session_state.price_series["price"],
        x=list(range(len(st.session_state.price_series))),
        mode="lines",
        name="Preis",
        line=dict(width=2)
    ))
    # midline (if it's exactly one of the grid levels, highlight it)
    fig.add_hline(y=mid_level, line=dict(color="#00d1ff", width=2, dash="dash"),
                  annotation_text="Mid grid", annotation_position="right")

    for L in long_levels:
        fig.add_hline(y=L, line=dict(color="#00ff88", width=1.8, dash="solid"),
                      annotation_text="Long", annotation_position="right")
    for L in short_levels:
        fig.add_hline(y=L, line=dict(color="#ff4d4d", width=1.8, dash="dot"),
                      annotation_text="Short", annotation_position="right")

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
