"""
journal.py — PREDICT-BEFORE-YOU-PEEK scoring + STATS OVER TIME (streak & hit-rate).

This is the heart of the cockpit's learning loop:
  1. Each morning you guess the DIRECTION (Up/Down) of a few headline instruments
     BEFORE seeing the moves.
  2. We score you, and log it.
  3. Over weeks you see your hit-rate and a daily streak — proof you showed up and
     a real recruiting line ("called markets every morning for X months, Y% directional").

Persistence is a simple local CSV (predictions_log.csv) — your personal data, gitignored
so it never gets committed or exposed. Same file-IO lesson as the equity bot's watchlist.
"""

import csv
import json
import os
from datetime import date, timedelta

LOG_PATH = os.path.join(os.path.dirname(__file__), "predictions_log.csv")
FIELDS = ["date", "correct", "total", "picks"]


def score_predictions(picks, board_flat):
    """
    picks: {symbol: "Up" | "Down"}  (the user's guesses)
    board_flat: markets_data.flatten(board)  (symbol -> row with the actual move)

    Returns {"correct", "total", "details": [{symbol, name, guess, actual_dir, move_str, hit}]}.
    A guess is right if its direction matches the sign of the actual move.
    """
    details, correct = [], 0
    for symbol, guess in picks.items():
        row = board_flat.get(symbol)
        if not row or not row.get("ok"):
            continue
        if row["kind"] == "yield":
            move = row["change_bps"]
            move_str = f"{move:+.1f} bps"
        else:
            move = row["change_pct"]
            move_str = f"{move:+.2f}%"
        actual_dir = "Up" if move > 0 else "Down" if move < 0 else "Flat"
        hit = (guess == actual_dir)
        if hit:
            correct += 1
        details.append({"symbol": symbol, "name": row["name"], "guess": guess,
                        "actual_dir": actual_dir, "move_str": move_str, "hit": hit})
    return {"correct": correct, "total": len(details), "details": details}


def log_session(result, today=None):
    """Append (or replace) today's scored session in the CSV. One session per day."""
    today = (today or date.today()).isoformat()
    rows = _read_all()
    rows = [r for r in rows if r["date"] != today]   # replace today's if re-run
    rows.append({
        "date": today,
        "correct": result["correct"],
        "total": result["total"],
        "picks": json.dumps({d["symbol"]: d["guess"] for d in result["details"]}),
    })
    rows.sort(key=lambda r: r["date"])
    with open(LOG_PATH, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _read_all():
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_history():
    """All logged sessions, oldest first, with ints parsed."""
    out = []
    for r in _read_all():
        try:
            out.append({"date": r["date"],
                        "correct": int(r["correct"]),
                        "total": int(r["total"])})
        except (ValueError, KeyError):
            continue
    return sorted(out, key=lambda r: r["date"])


def current_streak(today=None):
    """
    Consecutive-day streak of logged sessions, counted back from the most recent entry.
    A gap (a missed day) breaks it. Returns 0 if no history.
    """
    hist = load_history()
    if not hist:
        return 0
    days = sorted({date.fromisoformat(r["date"]) for r in hist})
    streak, cursor = 1, days[-1]
    for d in reversed(days[:-1]):
        if d == cursor - timedelta(days=1):
            streak += 1
            cursor = d
        else:
            break
    return streak


def summary_stats():
    """Headline numbers for the My Stats view."""
    hist = load_history()
    sessions = len(hist)
    total_correct = sum(r["correct"] for r in hist)
    total_calls = sum(r["total"] for r in hist)
    accuracy = (total_correct / total_calls * 100.0) if total_calls else 0.0
    return {
        "sessions": sessions,
        "streak": current_streak(),
        "accuracy": accuracy,
        "total_correct": total_correct,
        "total_calls": total_calls,
        "history": hist,
    }


if __name__ == "__main__":
    print("History:", load_history())
    print("Streak:", current_streak())
    print("Summary:", summary_stats())
