"""
commentary.py — the rule-based "WHAT MOVED & THE PATTERN" read.

HONEST CEILING (read this — it's the whole point of being a good tool-builder):
this code can describe WHAT moved and the cross-asset PATTERN it forms (risk-on/off,
curve flattening, dollar direction). It CANNOT truly know WHY — the catalyst, the
headline, the flow. That requires news/AI, which is the real Module 2. So everything
here is framed as observation, never causation. Knowing that boundary — and not
pretending the rule engine "understands" the market — is exactly the BS-detection
skill that matters.

It takes the board from markets_data.get_market_board() and returns:
  {"tone": str, "headline": str, "bullets": [str, ...]}
"""

from markets_data import flatten


def _pct(row):
    return row.get("change_pct") if row and row.get("ok") else None


def _bps(row):
    return row.get("change_bps") if row and row.get("ok") else None


def _arrow(x):
    return "up" if x > 0 else "down" if x < 0 else "flat"


def market_read(board):
    f = flatten(board)
    spx, ndx, dow, rut = f.get("^GSPC"), f.get("^IXIC"), f.get("^DJI"), f.get("^RUT")
    irx, tnx, tyx = f.get("^IRX"), f.get("^TNX"), f.get("^TYX")
    dxy, vix = f.get("DX-Y.NYB"), f.get("^VIX")
    oil, gold, copper = f.get("CL=F"), f.get("GC=F"), f.get("HG=F")

    spx_m, vix_m = _pct(spx), _pct(vix)
    bullets = []

    # --- overall risk tone: equities vs the fear gauge --------------------
    if spx_m is not None and vix_m is not None:
        if spx_m > 0 and vix_m < 0:
            tone, headline = "Risk-on", "Risk-on — stocks up, volatility bleeding off."
        elif spx_m < 0 and vix_m > 0:
            tone, headline = "Risk-off", "Risk-off — stocks down, volatility bid."
        else:
            tone, headline = "Mixed", "Mixed / choppy — stocks and volatility not confirming each other."
    else:
        tone, headline = "Unclear", "Read unavailable — missing equity or volatility data."

    # --- equities + breadth ----------------------------------------------
    if spx_m is not None and _pct(ndx) is not None:
        line = f"Equities: S&P {spx_m:+.2f}%, Nasdaq {_pct(ndx):+.2f}%"
        if _pct(dow) is not None:
            line += f", Dow {_pct(dow):+.2f}%"
        rut_m = _pct(rut)
        if rut_m is not None:
            # Breadth tell: are small-caps confirming the big-caps, or is it narrow?
            if (spx_m > 0) == (rut_m > 0):
                line += f". Small-caps {_arrow(rut_m)} too ({rut_m:+.2f}%) — broad move."
            else:
                line += f". But small-caps {_arrow(rut_m)} ({rut_m:+.2f}%) — narrow, not broad."
        bullets.append(line)

    # --- rates: level + curve shape --------------------------------------
    if _bps(tnx) is not None:
        line = f"Rates: 10Y at {tnx['last']:.2f}% ({_bps(tnx):+.1f} bps)"
        front = _bps(irx) if _bps(irx) is not None else _bps(f.get("^FVX"))
        long_ = _bps(tyx)
        if front is not None and long_ is not None:
            if front > long_ + 0.5:
                line += ". Curve flattening — front end rising faster than the long end."
            elif long_ > front + 0.5:
                line += ". Curve steepening — long end rising faster than the front."
            else:
                line += ". Curve roughly parallel today."
        bullets.append(line)

    # --- dollar ----------------------------------------------------------
    if _pct(dxy) is not None:
        d = _pct(dxy)
        tilt = "a tailwind for commodities & risk" if d < 0 else "a headwind for commodities & risk"
        bullets.append(f"Dollar: DXY {d:+.2f}% ({_arrow(d)}) — {tilt}.")

    # --- commodities: growth (oil/copper) vs fear/inflation (gold) -------
    if _pct(oil) is not None or _pct(gold) is not None:
        parts = []
        if _pct(oil) is not None:
            parts.append(f"oil {_pct(oil):+.2f}% (growth/demand tell)")
        if _pct(copper) is not None:
            parts.append(f"copper {_pct(copper):+.2f}%")
        if _pct(gold) is not None:
            parts.append(f"gold {_pct(gold):+.2f}% (fear/inflation hedge)")
        line = "Commodities: " + ", ".join(parts) + "."
        # Flag the classic divergence worth a second look.
        if tone == "Risk-on" and _pct(gold) is not None and _pct(gold) > 0.3:
            line += " Note: gold bid in a risk-on tape is unusual — watch it."
        bullets.append(line)

    # --- vol -------------------------------------------------------------
    if vix_m is not None:
        bullets.append(f"Volatility: VIX at {vix['last']:.2f} ({vix_m:+.2f}%) — "
                       f"{'calmer' if vix_m < 0 else 'more stressed'} than yesterday.")

    return {"tone": tone, "headline": headline, "bullets": bullets}


if __name__ == "__main__":
    from markets_data import get_market_board
    read = market_read(get_market_board())
    print(f"\n[{read['tone']}] {read['headline']}\n")
    for b in read["bullets"]:
        print(" •", b)
    print()
