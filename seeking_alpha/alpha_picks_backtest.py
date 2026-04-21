"""
Alpha Picks backtest.

User goal: "if I buy 5 seconds after the Alpha Picks announcement and sell at
+60 seconds, what's the win rate and expected profit?"

Reality of free data:
    * True second-level (tick) data is paywalled (Polygon.io, Databento, etc.).
    * yfinance 1-minute bars  -> last ~7 days only.
    * yfinance 1-hour bars    -> last ~730 days.
    * yfinance daily bars     -> full history.

So for picks older than ~30 days we CANNOT compute a real +5s -> +60s return.
This script therefore reports the finest-granularity return it can actually
get per pick, and labels the proxy clearly:

    INTRADAY_MIN : 1-min bar open  ->  1-min bar 1 minute later   (~as requested)
    INTRADAY_HOUR: 1-hour bar open ->  1-hour bar close           (proxy)
    DAILY_OC     : daily open      ->  daily close                (proxy)

Alpha Picks are published around 09:30 ET on the pick date (same as market
open), so "day-open -> day-close" is a defensible long-only proxy for
"enter right after announcement, see how it behaves that day".

Usage:
    pip install yfinance pandas
    python alpha_picks_backtest.py
    python alpha_picks_backtest.py --force daily    # skip intraday attempts
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import sys
import time
from typing import Optional

import pandas as pd
import yfinance as yf


# ---------------------------------------------------------------------------
# Pick list, transcribed from the user's screenshots. Dates = US format
# (MM/DD/YYYY) interpreted reverse-chronologically. "CVSA" with the Adtalem
# logo was treated as ATGE (display glitch in the source app).
# ---------------------------------------------------------------------------

PICKS: list[tuple[str, str]] = [
    ("ARQT",  "2025-03-17"),
    ("WFC",   "2025-03-03"),
    ("ITRN",  "2025-02-18"),
    ("CRDO",  "2025-02-03"),
    ("PYPL",  "2025-01-15"),
    ("ALL",   "2025-01-02"),
    ("LC",    "2024-12-16"),
    ("QTWO",  "2024-12-02"),
    ("CLS",   "2024-11-15"),
    ("CCL",   "2024-11-01"),
    ("AGX",   "2024-10-15"),
    ("POWL",  "2024-10-01"),
    ("PPC",   "2024-09-16"),
    ("SYF",   "2024-09-03"),
    ("ZETA",  "2024-08-15"),
    ("RGA",   "2024-08-01"),
    ("ATGE",  "2024-07-15"),   # was "CVSA" in the screenshot (Adtalem logo)
    ("BRK-B", "2024-07-01"),
    ("SFM",   "2024-06-17"),
    ("SKYW",  "2024-06-03"),
    ("BLBD",  "2024-05-15"),
    ("GM",    "2024-05-01"),
    ("GCT",   "2024-04-15"),
    ("STRL",  "2023-08-01"),
    ("DXPE",  "2023-07-15"),
    ("WLDN",  "2023-07-01"),
    ("SSRM",  "2023-06-16"),
    ("LRN",   "2023-06-02"),
    ("UNFI",  "2023-05-15"),
    ("MFC",   "2023-05-01"),
    ("EAT",   "2023-04-15"),
    ("NEXA",  "2023-04-15"),
    ("EZPW",  "2023-04-01"),
    ("CSTM",  "2023-04-01"),
    ("LITE",  "2023-03-16"),
    ("FN",    "2023-03-02"),
    ("GM",    "2023-02-17"),
    ("DY",    "2023-02-02"),
    ("NEM",   "2023-01-15"),
    ("B",     "2023-01-02"),
    ("TIGO",  "2022-12-15"),
]


@dataclasses.dataclass
class Result:
    ticker: str
    pick_date: str
    granularity: str               # INTRADAY_MIN | INTRADAY_HOUR | DAILY_OC | NO_DATA
    entry_price: Optional[float]
    exit_price: Optional[float]
    return_pct: Optional[float]    # (exit/entry - 1) * 100
    note: str = ""


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def _to_ny(df: pd.DataFrame) -> pd.DataFrame:
    idx = df.index
    if idx.tz is None:
        idx = idx.tz_localize("UTC").tz_convert("America/New_York")
    else:
        idx = idx.tz_convert("America/New_York")
    out = df.copy()
    out.index = idx
    return out


def _next_ts(ts: pd.Timestamp, index: pd.DatetimeIndex) -> Optional[pd.Timestamp]:
    pos = index.searchsorted(ts)
    if pos >= len(index):
        return None
    return index[pos]


def try_intraday_minute(ticker: str, pick_date: str) -> Optional[Result]:
    """+5s entry / +60s exit, approximated by 1-min bars. Only last ~7 days."""
    try:
        df = yf.download(
            ticker,
            start=pick_date,
            end=(pd.Timestamp(pick_date) + pd.Timedelta(days=3)).strftime("%Y-%m-%d"),
            interval="1m",
            progress=False,
            auto_adjust=False,
            prepost=False,
        )
    except Exception:
        return None
    if df is None or df.empty:
        return None
    df = _to_ny(_flatten(df))

    announce = pd.Timestamp(f"{pick_date} 09:30:05", tz="America/New_York")
    exit_ts  = pd.Timestamp(f"{pick_date} 09:31:00", tz="America/New_York")
    entry_ts = _next_ts(announce, df.index)
    exit_row = _next_ts(exit_ts, df.index)
    if entry_ts is None or exit_row is None:
        return None
    entry = float(df.loc[entry_ts, "Open"])
    exit_ = float(df.loc[exit_row, "Open"])
    return Result(ticker, pick_date, "INTRADAY_MIN", entry, exit_,
                  (exit_ / entry - 1.0) * 100.0,
                  "1-min bars: entry @09:30, exit @09:31")


def try_intraday_hour(ticker: str, pick_date: str) -> Optional[Result]:
    """Hour-open -> hour-close of the 09:30 ET bar. Only last ~730 days."""
    try:
        df = yf.download(
            ticker,
            start=pick_date,
            end=(pd.Timestamp(pick_date) + pd.Timedelta(days=2)).strftime("%Y-%m-%d"),
            interval="60m",
            progress=False,
            auto_adjust=False,
            prepost=False,
        )
    except Exception:
        return None
    if df is None or df.empty:
        return None
    df = _to_ny(_flatten(df))
    day_bars = df[df.index.date == pd.Timestamp(pick_date).date()]
    if day_bars.empty:
        return None
    first = day_bars.iloc[0]
    entry = float(first["Open"])
    exit_ = float(first["Close"])
    return Result(ticker, pick_date, "INTRADAY_HOUR", entry, exit_,
                  (exit_ / entry - 1.0) * 100.0,
                  "1-hour bar: open(09:30) -> close(10:30)")


def try_daily(ticker: str, pick_date: str) -> Optional[Result]:
    """Daily open -> daily close on the pick date (or next trading day)."""
    try:
        df = yf.download(
            ticker,
            start=(pd.Timestamp(pick_date) - pd.Timedelta(days=5)).strftime("%Y-%m-%d"),
            end=(pd.Timestamp(pick_date) + pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
            interval="1d",
            progress=False,
            auto_adjust=False,
        )
    except Exception:
        return None
    if df is None or df.empty:
        return None
    df = _flatten(df)
    target = pd.Timestamp(pick_date)
    on_or_after = df[df.index >= target]
    if on_or_after.empty:
        return None
    row = on_or_after.iloc[0]
    entry = float(row["Open"])
    exit_ = float(row["Close"])
    return Result(ticker, pick_date, "DAILY_OC", entry, exit_,
                  (exit_ / entry - 1.0) * 100.0,
                  f"daily bar on {row.name.date().isoformat()} (open->close)")


def run_one(ticker: str, pick_date: str, force: str) -> Result:
    fns = {
        "min":   [try_intraday_minute, try_intraday_hour, try_daily],
        "hour":  [try_intraday_hour, try_daily],
        "daily": [try_daily],
        "auto":  [try_intraday_minute, try_intraday_hour, try_daily],
    }[force]
    for fn in fns:
        r = fn(ticker, pick_date)
        if r is not None:
            return r
        time.sleep(0.2)  # be polite to Yahoo
    return Result(ticker, pick_date, "NO_DATA", None, None, None, "no data returned")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--force", choices=["auto", "min", "hour", "daily"], default="auto",
                   help="which granularity cascade to attempt")
    p.add_argument("--out-csv", default="seeking_alpha/alpha_picks_results.csv")
    args = p.parse_args()

    rows: list[Result] = []
    for ticker, date in PICKS:
        print(f"fetching {ticker:6s} {date} ...", file=sys.stderr, flush=True)
        rows.append(run_one(ticker, date, args.force))

    df = pd.DataFrame([dataclasses.asdict(r) for r in rows])
    df.to_csv(args.out_csv, index=False)
    print(f"\nwrote {args.out_csv}")

    print("\n=== Per-pick results ===")
    with pd.option_context("display.max_rows", None, "display.width", 160):
        print(df[["ticker", "pick_date", "granularity", "entry_price",
                  "exit_price", "return_pct"]].to_string(index=False))

    print("\n=== Summary by granularity ===")
    any_data = False
    for gran, grp in df.groupby("granularity"):
        if gran == "NO_DATA":
            print(f"  {gran:15s}: {len(grp)} picks (excluded from stats)")
            continue
        any_data = True
        rets = grp["return_pct"].dropna()
        wins = (rets > 0).sum()
        print(f"  {gran:15s}: n={len(rets):>2d}  "
              f"win_rate={wins/len(rets)*100:5.1f}%  "
              f"avg={rets.mean():+.2f}%  "
              f"median={rets.median():+.2f}%  "
              f"sum(eq-wt)={rets.sum():+.2f}%")

    if not any_data:
        print(
            "\nNo data was retrieved. Common causes:\n"
            "  - Sandbox / network blocks Yahoo Finance (curl query1.finance.yahoo.com\n"
            "    returns 403 'Host not in allowlist').\n"
            "  - yfinance rate-limit: wait a minute and retry, or run with\n"
            "    --force daily to reduce request count.\n"
            "  - Ticker symbol mismatch (e.g. 'B' = Barrick Mining post-rename;\n"
            "    on Yahoo try 'GOLD' for Barrick prior history, or 'B' if listed).\n",
            file=sys.stderr,
        )
        return 1

    overall = df["return_pct"].dropna()
    wins = (overall > 0).sum()
    print(f"  {'ALL (mixed)':15s}: n={len(overall):>2d}  "
          f"win_rate={wins/len(overall)*100:5.1f}%  "
          f"avg={overall.mean():+.2f}%  "
          f"median={overall.median():+.2f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
