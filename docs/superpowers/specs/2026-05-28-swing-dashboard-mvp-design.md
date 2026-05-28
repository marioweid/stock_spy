# Swing Dashboard MVP Design

## Goal

Build a local-first dashboard for managing swing trades produced by `swing_spy`.
The dashboard helps review potential swing candidates, record trades actually bought in an
external broker, monitor open positions, and close trades only after explicit user confirmation.

The MVP is a trading assistant and ledger, not a broker. It never places orders and never assumes
that an order filled.

## Scope

### In Scope

- Streamlit dashboard for local use.
- Candidate cards sourced only from the existing `swing_spy` scanner.
- Candidate actions:
  - `Executed`: record that the user already bought the trade in an external broker.
  - `Skip 1d`: hide the candidate for one day.
- Execution confirmation form with planned values prefilled.
- Open positions view with current price, stop, target, P/L, days held, deadline, and status.
- Monitoring flags for stop reached, target reached, and deadline reached.
- Exit confirmation form with suggested exit values prefilled.
- Closed trade persistence for future performance dashboards.
- Service-layer tests that prove Streamlit is only a UI adapter.

### Out of Scope

- Manual candidate entry.
- Editing the ticker universe or watched-stock list.
- Deep stock analysis agents.
- Broker integration or automatic trade execution.
- Tax calculations.
- Full performance analytics dashboard.
- Automatic position closure.

## Architecture

Streamlit must stay thin. It renders pages, collects form input, and calls plain Python services.
It must not contain trading rules, persistence rules, state transitions, price checks, or P/L
calculations.

Proposed modules:

- `swing_spy.dashboard_app`
  - Streamlit pages and components only.
  - Calls service methods with user input.
  - Renders returned models.
- `swing_spy.trade_lifecycle`
  - Candidate and position lifecycle service.
  - Executes candidates, skips candidates, evaluates position status, and closes positions.
- `swing_spy.trade_store`
  - SQLite repository for candidate snapshots, skips, open positions, and closed trades.
- `swing_spy.position_pricing`
  - Price lookup adapter for open-position monitoring.
  - Uses existing provider patterns so it can be swapped later.
- `swing_spy.trade_models`
  - Pydantic or dataclass models for dashboard trade state.

The service layer should be callable later from FastAPI without rewriting business logic:

```python
service.execute_candidate(candidate_id, actual_entry, shares, executed_at)
service.close_position(position_id, exit_price, shares, exit_reason)
service.list_open_positions()
```

## Candidate Cards

The potential swing trades view displays candidates as decision cards, four per row on desktop
where space allows.

Each card shows:

- Ticker with strong contrast and prominent type.
- Setup type.
- Currency.
- Entry.
- Stop.
- Target.
- R:R score.
- Planned share count.
- Cost and risk amount when space allows.
- Warning states returned by the scanner, such as imminent earnings.
- `Executed` action.
- `Skip 1d` action.

The ticker and values must be readable. Avoid low-contrast grey for important values.
Below-minimum R:R candidates remain filtered out by the existing scanner in the MVP.

## Candidate State

Candidate snapshots are persisted when `swing_spy` finds a dashboard-worthy candidate. A snapshot
stores the plan as it existed when generated:

- Ticker.
- Setup kind.
- Currency.
- Entry.
- Stop.
- Target.
- R:R.
- Shares.
- Cost.
- Risk amount.
- Reward amount.
- Rationale.
- Earnings warning.
- Candidate signature.
- Created timestamp.

Candidate states:

- `ACTIVE`: visible in potential swing trades.
- `SKIPPED_UNTIL`: hidden until the skip expiry; the MVP skip duration is one day.
- `EXECUTED`: no longer visible as a candidate and linked to an open position.

## Execution Flow

`Executed` means the user already bought the trade in an external broker, for example Trade
Republic, and wants this app to monitor it.

The app opens a confirmation form before creating a position. Planned values are prefilled, but
the user can correct real execution details:

- Actual entry price.
- Share count.
- Execution timestamp.
- Optional note.

After confirmation, the app creates an open position and preserves the original candidate plan for
later comparison.

## Open Positions

The open positions view shows positions created from executed candidates.

Each position shows:

- Ticker.
- Actual entry price.
- Share count.
- Current price.
- Stop.
- Target.
- Unrealized P/L.
- Days held.
- Deadline status.
- Trigger status.
- Actions relevant to the current state.

Position states:

- `OPEN`: actively monitored.
- `STOP_REACHED`: current price is at or below stop.
- `TARGET_REACHED`: current price is at or above target.
- `DEADLINE_REACHED`: max holding days reached.
- `CLOSED`: position has been explicitly closed by user confirmation.

Monitoring states are advisory. They do not close trades automatically.

## Exit Flow

When a position reaches stop, target, or deadline, the card becomes actionable. The user confirms
the actual external broker sale before the app closes the position.

Exit forms are prefilled based on the trigger:

- Stop reached: prefill exit price with stop.
- Target reached: prefill exit price with target.
- Deadline reached: prefill exit price with current price.

The user can correct:

- Actual exit price.
- Shares sold.
- Exit timestamp.
- Exit reason.
- Optional note.

The MVP supports full-position closes. Partial exits are out of scope.

Closed trades store gross P/L based on actual entry, actual exit, and shares sold.

## Human-In-The-Loop Rules

Because this app supports decisions around real money:

- The app never places broker orders.
- The app never assumes an order filled.
- The app never closes a trade from a price check alone.
- Every entry requires explicit user confirmation after buying externally.
- Every exit requires explicit user confirmation after selling externally.
- Defaults reduce typing but never replace confirmation.
- Service tests must prove monitoring flags do not create closed trades.

## Data Flow

1. `swing_spy` scanner evaluates the configured universe.
2. Passing setups are converted into persisted candidate snapshots.
3. Streamlit lists active candidate snapshots.
4. User skips or executes a candidate.
5. Executed candidate creates an open position after confirmation.
6. Position monitoring refreshes current prices and computes advisory states.
7. User confirms external sale when ready.
8. Service closes the position and writes a closed trade record.

## Error Handling

- Missing candidate: show a clear message that the candidate no longer exists or is no longer
  active.
- Duplicate execution: reject executing a candidate already linked to a position.
- Invalid prices or share counts: fail fast with actionable validation errors.
- Price lookup failure: keep the position visible, mark current price as unavailable, and avoid
  changing status from stale data.
- Database errors: surface the operation that failed and avoid partial lifecycle changes.

## Testing

Focus tests on services, not Streamlit widgets.

Required behavior tests:

- Candidate can be skipped for one day and becomes visible after the skip expires.
- Executing a candidate creates an open position and preserves the original plan.
- Actual execution values override planned values for the open position.
- Price below stop returns `STOP_REACHED`.
- Price above target returns `TARGET_REACHED`.
- Deadline expiry returns `DEADLINE_REACHED`.
- Monitoring flags never close a position.
- Only an explicit close command creates a closed trade.
- Closed trade gross P/L is computed from actual values.

Verification commands:

```bash
uv run pytest -q tests/swing_spy
uv run ruff check .
uv run ty check
```

## Future Extensions

- Editable watched-stock universe.
- Manual candidate entry.
- FastAPI backend using the same services.
- React frontend using the same lifecycle API.
- Deep analysis agents attached to candidate or position cards.
- Partial exits.
- Fees, tax, and full performance analytics.
