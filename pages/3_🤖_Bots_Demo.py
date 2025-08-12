
import streamlit as st, plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components
from utils import (
    ensure_state, BotConfig, price_to_grid_levels, rebuild_grid_orders,
    simulate_next_price, current_price, realized_unrealized, process_fills,
    update_equity, fetch_btc_spot_multi, push_price, neutral_split_levels
)

st.set_page_config(page_title="Bot-Demo", page_icon="🤖", layout="wide")
ensure_state(st.session_state)

# Robust scroll restore (multiple attempts after render)
components.html('''
<script>
  const key = "scrollY_bot_demo";
  const saved = parseInt(sessionStorage.getItem(key) || "0");
  function restore() { window.scrollTo(0, saved); }
  document.addEventListener("DOMContentLoaded", restore);
  let tries=0; let h=setInterval(()=>{ restore(); if(++tries>10) clearInterval(h); }, 120);
  setInterval(()=> sessionStorage.setItem(key, window.scrollY), 200);
</script>
''', height=0)

st.markdown("## 🤖 Bot-Demo (ohne API)")
st.caption("Grid-Linien sichtbar. Range & Grids live anpassbar.")

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

with st.expander("⚙️ Schnell anpassen"):
    w = st.slider("Breite um Preis (%)", 1, 20, 8)
    if st.button("Center Grid auf Preis", use_container_width=True):
        p = current_price(st.session_state)
        span = p * (w/100)
        cfg.range_min = round(p - span/2, 2)
        cfg.range_max = round(p + span/2, 2)
        rebuild_grid_orders(st.session_state)
        st.success("Grid um aktuellen Preis zentriert.")
    st.markdown("[Zum Chart springen](#chart)")

# Controls row
cA, cB, cC, cD, cE, cF, cG, cH = st.columns([1,1,1,1,1,1.4,1.2,1.2])
if cA.button("Start", type="primary", key="start_btn"):
    st.session_state.bot["running"] = True
    rebuild_grid_orders(st.session_state)
if cB.button("Stop", key="stop_btn"):
    st.session_state.bot["running"] = False
if cC.button("Grid ⬆️", key="grid_up"):
    d = cfg.step_shift; cfg.range_min += d; cfg.range_max += d; rebuild_grid_orders(st.session_state)
if cD.button("Grid ⬇️", key="grid_down"):
    d = cfg.step_shift; cfg.range_min -= d; cfg.range_max -= d; rebuild_grid_orders(st.session_state)
if cE.button("Rebuild Grid", key="rebuild"):
    rebuild_grid_orders(st.session_state)

if cF.button("⏭️ Tick (1x)", key="tick1"):
    simulate_next_price(st.session_state, vol=0.0015); process_fills(st.session_state, current_price(st.session_state))
if cG.button("⏭️ 10 Ticks", key="tick10"):
    for _ in range(10): simulate_next_price(st.session_state, vol=0.002); process_fills(st.session_state, current_price(st.session_state))
if cH.button("⏭️ 100 Ticks", key="tick100"):
    for _ in range(100): simulate_next_price(st.session_state, vol=0.0035); process_fills(st.session_state, current_price(st.session_state))

# Live / refresh
t0, t1, t2 = st.columns([1,1,2])
use_live = t0.toggle("Echter BTC-Preis", value=True, key="live_toggle")
pause = t1.toggle("Updates pausieren", value=False, help="Zum Verstellen kurz aktivieren.", key="pause_toggle")
refresh = t2.slider("Refresh (ms)", 1200, 5000, 2500, step=100, key="refresh_ms")

# Neutral behaviour
is_static = st.radio(
    "Neutral-Modus", ["Statisch (um Mid, wie Bitget manuell)","Dynamisch (preisabhängig)"],
    index=1, horizontal=True, key="neutral_mode_radio"
) == "Statisch (um Mid, wie Bitget manuell)"

status = "RUNNING" if st.session_state.bot.get("running") else "PAUSED"
bg = "#21c36f" if status == "RUNNING" else "#555"
st.markdown(f'''
<div style="margin-top:-10px;margin-bottom:8px">
  <span style="padding:4px 8px;border-radius:8px;background:{bg};
        color:white;font-weight:600">Status: {status}</span>
</div>
''', unsafe_allow_html=True)

if use_live and not pause:
    st_autorefresh(interval=refresh, limit=None, key="live_refresh_key")
    px, src = fetch_btc_spot_multi()
    push_price(st.session_state, px if px is not None else current_price(st.session_state))
    if px is not None: st.session_state.last_live_src = src
    if st.session_state.bot["running"]:
        process_fills(st.session_state, current_price(st.session_state))

# Metrics
price = current_price(st.session_state)
equity, r, u = update_equity(st.session_state)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Preis", f"{price:,.2f}")
m2.metric("Equity (USDT)", f"{equity:,.2f}")
m3.metric("Realized PnL", f"{r:,.2f}")
m4.metric("Unrealized PnL", f"{u:,.2f}")

y = st.session_state.price_series.tail(250)["price"]
spark = go.Figure(go.Scatter(y=y, mode="lines", line=dict(width=2)))
spark.update_layout(height=110, margin=dict(l=0,r=0,t=0,b=0))
st.plotly_chart(spark, use_container_width=True)
st.caption(f"Live-Quelle: {st.session_state.get('last_live_src', '…')}")

tab_chart, tab_orders, tab_logs = st.tabs(["📈 Chart", "📜 Orders", "🧾 Logs"])
with tab_chart:
    st.markdown('<a name="chart"></a>', unsafe_allow_html=True)
    levels = list(price_to_grid_levels(cfg))
    mid = (cfg.range_min + cfg.range_max) / 2.0

    if cfg.side == "Long":
        long_levels = [float(L) for L in levels if L < mid]
        short_levels = []
    elif cfg.side == "Short":
        long_levels = []
        short_levels = [float(L) for L in levels if L > mid]
    else:
        if is_static:
            eps = max(1e-9, (cfg.range_max - cfg.range_min) * 1e-9)
            base_long = [float(L) for L in levels if L < mid - eps]
            base_short = [float(L) for L in levels if L > mid + eps]
            if len(levels) % 2 == 1:
                mid_val = levels[len(levels)//2]
                if abs(mid_val - mid) < eps*10 + 1e-6:
                    base_short.append(float(mid_val))
            long_levels, short_levels = base_long, base_short
        else:
            buy_levels, sell_levels = neutral_split_levels(cfg, price, False)
            long_levels, short_levels = buy_levels, sell_levels

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
                      annotation_text="Lo", annotation_position="right")
    for L in short_levels:
        fig.add_hline(y=L, line=dict(color="#ff4d4d", width=1.8, dash="dot"),
                      annotation_text="Sh", annotation_position="right")
    fig.add_hline(y=price, line=dict(color="#ffd700", width=2.8, dash="solid"),
                  annotation_text=f"Price {price:.2f}", annotation_position="right")
    fig.update_layout(height=520, margin=dict(l=10,r=10,t=30,b=10))
    st.plotly_chart(fig, use_container_width=True)

with tab_orders:
    if st.session_state.bot["open_trades"]:
        st.dataframe(st.session_state.bot["open_trades"], use_container_width=True)
    else:
        st.info("Keine offenen Positionen.")

with tab_logs:
    if st.session_state.logs:
        for line in st.session_state.logs[::-1][:200]:
            st.write("•", line)
    else:
        st.info("Noch keine Logs.")
