"""Excel ledgers of every trade of the YouTube sweep strategy, one per version.

Sheets: Summary (rules, assumptions, totals), Trades (entry/exit time and price,
P&L before costs, each cost, net P&L, running total), Daily (end-of-day totals and
account balance), Yearly. Totals are Excel formulas. 2014-2024 only.

Writes docs/xauusd-sweep-trades-<target>-<stop>.xlsx for 2R/3R x close/touch stop.
Needs openpyxl (not in the pinned .venv); run with a Python that has it:
Usage: PYTHONPATH=src /opt/anaconda3/bin/python3 scripts/export_xauusd_sweep_ledger.py
"""

from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from trading_bot.backtesting.session_window import Array, CostModel, Sizing, load_bars
from trading_bot.backtesting.sweep_strategy import (
    SweepRule,
    TradingDay,
    build_days,
    run_sweep,
)
from trading_bot.data.histdata_bulk import BARS_DIR

COSTS_YAML = Path("config/xauusd_costs_expensive.yaml")
OUT_DIR = Path("docs")
RULES = [SweepRule(t, s) for t in (2.0, 3.0) for s in ("close", "touch")]  # type: ignore[arg-type]
DEV = range(2014, 2025)
NY = ZoneInfo("America/New_York")
FONT = "Arial"
USD = '#,##0.00;[Red]-#,##0.00;"-"'
PRICE = "#,##0.000"
BOLD = Font(name=FONT, bold=True)
HEAD_FILL = PatternFill("solid", fgColor="DDE4EE")


def ny(epoch: int) -> datetime:
    return datetime.fromtimestamp(epoch, UTC).astimezone(NY).replace(tzinfo=None)


def header(ws: Worksheet, cols: list[tuple[str, int]]) -> None:
    for i, (name, width) in enumerate(cols, 1):
        c = ws.cell(row=1, column=i, value=name)
        c.font, c.fill = BOLD, HEAD_FILL
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = "A2"


def main() -> None:
    costs = CostModel.from_yaml(COSTS_YAML)
    sizing = Sizing()
    bars = load_bars(BARS_DIR, 201401, 202412)
    days = build_days(bars)
    for rule in RULES:
        export(rule, bars, days, costs, sizing)


