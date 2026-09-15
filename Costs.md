---
tags: [algo-trading, backtest]
source: costs.py
---
# Cost Model

> [!important] The single most important file in the project
> A strategy is only "real" if it survives **this**. Costs are what separate a
> backtest that lies to you from one that doesn't.

Costs are expressed in **basis points** (bps): `1 bp = 0.01%`.

- A **liquid ETF** like SPY has a tiny spread (~1–3 bps).
- A **cheap weekly option** can have a spread of *hundreds* of bps — which is why
  naive options trading is ruin.

## How a cost is charged
Each unit of [[Backtest#Turnover|turnover]] crosses **half** the bid-ask spread
(mid → ask) plus slippage. A fixed per-trade fee is charged on any bar where a
trade happens, expressed as a fraction of capital — that's the piece that quietly
destroys a $23 account.

$$\text{cost}_t = \underbrace{\text{turnover}_t \cdot \tfrac{0.5\,\text{spread} + \text{slippage}}{10^4}}_{\text{proportional}} + \underbrace{\frac{\text{fee}}{\text{capital}}\big[\text{turnover}_t > 0\big]}_{\text{fixed}}$$

## Code
```python
from dataclasses import dataclass
import numpy as np


@dataclass
class CostModel:
    spread_bps: float = 3.0      # full bid-ask spread in bps
    slippage_bps: float = 1.0    # extra adverse fill beyond mid, bps
    fixed_fee: float = 0.0       # $ per trade (Robinhood equity commission = 0)
    capital: float = 10_000.0    # account size -> turns fixed_fee into a fraction

    def cost_fraction(self, turnover):
        """turnover[t] = |position[t] - position[t-1]|  (fraction of capital traded).
        Each unit of turnover crosses HALF the spread (mid->ask) plus slippage.
        fixed_fee is charged on any bar where a trade happens, as a fraction of capital
        -- this is what quietly destroys a $23 account."""
        turnover = np.asarray(turnover, dtype=float)
        prop  = turnover * (0.5 * self.spread_bps + self.slippage_bps) / 1e4
        fixed = np.where(turnover > 1e-12, self.fixed_fee / max(self.capital, 1e-9), 0.0)
        return prop + fixed
```

## The three regimes used in [[Run]]
| Regime | spread / slippage | Meaning |
|--------|-------------------|---------|
| FRICTIONLESS | 0 / 0 | The lie. Raw signal only. |
| LIQUID ETF | 3 / 1 bps | The truth for stocks. |
| CHEAP OPTION | 300 / 50 bps | Why frequent options trading → −100%. |

## Measured intraday quoted half-spreads — 2026-09-15

I1.4 measurement, **not yet the I1.5 execution-cost regime**. Median half-spread in
bps from 20 fixed full sessions/year, 2016–2026, through 2026-09-11. One sampled
instant per bucket/day; missing updates were backfilled up to 60 seconds at the
same timestamp. 21,094/21,120 observations are valid; every year/bucket has at
least 90% coverage. Quote-age p95 is 4.006 seconds. See
[[research/audits/intraday-data]] for the frozen design and limitations.

| Symbol | Open 09:30–10:00 | Midday 10:00–15:30 | Close 15:30–16:00 |
|---|---:|---:|---:|
| AAPL | 0.610 | 0.417 | 0.352 |
| ABBV | 3.058 | 1.139 | 0.815 |
| ADBE | 4.867 | 2.556 | 1.587 |
| AMZN | 2.065 | 1.234 | 0.878 |
| AVGO | 5.133 | 2.527 | 1.644 |
| BAC | 1.642 | 1.585 | 1.581 |
| CAT | 4.555 | 1.822 | 1.045 |
| COST | 4.230 | 2.008 | 1.450 |
| CRM | 3.854 | 1.576 | 0.862 |
| CVX | 1.779 | 0.849 | 0.518 |
| GOOGL | 2.458 | 1.794 | 1.169 |
| GS | 4.602 | 2.240 | 1.283 |
| HD | 3.465 | 1.429 | 0.873 |
| JNJ | 1.750 | 0.710 | 0.579 |
| JPM | 1.048 | 0.680 | 0.520 |
| KO | 1.025 | 0.910 | 0.903 |
| LLY | 5.075 | 2.081 | 1.304 |
| MA | 4.054 | 1.861 | 1.278 |
| MCD | 2.720 | 1.184 | 0.717 |
| META | 1.526 | 0.903 | 0.634 |
| MRK | 1.579 | 0.798 | 0.683 |
| MSFT | 0.823 | 0.553 | 0.490 |
| NKE | 1.809 | 0.902 | 0.746 |
| NVDA | 1.870 | 1.066 | 0.815 |
| ORCL | 1.508 | 1.041 | 0.924 |
| PG | 1.213 | 0.649 | 0.598 |
| QQQ | 0.291 | 0.273 | 0.238 |
| SPY | 0.180 | 0.170 | 0.165 |
| UNH | 4.082 | 1.932 | 1.181 |
| V | 2.067 | 0.853 | 0.617 |
| WMT | 1.348 | 0.695 | 0.555 |
| XOM | 0.948 | 0.638 | 0.614 |

SPY midday measured **0.170 bps**, below the plan's approximate 0.5–1.5 bps
expectation. A one-cent full spread at $300 implies a 0.167 bps half-spread, so
that rough expectation must not be forced onto the observations. All 32 pooled
medians show open > midday > close; that is not a claim about every individual day.

Local outputs: `research_data/spreads.csv` (median/mean/p95 by symbol and bucket),
`spreads_by_year.csv`, `spread_samples.csv`, and `spreads_manifest.json`.
Rebuild offline with `.venv/bin/python spreads.py`. Raw vendor-derived data stays
out of Git. These measurements omit execution slippage, fees, market impact and
auctions; pooled medians also hide annual changes. **The daily 3/1 bps regime is
unchanged. Tenzing still signs the I1.5 constants before adoption.**

## See also
- [[Backtest]] — where `cost_fraction` is subtracted from gross returns
- [[Run]] — defines the regimes above
