"""Hourly global news intensity and tone from GDELT 2.0 (BigQuery public data).

GDELT reads news worldwide in many languages every 15 minutes and tags each
article with themes and a tone score computed at publication time (no
hindsight). Coverage starts 2015-02-18. We keep, per UTC hour and per category
below, how many articles appeared and their average tone, plus all-news totals.

Only 2015-02-18 to 2024-12-31 is ever queried: 2025 and 2026 stay unseen.
Every query runs with a hard cap on bytes scanned.

Category theme lists were chosen from GDELT's own theme names before any model
result was seen. There is no dedicated AI or hedge-fund theme; the closest
themes are used and named as such.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path

from trading_bot.data.histdata_bulk import DATA_DIR

PROJECT = "project-ec8ba26a-6636-4e75-bb6"
TABLE = "gdelt-bq.gdeltv2.gkg_partitioned"
FIRST_DAY = date(2015, 2, 18)
LAST_DAY = date(2024, 12, 31)
NEWS_CSV = DATA_DIR.parent / "news" / "gdelt_hourly_2015_2024.csv"

CATEGORIES: dict[str, tuple[str, ...]] = {
    "gold": ("ECON_GOLDPRICE", "WB_2936_GOLD"),
    "central_banks": (
        "ECON_CENTRALBANK",
        "WB_1235_CENTRAL_BANKS",
        "EPU_POLICY_CENTRAL_BANK",
        "EPU_CATS_MONETARY_POLICY",
        "ECON_INTEREST_RATES",
    ),
    "inflation": ("ECON_INFLATION", "WB_442_INFLATION", "ECON_DEFLATION"),
    "dollar_fx": (
        "ECON_WORLDCURRENCIES_DOLLAR",
        "ECON_WORLDCURRENCIES_DOLLARS",
        "ECON_WORLDCURRENCIES_US_DOLLAR",
        "ECON_WORLDCURRENCIES_US_DOLLARS",
        "ECON_CURRENCY_EXCHANGE_RATE",
    ),
    "stock_market": ("ECON_STOCKMARKET",),
    "war_conflict": (
        "ARMEDCONFLICT",
        "WB_2462_POLITICAL_VIOLENCE_AND_WAR",
        "SEIGE",
        "BLOCKADE",
        "WMD",
    ),
    "terror": ("TERROR",),
    "sanctions": ("SANCTIONS",),
    "elections_government": ("ELECTION", "IMPEACHMENT", "RESIGNATION", "COUP"),
    "policy_uncertainty": ("EPU_UNCERTAINTY", "USPEC_UNCERTAINTY1"),
    "oil": ("ECON_OILPRICE",),
    "debt_crisis": (
        "ECON_DEBT",
        "ECON_BANKRUPTCY",
        "ECON_BUDGET_DEFICIT",
        "WB_1104_MACROECONOMIC_VULNERABILITY_AND_DEBT",
    ),
    "ai_tech": ("TECH_AUTOMATION", "TECH_SUPERCOMPUTING", "TECH_BIGDATA"),
    "bubble_speculation": ("ECON_BUBBLE", "TAX_FNCACT_SPECULATOR"),
    "funds_investors": ("WB_341_INVESTMENT_FUNDS", "TAX_FNCACT_INVESTOR"),
    "crypto": ("ECON_BITCOIN",),
}
# gold articles that also mention central banks (e.g. central banks buying gold)
COMBINED = {"gold_central_banks": ("gold", "central_banks")}


def _pattern(themes: Iterable[str]) -> str:
    # a theme appears as ";THEME," inside V2Themes ("THEME,offset;THEME,offset")
    return r"(^|;)(" + "|".join(themes) + r"),"


def hourly_sql(first: date, last: date) -> str:
    if first < FIRST_DAY or last > LAST_DAY or first > last:
        raise ValueError(f"dates must lie within {FIRST_DAY}..{LAST_DAY}")
    flags = ",\n    ".join(
        f"REGEXP_CONTAINS(V2Themes, r'{_pattern(t)}') AS f_{name}"
        for name, t in CATEGORIES.items()
    )
    aggs = ["COUNT(*) AS n_all", "AVG(tone) AS tone_all"]
    for name in CATEGORIES:
        aggs.append(f"COUNTIF(f_{name}) AS n_{name}")
        aggs.append(f"AVG(IF(f_{name}, tone, NULL)) AS tone_{name}")
    for name, (a, b) in COMBINED.items():
        aggs.append(f"COUNTIF(f_{a} AND f_{b}) AS n_{name}")
        aggs.append(f"AVG(IF(f_{a} AND f_{b}, tone, NULL)) AS tone_{name}")
    agg_sql = ",\n  ".join(aggs)
    return f"""
