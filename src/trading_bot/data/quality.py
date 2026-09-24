"""Pure, session-aware completeness checks over valid input observations."""

from datetime import datetime

from trading_bot.data.contracts import DataQualityIssue, IssueType, Severity


def gap_issues(
    symbol: str, expected: dict[datetime, datetime], observed: set[datetime]
) -> list[DataQualityIssue]:
    """Only session slots count; calendar closures never become phantom gaps."""
    missing = sorted(set(expected) - observed)
    issues = [
        DataQualityIssue(
            type=IssueType.MISSING_BAR,
            severity=Severity.WARNING,
            symbol=symbol,
            timestamp=t,
            message="Expected candle missing",
        )
        for t in missing
    ]
    if len(missing) >= 3:
        issues.append(
            DataQualityIssue(
                type=IssueType.LARGE_GAP,
                severity=Severity.WARNING,
                symbol=symbol,
                timestamp=missing[0],
                message="Multiple expected session candles missing",
                details={"missing_count": len(missing)},
            )
        )
    return issues
