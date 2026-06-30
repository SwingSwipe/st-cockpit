"""
lessons.py — the TEACHING layer. This is what turns a guess into a reasoned view.

The problem it solves: a beginner can write "why" all day, but without knowing the
cause→effect LINKAGES between assets, it's still a guess. So each day this reads the
ACTUAL tape and teaches the relationships that are showing up right now — live data
becomes the lesson. Do this every morning and the linkages become intuition; your
"why" stops being a guess and becomes a real read.

Two things here:
  RELATIONSHIPS — cross-asset cause→effect rules. Each has a trigger(board) that fires
                  when today's data shows it, plus a plain-English explanation of the WHY.
  CONCEPTS      — a rotating "concept of the day": the core S&T vocab/mental models,
                  one per day, so the foundation builds even on quiet tape.

Honest note: these explanations are the TEXTBOOK linkages — the usual reason assets move
together. On any given day the real driver can differ (correlation isn't causation). The
skill is learning the default linkage first, THEN noticing when today breaks the rule.
"""

from datetime import date
from markets_data import flatten


def _pct(row):
    return row.get("change_pct") if row and row.get("ok") and row.get("change_pct") is not None else None


def _bps(row):
    return row.get("change_bps") if row and row.get("ok") and row.get("change_bps") is not None else None


# ---------------------------------------------------------------------------
# RELATIONSHIPS — each is (name, trigger(f) -> bool, explanation).
# f = flattened board (symbol -> row). Triggers guard against missing data.
# ---------------------------------------------------------------------------
def _rates_up_growth_lags(f):
    tnx, ndx, dow = _bps(f.get("^TNX")), _pct(f.get("^IXIC")), _pct(f.get("^DJI"))
    if tnx is None or ndx is None or dow is None:
        return False
    # Yields rose AND Nasdaq (growth) underperformed the Dow (value-ish).
    return tnx > 0 and ndx < dow


def _weak_dollar_commodities(f):
    dxy, oil, gold = _pct(f.get("DX-Y.NYB")), _pct(f.get("CL=F")), _pct(f.get("GC=F"))
    if dxy is None:
        return False
    return dxy < 0 and ((oil or 0) > 0 or (gold or 0) > 0)


def _flight_to_quality(f):
    spx, tnx, vix, gold = _pct(f.get("^GSPC")), _bps(f.get("^TNX")), _pct(f.get("^VIX")), _pct(f.get("GC=F"))
    if spx is None or tnx is None:
        return False
    # Stocks down + yields down (bonds bid) + fear up / gold up = classic risk-off.
    return spx < 0 and tnx < 0 and ((vix or 0) > 0 or (gold or 0) > 0)


def _curve_flattening(f):
    front = _bps(f.get("^IRX"))
    if front is None:
        front = _bps(f.get("^FVX"))
    long_ = _bps(f.get("^TYX"))
    if front is None or long_ is None:
        return False
    return front > long_ + 0.5


def _cyclical_growth_bid(f):
    oil, copper, spx = _pct(f.get("CL=F")), _pct(f.get("HG=F")), _pct(f.get("^GSPC"))
    if oil is None or copper is None or spx is None:
        return False
    return oil > 0 and copper > 0 and spx > 0


def _gold_divergence(f):
    gold, vix, spx = _pct(f.get("GC=F")), _pct(f.get("^VIX")), _pct(f.get("^GSPC"))
    if gold is None or vix is None or spx is None:
        return False
    # Gold up while it's calm and risk-on — so NOT a fear bid. Different driver.
    return gold > 0.2 and vix < 0 and spx > 0


def _narrow_rally(f):
    spx, rut = _pct(f.get("^GSPC")), _pct(f.get("^RUT"))
    if spx is None or rut is None:
        return False
    return spx > 0 and rut < 0


def _broad_risk_on(f):
    spx, rut, vix = _pct(f.get("^GSPC")), _pct(f.get("^RUT")), _pct(f.get("^VIX"))
    if spx is None or rut is None or vix is None:
        return False
    return spx > 0 and rut > 0 and vix < 0


