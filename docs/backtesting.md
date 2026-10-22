# Phase 4 — event-driven historical simulation

Historical candles → completed features → scripted test intents → simulated orders
and fills → positions/cash → gross and net P&L. This is simulator infrastructure,
not a strategy or evidence of profitability. No optimization, ML, broker transport,
authentication, paper orders or live orders are implemented. Live configuration
continues to be rejected. Groww authenticated behavior remains **UNVERIFIED**.

## Components

`src/trading_bot/backtesting/` contains:

| File | Responsibility |
| --- | --- |
| `config.py`, `orders.py`, `decisions.py` | Validated assumptions, simulated order lifecycle, scripted test inputs |
| `inputs.py` | Existing historical/feature queries, content/selection compatibility checks |
| `clock.py`, `events.py`, `engine.py` | Deterministic event timeline, event records and per-run state |
| `execution.py` | MARKET/LIMIT/STOP_MARKET reachability and base prices |
| `slippage.py`, `costs.py` | Pluggable adverse slippage and versioned, centralized charges |
| `accounting.py` | Decimal cash, weighted-average long inventory, partial exits, flat-to-flat ledger |
| `metrics.py`, `results.py`, `report.py` | Equity metrics, structured outputs and human-readable report |
| `repository.py`, `service.py`, `run.py` | Audited atomic persistence, orchestration and CLI |

The simulator reuses `HistoryQuery.get_snapshot` and `FeatureRepository.get_features`.
It recomputes the selected feature set through the existing engine to verify the
historical content digest, configuration and stored rows before simulation. A changed
candle, missing feature set, mixed adjustment/source, tampered feature row or stale
selection fails. No independent historical provider was added.

## Simulated time and execution rules

The V1 policy is named `STRICT_NEXT_OPEN_SETTLE_ON_COMPLETE_V1`.

1. Candle timestamps identify openings; stored `available_at` identifies completion.
2. Scripted intents explicitly identify a feature's opening timestamp. That row must
   exist and be available by the intent's `created_at`. Any named `required_features`
   must be non-null. Warm-up outputs cannot be used by naming them as required inputs.
   A script using only session context can intentionally act before rolling warm-up ends.
3. An ordinary order may execute only against a bar whose opening is **strictly
   later** than the decision. An intent at 09:20 cannot use the 09:20 opening.
4. For 5-minute bars, the next eligible opening is 09:25. Execution uses that bar's
   permitted price and volume, and is **recorded at its completion, 09:30**. Until
   09:30 the fill/position/cash is not published to subsequent decisions.

This delayed settlement convention deliberately avoids using the execution bar's
final volume/high/low in an earlier event. A fill records both `bar_open` and
`timestamp` (publication/settlement). It does not claim a precise intrabar trade time.
The base MARKET price is the eligible bar's OPEN, not the signal candle's close.
Holding periods and exposure use the settlement clock, not reconstructed tick times.

At equal timestamps the stable clock processes session open, completed bars, scripted
decisions, new bar openings, then session close. Initial equity is recorded before
the first session event. Within a category ties use deterministic record references.
Only the opening price appears in BAR_OPEN; OHLCV execution evaluation happens in
BAR_COMPLETE. Feature/decision/order/fill/portfolio/session events are persisted.
Wall-clock timestamps are used solely for operational run audit start/completion.

Orders have CREATED → ACCEPTED → PENDING transitions, then TRIGGERED,
PARTIALLY_FILLED/FILLED, CANCELLED, REJECTED or EXPIRED. Transition history is retained
inside each order. Local order/fill/trade identifiers are deterministic within their
unique run ID. Simulated tables are separate from any future live-order tables.

## Fill prices and OHLC ambiguity

