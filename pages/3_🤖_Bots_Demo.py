
import time, random
import streamlit as st, plotly.graph_objects as go
from streamlit.components.v1 import html
from utils import (
    ensure_state, BotConfig, price_to_grid_levels, rebuild_grid_orders,
    simulate_next_price, current_price, process_fills,
    update_equity, fetch_btc_spot_multi, push_price, neutral_split_levels,
    force_cross_nearest
)

st.set_page_config(page_title="Bot-Demo", page_icon="🤖", layout="wide")
ensure_state(st.session_state)

# --- Keep scroll position across reruns (no more jumps) ---
html("""<script>
(function(){
  const key='ct_scrollY';
  const y = sessionStorage.getItem(key);
  if (y){ window.scrollTo(0, parseFloat(y)); }
  window.addEventListener('scroll', ()=>sessionStorage.setItem(key, window.scrollY));
})();
</script>""", height=0)

st.markdown("## 🤖 Bot-Demo (ohne API)")
st.caption("Scroll bleibt stabil – Updates laufen als *Soft-Refresh*.")

cfg: BotConfig = st.session_state.bot["config"]
c1, c2, c3, c4 = st.columns(4)
cfg.side = c1.selectbox("Richtung", ["Long","Short","Neutral"], index=2)
cfg.margin = c2.number_input("Margin (USDT)", min_value=1000.0, value=100000.0, step=1000.0)
cfg.leverage = c3.slider("Leverage", 1, 125, 10)
cfg.grid_count = c4.slider("Grids", 4, 60, 12)

cc5, cc6 = st.columns(2)
cfg.range_min = cc5.number_input("Range Min", min_value=10.0, value=60000.0, step=10.0, format="%.2f")
cfg.range_max = cc6.number_input("Range Max", min_value=20.0, value=64000.0, step=10.0, format="%.2f")
cfg.step_shift = st.slider("Grid verschieben (Stepgröße)", 1.0, 1000.0, 50.0, step=1.0)

with st.expander("⚙️ Schnell anpassen"):
    w = st.slider("Breite um Preis (%)", 1, 20, 8)
    if st.button("Center Grid auf Preis", use_container_width=True):
        p = current_price(st.session_state); span = p*(w/100)
        cfg.range_min = round(p-span/2,2); cfg.range_max = round(p+span/2,2)
        rebuild_grid_orders(st.session_state)
        st.success("Grid zentriert.")

r1 = st.columns([1,1,1,1,1,1.2,1.2,1.2,1.4])
if r1[0].button("Start", type="primary"): 
    st.session_state.bot["running"] = True; st.session_state["scroll_to_chart"] = True; rebuild_grid_orders(st.session_state)
if r1[1].button("Stop"): st.session_state.bot["running"] = False
if r1[2].button("Grid ⬆️"): d=cfg.step_shift; cfg.range_min+=d; cfg.range_max+=d; rebuild_grid_orders(st.session_state)
if r1[3].button("Grid ⬇️"): d=cfg.step_shift; cfg.range_min-=d; cfg.range_max-=d; rebuild_grid_orders(st.session_state)
if r1[4].button("Rebuild Grid"): rebuild_grid_orders(st.session_state)
if r1[5].button("Tick (1x)"): simulate_next_price(st.session_state, 0.0015); process_fills(st.session_state, current_price(st.session_state))
if r1[6].button("10 Ticks"): 
    for _ in range(10): simulate_next_price(st.session_state, 0.002); process_fills(st.session_state, current_price(st.session_state))
if r1[7].button("100 Ticks"):
    for _ in range(100): simulate_next_price(st.session_state, 0.0035); process_fills(st.session_state, current_price(st.session_state))
if r1[8].button("⚡ Force Cross (Demo-PnL)"):
    force_cross_nearest(st.session_state, "down" if cfg.side != "Short" else "up"); process_fills(st.session_state, current_price(st.session_state))

t0, t1, t2, t3 = st.columns([1,1,2,1])
use_live = t0.toggle("Echter BTC-Preis", value=True, key="live_toggle")
auto = t1.toggle("Auto-Update (soft)", value=True)
refresh = t2.slider("Refresh (ms)", 1200, 5000, 2500, step=100)
auto_fill = t3.toggle("Auto-Fill (Demo)", value=False, help="Erzwingt gelegentlich Fills (sichtbarer PnL).")

status = "RUNNING" if st.session_state.bot.get("running") else "PAUSED"
bg = "#21c36f" if status == "RUNNING" else "#555"
st.markdown(f'<div style="margin-top:-10px;margin-bottom:8px"><span style="padding:4px 8px;border-radius:8px;background:{bg};color:white;font-weight:600">Status: {status}</span></div>', unsafe_allow_html=True)

placeholder = st.empty()
cycles = 1 if not (auto and st.session_state.bot["running"]) else 12

for i in range(cycles):
    if use_live:
        px, src = fetch_btc_spot_multi()
        if px is not None: push_price(st.session_state, px); st.session_state.last_live_src = src
    else:
        simulate_next_price(st.session_state, vol=0.0015)

    if st.session_state.bot["running"] and auto_fill and random.random() < 0.15:
        force_cross_nearest(st.session_state, "down" if cfg.side != "Short" else "up")

    if st.session_state.bot["running"]:
        process_fills(st.session_state, current_price(st.session_state))

    price = current_price(st.session_state)
    equity, r, u = update_equity(st.session_state)

    with placeholder.container():
        st.markdown('<div id="chart-anchor"></div>', unsafe_allow_html=True)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Preis", f"{price:,.2f}")
        m2.metric("Equity (USDT)", f"{equity:,.2f}")
        m3.metric("Realized PnL", f"{r:,.2f}")
        m4.metric("Unrealized PnL", f"{u:,.2f}")

        y = st.session_state.price_series.tail(250)["price"]
        spark = go.Figure(go.Scatter(y=y, mode="lines", line=dict(width=2)))
        spark.update_layout(height=110, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(spark, use_container_width=True)
        st.caption(f"Live-Quelle: {st.session_state.get('last_live_src','…')}")

        levels = list(price_to_grid_levels(cfg))
        mid = (cfg.range_min + cfg.range_max) / 2.0
        if cfg.side == "Long":
            long_levels = [float(L) for L in levels if L < mid]; short_levels = []
        elif cfg.side == "Short":
            long_levels = []; short_levels = [float(L) for L in levels if L > mid]
        else:
            buy, sell = neutral_split_levels(cfg, price, static=False)
            long_levels, short_levels = buy, sell

        fig = go.Figure()
        fig.add_trace(go.Scatter(y=st.session_state.price_series["price"],
                                 x=list(range(len(st.session_state.price_series))),
                                 mode="lines", name="Preis", line=dict(width=2)))
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

        # Debug panel (verifiy orders / fills)
        with st.expander("🔎 Debug: Orders & Fills"):
            st.write("Open Orders:", st.session_state.bot.get("orders"))
            st.write("Fills:", st.session_state.bot.get("fills"))

        if st.session_state.get("scroll_to_chart"):
            html("""<script>
                const el = document.getElementById('chart-anchor');
                if (el) { el.scrollIntoView({behavior:'smooth', block:'start'}); }
            </script>""", height=0)
            st.session_state["scroll_to_chart"] = False

    if cycles > 1:
        time.sleep(refresh/1000.0)
