# XAUUSD G2A — MT5 macOS connectivity feasibility audit

Investigation only, 2026-10-30. Feasibility audit completed; terminal connectivity
has **not** been tested or verified. No terminal launched, account accessed,
trades/orders called, historical data downloaded or packages installed.

## Observed environment

- macOS **26.6.2**, build **25G83** (`sw_vers`).
- **Apple Silicon / arm64** (`uname -m` and Python platform).
- Project `.venv`: **CPython 3.12.7**, native macOS arm64.
- Dependency workflow: **pip**, `pyproject.toml`/setuptools and pinned
  `requirements.lock`/`requirements-dev.lock`; pip 26.2.2, setuptools 80.9.0.
- Official `MetaTrader5` distribution absent. Actual native import returned
  `ModuleNotFoundError: No module named 'MetaTrader5'`.
- No MetaTrader/Wine/CrossOver app found recursively under `/Applications` or
  `~/Applications`; Spotlight MetaTrader filename search returned no matches.
  `/Applications/MetaTrader 5.app` absent. No app version/location to report.
- Known MT5 Application Support locations (`Metatrader 5`, `MetaTrader 5`,
  `net.metaquotes.wine.metatrader5`) and `~/.wine` absent. Neither `wine` nor
  `wine64` is on PATH. No local Wine environment detected. Nonstandard locations,
  other users and unindexed volumes are not exhaustively excluded.
- `pip check` reports pre-existing conflicts: growwapi 1.5.0 requires certifi
  <2026 and pandas <3, while installed versions are certifi 2026.7.22 and pandas
  3.0.6. No repair attempted; these do not change the MT5 platform finding.

## Official package and macOS terminal

The inspected official MetaQuotes PyPI release **5.0.6231** supplies Windows
x86-64 wheels, including `cp312-cp312-win_amd64`, with no macOS wheel or source
archive listed. Python version alone is compatible, but OS/binary architecture
is not. Direct installation/import into this native macOS arm64 `.venv` is not
supported by these artifacts. No futile installation attempted. Rosetta alone
would not make a Windows binary a macOS Python extension.
[Official distribution files](https://pypi.org/project/MetaTrader5/)

The official macOS installer installs Wine and runs the terminal within it;
MetaQuotes documents Apple processor support. This describes terminal support,
not native macOS Python-package support. No local app exists to inspect for a
specific Wine version or terminal build.
[Official macOS installation](https://www.metatrader5.com/en/terminal/help/start_advanced/install_mac)

The official Python package communicates with a terminal through interprocess
communication. It is not a direct broker HTTP API.
[Official Python integration](https://www.mql5.com/en/docs/python_metatrader5)

## Route comparison — engineering assessment, not connection-test results

| Route | Feasibility here | Dependency / architecture impact | Security concerns | Testing complexity |
| --- | --- | --- | --- | --- |
| A. Official package in project Python | Not feasible natively with current published artifacts | Official package, incompatible OS binary; cannot simply add it to Mac requirements | Avoid forced binaries or unofficial replacements | Blocked at platform compatibility |
| B. Python bridge into MT5/Wine | Conditional future experiment; MT5/Wine/Windows Python absent | Requires Windows Python/package inside compatible Wine environment plus custom or third-party transport to native Python | Bridge code, credentials, arbitrary RPC and Wine prefix access enlarge trust boundary | High: Apple Silicon, Windows ABI, Wine, terminal IPC and bridge compatibility |
| C. Small local sidecar beside MT5 | Conditional; no terminal environment currently present | Narrow first-party read-only service/exporter; Windows Python under Wine or terminal-side MQL5 implementation; Mac bot remains normal Python | Allowlisted data operations, bounded requests, local-only endpoint or protected files; never expose generic terminal command forwarding | Medium-high: IPC, lifecycle, stale data, schema/version and precision checks; Wine compatibility still applies |
| D. Later Windows/VPS host | Feasible architecture, not provisioned or tested here | Official terminal + Windows x86-64 Python/package on a host; narrow first-party data service accessed by Mac | Host hardening, credential isolation, authenticated encrypted transport, restricted network access | Moderate: native SDK compatibility plus service integration; avoids Wine/ARM translation layers |

C and D can be combined: the narrow service in C can later run on a Windows host.
No third-party bridge package is inherently required. Route B could use one, but
none has been selected, installed, security-reviewed or verified by this audit.
A custom bridge is still software we must maintain and test; it is not an official
MetaQuotes remote API merely because it uses their SDK.

## Recommended architecture

For the safest practical eventual integration, prefer a **Windows x86-64 host
with the official terminal/SDK and a narrowly scoped first-party read-only data
service**, keeping development/backtesting on Mac. This is an engineering
recommendation to reduce compatibility uncertainty, not a deployment action.
If local-only operation is required, investigate C separately after an explicitly
authorized terminal setup; do not assume Wine Python IPC will work on this Mac.

Preserve the boundary:

```text
trading_bot core → broker/data adapter interface → MT5-specific adapter → terminal
```

The adapter may communicate with a sidecar; core strategy/risk/domain modules must
not import MetaTrader5. Keep SDK dependencies isolated on the terminal host. A
future read-only service should expose only reviewed data operations, never
arbitrary method names, eval, order submission or account-changing actions.
Credentials remain on the terminal host; use a demo/read-only account and reduced
permissions where supported in a separately authorized checkpoint. No live
account is required for feasibility work.

Future verification must establish terminal/SDK compatibility, symbol mapping,
UTC timestamps, quote precision, contract provenance, stale-data handling and
actual access restrictions. None is claimed verified here. This audit does not
choose a broker, install a terminal or begin G2B.

## Changes and verification

Only this report was added. No source/configuration, dependency, migration or
trading behavior changed. Full tests intentionally not rerun for documentation
only. Local platform/version/import/distribution checks, application/path checks,
`pip check`, `git status`, `git diff` and whitespace review performed. Initial
Git status was clean; final change is this untracked report only. Nothing committed.
