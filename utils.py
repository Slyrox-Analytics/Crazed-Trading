# utils.py
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import List, Literal, Tuple
import pandas as pd
import numpy as np

Side = Literal["long", "short"]

# ---------- Bot-Datenmodell ----------
@dataclass
class Trade:
    ts: float
    price: float
    side: Side
    qty: float
    realized: float

@dataclass
class BotState:
    # Markt
    last_price: float = 120000.0
    price_series: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(
        {"ts":[time.time()], "price":[120000.0]}
    ))

    # Grid-Setup
    range_min: float = 115000.0
    range_max: float = 123000.0
    n_grids: int = 12
    mode: Literal["static", "dynamic"] = "dynamic"  # dynamic = um Preis herum

    # Orders
    qty_per_order: float = 0.001  # BTC pro Fill (Demo)
    grids: List[Tuple[float, Side]] = field(default_factory=list)  # (level, side)

    # Position
    pos_qty: float = 0.0          # >0 long, <0 short (in BTC)
    pos_avg: float = 0.0          # durchschnittlicher Entry
    realized: float = 0.0         # USDT
    unrealized: float = 0.0       # USDT

    # Laufstatus
    running: bool = False
    trades: List[Trade] = field(default_factory=list)

def ensure_state(st):
    if "bot" not in st:
        st.bot = BotState()
        rebuild_grid(st.bot, price=st.bot.last_price)

# ---------- Preis / Kurs-Feed ----------
def push_price(st, price: float):
    st.bot.last_price = float(price)
    st.bot.price_series = pd.concat(
        [st.bot.price_series, pd.DataFrame({"ts":[time.time()], "price":[price]})],
        ignore_index=True
    )
    _update_unrealized(st.bot)

def current_price(st) -> float:
    return float(st.bot.last_price)

# ---------- Grid bauen ----------
def rebuild_grid(bot: BotState, price: float | None = None):
    if price is None:
        price = bot.last_price

    lo, hi = float(bot.range_min), float(bot.range_max)
    n = int(bot.n_grids)

    # Aufteilung long (unter Mid) / short (über Mid) – ungleichmäßig erlaubt
    mid = price if bot.mode == "dynamic" else (lo + hi) / 2.0
    below = [x for x in np.linspace(lo, mid, n, endpoint=False)]
    above = [x for x in np.linspace(mid, hi, n, endpoint=False)][1:]  # mid nicht doppelt

    longs  = [(lvl, "long") for lvl in below if lvl < mid]
    shorts = [(lvl, "short") for lvl in above if lvl > mid]
    bot.grids = longs + shorts

def _crossed(prev: float, now: float, level: float, side: Side) -> bool:
    if side == "long":   # Kauf, wenn Preis von oben nach unten über level
        return prev > level and now <= level
    else:                # Verkauf, wenn Preis von unten nach oben über level
        return prev < level and now >= level

def _fill(bot: BotState, level: float, side: Side):
    px  = float(level)
    qty = bot.qty_per_order if side == "long" else -bot.qty_per_order
    new_pos = bot.pos_qty + qty

    # Realized PnL bei Positionsreduktion/Flip
    realized = 0.0
    if bot.pos_qty != 0.0 and np.sign(bot.pos_qty) != np.sign(new_pos):
        # kompletter Flip -> erst schließen
        close_qty = -bot.pos_qty
        if bot.pos_qty > 0:  # long schließen -> (px - avg) * qty
            realized += (px - bot.pos_avg) * abs(close_qty)
        else:                # short schließen -> (avg - px) * qty
            realized += (bot.pos_avg - px) * abs(close_qty)

    elif abs(new_pos) < abs(bot.pos_qty):
        # Teil-Schließung
        close_qty = qty if np.sign(qty) != np.sign(bot.pos_qty) else 0.0
        if close_qty != 0.0:
            if bot.pos_qty > 0:
                realized += (px - bot.pos_avg) * abs(close_qty)
            else:
                realized += (bot.pos_avg - px) * abs(close_qty)

    # Avg neu berechnen, wenn wir in gleiche Richtung addieren
    if np.sign(new_pos) == np.sign(bot.pos_qty) or bot.pos_qty == 0.0:
        total_notional = bot.pos_avg * abs(bot.pos_qty) + px * abs(qty)
        bot.pos_qty = new_pos
        bot.pos_avg = 0.0 if bot.pos_qty == 0 else total_notional / abs(bot.pos_qty)
    else:
        # wir haben reduziert / geflippt
        bot.pos_qty = new_pos
        if bot.pos_qty == 0:
            bot.pos_avg = 0.0
        # bei Flip bleibt avg = px der Restposition
        else:
            bot.pos_avg = px

    bot.realized += realized
    bot.trades.append(Trade(time.time(), px, side, abs(qty), realized))
    _update_unrealized(bot)

def _update_unrealized(bot: BotState):
    px = bot.last_price
    if bot.pos_qty > 0:
        bot.unrealized = (px - bot.pos_avg) * abs(bot.pos_qty)
    elif bot.pos_qty < 0:
        bot.unrealized = (bot.pos_avg - px) * abs(bot.pos_qty)
    else:
        bot.unrealized = 0.0

# ---------- Tick-Logik ----------
def process_tick(st, new_price: float):
    bot = st.bot
    prev = float(bot.last_price)
    push_price(st, new_price)  # aktualisiert last_price + chart
    now = float(bot.last_price)

    # multi-cross sicher behandeln (bei großen Sprüngen)
    for level, side in bot.grids:
        if _crossed(prev, now, level, side):
            _fill(bot, level, side)

# ---------- PnL/Equity für Anzeigen ----------
def realized_unrealized(st):
    return float(st.bot.realized), float(st.bot.unrealized)

def update_equity(st):
    # Equity = Start-Equity 100k + Realized + Unrealized (reiner Demo-Wert)
    base = 100000.0
    R, U = realized_unrealized(st)
    return base + R + U, R, U