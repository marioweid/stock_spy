"""Plain-language explanations of every metric the reports show.

This is the single source of truth for beginner education: the report formatter pulls
one-line glosses from here, and the LLM prompt is told to define any term it uses. Keys are
the short labels used in reports.
"""

from __future__ import annotations

GLOSSARY: dict[str, str] = {
    "Composite score": (
        "Our 0-100 health score for the stock, blending its finances (45%), price trend "
        "(25%), and recent-news mood (30%). Higher is healthier."
    ),
    "Signal": "Our overall read from the score: Buy, Hold, or Sell. Not financial advice.",
    "Conviction": "How confident the analysis is, from 0 to 1. Higher means more certain.",
    "Position size": (
        "How much of your money to put in one stock, as a percent. Spreading across several "
        "keeps any single mistake small."
    ),
    "P/E": (
        "Price-to-Earnings: the share price divided by yearly profit per share. Roughly how "
        "many years of profit you pay for. Lower is cheaper; very high means pricey or "
        "fast-growing."
    ),
    "Forward P/E": "Like P/E but using profit analysts expect next year instead of last year.",
    "PEG": (
        "P/E divided by growth rate. Around 1 is reasonable for the growth you get; above 2 "
        "looks expensive."
    ),
    "P/B": "Price-to-Book: share price vs the company's net assets. Under ~1 can mean cheap.",
    "Profit margin": "Of every euro of sales, how much becomes profit. Higher is better.",
    "Gross margin": "Sales left after the direct cost of making the product. Higher is better.",
    "Revenue growth": "How fast yearly sales are rising. Positive and steady is good.",
    "Earnings growth": "How fast yearly profit is rising.",
    "ROE": "Return on Equity: profit earned on shareholders' money. Higher means efficient.",
    "Debt/Equity": "How much debt the company uses vs its own money. Lower is safer.",
    "Beta": "How much the stock moves vs the market. Above 1 = swingier than the market.",
    "Market cap": "Total value of all the company's shares — its size.",
    "Dividend yield": "Yearly cash paid to shareholders as a percent of the share price.",
    "Free cash flow": "Cash left after running the business and investing — fuel for dividends.",
    "Analyst target": "The average price professional analysts expect over the next year.",
    "RSI": (
        "Relative Strength Index, 0-100. Above 70 means it has run up fast (overbought); "
        "below 30 means it has fallen hard (oversold)."
    ),
    "MACD": (
        "A momentum gauge from two moving averages. When it crosses above its signal line, "
        "momentum is turning up."
    ),
    "ATR": "Average True Range: how many euros the price typically moves in a day.",
    "SMA": (
        "Simple Moving Average: the average closing price over N days (we use 50 and 200). "
        "Price above them = uptrend; the 200-day is a key long-term line."
    ),
    "Support": "A price level where buyers have stepped in before — a floor that may hold.",
    "Resistance": "A price level where selling appeared before — a ceiling that may cap gains.",
    "52-week range": "The highest and lowest price over the past year.",
    "Volatility": "How jumpy the price is. Higher means bigger, faster swings (more risk).",
    "Unrealized P/L": "Your paper gain or loss — what you'd make/lose if you sold now.",
    "Risk level": "How threatened a holding looks now: low, elevated, high, or critical.",
}


def explain(term: str) -> str:
    """Return the beginner explanation for a term, or an empty string if unknown."""
    return GLOSSARY.get(term, "")
