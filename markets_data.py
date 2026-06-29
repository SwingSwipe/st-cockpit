"""
markets_data.py — the DATA ENGINE for the S&T Cockpit.

Keeps ALL data/logic here; the UI (app.py) only displays what this returns.
Run it straight from the terminal to test the engine: `python markets_data.py`.

THE BIG IDEA: a trader reads markets as ONE cross-asset picture, grouped by asset
class. So we pull a structured "board" and compute each move the RIGHT way for its type:
  - equities / FX / commodities -> percent change (%)
  - rates (yields)              -> basis-point change (bps), because that's how rates trade

This version also returns, per instrument: the 52-week range (where does today sit in
the year?) and a short price history for sparklines — plus a market open/closed status
and a retry wrapper so a flaky free-data call doesn't crash the app.
"""

from datetime import datetime, time, timezone
import time as _time
import pandas as pd
import yfinance as yf


# ---------------------------------------------------------------------------
# THE BOARD: what a trader watches every morning, grouped by asset class.
# Each instrument = (yahoo_symbol, display_name, kind).
#   kind = "pct"   -> move reported as a percent change   (equities, FX, commodities)
#   kind = "yield" -> move reported in basis points (bps)  (Treasury yields)
# Editing this dict is how the dashboard grows — add a row, it shows up.
# ---------------------------------------------------------------------------
BOARD = {
    "Equities": [
        ("^GSPC", "S&P 500",      "pct"),
        ("^IXIC", "Nasdaq Comp",  "pct"),
        ("^DJI",  "Dow Jones",    "pct"),
        ("^RUT",  "Russell 2000", "pct"),
    ],
    "Rates": [
        # ^IRX (13-week T-bill yield) is the honest free proxy for the front end /
        # Fed-policy expectations — Yahoo has no direct fed funds ticker.
        ("^IRX", "13wk Bill", "yield"),
        ("^FVX", "5Y Yield",  "yield"),
        ("^TNX", "10Y Yield", "yield"),
        ("^TYX", "30Y Yield", "yield"),
    ],
    "FX": [
        ("DX-Y.NYB", "Dollar (DXY)", "pct"),
        ("EURUSD=X", "EUR/USD",      "pct"),
        ("USDJPY=X", "USD/JPY",      "pct"),
        ("GBPUSD=X", "GBP/USD",      "pct"),
    ],
    "Commodities": [
        ("CL=F", "WTI Crude", "pct"),
        ("BZ=F", "Brent",     "pct"),
        ("GC=F", "Gold",      "pct"),
        ("SI=F", "Silver",    "pct"),
        ("NG=F", "Nat Gas",   "pct"),
        ("HG=F", "Copper",    "pct"),
    ],
    "Volatility": [
        ("^VIX", "VIX", "pct"),
    ],
}

# The handful of headline instruments the "predict-before-you-peek" game uses —
# one tell per asset block so a morning round is quick (~6 calls of judgment).
PREDICT_SET = [
    ("^GSPC",    "S&P 500"),
    ("^TNX",     "10Y Yield"),
    ("DX-Y.NYB", "Dollar (DXY)"),
    ("CL=F",     "WTI Crude"),
    ("GC=F",     "Gold"),
    ("^VIX",     "VIX"),
]


def _all_symbols():
    return [sym for group in BOARD.values() for (sym, _n, _k) in group]


def _retry(fn, tries=3, pause=1.0):
    """
    Free data (yfinance/Yahoo) is flaky — DNS hiccups, rate limits, empty frames.
    Try a few times before giving up. (Ported from the equity bot — same lesson:
    a robust tool retries transient failures instead of falling over.)
    """
    last_err = None
    for attempt in range(tries):
        try:
            result = fn()
            if result is not None and not (isinstance(result, pd.DataFrame) and result.empty):
                return result
        except Exception as e:  # noqa: BLE001 — we genuinely want to swallow + retry
            last_err = e
        _time.sleep(pause * (attempt + 1))   # back off a bit more each try
    if last_err:
        raise last_err
    return None


def _kind_of(symbol):
    for group in BOARD.values():
        for sym, _name, kind in group:
            if sym == symbol:
                return kind
    return "pct"


