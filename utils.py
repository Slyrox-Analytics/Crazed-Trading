
from dataclasses import dataclass
import pandas as pd, numpy as np, time, random
import requests

QTY_PER_ORDER = 0.001  # 0.001 BTC pro Grid
MAX_SERIES = 1200

@dataclass
class BotConfig:
    side: str = "Neutral"         # Long / Short / Neutral
    margin: float = 100000.0
    leverage: int = 10
    grid_count: int = 12
    range_min: float = 60000.0
    range_max: float = 64000.0
    step_shift: float = 50.0

def _init_series(p0: float = 62000.0) -> pd.DataFrame:
    return pd.DataFrame([{"t": pd.Timestamp.utcnow(), "price": float(p0)}])

def ensure_state(st):
    if "price_series" not in st:
        st.price_series = _init_series()
    if "logs" not in st: st.logs = []
    if "bot" not in st:
        st.bot = {"config": BotConfig(), "running": False, "open_orders": [], "open_trades": [],
                  "realized": 0.0}
    if "last_live_src" not in st: st.last_live_src = "bitstamp"

def current_price(st) -> float:
    return float(st.price_series.iloc[-1]["price"])

def push_price(st, px: float):
    st.price_series.loc[len(st.price_series)] = {"t": pd.Timestamp.utcnow(), "price": float(px)}
    if len(st.price_series) > MAX_SERIES:
        st.price_series = st.price_series.iloc[-MAX_SERIES:].reset_index(drop=True)

def simulate_next_price(st, vol: float = 0.001):
    p = current_price(st)
    step = np.random.normal(0, vol) * p
    push_price(st, max(10.0, p + step))

def fetch_btc_spot_multi():
    # try Bitstamp
    try:
        r = requests.get("https://www.bitstamp.net/api/v2/ticker/btcusd", timeout=4)
        if r.ok:
            return float(r.json()["last"]), "bitstamp"
    except Exception:
        pass
    # try Binance
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=4)
        if r.ok:
            return float(r.json()["price"]), "binance"
    except Exception:
        pass
    return None, "offline"

def _grid_step(cfg: BotConfig) -> float:
    if cfg.grid_count <= 1: return cfg.range_max - cfg.range_min
    return (cfg.range_max - cfg.range_min) / (cfg.grid_count - 1)

def price_to_grid_levels(cfg: BotConfig):
    return np.linspace(cfg.range_min, cfg.range_max, int(cfg.grid_count))

def neutral_split_levels(cfg: BotConfig, price: float, static: bool):
    levels = list(price_to_grid_levels(cfg))
    mid = (cfg.range_min + cfg.range_max) / 2.0
    eps = max(1e-9, (cfg.range_max - cfg.range_min) * 1e-9)
    if static:
        longs = [float(L) for L in levels if L < mid - eps]
        shorts = [float(L) for L in levels if L > mid + eps]
        # mid (wenn ungerade) -> Short, damit volle Linienzahl sichtbar
        if len(levels) % 2 == 1:
            mid_val = levels[len(levels)//2]
            if abs(mid_val - mid) < eps*10 + 1e-6: shorts.append(float(mid_val))
        return longs, shorts
    else:
        longs = [float(L) for L in levels if L < price - eps]
        shorts = [float(L) for L in levels if L > price + eps]
        return longs, shorts

def rebuild_grid_orders(st):
    # nur Info für UI; Orders werden virtuell über Levels berechnet
    st.bot["open_orders"] = [{"level": float(L)} for L in price_to_grid_levels(st.bot["config"])]
    st.logs.append(f"{pd.Timestamp.utcnow()}: Grid rebuilt.")

def _crossed(prev: float, now: float, level: float, is_buy: bool) -> bool:
    '''True wenn Preis das Level in richtige Richtung kreuzt (Buy: von oben nach unten, Sell: unten nach oben).'''
    if is_buy:
        return prev > level >= now
    else:
        return prev < level <= now

def process_fills(st, price: float):
    cfg: BotConfig = st.bot["config"]
    if len(st.price_series) < 2: return
    prev = float(st.price_series.iloc[-2]["price"])
    step = _grid_step(cfg)

    # Levels entsprechend Modus
    levels = list(price_to_grid_levels(cfg))
    mid = (cfg.range_min + cfg.range_max) / 2.0
    if cfg.side == "Long":
        long_levels = [float(L) for L in levels if L < mid]
        short_levels = []
    elif cfg.side == "Short":
        long_levels = []
        short_levels = [float(L) for L in levels if L > mid]
    else:
        # dynamisch um Preis herum
        long_levels = [float(L) for L in levels if L < price]
        short_levels = [float(L) for L in levels if L > price]

    # Eröffnungen
    for L in long_levels:
        if _crossed(prev, price, L, is_buy=True):
            st.bot["open_trades"].append({"side":"long","entry":L,"tp":L+step,"qty":QTY_PER_ORDER})
            st.logs.append(f"{pd.Timestamp.utcnow()}: LONG filled @ {L:.2f} → TP {L+step:.2f}")
    for S in short_levels:
        if _crossed(prev, price, S, is_buy=False):
            st.bot["open_trades"].append({"side":"short","entry":S,"tp":S-step,"qty":QTY_PER_ORDER})
            st.logs.append(f"{pd.Timestamp.utcnow()}: SHORT filled @ {S:.2f} → TP {S-step:.2f}")

    # Schließungen (TP)
    still_open = []
    realized = st.bot.get("realized", 0.0)
    for t in st.bot["open_trades"]:
        if t["side"] == "long":
            # TP überschritten?
            if prev < t["tp"] <= price:
                pnl = (t["tp"] - t["entry"]) * t["qty"] * cfg.leverage
                realized += pnl
                st.logs.append(f"{pd.Timestamp.utcnow()}: LONG TP @ {t['tp']:.2f}  (+{pnl:.2f})")
            else:
                still_open.append(t)
        else:
            if prev > t["tp"] >= price:
                pnl = (t["entry"] - t["tp"]) * t["qty"] * cfg.leverage
                realized += pnl
                st.logs.append(f"{pd.Timestamp.utcnow()}: SHORT TP @ {t['tp']:.2f}  (+{pnl:.2f})")
            else:
                still_open.append(t)
    st.bot["open_trades"] = still_open
    st.bot["realized"] = realized

def realized_unrealized(st):
    cfg: BotConfig = st.bot["config"]
    price = current_price(st)
    realized = st.bot.get("realized", 0.0)
    u = 0.0
    for t in st.bot.get("open_trades", []):
        if t["side"] == "long":
            u += (price - t["entry"]) * t["qty"] * cfg.leverage
        else:
            u += (t["entry"] - price) * t["qty"] * cfg.leverage
    return realized, u

def update_equity(st):
    r,u = realized_unrealized(st)
    eq = st.bot["config"].margin + r + u
    return eq, r, u