RELATIONSHIPS = [
    ("Rates up → growth stocks lag", _rates_up_growth_lags,
     "A stock is worth the present value of its future earnings. Higher yields discount "
     "those future earnings harder — and growth/tech names (Nasdaq) have the most earnings "
     "far in the future, so they fall the most. This is *duration* applied to stocks."),

    ("Weak dollar → commodities firm", _weak_dollar_commodities,
     "Oil, gold and copper are priced in dollars worldwide. A weaker dollar means it takes "
     "more dollars to buy the same barrel (so the dollar price rises), and it makes "
     "commodities cheaper for foreign buyers, lifting demand. Dollar down is a commodity tailwind."),

    ("Flight to quality (risk-off)", _flight_to_quality,
     "When investors get scared they sell stocks and buy safety — Treasuries (which pushes "
     "yields DOWN as bond prices rise) and gold, while the VIX 'fear gauge' jumps. Stocks "
     "down *and* yields down together is the fingerprint of fear, not weak growth."),

    ("The yield curve flattened", _curve_flattening,
     "The front end (short yields) tracks Fed-policy expectations; the long end tracks "
     "long-run growth and inflation. When the front rises faster than the long end, the "
     "market is pricing a tighter Fed and/or softer future growth. Flattening/inversion "
     "has historically led slowdowns."),

    ("Cyclical / growth bid", _cyclical_growth_bid,
     "Oil and copper are demand-sensitive industrial commodities — 'Dr. Copper has a PhD "
     "in economics.' Both rising alongside stocks says the market is pricing stronger "
     "growth and demand, not just financial-asset froth."),

    ("Gold up in a risk-on tape", _gold_divergence,
     "Gold rose but the VIX fell and stocks are up — so this is NOT a fear bid. More often "
     "it's a weaker dollar, falling *real* yields, or inflation/debasement worry. Same price "
     "move, different driver — always ask *which*."),

    ("Narrow rally (weak breadth)", _narrow_rally,
     "The S&P is up but small-caps (Russell 2000) are down — so a handful of mega-caps are "
     "doing the lifting. Narrow breadth is less healthy than a broad advance; it can mask "
     "weakness under the index surface."),

    ("Broad risk-on (strong breadth)", _broad_risk_on,
     "Big-caps AND small-caps rising while the VIX falls = broad participation and rising "
     "risk appetite. Small-caps are higher-beta and more domestic, so their participation "
     "signals conviction, not just a narrow mega-cap squeeze."),
]


def todays_lessons(board):
    """Return the relationships that today's tape is actually demonstrating."""
    f = flatten(board)
    out = []
    for name, trigger, explanation in RELATIONSHIPS:
        try:
            if trigger(f):
                out.append({"name": name, "explanation": explanation})
        except Exception:
            continue
    return out


# ---------------------------------------------------------------------------
# CONCEPTS — the core S&T vocab / mental models. One surfaces per day so the
# foundation builds even when the tape is quiet. (term, definition)
# ---------------------------------------------------------------------------
CONCEPTS = [
    ("Basis point (bp)", "1/100th of a percent. A yield moving 4.20%→4.25% rose 5 bps. "
        "Rates trade in bps because the moves are small but the dollar impact is huge."),
    ("Duration", "How sensitive a bond's (or a stock's) price is to interest-rate moves. "
        "Longer-dated cash flows = more duration = bigger price swing when rates move."),
    ("The yield curve", "Yields plotted from short to long maturities. Its SHAPE (steep, "
        "flat, inverted) is the market's read on growth and Fed policy."),
    ("Real vs nominal yield", "Nominal = the quoted yield. Real = nominal minus expected "
        "inflation. Gold and risk assets care most about REAL yields."),
    ("Risk-on / risk-off", "Risk-on = buying stocks/commodities, selling safe havens. "
        "Risk-off = the reverse (Treasuries, gold, dollar, yen bid). The market's mood."),
    ("VIX (implied volatility)", "The 'fear gauge' — the option market's expected S&P "
        "volatility over the next 30 days. Spikes in stress, drifts low in calm."),
    ("Breadth", "How MANY names participate in a move. A rally on broad breadth (small-caps "
        "too) is healthier than one carried by a few mega-caps."),
    ("Safe haven", "Assets investors flee TO in fear: US Treasuries, gold, the dollar, the "
        "yen. Their bid is a tell that risk appetite is falling."),
    ("Dr. Copper", "Copper's nickname — its demand is so tied to real economic activity "
        "that its price is treated as a barometer of global growth."),
    ("Carry", "The income you earn for holding a position (e.g. a high-yield currency vs a "
        "low-yield one). 'Carry trades' unwind violently in risk-off."),
    ("Term premium", "The extra yield investors demand for lending long instead of rolling "
        "short — compensation for the risk of holding a long bond."),
    ("Beta", "How much an asset moves relative to the market. Small-caps are high-beta — "
        "they amplify both up and down moves."),
    ("Flight to quality", "The risk-off reflex of selling risky assets and crowding into "
        "the safest ones, pushing safe-haven prices up and their yields down."),
    ("The dollar smile", "The theory that the USD strengthens in both extremes — US boom "
        "(strong growth) AND global panic (safe-haven) — and is weakest in the calm middle."),
]


def concept_of_the_day(today=None):
    today = today or date.today()
    return CONCEPTS[today.timetuple().tm_yday % len(CONCEPTS)]


if __name__ == "__main__":
    from markets_data import get_market_board
    board = get_market_board()
    print("\nToday's linkages on the tape:")
    for L in todays_lessons(board):
        print(f"\n• {L['name']}\n  {L['explanation']}")
    term, definition = concept_of_the_day()
    print(f"\nConcept of the day — {term}: {definition}\n")
