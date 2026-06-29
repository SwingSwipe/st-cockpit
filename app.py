"""
app.py — S&T COCKPIT  ▸  Module 1: Morning Markets Dashboard

The UI layer. All it does is ASK markets_data.py for the board and DISPLAY it nicely.
No data logic lives here — that's the discipline (engine vs UI) carried over from the
equity bot. Run it with:

    python -m streamlit run app.py

THE HABIT THIS BUILDS: open it every morning, read the cross-asset picture top-to-bottom,
and know where markets are before anyone asks. That "knowing the levels" reflex is the
#1 thing that separates people on an S&T floor.
"""

import streamlit as st

from markets_data import get_market_board


# --- page setup ------------------------------------------------------------
st.set_page_config(page_title="S&T Cockpit — Morning Markets", page_icon="📊", layout="wide")


# Cache the pull for 5 min so flipping around the app doesn't hammer Yahoo.
# The Refresh button below clears this to force a fresh pull.
@st.cache_data(ttl=300, show_spinner="Pulling the market board…")
def load_board():
    return get_market_board()


def fmt_level(value, kind):
    """Format the headline LEVEL the way a trader expects to read it."""
    if kind == "yield":
        return f"{value:.2f}%"
    # price-like: scale decimals to the magnitude (indices vs FX vs commodities)
    if value >= 1000:
        return f"{value:,.2f}"
    if value >= 10:
        return f"{value:.2f}"
    return f"{value:.4f}"          # FX pairs like EUR/USD need the extra decimals


def fmt_move(row):
    """Format the daily MOVE: bps for yields, % for everything else."""
    if row["kind"] == "yield":
        return f"{row['change_bps']:+.1f} bps"
    return f"{row['change_pct']:+.2f}%"


# Emoji headers so the eye finds each asset class instantly (a real desk reads by block).
GROUP_ICONS = {
    "Equities": "📈",
    "Rates": "💵",
    "FX": "💱",
    "Commodities": "🛢️",
    "Volatility": "😨",
}


# --- header ----------------------------------------------------------------
st.title("📊 S&T Cockpit")
st.caption("Module 1 · Morning Markets Dashboard — know where markets are before the day starts.")

top_l, top_r = st.columns([4, 1])
with top_r:
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

board = load_board()

with top_l:
    st.caption(
        f"Data as of **{board['asof']:%Y-%m-%d %H:%M} UTC** · "
        "free Yahoo quotes are ~15 min delayed · moves = latest session vs prior close."
    )


# --- the board -------------------------------------------------------------
for group_name, rows in board["groups"].items():
    icon = GROUP_ICONS.get(group_name, "•")
    st.subheader(f"{icon} {group_name}")

    cols = st.columns(len(rows))
    for col, row in zip(cols, rows):
        with col:
            if not row["ok"]:
                st.metric(row["name"], "—", "no data")
                continue
            st.metric(
                label=row["name"],
                value=fmt_level(row["last"], row["kind"]),
                delta=fmt_move(row),
            )
    st.divider()


# --- the teaching layer: how to actually READ this ------------------------
with st.expander("🧠 How to read this board (the cross-asset picture)"):
    st.markdown(
        """
A trader doesn't read these in isolation — they read the **relationships**:

- **Equities** — Are big-caps *and* small-caps moving together (broad rally) or is it
  narrow (e.g. Nasdaq up, Russell down = just mega-cap tech)? Breadth matters.
- **Rates** — Yields are the price of money and drive everything. Watch the **shape**:
  if the front end (13wk/5Y) rises more than the long end (30Y), the curve is *flattening*
  (often = market pricing tighter Fed / slower growth ahead).
- **FX** — A **weaker dollar (DXY down)** is usually risk-on and a tailwind for commodities
  and non-US assets. Check EUR/JPY/GBP for *where* the dollar is moving.
- **Commodities** — **Oil & copper** = growth/demand signal. **Gold** = fear/inflation hedge;
  gold rising while stocks rise and VIX falls is unusual — worth a second look.
- **VIX** — the "fear gauge." Falling VIX = calm/complacency; spiking VIX = stress.

**The reps:** each morning, before you read any headline, look at the board and say *why*
you think each block moved. Module 2 will add an AI "what moved & why" and make you write
your guess *first*, then grade you. That's where passive watching becomes active reasoning.
        """
    )

st.caption("Built by Arjun Chhabra · S&T Cockpit · grows a new module every few weeks.")