- **MARKET:** eligible bar open, then adverse slippage.
- **BUY LIMIT:** reachable only when low ≤ limit; base=min(open,limit).
- **SELL LIMIT:** reachable only when high ≥ limit; base=max(open,limit).
- Limits receive adverse slippage only within their limit bound: no buy above its
  limit and no sell below its limit. Touch reachability is an approximation, not
  queue-priority or exchange execution evidence.
- **BUY STOP_MARKET:** trigger when high ≥ trigger; base=max(open,trigger).
- **SELL STOP_MARKET:** trigger when low ≤ trigger; base=min(open,trigger).
- An opening gap beyond a stop uses the adverse opening price, not the old trigger.
  Once triggered, remaining quantity stays market-like on later bars even without
  another touch. Partial fills do not reset the trigger.

Default CONSERVATIVE policy: if a held long position's stop and favorable sell limit
are both reachable, process the stop first and suppress the favorable limit for that
bar. Persist `INTRABAR_AMBIGUITY` and an event with the policy. Optional explicit OCO
exit groups cancel siblings on the first positive fill, including partial fills.
Without OCO, remaining orders are rechecked against actual inventory; no short can
be opened accidentally. These rules never infer a favorable high/low path.

There is no bid/ask, tick-size rounding, queue position or intrabar path reconstruction.
Basis-point slippage is a synthetic adverse-price estimate and can exceed the observed
OHLC envelope; limit bounds still hold. This is not an exchange microstructure model.

## Liquidity, capital and accounting

The default participation rate is 0.1: aggregate filled shares across all orders for
one symbol/bar cannot exceed floor(volume × rate). Capacity is shared in deterministic
order sequence, with adverse stops prioritized when necessary. Remaining order quantity
waits for later bars. Zero-volume bars fill nothing under the constraint. Disabling
participation is explicit and intended for controlled tests; it removes that cap.

Whole shares only, **long inventory only, 1× cash only**. A SELL beyond held quantity
is rejected. Signed-domain concepts are extensible, but short selling and margin are
not implemented or silently enabled. Before each BUY fill, the remaining order's
full notional plus incremental costs must fit available cash; otherwise it is rejected.
No automatic resizing for affordability. Volume-driven partial fills are separate.
Pending orders reserve zero cash; sequential fill-time capital checks are authoritative.

Accounting uses an isolated 40-digit Decimal context. Cash changes by executed
notional and charges. Position basis increases with entries; partial exits release
weighted-average basis, and a full exit releases the exact residual basis. Marking
uses only completed, known closes. Equity=cash+market value; realized/unrealized P&L,
gross/net exposure, running peak and drawdown are recorded chronologically. Inventory
is separate per symbol. Costs are deducted once; slippage is already embedded in fill
prices and is not subtracted from cash a second time.

Each flat-to-flat long cycle is one trade. Multiple entries and partial exits are
aggregated into entry quantity, volume-weighted entry/exit price, entry/exit settlement
times, gross pre-slippage P&L, execution P&L, all fee components, slippage estimate, net
P&L and exit reason. Intermediate realized/unrealized values remain in the equity curve.

## Session-end and missing data

Only complete requested sessions are supported. Existing NSE calendars determine
weekends, holidays, exceptional sessions and actual close times. DAILY timeframe is
rejected; other existing intraday timeframes use calendar slots, including clipped
final bars. Calendar identity/authority and adjustment policy are inherited unchanged.

`exit_minutes_before_close` defaults to 10; it is a simulator configuration, not an
assertion of a broker's actual cutoff. The engine chooses the first available opening
at/after the requested cutoff, or the last bar opening if none remains. A zero-minute
cutoff therefore precommits liquidation to the last bar. Publication still occurs at
that bar's completion. Coarse bars do not provide exact wall-time cutoff execution.

At the cutoff, existing positions receive pre-scheduled market liquidation orders
eligible for the cutoff bar; that pre-scheduled session policy is the only exception
to ordinary strictly-later intent eligibility. Active orders for those positions are
cancelled. Further ordinary execution is blocked from the cutoff onward; new intents
are rejected. Unfilled DAY orders without liquidation cancellation expire at session
end. Forced exits carry `FORCED_SESSION_EXIT`, ordinary costs and slippage. An optional
explicit profile charge can model assisted square-off; default additional charge is 0.

