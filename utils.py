# utils.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import math
import random
from typing import List, Dict, Tuple, Optional

import numpy as np
import pandas as pd

# ------------------------------------------------------------
# State initialisieren
# ------------------------------------------------------------

def ensure_state(st):
    if "price_series" not in st:
        st.price_series = pd.DataFrame([{"ts": pd.Timestamp.utcnow(), "price": 62000.0}])

    if "bot" not in st:
        st.bot = {
            "running": False,
            "mode": "neutral",            # "neutral" | "long" | "short"
            "range_min": 60000.0,
            "range_max": 64000.0,
            "grids": 10,                  # Anzahl Grid-Linien gesamt
            "qty": 0.001,                 # Kontraktgröße pro Fill (Demo)
            "grid": {"long": [], "short": []},      # Listen mit Leveln
            "long_open": {},              # lvl -> entry_price
            "short_open": {},             # lvl -> entry_price
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
        }

    if "orders" not in st:
        st.orders = []       # offene "Grid-Orders" (nur Anzeige)
    if "fills" not in st:
        st.fills = []        # abgeschlossene Fills (Trades)

# ------------------------------------------------------------
# Preis-Funktionen
# ------------------------------------------------------------

def current_price(st) -> float:
    return float(st.price_series["price"].iloc[-1])

def push_price(st, price: float):
    st.price_series = pd.concat(
        [st.price_series, pd.DataFrame([{"ts": pd.Timestamp.utcnow(), "price": float(price)}])],
        ignore_index=True,
    )
    # nur die letzten 1.000 Punkte behalten
    if len(st.price_series) > 1000:
        st.price_series = st.price_series.tail(1000).reset_index(drop=True)

def simulate_next_price(st, vol: float = 0.0012):
    """Kleiner Random Walk um den letzten Preis (Demo)."""
    p = current_price(st)
    step = p * vol * np.random.normal(0, 1)
    push_price(st, max(10.0, p + step))

# ------------------------------------------------------------
# Live-Preis (leichtgewichtig; Bitstamp bevorzugt)
# ------------------------------------------------------------

import json
import urllib.request

def _fetch_json(url: str) -> Optional[dict]:
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None

def fetch_btc_spot_multi() -> Tuple[Optional[float], str]:
    # 1) bitstamp
    j = _fetch_json("https://www.bitstamp.net/api/v2/ticker/btcusd")
    if j and "last" in j:
        try:
            return float(j["last"]), "bitstamp"
        except Exception:
            pass
    # 2) kraken (fallback)
    j = _fetch_json("https://api.kraken.com/0/public/Ticker?pair=BTCUSD")
    try:
        p = float(j["result"]["XXBTZUSD"]["c"][0])
        return p, "kraken"
    except Exception:
        pass
    return None, "none"

# ------------------------------------------------------------
# Grid-Berechnung
# ------------------------------------------------------------

def build_grid(bot: dict):
    """Berechnet Grid-Level (long/short) aus Range & Anzahl."""
    mn = float(bot["range_min"])
    mx = float(bot["range_max"])
    n = int(bot["grids"])
    if mx <= mn:
        mx = mn + 100.0
    n = max(4, min(60, n))

    step = (mx - mn) / n
    levels = [mn + i * step for i in range(1, n)]  # innere Linien, ohne harte Grenzen
    mid = (mn + mx) / 2.0

    long_lvls = [x for x in levels if x <= mid]      # Käufe unten
    short_lvls = [x for x in levels if x > mid]      # Verkäufe oben

    long_lvls.sort()
    short_lvls.sort()

    bot["grid"] = {"long": long_lvls, "short": short_lvls}

# ------------------------------------------------------------
# Fill-Engine (Kreuzungserkennung + Realized/Unrealized)
# ------------------------------------------------------------

