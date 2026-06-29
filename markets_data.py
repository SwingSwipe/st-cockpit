"""
markets_data.py — the DATA ENGINE for the S&T Cockpit's Morning Markets Dashboard.

Design rule (same as the equity bot): keep the data/logic here, keep the UI in app.py.
This file knows nothing about Streamlit. You can run it straight from the terminal
(`python markets_data.py`) and it prints the board — that's how we test the engine
before ever touching the UI.

THE BIG IDEA: a trader reads markets as ONE cross-asset picture, grouped by asset class.
So we don't pull a random list of tickers — we pull a structured "board" and compute
each instrument's move the RIGHT way for its type:
  - equities / FX / commodities  -> percent change (%)
  - rates (yields)               -> basis-point change (bps), because that's how rates trade
"""

from datetime import datetime, timezone
import pandas as pd
import yfinance as yf


# ---------------------------------------------------------------------------
# THE BOARD: what a trader watches every morning, grouped by asset class.
#
# Each instrument is (yahoo_symbol, display_name, kind).
#   kind = "pct"   -> report the move as a percent change   (equities, FX, commodities, indices)
#   kind = "yield" -> report the move in basis points (bps)  (Treasury yields)
#
# Editing this dict is how the dashboard grows — add a row, it shows up. That's the
# whole point: the board is data, not hard-coded UI.
# ---------------------------------------------------------------------------
BOARD = {
    "Equities": [
        ("^GSPC", "S&P 500",        "pct"),
        ("^IXIC", "Nasdaq Comp",    "pct"),
        ("^DJI",  "Dow Jones",      "pct"),
        ("^RUT",  "Russell 2000",   "pct"),
    ],
    "Rates": [
        # ^IRX is the 13-week T-bill yield — the honest free proxy for the front end /
        # Fed policy expectations (Yahoo has no direct fed funds ticker).
        ("^IRX",  "13wk Bill",      "yield"),
        ("^FVX",  "5Y Yield",       "yield"),
        ("^TNX",  "10Y Yield",      "yield"),
        ("^TYX",  "30Y Yield",      "yield"),
    ],
    "FX": [
        ("DX-Y.NYB", "Dollar (DXY)", "pct"),
        ("EURUSD=X",  "EUR/USD",     "pct"),
        ("USDJPY=X",  "USD/JPY",     "pct"),
        ("GBPUSD=X",  "GBP/USD",     "pct"),
    ],
    "Commodities": [
        ("CL=F", "WTI Crude",  "pct"),
        ("BZ=F", "Brent",      "pct"),
        ("GC=F", "Gold",       "pct"),
        ("SI=F", "Silver",     "pct"),
        ("NG=F", "Nat Gas",    "pct"),
        ("HG=F", "Copper",     "pct"),
    ],
    "Volatility": [
        ("^VIX", "VIX",        "pct"),
    ],
}


def _all_symbols():
    """Flat list of every Yahoo symbol on the board (for one batched download)."""
    return [sym for group in BOARD.values() for (sym, _name, _kind) in group]


def _last_two_closes(close_series):
    """
    Given a Close price series, return (latest_close, prior_close).

    We pull ~5 calendar days so weekends/holidays don't leave us with one bar.
    The 'move' a trader cares about each morning = latest session vs the one before it.
    Returns (None, None) if there isn't enough clean data.
    """
    s = close_series.dropna()
    if len(s) < 2:
        return None, None
    return float(s.iloc[-1]), float(s.iloc[-2])


def get_market_board():
    """
    Pull the whole board in ONE batched yfinance call and compute each move.

    Returns a dict:
      {
        "asof": <UTC datetime of the pull>,
        "groups": {
            "Equities": [ {row}, {row}, ... ],
            "Rates":    [ ... ],
            ...
        }
      }

    Each {row} = {
        "symbol", "name", "kind",
        "last":        latest level (price, or yield in %),
        "prev":        prior close,
        "change_pct":  % move      (None for yields),
        "change_bps":  bps move    (None for non-yields),
        "ok":          True if we got clean data, else False,
    }
    """
    symbols = _all_symbols()

    # ONE call for everything = fewer round-trips = less chance of Yahoo rate-limiting us.
    # group_by="ticker" gives columns like data[("^TNX", "Close")].
    # auto_adjust=False keeps the raw Close (we don't want dividend adjustments on indices/FX).
    data = yf.download(
        symbols,
        period="5d",
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True,
    )

    groups = {}
    for group_name, instruments in BOARD.items():
        rows = []
        for symbol, name, kind in instruments:
            row = {"symbol": symbol, "name": name, "kind": kind,
                   "last": None, "prev": None,
                   "change_pct": None, "change_bps": None, "ok": False}
            try:
                # When multiple tickers are requested, columns are a MultiIndex.
                close = data[symbol]["Close"]
                last, prev = _last_two_closes(close)
                if last is not None:
                    row["last"] = last
                    row["prev"] = prev
                    if kind == "yield":
                        # Yields are quoted in percent (e.g. 4.23). A move from 4.20->4.25
                        # is +5 basis points = (4.25 - 4.20) * 100.
                        row["change_bps"] = (last - prev) * 100.0
                    else:
                        row["change_pct"] = (last - prev) / prev * 100.0
                    row["ok"] = True
            except Exception:
                # A single bad ticker shouldn't sink the whole board — skip it, mark not-ok.
                pass
            rows.append(row)
        groups[group_name] = rows

    return {"asof": datetime.now(timezone.utc), "groups": groups}


# ---------------------------------------------------------------------------
# Run this file directly to test the ENGINE before touching the UI:
#   python markets_data.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    board = get_market_board()
    print(f"\nMorning Markets Board — pulled {board['asof']:%Y-%m-%d %H:%M} UTC\n")
    for group_name, rows in board["groups"].items():
        print(f"== {group_name} ==")
        for r in rows:
            if not r["ok"]:
                print(f"  {r['name']:<14} (no data)")
                continue
            if r["kind"] == "yield":
                move = f"{r['change_bps']:+.1f} bps"
                print(f"  {r['name']:<14} {r['last']:>8.2f}%   {move}")
            else:
                move = f"{r['change_pct']:+.2f}%"
                print(f"  {r['name']:<14} {r['last']:>10.2f}   {move}")
        print()
