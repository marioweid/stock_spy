1. The "Sideways Base" Protocol (Stagnant Stalls)

    Definition: Occurs when a stock triggers your stop-loss but, instead of aggressively dropping or instantly bouncing, it sits flat and consolidates right around or slightly below that level for days.

    System Treatment: The app must treat this as a dead trade state that cannot be modified. To trade this asset again, it must be qualified as a completely separate entry candidate.

    The Trigger Rule: The backend should flag the asset as "stagnant" and require a "Trigger Candle" (the price breaking and closing above the highest point of that 2-day flat consolidation) before a new position calculation can be initialized.

2. The Time-Out & Trailing Stop Engine (Target Not Reached)

If a trade gets stuck in limbo and never reaches your planned profit target, the engine must handle the execution using a timeout mechanism or a dynamic trailing protocol. The database must track these four specific Exit Reasons to evaluate your execution quality:

    TARGET: Hit your planned profit target (Max Profit).

    STOP: Hit your planned stop-loss floor (Max Defined Loss).

    TIME_OUT (The Timeout Mechanism): Automatically flags a trade for manual exit if a set period passes (e.g., 10 trading days) without hitting either bracket target. This prevents capital from being locked up in dead, non-moving assets.

    TRAILED: Triggered a dynamic trailing stop-loss. The logic dictates that once a stock completes 50% of its journey toward the profit target, the stop-loss automatically moves up to Break-Even (Entry Price) to ensure a risk-free trade. Alternatively, it trails behind structural daily lows to lock in partial profits if the stock reverses early.





I am providing additional specification context regarding how the backend engine and database state machine must handle stagnant stocks and unfulfilled targets.

Please integrate these specific business rules into the FastAPI backend and SQLAlchemy data models:
1. Implement the "Sideways Base" logic: Ensure a triggered stop-loss completely destroys the previous trade state. Any re-entry after days of flat consolidation must be handled as a completely fresh trade ID with new parameters.
2. Implement the 4 distinct Exit Statuses (TARGET, STOP, TIME_OUT, TRAILED) within the trade tracking schema.
3. Write a helper function in Python that monitors "Days in Trade" to flag positions that hit a 10-day TIME_OUT, as well as a function that triggers a Break-Even stop-loss adjustment once a position reaches 50% of its target distance.
4. For all targets and i actions i need to take f.e. move the stop loss i want a telegram notification
