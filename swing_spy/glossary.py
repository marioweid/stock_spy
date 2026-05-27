"""Plain-language explanations of every term a candidate alert shows."""

from __future__ import annotations

GLOSSARY: dict[str, str] = {
    "Swing trade": "A trade held days to weeks to catch one move, not a long-term hold.",
    "Entry zone": "The price range to buy in if you take the trade.",
    "Stop-loss": (
        "A pre-set exit price that caps your loss if the trade goes wrong. Plan it before buying."
    ),
    "Target": "A planned price to take profit.",
    "Risk/Reward": (
        "Potential gain vs potential loss on a trade. 2 means you aim to make twice what you risk."
    ),
    "Position size": (
        "How many shares to buy. Sized so that being stopped out loses only ~1% of your account."
    ),
    "Support": "A price level where buyers have stepped in before — a floor that may hold.",
    "Resistance": "A price level where selling appeared before — a ceiling that may cap gains.",
    "RSI": (
        "Relative Strength Index, 0-100. Above 70 means it has run up fast (overbought); "
        "below 30 means it has fallen hard (oversold)."
    ),
    "SMA": (
        "Simple Moving Average: the average closing price over N days (we use 50 and 200). "
        "Price above them = uptrend; the 200-day is a key long-term line."
    ),
    "ATR": "Average True Range: how many currency units the price typically moves in a day.",
    "Pullback": "A temporary dip within an uptrend — a chance to buy before it resumes.",
}


def explain(term: str) -> str:
    """Return the beginner explanation for a term, or an empty string if unknown."""
    return GLOSSARY.get(term, "")
