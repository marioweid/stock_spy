"""Technical indicators derived from daily price history.

Indicators are computed by hand from the OHLCV frame yfinance returns, so no charting
dependency is needed. Each helper takes the price data and returns ``None`` when there is
too little history to compute it, keeping a short series from aborting a report.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import yfinance as yf

from spy_core.models import Technicals


def get_technicals(
    ticker: str,
    *,
    history_fn: Callable[[str], Any] = lambda t: yf.Ticker(t).history(period="1y", interval="1d"),
) -> Technicals:
    """Compute indicators for a ticker from ~1 year of daily history.

    Args:
        ticker: The ticker symbol.
        history_fn: Returns an OHLCV DataFrame for the ticker; injectable for tests.

    Returns:
        A :class:`Technicals`; fields the history is too short to support are ``None``.
    """
    df = history_fn(ticker)
    if df is None or len(df) == 0:
        return Technicals()
    closes = df["Close"].dropna()
    if len(closes) == 0:
        return Technicals()

    last_close = float(closes.iloc[-1])
    macd_line, macd_signal = _macd(closes)
    support, resistance = _levels(df, 30)
    swing_low, swing_high = _levels(df, 10)
    return Technicals(
        last_close=last_close,
        sma_50=_sma(closes, 50),
        sma_200=_sma(closes, 200),
        rsi_14=_rsi(closes, 14),
        macd=macd_line,
        macd_signal=macd_signal,
        atr_14=_atr(df, 14),
        support=support,
        resistance=resistance,
        recent_swing_low=swing_low,
        recent_swing_high=swing_high,
        pct_from_52w_high=_pct_from_extreme(last_close, closes, high=True),
        pct_from_52w_low=_pct_from_extreme(last_close, closes, high=False),
        volatility_30d=_volatility(closes),
    )


def _finite(value: Any) -> float | None:
    """Return ``float(value)`` if finite, else ``None`` (filters NaN/inf)."""
    number = float(value)
    return number if math.isfinite(number) else None


def _sma(closes: Any, period: int) -> float | None:
    """Simple moving average of the last ``period`` closes."""
    if len(closes) < period:
        return None
    return _finite(closes.rolling(period).mean().iloc[-1])


def _rsi(closes: Any, period: int = 14) -> float | None:
    """Relative Strength Index over ``period`` closes (0-100; >70 overbought, <30 oversold)."""
    if len(closes) <= period:
        return None
    delta = closes.diff()
    avg_gain = delta.clip(lower=0).rolling(period).mean().iloc[-1]
    avg_loss = (-delta.clip(upper=0)).rolling(period).mean().iloc[-1]
    if not math.isfinite(float(avg_gain)) or not math.isfinite(float(avg_loss)):
        return None
    if avg_loss == 0:
        return 100.0
    rs = float(avg_gain) / float(avg_loss)
    return 100.0 - (100.0 / (1.0 + rs))


def _macd(closes: Any) -> tuple[float | None, float | None]:
    """MACD line (EMA12 minus EMA26) and its 9-period signal line."""
    if len(closes) < 35:
        return None, None
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    return _finite(macd_line.iloc[-1]), _finite(signal.iloc[-1])


def _atr(df: Any, period: int = 14) -> float | None:
    """Average True Range: typical daily price range over ``period`` bars."""
    if len(df) <= period:
        return None
    high, low, prev_close = df["High"], df["Low"], df["Close"].shift(1)
    true_range = (
        (high - low).combine((high - prev_close).abs(), max).combine((low - prev_close).abs(), max)
    )
    return _finite(true_range.rolling(period).mean().iloc[-1])


def _levels(df: Any, lookback: int) -> tuple[float | None, float | None]:
    """Support (lowest low) and resistance (highest high) over the last ``lookback`` bars."""
    if len(df) < 2:
        return None, None
    window = df.tail(lookback)
    return _finite(window["Low"].min()), _finite(window["High"].max())


def _pct_from_extreme(last_close: float, closes: Any, *, high: bool) -> float | None:
    """Percent distance of the last close from its 52-week high (or low)."""
    window = closes.tail(252)
    reference = float(window.max()) if high else float(window.min())
    if reference == 0:
        return None
    return (last_close - reference) / reference * 100.0


def _volatility(closes: Any) -> float | None:
    """Standard deviation of the last 30 daily returns, in percent."""
    if len(closes) < 3:
        return None
    returns = closes.pct_change().tail(30).dropna()
    if len(returns) < 2:
        return None
    return _finite(returns.std() * 100.0)
