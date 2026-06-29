"""
app.py — S&T COCKPIT  ▸  Module 1 (Morning Markets Dashboard) + the active-learning layer.

UI only — every bit of data/logic lives in the engine modules:
  markets_data.py  the board (levels, moves, 52wk range, sparklines, market status)
  commentary.py    the rule-based "what moved & the pattern" read
  catalysts.py     the economic calendar (CPI / NFP / FOMC)
  journal.py       predict-before-you-peek scoring + streak/stats

Run:  python -m streamlit run app.py

THE LOOP THIS BUILDS: open it each morning → on the Predict tab, guess the direction of
the headline movers BEFORE you peek → reveal, score, read the pattern → your streak and
hit-rate accrue on My Stats. Passive dashboard → active reasoning reps.
"""

import pandas as pd
import streamlit as st

from markets_data import get_market_board, flatten, PREDICT_SET
from commentary import market_read
from catalysts import upcoming
from journal import score_predictions, log_session, summary_stats


st.set_page_config(page_title="S&T Cockpit", page_icon="📊", layout="wide")


@st.cache_data(ttl=300, show_spinner="Pulling the market board…")
def load_board():
    return get_market_board()


# --- formatting helpers ----------------------------------------------------
def fmt_level(value, kind):
    if value is None:
        return "—"
    if kind == "yield":
        return f"{value:.2f}%"
    if value >= 1000:
        return f"{value:,.2f}"
    if value >= 10:
        return f"{value:.2f}"
    return f"{value:.4f}"


def fmt_move(row):
    if not row.get("ok"):
        return "no data"
    if row["kind"] == "yield":
        return f"{row['change_bps']:+.1f} bps"
    return f"{row['change_pct']:+.2f}%"


GROUP_ICONS = {"Equities": "📈", "Rates": "💵", "FX": "💱", "Commodities": "🛢️", "Volatility": "😨"}


# --- shared header ---------------------------------------------------------
st.title("📊 S&T Cockpit")

board = load_board()
status = board["status"]

hcol1, hcol2, hcol3 = st.columns([3, 2, 1])
with hcol1:
    st.markdown(f"### {status['label']}")
    st.caption(f"{status['detail']} · data as of {board['asof']:%H:%M} UTC · ~15 min delayed")
with hcol3:
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

view = st.segmented_control(
    "view", options=["📊 Dashboard", "🎯 Predict", "📈 My Stats"],
    default="📊 Dashboard", label_visibility="collapsed",
)


# ===========================================================================
# CATALYST STRIP — shown on every view: what's coming and when.
# ===========================================================================
def render_catalyst_strip():
    events = upcoming(4)
    if not events:
        return
    st.caption("🗓️ **Next catalysts** — when rates & risk reprice")
    cols = st.columns(len(events))
    for col, e in zip(cols, events):
        dot = "🔴" if e["importance"] == "high" else "🟡"
        with col:
            st.markdown(f"{dot} **{e['name']}**")
            st.caption(f"{e['weekday']} · {e['when']}")
    st.divider()


# ===========================================================================
# DASHBOARD VIEW
# ===========================================================================
def render_dashboard():
    render_catalyst_strip()

    # --- the rule-based pattern read --------------------------------------
    read = market_read(board)
    box = {"Risk-on": st.success, "Risk-off": st.error}.get(read["tone"], st.warning)
    box(f"**{read['headline']}**")
    st.markdown("\n".join(f"- {b}" for b in read["bullets"]))
    st.caption("Rule-based read — it describes *what* moved & the pattern, not *why*. "
               "The true 'why' (news/catalyst) is the AI layer coming in Module 2.")
    st.divider()

    # --- the board: colored glance tiles + a depth expander per group -----
    for group_name, rows in board["groups"].items():
        st.subheader(f"{GROUP_ICONS.get(group_name, '•')} {group_name}")

        cols = st.columns(len(rows))
        for col, row in zip(cols, rows):
            with col:
                if not row.get("ok"):
                    st.metric(row["name"], "—", "no data")
                    continue
                # VIX reads more naturally inverted: green when fear FALLS.
                delta_color = "inverse" if row["symbol"] == "^VIX" else "normal"
                st.metric(row["name"], fmt_level(row["last"], row["kind"]),
                          fmt_move(row), delta_color=delta_color)

        with st.expander("📐 5-day trend & 52-week range"):
            data = []
            for row in rows:
                if not row.get("ok"):
                    continue
                data.append({
                    "Name": row["name"],
                    "Last": fmt_level(row["last"], row["kind"]),
                    "Move": fmt_move(row),
                    "Trend (30d)": row["spark"],
                    "52wk range": row["range_pct"],
                })
            if data:
                st.dataframe(
                    pd.DataFrame(data), hide_index=True, use_container_width=True,
                    column_config={
                        "Trend (30d)": st.column_config.LineChartColumn("Trend (30d)", width="medium"),
                        "52wk range": st.column_config.ProgressColumn(
                            "52wk range", min_value=0, max_value=100, format="%.0f%%"),
                    },
                )
                st.caption("52wk range: 0% = at the 1-year low, 100% = at the 1-year high.")
        st.divider()

    with st.expander("🧠 How to read this board (the cross-asset picture)"):
        st.markdown(
            """
Read the **relationships**, not the tickers in isolation:
- **Equities** — big-caps *and* small-caps together = broad; Nasdaq up but Russell down = narrow (just mega-cap tech). Breadth matters.
- **Rates** — yields are the price of money. Watch the **curve shape**: front end rising faster than the long end = *flattening* (often tighter-Fed / slower-growth pricing).
- **FX** — a **weaker dollar (DXY down)** is usually risk-on and a commodity tailwind.
- **Commodities** — **oil & copper** = growth/demand; **gold** = fear/inflation hedge. Gold up *into* a risk-on tape is unusual.
- **VIX** — falling = calm/complacency; spiking = stress.
            """
        )