def export(
    rule: SweepRule,
    bars: dict[str, Array],
    days: list[TradingDay],
    costs: CostModel,
    sizing: Sizing,
) -> None:
    out = OUT_DIR / f"xauusd-sweep-trades-{rule.name.replace('/', '-')}.xlsx"
    trades, n_days = run_sweep(bars, days, rule, costs, sizing, DEV)
    pf = costs.per_fill

    wb = Workbook()
    summary = wb.active
    summary.title = "Summary"
    tr = wb.create_sheet("Trades")
    header(
        tr,
        [
            ("Trade #", 8),
            ("Trading day", 12),
            ("Direction", 9),
            ("Entry time (New York)", 17),
            ("Entry price (chart mid)", 12),
            ("Entry fill (incl. spread + costs)", 13),
            ("Stop", 11),
            ("Target", 11),
            ("Exit time (New York)", 17),
            ("Exit price (chart mid)", 12),
            ("Exit fill (incl. spread + costs)", 13),
            ("Exit reason", 10),
            ("Lots", 7),
            ("Ounces", 8),
            ("P&L before costs $", 12),
            ("Spread $", 10),
            ("Extra spread + slippage $", 12),
            ("Commission $", 11),
            ("Net P&L $", 11),
            ("Running total $", 13),
        ],
    )
    m = bars["minute_utc"]
    for r, t in enumerate(trades, 2):
        s, k, d = t.entry_minute, t.exit_bar, t.direction
        half_in = float(bars["ask_open"][s] - bars["bid_open"][s]) / 2
        at_close = t.exit_reason in ("stop", "time_exit")  # close-based exits
        side = "close" if at_close else "open"
        half_out = float(bars[f"ask_{side}"][k] - bars[f"bid_{side}"][k]) / 2
        entry_mid = float(bars["bid_open"][s]) + half_in
        exit_mid = t.exit + d * (pf + half_out)
        row = [
            r - 1,
            t.day,
            "BUY" if d == 1 else "SELL",
            ny(int(m[s])),
            entry_mid,
            t.entry,
            t.stop,
            t.target,
            ny(int(m[k])),
            exit_mid,
            t.exit,
            {"stop": "Stop", "target": "Target", "time_exit": "End of day"}[
                t.exit_reason
            ],
            t.lots,
            f"=M{r}*100",
            f'=(J{r}-E{r})*IF(C{r}="BUY",1,-1)*N{r}',
            (half_in + half_out) * 100 * t.lots,
            2 * pf * 100 * t.lots,
            costs.commission_per_lot * t.lots,
            f"=O{r}-P{r}-Q{r}-R{r}",
            f"=S{r}" if r == 2 else f"=T{r - 1}+S{r}",
        ]
        for col, v in enumerate(row, 1):
            c = tr.cell(row=r, column=col, value=v)
            c.font = Font(name=FONT)
        assert (
            abs(
                (exit_mid - entry_mid) * d * 100 * t.lots
                - row[15]
                - row[16]
                - row[17]
                - t.pnl_usd  # type: ignore[operator]
            )
            < 0.01
        ), t
        for col in (5, 6, 7, 8, 10, 11):
            tr.cell(row=r, column=col).number_format = PRICE
        for col in (15, 16, 17, 18, 19, 20):
            tr.cell(row=r, column=col).number_format = USD
        tr.cell(row=r, column=2).number_format = "yyyy-mm-dd"
        for col in (4, 9):
            tr.cell(row=r, column=col).number_format = "yyyy-mm-dd hh:mm"
    last = len(trades) + 1

    dy = wb.create_sheet("Daily")
    header(
        dy,
        [
            ("Trading day", 12),
            ("Year", 7),
            ("Trades", 8),
            ("Winning trades", 9),
            ("Losing trades", 9),
            ("P&L before costs $", 13),
            ("Total costs $", 12),
            ("Net P&L at end of day $", 14),
            ("Account balance $", 14),
        ],
    )
    trade_days = sorted({t.day for t in trades})
    rng = f"Trades!$B$2:$B${last}"
    for r, day in enumerate(trade_days, 2):
        vals = [
            day,
            f"=YEAR(A{r})",
            f"=COUNTIF({rng},A{r})",
            f'=COUNTIFS({rng},A{r},Trades!$S$2:$S${last},">0")',
            f"=C{r}-D{r}",
            f"=SUMIF({rng},A{r},Trades!$O$2:$O${last})",
            f"=SUMIF({rng},A{r},Trades!$P$2:$P${last})"
            f"+SUMIF({rng},A{r},Trades!$Q$2:$Q${last})"
            f"+SUMIF({rng},A{r},Trades!$R$2:$R${last})",
            f"=F{r}-G{r}",
            f"=Summary!$B$4+H{r}" if r == 2 else f"=I{r - 1}+H{r}",
        ]
        for col, v in enumerate(vals, 1):
            dy.cell(row=r, column=col, value=v).font = Font(name=FONT)
        dy.cell(row=r, column=1).number_format = "yyyy-mm-dd"
        dy.cell(row=r, column=2).number_format = "0"
        for col in (6, 7, 8, 9):
            dy.cell(row=r, column=col).number_format = USD
    dlast = len(trade_days) + 1

    yr = wb.create_sheet("Yearly")
    header(
        yr,
        [
            ("Year", 8),
            ("Days with trades", 10),
            ("Trades", 8),
            ("Winning trades", 9),
            ("Win rate", 9),
            ("P&L before costs $", 13),
            ("Total costs $", 12),
            ("Net P&L $", 12),
            ("Worst day $", 11),
            ("Best day $", 11),
        ],
    )
    yrng = f"Daily!$B$2:$B${dlast}"
    for r, year in enumerate(DEV, 2):
        vals = [
            year,
            f"=COUNTIF({yrng},A{r})",
            f"=SUMIF({yrng},A{r},Daily!$C$2:$C${dlast})",
            f"=SUMIF({yrng},A{r},Daily!$D$2:$D${dlast})",
            f"=IF(C{r}=0,0,D{r}/C{r})",
            f"=SUMIF({yrng},A{r},Daily!$F$2:$F${dlast})",
            f"=SUMIF({yrng},A{r},Daily!$G$2:$G${dlast})",
            f"=SUMIF({yrng},A{r},Daily!$H$2:$H${dlast})",
            f"=_xlfn.MINIFS(Daily!$H$2:$H${dlast},{yrng},A{r})",
            f"=_xlfn.MAXIFS(Daily!$H$2:$H${dlast},{yrng},A{r})",
        ]
        for col, v in enumerate(vals, 1):
            yr.cell(row=r, column=col, value=v).font = Font(name=FONT)
        yr.cell(row=r, column=5).number_format = "0.0%"
        for col in (6, 7, 8, 9, 10):
            yr.cell(row=r, column=col).number_format = USD
    tot = len(DEV) + 2
    yr.cell(row=tot, column=1, value="Total").font = BOLD
    for col in (2, 3, 4, 6, 7, 8):
        L = get_column_letter(col)
        c = yr.cell(row=tot, column=col, value=f"=SUM({L}2:{L}{tot - 1})")
        c.font = BOLD
        if col >= 6:
            c.number_format = USD
    yr.cell(row=tot, column=5, value=f"=D{tot}/C{tot}").number_format = "0.0%"

    s = summary
    s.column_dimensions["A"].width = 44
    s.column_dimensions["B"].width = 16
    lines: list[tuple[str, object, str | None]] = [
        (
            "YouTube 'daily zone + liquidity sweep' gold strategy - "
            "every trade 2014-2024",
            None,
            None,
        ),
        ("Video: youtube.com/watch?v=ctLHzjrH3Rk (The Trading School)", None, None),
        ("", None, None),
        ("Starting account balance $ (edit me)", 3000, USD),
        ("Risk per trade $ (1% of $3,000, fixed)", sizing.risk_usd, USD),
        ("Variant", rule.name, None),
        ("Trading days tested", n_days, "#,##0"),
        ("Days with at least one trade", f"=COUNTA(Daily!A2:A{dlast})", "#,##0"),
        ("Trades", f"=COUNTA(Trades!A2:A{last})", "#,##0"),
        ("Winning trades", f'=COUNTIF(Trades!S2:S{last},">0")', "#,##0"),
        ("Win rate", "=B10/B9", "0.0%"),
        ("Total P&L before costs $", f"=SUM(Trades!O2:O{last})", USD),
        ("Total spread $", f"=SUM(Trades!P2:P{last})", USD),
        ("Total extra spread + slippage $", f"=SUM(Trades!Q2:Q{last})", USD),
        ("Total commission $", f"=SUM(Trades!R2:R{last})", USD),
        ("Total net P&L $", "=B12-B13-B14-B15", USD),
        ("Final account balance $", "=B4+B16", USD),
        ("Worst day $", f"=MIN(Daily!H2:H{dlast})", USD),
        ("Best day $", f"=MAX(Daily!H2:H{dlast})", USD),
        ("", None, None),
        ("How to read the Trades sheet", None, None),
        (
            "Entry/exit price (chart mid) = halfway between buy and sell price, "
            "as on a "
            "chart. Fill = the price actually paid/received after the recorded spread, "
            "$0.20 extra spread and $0.10 slippage. P&L before costs uses the chart "
            "prices; Net P&L subtracts every cost.",
            None,
            None,
        ),
        (
            "Times are New York time. Trading day runs 17:00 to 17:00 New York; "
            "anything open is closed at 16:45. 1 lot = 100 oz. Commission $8 per lot.",
            None,
            None,
        ),
        (
            "Lots are sized so hitting the stop loses about $30. "
            + (
                "The 'stop on candle close' rule (as in the video) can lose more "
                "when a 15-minute candle closes far beyond the stop."
                if rule.stop_mode == "close"
                else "This version uses a normal stop order, which closes the trade "
                "as soon as price touches the stop (more if price jumps past it)."
            ),
            None,
            None,
        ),
        (
            "The balance keeps trading $30 risk per trade even after the account would "
            "be empty, to show the strategy's full result.",
            None,
            None,
        ),
    ]
    for r, (label, value, fmt) in enumerate(lines, 1):
        a = s.cell(row=r, column=1, value=label)
        a.font = BOLD if r in (1, 21) else Font(name=FONT)
        a.alignment = Alignment(wrap_text=True, vertical="top")
        if value is not None:
            b = s.cell(row=r, column=2, value=value)
            b.font = Font(name=FONT, color="0000FF" if r in (4,) else "000000")
            if fmt:
                b.number_format = fmt
    s["B4"].fill = PatternFill("solid", fgColor="FFFF00")
    for r in (22, 23, 24, 25):
        s.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
        s.row_dimensions[r].height = 45
    wb.save(out)
    print(f"wrote {out}: {len(trades)} trades, {len(trade_days)} trading days")


if __name__ == "__main__":
    main()
