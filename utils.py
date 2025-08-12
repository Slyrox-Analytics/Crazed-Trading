
import numpy as np
import pandas as pd
from dataclasses import dataclass
import requests

@dataclass
class BotConfig:
    side: str = "Neutral"
    margin: float = 100000.0
    leverage: int = 10
    grid_count: int = 8
    range_min: float = 60000.0
    range_max: float = 64000.0
    step_shift: float = 50.0
    fee_rate: float = 0.0006
    qty_per_order: float = 0.001

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
    if "last_live_src" not in st:
        st.last_live_src = None

def current_price(st):
    return float(st.price_series["price"].iloc[-1])

def simulate_next_price(st, vol=0.002):
    p = current_price(st)
    shock = np.random.randn()*vol
    new = max(100.0, p * (1.0 + shock))
    st.price_series.loc[len(st.price_series)] = new
    return new

# ---- Live price helpers (multi-source) ----
def _fetch_binance():
    r = requests.get("https://api.binance.com/api/v3/ticker/price", params={"symbol":"BTCUSDT"}, timeout=4)
    r.raise_for_status()
    return float(r.json()["price"]), "binance"

def _fetch_bitstamp():
    r = requests.get("https://www.bitstamp.net/api/v2/ticker/btcusd", timeout=4)
    r.raise_for_status()
    return float(r.json()["last"]), "bitstamp"

def _fetch_coinbase():
    r = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=4)
    r.raise_for_status()
    return float(r.json()["data"]["amount"]), "coinbase"

LIVE_SOURCES = [_fetch_binance, _fetch_bitstamp, _fetch_coinbase]

def fetch_btc_spot_multi():
    for fn in LIVE_SOURCES:
        try:
            price, src = fn()
            return price, src
        except Exception:
            continue
    return None, None

def push_price(st, new_price: float):
    if new_price is not None:
        st.price_series.loc[len(st.price_series)] = float(new_price)
        return float(new_price)
    return None

# ---- Grid helpers ----
def price_to_grid_levels(cfg: BotConfig):
    # Arithmetisch: gleichmäßige Abstände über Range (inklusive Endpunkte)
    return np.linspace(cfg.range_min, cfg.range_max, int(cfg.grid_count))

def neutral_split_levels(cfg: BotConfig, price: float):
    """Bitget-like: Verteilung in Neutral hängt von Preisposition ab.
    Gibt (buy_levels, sell_levels) zurück, jeweils Listen der Level-Preise.
    """
    levels = list(price_to_grid_levels(cfg))
    rng = max(1e-9, (cfg.range_max - cfg.range_min))
    ratio = (price - cfg.range_min) / rng  # 0..1
    N = int(cfg.grid_count)
    buy_count = max(1, min(N-1, round(N * ratio)))  # mindestens 1, höchstens N-1
    sell_count = N - buy_count
    levels_sorted = sorted(levels)
    buy_levels = levels_sorted[:buy_count]
    sell_levels = levels_sorted[-sell_count:] if sell_count > 0 else []
    return [float(x) for x in buy_levels], [float(x) for x in sell_levels]

def rebuild_grid_orders(st):
    cfg: BotConfig = st.bot["config"]
    px = current_price(st)
    orders = []
    if cfg.side == "Long":
        for L in price_to_grid_levels(cfg):
            if L <= (cfg.range_min + cfg.range_max)/2.0:
                orders.append({"type":"buy_limit","price":float(L), "qty":cfg.qty_per_order})
    elif cfg.side == "Short":
        for L in price_to_grid_levels(cfg):
            if L >= (cfg.range_min + cfg.range_max)/2.0:
                orders.append({"type":"sell_limit","price":float(L), "qty":cfg.qty_per_order})
    else:
        buy_levels, sell_levels = neutral_split_levels(cfg, px)
        for L in buy_levels:
            orders.append({"type":"buy_limit","price":float(L), "qty":cfg.qty_per_order})
        for L in sell_levels:
            orders.append({"type":"sell_limit","price":float(L), "qty":cfg.qty_per_order})
    st.bot["open_orders"] = orders

def process_fills(st, new_price):
    cfg: BotConfig = st.bot["config"]
    to_remove, to_add = [], []
    orders = st.bot["open_orders"]
    levels = list(price_to_grid_levels(cfg))
    for i, od in enumerate(list(orders)):
        if od["type"]=="buy_limit" and new_price <= od["price"]:
            entry = od["price"]
            st.bot["position_size"] += cfg.qty_per_order
            pe, ps, q = st.bot["avg_entry"], st.bot["position_size"]-cfg.qty_per_order, cfg.qty_per_order
            st.bot["avg_entry"] = entry if pe is None else (pe*ps + entry*q)/(ps+q)
            st.logs.append(f"Buy filled @ {entry:.2f}")
            # TP = nächstes höheres Level
            above = [L for L in levels if L > entry]
            if above:
                tp = min(above)
                to_add.append({"type":"sell_limit","price":float(tp),"qty":q,"tp_of":entry})
            to_remove.append(i)
        elif od["type"]=="sell_limit" and new_price >= od["price"]:
            exit_price = od["price"]; q = cfg.qty_per_order
            if st.bot["position_size"]>0 and st.bot["avg_entry"] is not None:
                pnl = (exit_price - st.bot["avg_entry"]) * q
                fee = (exit_price + st.bot["avg_entry"]) * q * cfg.fee_rate
                pnl -= fee
                st.bot["pnl_realized"] += pnl
                st.bot["position_size"] -= q
                st.logs.append(f"TP sell @ {exit_price:.2f} | Realized PnL: {pnl:.2f}")
                if st.bot["position_size"]<=0: st.bot["avg_entry"]=None
            else:
                st.logs.append(f"Sell filled @ {exit_price:.2f}")
            to_remove.append(i)
    for idx in sorted(set(to_remove), reverse=True): orders.pop(idx)
    orders.extend(to_add)

def next_tp_target(cfg: BotConfig, entry: float):
    levels = list(price_to_grid_levels(cfg))
    above = [L for L in levels if L > entry]
    return float(min(above)) if above else None

def insight_expected_tp_pnl(st):
    cfg: BotConfig = st.bot["config"]
    if st.bot["avg_entry"] is None:
        return None
    tp = next_tp_target(cfg, st.bot["avg_entry"])
    if tp is None:
        return None
    q = cfg.qty_per_order
    pnl = (tp - st.bot["avg_entry"]) * q
    fee = (tp + st.bot["avg_entry"]) * q * cfg.fee_rate
    pnl -= fee
    return {"avg_entry": float(st.bot["avg_entry"]), "next_tp": float(tp),
            "distance": float(tp - st.bot["avg_entry"]), "expected_pnl_at_tp": float(pnl), "qty": float(q)}

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

# ---- Candles for Dashboard ----
def fetch_binance_klines(interval="1m", limit=180):
    url = "https://api.binance.com/api/v3/klines"
    try:
        r = requests.get(url, params={"symbol":"BTCUSDT", "interval":interval, "limit":limit}, timeout=5)
        r.raise_for_status()
        raw = r.json()
        # Columns: [openTime, open, high, low, close, volume, closeTime, ...]
        df = pd.DataFrame(raw, columns=[
            "t","o","h","l","c","v","ct","qv","n","tb","tqv","ig"
        ])
        df["t"] = pd.to_datetime(df["t"], unit="ms")
        for col in ["o","h","l","c","v"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df[["t","o","h","l","c","v"]]
    except Exception:
        return None
