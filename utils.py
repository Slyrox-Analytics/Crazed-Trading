
import numpy as np
import pandas as pd
from dataclasses import dataclass
import requests

@dataclass
class BotConfig:
    side: str = "Neutral"   # "Long", "Short", "Neutral"
    margin: float = 100000.0
    leverage: int = 10
    grid_count: int = 8
    range_min: float = 60000.0
    range_max: float = 64000.0
    step_shift: float = 50.0  # amount to shift grid up/down
    fee_rate: float = 0.0006  # taker as simplification
    qty_per_order: float = 0.001 # synthetic contract size

def ensure_state(st):
    if "price_series" not in st:
        st.price_series = pd.DataFrame({"price":[62000.0]})
    if "bot" not in st:
        st.bot = {
            "config": BotConfig(),
            "running": False,
            "open_orders": [],
            "trades": [],
            "pnl_realized": 0.0,
            "position_size": 0.0,
            "avg_entry": None
        }
    if "logs" not in st:
        st.logs = []
    if "equity_series" not in st:
        st.equity_series = pd.DataFrame({"equity":[st.bot["config"].margin]})

def current_price(st):
    return float(st.price_series["price"].iloc[-1])

def simulate_next_price(st, vol=0.002):
    p = current_price(st)
    shock = np.random.randn()*vol
    new = max(100.0, p * (1.0 + shock))
    st.price_series.loc[len(st.price_series)] = new
    return new

def fetch_btc_spot():
    """Simple BTCUSDT spot price from Binance public API (no key)."""
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price", params={"symbol":"BTCUSDT"}, timeout=3)
        r.raise_for_status()
        return float(r.json()["price"])
    except Exception:
        return None

def push_price(st, new_price: float):
    if new_price is not None:
        st.price_series.loc[len(st.price_series)] = float(new_price)
        return float(new_price)
    return None

def price_to_grid_levels(cfg: BotConfig):
    levels = np.linspace(cfg.range_min, cfg.range_max, int(cfg.grid_count))
    return levels

def rebuild_grid_orders(st):
    cfg: BotConfig = st.bot["config"]
    levels = price_to_grid_levels(cfg)
    orders = []
    mid = (cfg.range_min + cfg.range_max)/2.0
    px = current_price(st)

    if cfg.side == "Long":
        for L in levels:
            if L < mid:
                orders.append({"type":"buy_limit","price":float(L),"qty":cfg.qty_per_order})
    elif cfg.side == "Short":
        for L in levels:
            if L > mid:
                orders.append({"type":"sell_limit","price":float(L),"qty":cfg.qty_per_order})
    else:
        # Neutral → Bitget-like split based on price position within range
        rng = max(1e-9, (cfg.range_max - cfg.range_min))
        ratio = (px - cfg.range_min) / rng  # 0..1
        N = int(cfg.grid_count)
        buy_count = max(1, min(N-1, round(N * ratio)))
        sell_count = N - buy_count
        sorted_levels = sorted(levels)
        buy_levels = sorted_levels[:buy_count]
        sell_levels = sorted_levels[-sell_count:] if sell_count > 0 else []
        for L in buy_levels:
            orders.append({"type":"buy_limit","price":float(L),"qty":cfg.qty_per_order})
        for L in sell_levels:
            orders.append({"type":"sell_limit","price":float(L),"qty":cfg.qty_per_order})

    st.bot["open_orders"] = orders

def process_fills(st, new_price):
    cfg: BotConfig = st.bot["config"]
    to_remove = []
    to_add = []
    orders = st.bot["open_orders"]
    levels = price_to_grid_levels(cfg)
    level_list = list(levels)
    for i, od in enumerate(list(orders)):
        if od["type"]=="buy_limit" and new_price <= od["price"]:
            entry = od["price"]
            st.bot["position_size"] = st.bot["position_size"] + cfg.qty_per_order
            if st.bot["avg_entry"] is None:
                st.bot["avg_entry"] = entry
            else:
                pe = st.bot["avg_entry"]
                ps = abs(st.bot["position_size"] - cfg.qty_per_order)
                st.bot["avg_entry"] = (pe*ps + entry*cfg.qty_per_order)/(ps+cfg.qty_per_order)
            st.logs.append(f"Buy filled @ {entry:.2f}")
            # TP at next upper grid level
            idx = max(1, level_list.index(min(level_list, key=lambda x: abs(x-entry)))+1)
            if idx < len(level_list):
                tp = level_list[idx]
                to_add.append({"type":"sell_limit","price":float(tp),"qty":cfg.qty_per_order,"tp_of":entry})
            to_remove.append(i)
        elif od["type"]=="sell_limit" and new_price >= od["price"]:
            exit_price = od["price"]
            qty = cfg.qty_per_order
            if st.bot["position_size"]>0 and st.bot["avg_entry"] is not None:
                pnl = (exit_price - st.bot["avg_entry"]) * qty
                fee = (exit_price + st.bot["avg_entry"]) * qty * cfg.fee_rate
                pnl -= fee
                st.bot["pnl_realized"] += pnl
                st.bot["position_size"] -= qty
                st.logs.append(f"TP sell @ {exit_price:.2f} | Realized PnL: {pnl:.2f}")
                if st.bot["position_size"]<=0:
                    st.bot["avg_entry"] = None
            else:
                st.logs.append(f"Sell filled @ {exit_price:.2f}")
            to_remove.append(i)
    for idx in sorted(set(to_remove), reverse=True):
        orders.pop(idx)
    orders.extend(to_add)

def next_tp_target(cfg: BotConfig, entry: float):
    levels = price_to_grid_levels(cfg)
    level_list = list(levels)
    idx = max(1, level_list.index(min(level_list, key=lambda x: abs(x-entry)))+1)
    if idx < len(level_list):
        return float(level_list[idx])
    return None

def insight_expected_tp_pnl(st):
    cfg: BotConfig = st.bot["config"]
    if st.bot["avg_entry"] is None:
        return None
    tp = next_tp_target(cfg, st.bot["avg_entry"])
    if tp is None:
        return None
    qty = cfg.qty_per_order
    pnl = (tp - st.bot["avg_entry"]) * qty
    fee = (tp + st.bot["avg_entry"]) * qty * cfg.fee_rate
    pnl -= fee
    return {
        "avg_entry": float(st.bot["avg_entry"]),
        "next_tp": float(tp),
        "distance": float(tp - st.bot["avg_entry"]),
        "expected_pnl_at_tp": float(pnl),
        "qty": float(qty)
    }

def realized_unrealized(st):
    px = current_price(st)
    upnl = 0.0
    if st.bot["position_size"] and st.bot["avg_entry"]:
        upnl = (px - st.bot["avg_entry"]) * st.bot["position_size"]
    return st.bot["pnl_realized"], upnl

def update_equity(st):
    r, u = realized_unrealized(st)
    equity = st.bot["config"].margin + r + u
    st.equity_series.loc[len(st.equity_series)] = equity
    return equity, r, u
