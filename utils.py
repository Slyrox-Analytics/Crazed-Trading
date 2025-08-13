# utils.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Tuple, Optional
import json, urllib.request, math
import numpy as np
import pandas as pd

# ------------------------------------------------------------
# State
# ------------------------------------------------------------
def ensure_state(st):
    if "price_series" not in st:
        st.price_series = pd.DataFrame([{"ts": pd.Timestamp.utcnow(), "price": 62000.0}])
    if "bot" not in st:
        st.bot = {
            "running": False,
            "mode": "neutral",
            "range_min": 60000.0,
            "range_max": 64000.0,
            "grids": 12,
            "qty": 0.001,
            "grid": {"long": [], "short": []},
            "long_open": {},
            "short_open": {},
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
        }
    if "orders" not in st:
        st.orders = []
    if "fills" not in st:
        st.fills = []

# ------------------------------------------------------------
# Preis
# ------------------------------------------------------------
def current_price(st) -> float:
    return float(st.price_series["price"].iloc[-1])

def push_price(st, price: float):
    st.price_series = pd.concat(
        [st.price_series, pd.DataFrame([{"ts": pd.Timestamp.utcnow(), "price": float(price)}])],
        ignore_index=True,
    )
    if len(st.price_series) > 1200:
        st.price_series = st.price_series.tail(1200).reset_index(drop=True)

def _fetch_json(url: str) -> Optional[dict]:
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None

def fetch_btc_spot_multi() -> Tuple[Optional[float], str]:
    j = _fetch_json("https://www.bitstamp.net/api/v2/ticker/btcusd")
    if j and "last" in j:
        try:
            return float(j["last"]), "bitstamp"
        except Exception:
            pass
    j = _fetch_json("https://api.kraken.com/0/public/Ticker?pair=BTCUSD")
    try:
        p = float(j["result"]["XXBTZUSD"]["c"][0])
        return p, "kraken"
    except Exception:
        pass
    return None, "none"

# ------------------------------------------------------------
# Grid
# ------------------------------------------------------------
def build_grid(bot: dict):
    mn = float(bot["range_min"]); mx = float(bot["range_max"])
    n = max(4, min(60, int(bot["grids"])))
    if mx <= mn: mx = mn + 100.0
    step = (mx - mn) / n
    levels = [mn + i * step for i in range(1, n)]  # 1..n-1
    mid = (mn + mx) / 2.0
    long_lvls = [x for x in levels if x <= mid]
    short_lvls = [x for x in levels if x > mid]
    long_lvls.sort(); short_lvls.sort()
    bot["grid"] = {"long": long_lvls, "short": short_lvls}

def grid_step(bot: dict) -> float:
    n = max(4, min(60, int(bot["grids"])))
    return (float(bot["range_max"]) - float(bot["range_min"])) / n

# ------------------------------------------------------------
# Demo-Preisbewegung (an Gridbreite gekoppelt)
# ------------------------------------------------------------
def simulate_next_price(st):
    p = current_price(st)
    bot = st.bot
    step_abs = max(10.0, grid_step(bot))        # absoluter Grid-Abstand in $
    # vol ≈ 0.8 Gridbreiten (damit es regelmäßig Linien kreuzt)
    target = 0.8 * step_abs
    move = np.random.normal(0, target)
    push_price(st, max(10.0, p + move))

# ------------------------------------------------------------
# Fill-Engine
# ------------------------------------------------------------
def _prev_curr(st) -> Tuple[float, float]:
    if len(st.price_series) < 2:
        p = current_price(st)
        return p, p
    prev = float(st.price_series["price"].iloc[-2])
    curr = float(st.price_series["price"].iloc[-1])
    return prev, curr

def _next_above(levels: List[float], x: float) -> Optional[float]:
    for lv in levels:
        if lv > x:
            return lv
    return None

def _next_below(levels: List[float], x: float) -> Optional[float]:
    for lv in reversed(levels):
        if lv < x:
            return lv
    return None

def process_fills(st, price: float):
    bot = st.bot
    if not bot.get("running"): return
    long_lvls = bot["grid"]["long"]; short_lvls = bot["grid"]["short"]
    qty = float(bot.get("qty", 0.001))
    prev, curr = _prev_curr(st)

    # LONG open (down-cross)
    for lv in long_lvls:
        if prev > lv >= curr and lv not in bot["long_open"]:
            bot["long_open"][lv] = lv
            st.orders.append({"side": "BUY", "level": lv, "status": "filled", "ts": datetime.utcnow().isoformat()})

    # LONG close (up-cross nächstes Level)
    all_lvls = sorted(long_lvls + short_lvls)
    for entry_lv in list(bot["long_open"].keys()):
        tp_lv = _next_above(all_lvls, entry_lv) or entry_lv + grid_step(bot)
        if prev < tp_lv <= curr:
            entry = bot["long_open"].pop(entry_lv)
            pnl = (tp_lv - entry) * qty
            bot["realized_pnl"] += pnl
            st.fills.append({"side": "LONG", "entry": round(entry,2), "exit": round(tp_lv,2),
                             "qty": qty, "pnl": round(pnl,2), "ts": datetime.utcnow().isoformat()})

    # SHORT open (up-cross)
    for lv in short_lvls:
        if prev < lv <= curr and lv not in bot["short_open"]:
            bot["short_open"][lv] = lv
            st.orders.append({"side": "SELL", "level": lv, "status": "filled", "ts": datetime.utcnow().isoformat()})

    # SHORT close (down-cross nächstes Level)
    for entry_lv in list(bot["short_open"].keys()):
        tp_lv = _next_below(all_lvls, entry_lv) or entry_lv - grid_step(bot)
        if prev > tp_lv >= curr:
            entry = bot["short_open"].pop(entry_lv)
            pnl = (entry - tp_lv) * qty
            bot["realized_pnl"] += pnl
            st.fills.append({"side": "SHORT", "entry": round(entry,2), "exit": round(tp_lv,2),
                             "qty": qty, "pnl": round(pnl,2), "ts": datetime.utcnow().isoformat()})

    # Unrealized grob
    u = 0.0
    c = current_price(st)
    for entry in bot["long_open"].values():
        u += (c - entry) * qty
    for entry in bot["short_open"].values():
        u += (entry - c) * qty
    bot["unrealized_pnl"] = float(u)

def update_equity(st) -> Tuple[float, float, float]:
    base = 100_000.0
    r = float(st.bot.get("realized_pnl", 0.0))
    u = float(st.bot.get("unrealized_pnl", 0.0))
    return base + r + u, r, u

# ------------------------------------------------------------
# Garantierter Roundtrip
# ------------------------------------------------------------
def force_cross(st):
    bot = st.bot
    p = current_price(st)
    lvls = sorted(bot["grid"]["long"] + bot["grid"]["short"])
    if not lvls:
        return
    # näheste Linie und deren Nachbar ermitteln
    nearest = min(lvls, key=lambda x: abs(x - p))
    idx = lvls.index(nearest)
    step_abs = max(5.0, grid_step(bot))
    # erst klar darunter, dann klar über die nächste Linie → öffnet & schließt
    down = nearest - 0.6*step_abs
    up   = (lvls[min(idx+1, len(lvls)-1)] + 0.6*step_abs)
    push_price(st, down); process_fills(st, down)
    push_price(st, up);   process_fills(st, up)