WITH a AS (
  SELECT
    TIMESTAMP_TRUNC(
      PARSE_TIMESTAMP('%Y%m%d%H%M%S', CAST(DATE AS STRING)), HOUR
    ) AS hour,
    SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(0)] AS FLOAT64) AS tone,
    {flags}
  FROM `{TABLE}`
  WHERE _PARTITIONTIME >= TIMESTAMP('{first.isoformat()}')
    AND _PARTITIONTIME < TIMESTAMP_ADD(TIMESTAMP('{last.isoformat()}'), INTERVAL 1 DAY)
    AND DATE IS NOT NULL
)
SELECT hour,
  {agg_sql}
FROM a
WHERE hour < TIMESTAMP_ADD(TIMESTAMP('{last.isoformat()}'), INTERVAL 1 DAY)
GROUP BY hour
ORDER BY hour
"""


def columns() -> list[str]:
    cols = ["hour", "n_all", "tone_all"]
    for name in [*CATEGORIES, *COMBINED]:
        cols += [f"n_{name}", f"tone_{name}"]
    return cols


def dry_run_tb(sql: str, project: str = PROJECT) -> float:
    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    job = client.query(
        sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    )
    return float(job.total_bytes_processed or 0) / 1e12


def fetch_hourly(
    first: date,
    last: date,
    max_tb: float,
    path: Path = NEWS_CSV,
    project: str = PROJECT,
) -> Path:
    """Run the hourly query (refused by BigQuery if it would scan > max_tb)."""
    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    cfg = bigquery.QueryJobConfig(maximum_bytes_billed=int(max_tb * 1e12))
    rows = client.query(hourly_sql(first, last), job_config=cfg).result()
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = columns()
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow(
                [r["hour"].strftime("%Y-%m-%dT%H:00Z")]
                + ["" if r[c] is None else r[c] for c in cols[1:]]
            )
    return path


def load_hourly(path: Path = NEWS_CSV) -> tuple[list[datetime], dict[str, list[float]]]:
    """Hours (UTC, the hour's start) and each column as floats (nan if empty)."""
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    hours = [datetime.fromisoformat(r["hour"].replace("Z", "+00:00")) for r in rows]
    if hours and hours[-1].date() > LAST_DAY:
        raise ValueError("news history must stop at 2024-12-31")
    data = {
        c: [float(r[c]) if r[c] != "" else float("nan") for r in rows]
        for c in columns()[1:]
    }
    return hours, data


# --- extra sources: event records, people and organisations -----------------

EVENTS_TABLE = "gdelt-bq.gdeltv2.events_partitioned"
EVENTS_CSV = DATA_DIR.parent / "news" / "gdelt_events_hourly_2015_2024.csv"
ENTITIES_CSV = DATA_DIR.parent / "news" / "gdelt_entities_hourly_2015_2024.csv"

# CAMEO root codes: 13 threaten, 14 protest, 15 show of force, 16 reduce
# relations, 17 coerce (incl. sanctions), 18 assault, 19 fight, 20 mass violence
EVENT_GROUPS: dict[str, str] = {
    "threaten": "EventRootCode = '13'",
    "protest": "EventRootCode = '14'",
    "force_posture": "EventRootCode = '15'",
    "coerce": "EventRootCode IN ('16', '17')",
    "fighting": "EventRootCode IN ('18', '19', '20')",
    "material_conflict": "QuadClass = 4",
    "cooperation": "QuadClass IN (1, 2)",
}
# where the event happened (FIPS country codes used by GDELT geography)
EVENT_REGIONS: dict[str, tuple[str, ...]] = {
    "russia_ukraine": ("RS", "UP"),
    "middle_east": ("IS", "IR", "IZ", "SY", "LE", "YM", "SA", "GZ", "WE"),
    "china_taiwan": ("CH", "TW"),
    "korea": ("KN", "KS"),
    "usa": ("US",),
}

PERSONS: dict[str, str] = {
    "fed_chair": r"jerome powell|janet yellen",
    "trump": r"donald trump",
    "biden": r"joe biden",
    "xi": r"xi jinping",
    "putin": r"vladimir putin",
}
ORGANISATIONS: dict[str, str] = {
    "federal_reserve": r"federal reserve",
    "ecb": r"european central bank",
    "pboc": r"people'?s bank of china",
    "world_gold_council": r"world gold council",
    "opec": r"\bopec\b",
    "imf": r"international monetary fund",
    "ai_companies": r"\bnvidia\b|\bopenai\b",
    "big_funds": r"bridgewater|blackrock|citadel|renaissance technologies",
}


def _range_check(first: date, last: date) -> None:
    if first < FIRST_DAY or last > LAST_DAY or first > last:
        raise ValueError(f"dates must lie within {FIRST_DAY}..{LAST_DAY}")


def events_hourly_sql(first: date, last: date) -> str:
    """Event records per hour they were added (= published), with average
    Goldstein conflict/cooperation score and mention-weighted counts."""
    _range_check(first, last)
    aggs = [
        "COUNT(*) AS ev_n",
        "SUM(NumMentions) AS ev_mentions",
        "AVG(GoldsteinScale) AS ev_goldstein",
        "AVG(AvgTone) AS ev_tone",
    ]
    for name, cond in EVENT_GROUPS.items():
        aggs.append(f"SUM(IF({cond}, NumMentions, 0)) AS ev_{name}")
    for name, codes in EVENT_REGIONS.items():
        in_list = ", ".join(f"'{c}'" for c in codes)
        region = f"ActionGeo_CountryCode IN ({in_list})"
        aggs.append(f"SUM(IF({region}, NumMentions, 0)) AS ev_{name}")
        aggs.append(
            f"SUM(IF({region} AND QuadClass = 4, NumMentions, 0)) "
            f"AS ev_{name}_conflict"
        )
    agg_sql = ",\n  ".join(aggs)
    return f"""
WITH a AS (
  SELECT
    TIMESTAMP_TRUNC(
      PARSE_TIMESTAMP('%Y%m%d%H%M%S', CAST(DATEADDED AS STRING)), HOUR
    ) AS hour,
    EventRootCode, QuadClass, GoldsteinScale, NumMentions, AvgTone,
    ActionGeo_CountryCode
  FROM `{EVENTS_TABLE}`
  WHERE _PARTITIONTIME >= TIMESTAMP('{first.isoformat()}')
    AND _PARTITIONTIME < TIMESTAMP_ADD(TIMESTAMP('{last.isoformat()}'), INTERVAL 1 DAY)
    AND DATEADDED IS NOT NULL
)
SELECT hour,
  {agg_sql}
FROM a
WHERE hour >= TIMESTAMP('{first.isoformat()}')
  AND hour < TIMESTAMP_ADD(TIMESTAMP('{last.isoformat()}'), INTERVAL 1 DAY)
GROUP BY hour
ORDER BY hour
"""


def entities_hourly_sql(first: date, last: date) -> str:
    """Articles per hour mentioning each person / organisation group, and their
    average tone."""
    _range_check(first, last)
    flags = [
        f"REGEXP_CONTAINS(LOWER(IFNULL(V2Persons, '')), r'{p}') AS p_{n}"
        for n, p in PERSONS.items()
    ] + [
        f"REGEXP_CONTAINS(LOWER(IFNULL(V2Organizations, '')), r\"{p}\") AS o_{n}"
        for n, p in ORGANISATIONS.items()
    ]
    aggs = []
    for prefix, names in (("p", PERSONS), ("o", ORGANISATIONS)):
        for n in names:
            aggs.append(f"COUNTIF({prefix}_{n}) AS n_{n}")
            aggs.append(f"AVG(IF({prefix}_{n}, tone, NULL)) AS tone_{n}")
    flag_sql = ",\n    ".join(flags)
    agg_sql = ",\n  ".join(aggs)
    return f"""
WITH a AS (
  SELECT
    TIMESTAMP_TRUNC(
      PARSE_TIMESTAMP('%Y%m%d%H%M%S', CAST(DATE AS STRING)), HOUR
    ) AS hour,
    SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(0)] AS FLOAT64) AS tone,
    {flag_sql}
  FROM `{TABLE}`
  WHERE _PARTITIONTIME >= TIMESTAMP('{first.isoformat()}')
    AND _PARTITIONTIME < TIMESTAMP_ADD(TIMESTAMP('{last.isoformat()}'), INTERVAL 1 DAY)
    AND DATE IS NOT NULL
)
SELECT hour,
  {agg_sql}
FROM a
WHERE hour < TIMESTAMP_ADD(TIMESTAMP('{last.isoformat()}'), INTERVAL 1 DAY)
GROUP BY hour
ORDER BY hour
"""


def fetch_table(sql: str, path: Path, max_tb: float, project: str = PROJECT) -> Path:
    """Run a query (refused by BigQuery above max_tb) and save every column."""
    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    cfg = bigquery.QueryJobConfig(maximum_bytes_billed=int(max_tb * 1e12))
    result = client.query(sql, job_config=cfg).result()
    names = [f.name for f in result.schema]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(names)
        for r in result:
            w.writerow(
                [r["hour"].strftime("%Y-%m-%dT%H:00Z")]
                + ["" if r[c] is None else r[c] for c in names[1:]]
            )
    return path


def load_table(path: Path) -> tuple[list[datetime], dict[str, list[float]]]:
    with path.open() as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        names = list(reader.fieldnames or [])
    hours = [datetime.fromisoformat(r["hour"].replace("Z", "+00:00")) for r in rows]
    if hours and hours[-1].date() > LAST_DAY:
        raise ValueError("news history must stop at 2024-12-31")
    data = {
        c: [float(r[c]) if r[c] != "" else float("nan") for r in rows]
        for c in names
        if c != "hour"
    }
    return hours, data