def _prev_curr_prices(st) -> Tuple[float, float]:
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
    """Wird auf jedem Tick aufgerufen, wenn der Bot läuft.
    Öffnet Longs (unten) bei DOWN-Cross & schließt beim nächsten UP-Cross.
    Öffnet Shorts (oben) bei UP-Cross & schließt beim nächsten DOWN-Cross.
    """
    bot = st.bot
    if not bot.get("running"):
        return

    long_lvls = bot["grid"]["long"]
    short_lvls = bot["grid"]["short"]
    qty = float(bot.get("qty", 0.001))

    prev, curr = _prev_curr_prices(st)

    # --- LONGS ---
    # Open: wenn von oben nach unten über ein Long-Level gekreuzt wird
    for lv in long_lvls:
        if prev > lv >= curr and lv not in bot["long_open"]:
            bot["long_open"][lv] = lv  # Entry = Level
            st.orders.append(
                {"side": "BUY", "level": lv, "status": "filled", "ts": datetime.utcnow().isoformat()}
            )
    # Close: wenn ein offener Long die NÄCHSTE Linie darüber nach oben kreuzt
    for entry_lv in list(bot["long_open"].keys()):
        tp_lv = _next_above(long_lvls + short_lvls, entry_lv)
        if tp_lv is None:
            tp_lv = entry_lv + (entry_lv * 0.002)  # kleiner Not-TP
        # Cross up
        if prev < tp_lv <= curr:
            entry_price = bot["long_open"].pop(entry_lv)
            pnl = (tp_lv - entry_price) * qty
            bot["realized_pnl"] += pnl
            st.fills.append(
                {
                    "side": "LONG",
                    "entry": round(entry_price, 2),
                    "exit": round(tp_lv, 2),
                    "qty": qty,
                    "pnl": round(pnl, 2),
                    "ts": datetime.utcnow().isoformat(),
                }
            )

    # --- SHORTS ---
    # Open: wenn von unten nach oben über ein Short-Level gekreuzt wird
    for lv in short_lvls:
        if prev < lv <= curr and lv not in bot["short_open"]:
            bot["short_open"][lv] = lv
            st.orders.append(
                {"side": "SELL", "level": lv, "status": "filled", "ts": datetime.utcnow().isoformat()}
            )
    # Close: wenn ein offener Short die NÄCHSTE Linie darunter nach unten kreuzt
    for entry_lv in list(bot["short_open"].keys()):
        tp_lv = _next_below(long_lvls + short_lvls, entry_lv)
        if tp_lv is None:
            tp_lv = entry_lv - (entry_lv * 0.002)
        # Cross down
        if prev > tp_lv >= curr:
            entry_price = bot["short_open"].pop(entry_lv)
            pnl = (entry_price - tp_lv) * qty
            bot["realized_pnl"] += pnl
            st.fills.append(
                {
                    "side": "SHORT",
                    "entry": round(entry_price, 2),
                    "exit": round(tp_lv, 2),
                    "qty": qty,
                    "pnl": round(pnl, 2),
                    "ts": datetime.utcnow().isoformat(),
                }
            )

    # Unrealized grob als Distanz zu nächstem TP für offene Stücke
    u = 0.0
    for entry_lv in bot["long_open"].values():
        tp = _next_above(long_lvls + short_lvls, entry_lv) or curr
        u += (curr - entry_lv) * qty * 0.5 if curr < tp else (tp - curr) * qty * 0.2
    for entry_lv in bot["short_open"].values():
        tp = _next_below(long_lvls + short_lvls, entry_lv) or curr
        u += (entry_lv - curr) * qty * 0.5 if curr > tp else (curr - tp) * qty * 0.2
    bot["unrealized_pnl"] = float(u)

def update_equity(st) -> Tuple[float, float, float]:
    """Equity = Startkapital (100k Demo) + Realized + Unrealized"""
    base = 100_000.0
    r = float(st.bot.get("realized_pnl", 0.0))
    u = float(st.bot.get("unrealized_pnl", 0.0))
    return base + r + u, r, u

# ------------------------------------------------------------
# Hilfsaktionen für Buttons
# ------------------------------------------------------------

def force_cross(st):
    """Erzwingt einen 'Roundtrip' in der Nähe des aktuellen Preises."""
    p = current_price(st)
    # simuliere zwei schnelle Ticks rund um p, damit eine TP-Linie gekreuzt wird
    push_price(st, p * 0.999)
    process_fills(st, p * 0.999)
    push_price(st, p * 1.001)
    process_fills(st, p * 1.001)