### Module E: Notification & Event Alert Engine
The backend must feature a notification manager (`alert_manager.py`) that processes incoming data streams and sends a web-hook alert (or console log notice) when specific criteria are met.

Please code functions to track and trigger alerts for:
1. **Earnings Safeguard:** Ingest corporate calendar data to send a warning alert if an open position is within 3 days of an Earnings Release.
2. **Dividend Disruption:** Send an alert 48 hours prior to an Ex-Dividend date for any stock currently held in the database.
3. **RSI Scanner:** Daily check on the watchlist; trigger an "Oversold Opportunity" alert if daily RSI falls below 30.
4. **Breakout Tracker:** Monitor the 3-day local price channel high. Trigger a notification if the current live price breaks above that high to signal a potential swing trading entry.


As a swing trader, your main goal is to find volatility (price movement) while protecting yourself from unpredictable price spikes that can blow past your stop-loss.

When setting up custom automated notifications in your app, you should look for two categories of events: Scheduled Calendar Events (fundamental risks you want to avoid) and Technical Price Triggers (opportunities you want to trade).

Here are the exact events you should monitor, why they matter, and how to define them in your notification engine.
1. Scheduled Corporate Events (The "Risk Avoidance" Alerts)

These are events announced by the company weeks in advance. For a swing trader, these are usually no-trade zones where you want your app to warn you to stay away or close your position.
A. Earnings Reports (Quarterly Closings / Quartalszahlen)

    What it is: Every three months, companies release their financial results.

    Why it matters: Earnings are wildly unpredictable. A stock can gap down 15% overnight, completely skipping past your 1% stop-loss and costing you much more money than planned.

    Your Notification Rule: "Alert me 3 days before any stock on my watchlist or in my active portfolio releases earnings." (This gives you time to close the swing trade safely before the announcement).

B. Dividend Ex-Dates (Ex-Dividenden-Tag)

    What it is: The specific day a stock cuts its dividend payout from its share price.

    Why it matters: On the ex-dividend morning, a stock’s price automatically drops by the exact amount of the dividend payouts (e.g., if Munich Re pays a €15 dividend, the stock price automatically drops €15 at market open). This is an artificial drop that can accidentally trigger your technical stop-loss.

    Your Notification Rule: "Alert me 2 days before a stock's Ex-Dividend date."

2. Technical Price Triggers (The "Opportunity" Alerts)

These alerts are calculated by your Python backend using live market data (yfinance). They tell you when a stock is perfectly set up for a trade.
C. Major Moving Average Touch (Trend Support)

    What it is: When a stock pulls back and touches a historically strong moving average, like the 50-day or 200-day Exponential Moving Average (EMA).

    Why it matters: Institutional buyers love to buy high-quality stocks at these specific moving averages. It often acts as a trampoline for a swing trade bounce.

    Your Notification Rule: "Alert me when the price is within 0.5% of its 50-day EMA."

D. RSI Extreme Levels (Oversold / Overbought)

    What it is: The Relative Strength Index (RSI) measures market momentum on a scale of 0 to 100.

    Why it matters: If a stock's daily RSI drops below 30, it is statistically "oversold" (sellers are exhausted, and a bounce is likely). If it goes above 70, it is "overbought" (too hot to buy right now).

    Your Notification Rule: "Alert me if a stock on my watchlist drops below an RSI of 30."

E. The Consolidation Breakout (The Sideways Tracker)

    What it is: This perfectly fits the "Sideways Base" protocol we just discussed.

    Why it matters: When a stock sits flat for 2 to 3 days, you don't want to look at it every hour. You want an alert the exact second it wakes up.

    Your Notification Rule: "Alert me if the price breaks above the maximum high of the last 3 days."