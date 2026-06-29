"""
catalysts.py — the ECONOMIC CALENDAR (catalyst awareness).

Why this matters: half of "knowing the levels" is knowing WHAT's coming and WHEN.
CPI, NFP (jobs), and FOMC days are when rates and risk reprice violently — a trader
positions around them. Seeing the next catalyst every morning teaches you the rhythm
of what actually moves markets.

HONEST DESIGN: this is a hand-maintained STARTER schedule (free, no data feed). NFP is
computed reliably (it's the first Friday of each month); the rest are seeded with
2026 dates you should VERIFY/EDIT against the source (links below). Updating CALENDAR
is a one-line edit — and reading the BLS/Fed schedules yourself is part of the learning.

Sources to verify against:
  BLS (CPI/PPI/NFP):  https://www.bls.gov/schedule/news_release/
  Fed (FOMC):         https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
  BEA (GDP/PCE):      https://www.bea.gov/news/schedule
"""

from datetime import date, timedelta

# High-impact US events. (iso_date, name, importance) — importance: "high" | "med".
# SEED VALUES for 2026 — verify/replace from the sources above. NFP rows are computed
# below so you don't have to maintain them.
CALENDAR = [
    ("2026-07-15", "CPI (June)",            "high"),
    ("2026-07-16", "PPI (June)",            "med"),
    ("2026-07-29", "FOMC decision",         "high"),
    ("2026-07-30", "GDP (Q2 advance)",      "med"),
    ("2026-07-31", "PCE inflation (June)",  "high"),
    ("2026-08-13", "CPI (July)",            "high"),
    ("2026-09-16", "FOMC decision",         "high"),
    ("2026-10-28", "FOMC decision",         "high"),
    ("2026-12-09", "FOMC decision",         "high"),
]


def _first_fridays(start, months=6):
    """NFP (the monthly jobs report) lands on the first Friday of each month."""
    out = []
    y, m = start.year, start.month
    for _ in range(months):
        d = date(y, m, 1)
        # weekday(): Mon=0 .. Sun=6; Friday=4. Step to the first Friday.
        d += timedelta(days=(4 - d.weekday()) % 7)
        out.append((d.isoformat(), "NFP — Jobs Report", "high"))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def _all_events():
    events = list(CALENDAR) + _first_fridays(date.today(), months=6)
    # Parse, dedupe by (date, name), sort by date.
    seen, parsed = set(), []
    for iso, name, imp in events:
        key = (iso, name)
        if key in seen:
            continue
        seen.add(key)
        parsed.append({"date": date.fromisoformat(iso), "name": name, "importance": imp})
    return sorted(parsed, key=lambda e: e["date"])


def upcoming(n=4, today=None):
    """The next n events from today onward, each with days_out and a weekday label."""
    today = today or date.today()
    out = []
    for e in _all_events():
        if e["date"] >= today:
            days = (e["date"] - today).days
            out.append({**e, "days_out": days,
                        "when": "Today" if days == 0 else "Tomorrow" if days == 1 else f"in {days}d",
                        "weekday": e["date"].strftime("%a %b %d")})
            if len(out) >= n:
                break
    return out


if __name__ == "__main__":
    print("\nUpcoming catalysts:")
    for e in upcoming(6):
        flag = "🔴" if e["importance"] == "high" else "🟡"
        print(f"  {flag} {e['weekday']}  ({e['when']:>6})  {e['name']}")
    print()