def market_status(now_utc=None):
    """
    Is the US equity market open? Returns {label, state, detail}.

    state in {"open", "pre", "after", "closed"}. Based on New York time and regular
    9:30–16:00 ET hours. HONEST LIMIT: this ignores market holidays (no holiday
    calendar), and other assets trade different hours (futures ~24h, FX 24/5) — it's
    a quick orientation flag for the US cash equity session, not gospel.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    # Convert to New York time. zoneinfo needs the IANA tz database; if it's missing
    # on this machine, fall back to a fixed EDT offset (UTC-4) so we never crash.
    try:
        from zoneinfo import ZoneInfo
        now_et = now_utc.astimezone(ZoneInfo("America/New_York"))
        tz_note = ""
    except Exception:
        from datetime import timedelta
        now_et = now_utc.astimezone(timezone(timedelta(hours=-4)))
        tz_note = " (approx ET)"

    if now_et.weekday() >= 5:  # Sat/Sun
        return {"label": "🔴 Closed — weekend", "state": "closed", "detail": now_et.strftime("%a %H:%M ET") + tz_note}

    t = now_et.time()
    open_t, close_t = time(9, 30), time(16, 0)
    pre_t, after_t = time(4, 0), time(20, 0)
    stamp = now_et.strftime("%a %H:%M ET") + tz_note

    if open_t <= t < close_t:
        return {"label": "🟢 US market OPEN", "state": "open", "detail": stamp}
    if pre_t <= t < open_t:
        return {"label": "🟡 Pre-market", "state": "pre", "detail": stamp}
    if close_t <= t < after_t:
        return {"label": "🟠 After-hours", "state": "after", "detail": stamp}
    return {"label": "🔴 Closed", "state": "closed", "detail": stamp}


def _build_row(symbol, name, kind, close_series):
    """Turn a Close-price series into a fully-computed board row."""
    row = {
        "symbol": symbol, "name": name, "kind": kind,
        "last": None, "prev": None, "change_pct": None, "change_bps": None,
        "high_52w": None, "low_52w": None, "range_pct": None, "spark": [], "ok": False,
    }
    s = close_series.dropna()
    if len(s) < 2:
        return row

    last, prev = float(s.iloc[-1]), float(s.iloc[-2])
    row["last"], row["prev"] = last, prev
    if kind == "yield":
        row["change_bps"] = (last - prev) * 100.0   # 4.20 -> 4.25 = +5 bps
    else:
        row["change_pct"] = (last - prev) / prev * 100.0

    hi, lo = float(s.max()), float(s.min())
    row["high_52w"], row["low_52w"] = hi, lo
    # Where in the 52-week range does today sit? 0% = at the low, 100% = at the high.
    row["range_pct"] = (last - lo) / (hi - lo) * 100.0 if hi > lo else 50.0
    row["spark"] = [float(x) for x in s.tail(30)]    # last ~30 closes for the sparkline
    row["ok"] = True
    return row


def get_market_board():
    """
    Pull the whole board in ONE batched, retried yfinance call and compute everything.

    Returns:
      {
        "asof":   <UTC datetime of the pull>,
        "status": {market_status dict},
        "groups": { "Equities": [ {row}, ... ], "Rates": [...], ... },
      }
    Each row: symbol, name, kind, last, prev, change_pct, change_bps,
              high_52w, low_52w, range_pct, spark[], ok.
    """
    symbols = _all_symbols()

    # period="1y" gives us a year of daily closes in one call — enough for the day move,
    # the 52-week range, AND the sparkline. group_by="ticker" => data[sym]["Close"].
    data = _retry(lambda: yf.download(
        symbols, period="1y", interval="1d",
        group_by="ticker", auto_adjust=False, progress=False, threads=True,
    ))

    groups = {}
    for group_name, instruments in BOARD.items():
        rows = []
        for symbol, name, kind in instruments:
            try:
                close = data[symbol]["Close"]
                rows.append(_build_row(symbol, name, kind, close))
            except Exception:
                # One bad ticker shouldn't sink the board.
                rows.append({"symbol": symbol, "name": name, "kind": kind,
                             "last": None, "ok": False, "spark": []})
        groups[group_name] = rows

    return {"asof": datetime.now(timezone.utc), "status": market_status(), "groups": groups}


def flatten(board):
    """Helper: dict of symbol -> row, across all groups (handy for lookups)."""
    out = {}
    for rows in board["groups"].values():
        for r in rows:
            out[r["symbol"]] = r
    return out


# ---------------------------------------------------------------------------
# Test the ENGINE before touching the UI:  python markets_data.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    board = get_market_board()
    s = board["status"]
    print(f"\nMorning Markets Board — {board['asof']:%Y-%m-%d %H:%M} UTC | {s['label']} ({s['detail']})\n")
    for group_name, rows in board["groups"].items():
        print(f"== {group_name} ==")
        for r in rows:
            if not r["ok"]:
                print(f"  {r['name']:<14} (no data)")
                continue
            if r["kind"] == "yield":
                move = f"{r['change_bps']:+.1f} bps"
                lvl = f"{r['last']:.2f}%"
            else:
                move = f"{r['change_pct']:+.2f}%"
                lvl = f"{r['last']:,.2f}"
            rng = f"range {r['range_pct']:.0f}%"
            print(f"  {r['name']:<14} {lvl:>10}   {move:>10}   {rng}")
        print()
