# 📊 S&T Cockpit

A Sales & Trading learning app I build and keep returning to. **One app that grows a new
module every few weeks** — it never "finishes." The bet: *building the tool is the learning.*
To code a duration calculator, you have to actually understand duration. So as I learn a
desk in my S&T studies, I build the matching module here.

Built with Python · [yfinance](https://github.com/ranaroussi/yfinance) (free data) · Streamlit.

## Run it

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

Opens at http://localhost:8501.

## Modules

| # | Module | Status | Teaches |
|---|--------|--------|---------|
| 1 | **Morning Markets Dashboard** | ✅ live | Knowing where markets are — the #1 S&T reflex |
| 2 | AI "what moved & why" + daily quiz | planned | Active reasoning (predict-before-you-peek) |
| 3 | Mental math + brainteaser trainer | planned | What S&T interviews actually test |
| 4 | Bond / rates playground | planned | Fixed-income intuition (price, duration, convexity) |
| 5 | Options & Greeks visualizer | planned | Derivatives intuition |
| 6 | Trade thesis journal | planned | Reasoned views + learning from being wrong |
| 7 | Adaptive S&T quiz engine | planned | Spaced repetition on weak spots |

### Module 1 — Morning Markets Dashboard

The daily-habit anchor. Pulls the cross-asset board a trader watches every morning,
grouped the way a desk thinks about it:

- **📈 Equities** — S&P 500, Nasdaq, Dow, Russell 2000 (risk-on/off, breadth)
- **💵 Rates** — 13wk bill, 5Y, 10Y, 30Y yields (moves shown in **basis points**)
- **💱 FX** — Dollar Index, EUR/USD, USD/JPY, GBP/USD
- **🛢️ Commodities** — WTI, Brent, Gold, Silver, Nat Gas, Copper
- **😨 Volatility** — VIX

**Honest data notes:**
- Free Yahoo quotes are ~15 min delayed; the daily move = latest session vs prior close.
- There's no clean fed funds ticker on Yahoo (it's a policy rate, not a traded price),
  so the **13-week T-bill yield (^IRX)** is used as the front-end / Fed-expectations proxy.
- Yields are reported in **basis points**, not percent — because that's how rates trade.

## Architecture

- `markets_data.py` — the data engine (no UI; run it directly to test: `python markets_data.py`)
- `app.py` — the Streamlit UI (just displays what the engine returns)

Engine/UI split on purpose: the logic is testable from the terminal without ever opening a browser.