Participation limits also apply to forced exits. If inventory remains at the close,
the run **fails**, with no published successful partial ledger. No position silently
survives overnight. Pending orders do not cross sessions.

Default missing-data policy is **FAIL_RUN**, checked against every expected slot for
every selected symbol before decisions execute. No synthetic missing-candle fill or
forward-filled execution price is created. Corporate-action transformations are absent;
selected RAW/adjusted data remain isolated. There is no corporate-action event database
or guarantee of historically correct vendor vintages. RAW discontinuities remain a
research interpretation limitation, even though inventory is flattened daily.

## Reference cost profile

`config/groww_nse_intraday_reference_v1.yaml`, version **2026-09-24-research-1**, records
public sources, review date, unknown broker effective date, rates, explicit rounding,
GST bases and warnings. It is a fixed research assumption, not authenticated billing
verification or a historical rate schedule.

For cumulative executed turnover T **per order**, brokerage is:
`max(min(20, 0.001*T), min(5, 0.025*T))`, with zero for T=0.
This includes the small-turnover minimum exception documented by
[Groww intraday help](https://groww.in/help/stocks/sx-pricing/what-are-intraday-charges).

The published reference has SELL STT 0.025%, BUY stamp 0.003%, both-side exchange
0.00297%, SEBI 0.0001%, IPFT 0.0001%. GST is 18% on configured brokerage, exchange,
SEBI, IPFT and other charges; STT/stamp are excluded. Intraday DP charges are absent.
The optional additional square-off charge defaults to zero.
[Groww pricing](https://groww.in/pricing).

NSE's [27 February 2026 circular](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf)
changes the exchange/IPFT split from 1 March 2026 to ₹306.99/₹0.01 per crore per side,
while total ₹307 stays unchanged. Groww's public page still shows the earlier split.
The profile preserves the explicitly named Groww reference and emits the discrepancy
warning rather than claiming the old split is verified current exchange billing.

Rounding is explicitly **research-only**, not guessed broker behavior: each cumulative
order component rounds to ₹0.01 HALF_UP; GST uses the rounded configured components
and is rounded likewise. Each partial fill pays cumulative cost minus prior cumulative
cost, so brokerage minima/caps are not charged repeatedly. The source does not establish
all contract-note rounding/aggregation semantics. Runs using this reference therefore
complete with warnings. Review fees before any future production use.

Independent ₹10,000 turnover examples: BUY brokerage 10, stamp .30, exchange .30,
SEBI .01, IPFT .01, GST 1.86, STT 0 → **₹12.48**. SELL has STT 2.50 and no stamp,
other components identical → **₹14.68**. Tests check every component separately,
minimum/cap boundaries, configured GST bases and partial-fill increments.

## Persistence, provenance and failure handling

Migration **0004** creates `backtest_runs`, `backtest_orders`, `backtest_fills`,
`backtest_trades`, `backtest_equity_points`, `backtest_events`. Runs own children by
foreign key; fills additionally reference an order within the same run. Stable sequence
keys order fills/trades/equity/events. Exact Decimal amounts serialize as decimal strings
in JSON payloads and are restored into typed financial records/metrics. UTC timestamps
are also indexed by the per-run chronological sequence. No live-order table is reused.

A RUNNING audit row commits before data loading/calculation. All result rows plus run
completion commit in one transaction. A calculation/validation/result-write failure
rolls back results and marks the audit FAILED separately with a sanitized reason.
`get_result` returns only completed runs. `get_audit` exposes failure metadata. If the
database itself is unavailable, durable audit cannot be promised: a sanitized failure
log/exception carries the generated run ID. Invalid CLI/config syntax rejected before a
run can be constructed yields a nonzero exit, not a fabricated successful run. Process
crashes may leave RUNNING audits; automatic crash recovery is not implemented.

Manifests include historical dataset key/identities, feature-set key and definitions,
source, exchange/segment, symbols, timeframe, range, adjustment, calendar, script,
starting capital, cost/slippage profiles and all execution assumptions. A canonical
configuration key excludes operational run UUID/time and ingestion UUID-only provenance.
Changed slippage, cost version, input content, script or execution assumptions changes
identity. An identical rerun has a new auditable run ID and identical deterministic
result payload (excluding run ID). Results are not deduplicated across separate runs.

## Metrics and visualization-ready data

Reports separate **gross before slippage**, **execution P&L after slippage**, fees and
**net after all charges**. Reconcile:
`gross - slippage - costs = net = ending equity - starting capital`.

Metrics include starting/ending equity, costs/components, brokerage, slippage, total
return, trade/winner/loser counts, win rate, summed positive/negative net trade outcomes
(`gross_profit`/`gross_loss` for profit factor), average/largest winner/loser, expectancy,
turnover, mean holding duration and exposure percentage. Break-even trades count in the
win-rate denominator but neither winner nor loser count. No losers means profit factor
is null, not an invented finite ratio.

Drawdown is measured from chronological equity including open inventory, not just closed
trades: running peak minus equity, divided by peak for percentage. Exposure is the
same-session elapsed-time fraction with positive marked exposure on the settlement
clock; overnight time is excluded.

Sharpe/Sortino use daily closing-equity returns, zero risk-free/target, 252 sessions/year
and at least 20 observed sessions. Sharpe uses sample standard deviation; Sortino uses
root mean squared negative returns over all sampled days. Insufficient/zero-variance or
zero-downside cases return null. No profitability inference comes from fixture ratios.

Structured results supply trades/fills for markers and trade P&L distribution,
equity/drawdown curves, daily P&L and cost breakdowns. No dashboard was built.

## CLI and reproducible demonstration

With `.venv` active, `PYTHONPATH=src` and DATABASE_URL exported:

```sh
alembic upgrade head
python scripts/demonstrate_phase4.py
```

The script creates a disposable schema, imports the committed synthetic 75-bar RELIANCE
fixture, generates baseline features, runs four simulations, checks assertions, writes
compact evidence and drops its schema. It does not overwrite research datasets.

For a retained test database, ingest `tests/fixtures/reliance_backtest.csv` and generate
features for the complete session using the existing Phase 2/3 CLIs. Supply that key:

```sh
python -m trading_bot.backtesting.run \
  --symbol RELIANCE --source local --timeframe 5minute --adjustment RAW \
  --start '2026-01-05T09:15:00+05:30' --end '2026-01-05T15:30:00+05:30' \
  --starting-capital 200000 --feature-set-key '<generated-key>' \
  --decision-script tests/fixtures/backtest_decisions.yaml \
  --cost-model groww_nse_intraday_reference_v1 --slippage-bps 5
```

Optional `--json-output PATH` writes machine-readable results. Repeat `--symbol` for
multiple instruments. `--cost-model zero` and `--disable-participation` are explicit
test options. A selected reviewed profile can be supplied via `--cost-profile`.
Unsupported model/type values fail validation; no dynamic code loading occurs.

Read persisted results through `BacktestRepository(engine).get_result(run_id)` and
audit metadata through `get_audit(run_id)`. The result contains all chronological
records, not future decision inputs. A future real decision source must preserve the
same guarded feature-access contract; arbitrary strategy callbacks are not provided.

Bounded historical/feature snapshots and all simulation events are held in memory.
This V1 is not a streaming, tick-level, short-selling, leverage, settlement-cycle or
vendor-vintage platform. See [actual verification and worked results](phase4-verification.md).
Phase 5 has not begun.