# ===========================================================================
# PREDICT VIEW — predict-before-you-peek
# ===========================================================================
def render_predict():
    render_catalyst_strip()
    bflat = flatten(board)

    st.subheader("🎯 Predict before you peek")
    st.caption("Call the **direction** of today's headline movers *before* you see them. "
               "This is the rep that turns watching into reasoning.")

    if not st.session_state.get("predict_revealed"):
        st.markdown("**Up or Down today?** (vs the prior close)")
        picks = {}
        cols = st.columns(len(PREDICT_SET))
        for col, (symbol, label) in zip(cols, PREDICT_SET):
            with col:
                picks[symbol] = st.radio(label, ["Up", "Down"], index=None, key=f"pick_{symbol}")

        ready = all(v is not None for v in picks.values())
        if st.button("👀 Reveal & score", type="primary", disabled=not ready):
            result = score_predictions(picks, bflat)
            log_session(result)                       # persist the scored session
            st.session_state["predict_result"] = result
            st.session_state["predict_revealed"] = True
            st.rerun()
        if not ready:
            st.caption("Pick a direction for every instrument to reveal.")
        return

    # --- revealed: show the score + the truth ----------------------------
    result = st.session_state["predict_result"]
    c, t = result["correct"], result["total"]
    pct = (c / t * 100) if t else 0
    st.metric("Today's score", f"{c} / {t}", f"{pct:.0f}% directional")

    rows = [{
        "Instrument": d["name"],
        "Your call": d["guess"],
        "Actual": d["actual_dir"],
        "Move": d["move_str"],
        "Result": "✅ hit" if d["hit"] else "❌ miss",
    } for d in result["details"]]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    # Now teach: show the pattern read so he learns WHY his calls were right/wrong.
    read = market_read(board)
    st.markdown(f"**Pattern read — {read['headline']}**")
    st.markdown("\n".join(f"- {b}" for b in read["bullets"]))

    st.success("Logged to your streak. Come back tomorrow.")
    if st.button("🔄 New round"):
        for symbol, _ in PREDICT_SET:
            st.session_state.pop(f"pick_{symbol}", None)
        st.session_state["predict_revealed"] = False
        st.rerun()


# ===========================================================================
# MY STATS VIEW — streak + hit-rate over time
# ===========================================================================
def render_stats():
    s = summary_stats()
    st.subheader("📈 My Stats")

    c1, c2, c3 = st.columns(3)
    c1.metric("🔥 Streak", f"{s['streak']} day{'s' if s['streak'] != 1 else ''}")
    c2.metric("Sessions logged", s["sessions"])
    c3.metric("Directional accuracy", f"{s['accuracy']:.0f}%",
              f"{s['total_correct']}/{s['total_calls']} calls")

    if s["history"]:
        df = pd.DataFrame(s["history"])
        df["accuracy"] = (df["correct"] / df["total"] * 100).round(0)
        df = df.set_index("date")
        # A line needs at least two points to draw a range — show the trend only
        # once there's history to trend; one session just gets the table.
        if len(df) >= 2:
            st.markdown("**Accuracy over time**")
            st.line_chart(df["accuracy"], y_label="% correct")
        st.markdown("**History**")
        st.dataframe(
            df.reset_index()[["date", "correct", "total", "accuracy"]],
            hide_index=True, use_container_width=True,
            column_config={"accuracy": st.column_config.NumberColumn("accuracy", format="%.0f%%")},
        )
    else:
        st.info("No sessions yet — head to the **🎯 Predict** tab and make your first calls. "
                "Each morning you log builds the streak (and the recruiting line: "
                "\"called markets every morning for X months\").")

    st.caption("Honest note: a few sessions is pure noise. The value is in months of "
               "consistency — show up daily, judge the trend later, don't over-read a small sample.")


# --- route -----------------------------------------------------------------
if view == "🎯 Predict":
    render_predict()
elif view == "📈 My Stats":
    render_stats()
else:
    render_dashboard()

st.divider()
st.caption("Built by Arjun Chhabra · S&T Cockpit · github.com/SwingSwipe/st-cockpit · grows a new module every few weeks.")
