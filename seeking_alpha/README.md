# Alpha Picks — "+5s entry / +60s exit" backtest

Research question from the user:

> If I buy 5 seconds after the Seeking Alpha *Alpha Picks* announcement and
> sell at +60 seconds, what is the **win rate** and **average profit**?

## TL;DR

1. **The literal question cannot be answered with free data.**
   Second-level (tick) price data is paywalled. Yahoo Finance (yfinance) —
   the only no-cost provider with programmatic access — offers 1-minute
   bars **only for the last ~7 days** and 1-hour bars for ~730 days. Every
   pick in the supplied list is older than 7 days, so the true
   `+5s → +60s` window is unavailable.
2. **The backtest in this sandbox also couldn't run**, because the sandbox
   network blocks `query1.finance.yahoo.com`, Polygon, Alpha Vantage and
   Stooq (all return `403 Host not in allowlist`). The script
   (`alpha_picks_backtest.py`) is designed to run on a normal developer
   machine and will produce results there.
3. **Useful qualitative finding** from public sources: Seeking Alpha itself
   acknowledges that some Alpha Picks get an **announcement-day pop that
   typically reverts by end of day**, especially small-caps / low-float
   names. Their own performance numbers are computed off *VWAP*, not the
   +5s print — so buying at +5s is *worse* than their published track
   record in expectation. (See Sources below.)

If you want a real `+5s → +60s` backtest, you need paid tick data from e.g.
[Polygon.io](https://polygon.io) (Stocks Starter plan, ~\$29/mo, offers
second aggregates and trade-tick data back several years) or
[Databento](https://databento.com).

---

## Files

| File                          | Purpose                                    |
|-------------------------------|--------------------------------------------|
| `alpha_picks_backtest.py`     | Runnable backtest, cascades 1-min → 1-hour → daily. |
| `requirements.txt`            | `yfinance`, `pandas`.                       |
| `alpha_picks_results.csv`     | Written by the script (not committed).      |
| `README.md`                   | This file.                                  |

## The pick list used

Transcribed from the user's screenshots. Where a ticker symbol on screen
didn't match the logo (e.g. `CVSA` shown with the Adtalem Global Education
logo), the **logo** was trusted: that row uses `ATGE`.

41 picks spanning 2022-12-15 → 2025-03-17. Source: user screenshots.

## Methodology (what the script does)

For each `(ticker, pick_date)` pair, it tries three granularities and uses
the finest one that returns data, labeling the result so you know which
proxy was used:

| Granularity   | Entry             | Exit              | Approximates          | Availability       |
|---------------|-------------------|-------------------|-----------------------|--------------------|
| `INTRADAY_MIN`  | 1-min bar @09:30 | 1-min bar @09:31 | real `+5s → +60s` question | last ~7 days only  |
| `INTRADAY_HOUR` | 09:30 hr-bar open | 09:30 hr-bar close | "did the pop hold for an hour?" | last ~730 days |
| `DAILY_OC`      | pick-day open    | pick-day close   | "did the pop hold to EOD?" | full history   |

Then it prints per-granularity win rate, average return, median return, and
equal-weighted sum. No granularity is mixed into a single statistic.

### Why 09:30 ET?

Alpha Picks are published at US market open on the pick date (1st & 3rd
Monday of the month). So "buy 5s after announcement" ≈ "buy 5s after the
09:30 ET open". That's the timing assumption baked into the script.

### Caveats

- No slippage / commissions modeled.
- yfinance 1-min bars are **trade-based** (last trade per minute), not NBBO
  midpoints — entry fill would differ.
- A real trader buying at +5s would *lift the ask*, not get the print of
  the 09:30 bar.
- The "hour" and "daily" proxies answer **a different question** (momentum
  within the day) than the user's literal `+5s → +60s` question.

## How to run

```bash
git clone <this repo>
cd seeking_alpha
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python alpha_picks_backtest.py               # auto cascade
python alpha_picks_backtest.py --force daily # if you only care about EOD proxy
```

Expected output:

```
=== Per-pick results ===
ticker pick_date  granularity  entry_price  exit_price  return_pct
ARQT   2025-03-17 DAILY_OC     8.32         8.41        +1.08
...

=== Summary by granularity ===
  DAILY_OC       : n=41  win_rate=XX.X%  avg=+X.XX%  median=+X.XX%  sum(eq-wt)=...
```

## What to do with a real tick-data feed

Replace `try_intraday_minute()` with a function that queries your tick
source for all trades between `pick_date 09:30:00` and `09:31:05 ET`:

```python
# pseudocode, Polygon.io
entry_trade = polygon.get_first_trade_at_or_after(ticker, "09:30:05")
exit_trade  = polygon.get_first_trade_at_or_after(ticker, "09:31:00")
ret = exit_trade.price / entry_trade.price - 1
```

That answers the literal question.

## Related: what the +5s → +60s hypothesis is really testing

You are hypothesizing that there is a brief, predictable price pop in the
~55 seconds after Alpha Picks publishes a name, driven by subscribers
hitting market-buy orders. For this to be exploitable net of costs:

1. The pop must exceed **spread + slippage + commission** (realistic round
   trip on a small-cap: 10–50 bps).
2. **Your order must be among the first**, or the pop is already paid for.
3. Alpha Picks does NOT pre-announce, so you'd have to scrape their web /
   app the instant a new pick drops — a latency race you'd lose to bots.
4. Seeking Alpha's own documentation notes the pop "usually corrects by
   end of day" → a +5s buy / +EOD sell is *probably* net-negative vs. just
   entering at VWAP, which is how Alpha Picks measures their own track
   record.

So even before running the numbers the prior should be: small edge if any,
eaten by costs and competition from other latency-sensitive subscribers.
The EOD proxy (DAILY_OC column) is the cheapest way to sanity-check that.

---

## Sources

- [Deep Dive into Alpha Picks — Seeking Alpha](https://seekingalpha.com/article/4829591-finding-opportunity-in-uncertain-markets-with-alpha-picks)
- [Alpha Picks subscribe page — Seeking Alpha](https://seekingalpha.com/alpha-picks/subscribe)
- [Alpha Picks Review — matchmybroker.com](https://www.matchmybroker.com/tools/alpha-picks-by-seeking-alpha-review)
- [Alpha Picks Review — howthemarketworks.com](https://www.howthemarketworks.com/advanced/charts-and-patterns/seeking-alpha-alpha-picks-review/)
- [Alpha Picks Review — Ryan O'Connell, CFA](https://ryanoconnellfinance.com/alpha-picks-review/)
- [Seeking Alpha Review — liberatedstocktrader.com](https://www.liberatedstocktrader.com/seeking-alpha-review/)
