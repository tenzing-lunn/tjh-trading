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
"""Cost models. The single most important file in the project.

``CostModel`` is the original daily/options model.  Its behavior is deliberately
unchanged.  ``IntradayCostModel`` is an opt-in, unsigned research draft.  It has
a separate API because the legacy backtest does not carry the side, timestamp,
shares, price, or volume provenance needed to calculate honest intraday costs.
"""
from dataclasses import dataclass
from datetime import date, datetime
import csv
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

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


# Effective-date facts, not strategy assumptions.  Section 31 is dollars per
# $1,000,000 of covered sales.  FINRA TAF is dollars per share, capped per sale.
# Sources and limitations are recorded in research/intraday-cost-proposal.md.
_SEC_SECTION_31 = (
    (date(2016, 1, 1), 18.40),
    (date(2016, 2, 16), 21.80),
    (date(2017, 7, 4), 23.10),
    (date(2018, 5, 22), 13.00),
    (date(2019, 4, 16), 20.70),
    (date(2020, 2, 18), 22.10),
    (date(2021, 2, 25), 5.10),
    (date(2022, 5, 14), 22.90),
    (date(2023, 2, 27), 8.00),
    (date(2024, 5, 22), 27.80),
    (date(2025, 5, 14), 0.00),
    (date(2026, 4, 4), 20.60),
)
_FINRA_TAF = (
    (date(2016, 1, 1), 0.000119, 5.95),
    (date(2022, 1, 1), 0.000130, 6.49),
    (date(2023, 1, 1), 0.000145, 7.27),
    (date(2024, 1, 1), 0.000166, 8.30),
    (date(2026, 1, 1), 0.000195, 9.79),
)
_FEE_SUPPORT_START = date(2016, 1, 1)
_FEE_VERIFIED_THROUGH = date(2026, 9, 16)
_NY = ZoneInfo("America/New_York")
_BUCKETS = ("open", "mid", "close")
_CAUSAL_VOLUME_SOURCES = frozenset(
    {"observed_before_order", "prior_bar", "training_profile"}
)
_ALL_VOLUME_SOURCES = _CAUSAL_VOLUME_SOURCES | {"full_bar_retrospective"}


@dataclass(frozen=True)
class RegulatoryFees:
    """Unrounded statutory sell-side assessments for one covered equity sale."""

    section_31_dollars: float
    finra_taf_dollars: float

    @property
    def total_dollars(self):
        return self.section_31_dollars + self.finra_taf_dollars


@dataclass(frozen=True)
class IntradayCostEstimate:
    """Auditable cost breakdown for one hypothetical buy or sell."""

    symbol: str
    bucket: str
    side: str
    calibration_mode: str
    spread_half_bps: float
    spread_sample_count: int
    spread_coverage: float
    participation: float
    slippage_bps: float
    regulatory_fees: RegulatoryFees
    execution_cost_dollars: float
    total_cost_dollars: float
    total_cost_bps: float
    volume_source: str


def _finite_positive(name, value, *, allow_zero=False):
    value = float(value)
    valid = math.isfinite(value) and (value >= 0 if allow_zero else value > 0)
    if not valid:
        relation = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be finite and {relation}")
    return value


def _rate_on(day, schedule):
    eligible = [row for row in schedule if row[0] <= day]
    if not eligible:
        raise ValueError(f"No fee schedule for {day.isoformat()}")
    return eligible[-1][1:]


def _ceil_cent(value):
    return math.ceil(value * 100.0) / 100.0 if value > 0 else 0.0


def equity_sell_fees(sale_date, shares, unadjusted_price, *, rounding_mode):
    """Return date-appropriate Section 31 and FINRA TAF equity sale fees.

    The inputs must be actual shares and the contemporaneous unadjusted price.
    Unsupported dates fail closed because both schedules can change.
    """
    if isinstance(sale_date, datetime):
        sale_date = sale_date.date()
    if not isinstance(sale_date, date):
        raise TypeError("sale_date must be a date or datetime")
    if not _FEE_SUPPORT_START <= sale_date <= _FEE_VERIFIED_THROUGH:
        raise ValueError(
            "Regulatory fee date is outside the verified 2016-01-01 through "
            "2026-09-16 schedule"
        )
    if rounding_mode not in {"raw_statutory", "ceil_cent_per_component"}:
        raise ValueError(
            "rounding_mode must be 'raw_statutory' or 'ceil_cent_per_component'"
        )
    shares = _finite_positive("shares", shares)
    price = _finite_positive("unadjusted_price", unadjusted_price)
    notional = shares * price
    if not math.isfinite(notional) or notional <= 0:
        raise ValueError("shares * unadjusted_price must be finite and positive")
    (sec_per_million,) = _rate_on(sale_date, _SEC_SECTION_31)
    taf_per_share, taf_cap = _rate_on(sale_date, _FINRA_TAF)
    sec = notional * sec_per_million / 1_000_000.0
    # FINRA Schedule A waives TAF when execution price is below the per-share rate.
    taf = 0.0 if price < taf_per_share else min(shares * taf_per_share, taf_cap)
    if not math.isfinite(sec) or not math.isfinite(taf):
        raise ValueError("Calculated regulatory fee is nonfinite")
    if rounding_mode == "ceil_cent_per_component":
        sec, taf = _ceil_cent(sec), _ceil_cent(taf)
    return RegulatoryFees(sec, taf)


class IntradayCostModel:
    """Unsigned intraday cost draft backed by admitted I1.4 quote samples.

    Every policy choice is explicit at construction; there is intentionally no
    adopted ``INTRADAY`` singleton.  ``causal`` uses only sample values dated
    before the hypothetical trade.  The original sampling-plan construction is
    retrospective, so this is time-filtered calibration rather than a claim of
    fully point-in-time sample selection.
    """

    def __init__(
        self,
        *,
        spread_samples_path,
        spread_manifest_path,
        expected_plan_hash,
        expected_samples_sha256,
        calibration_mode,
        spread_quantile,
        minimum_spread_coverage,
        minimum_causal_samples,
        slippage_floor_bps,
        slippage_sqrt_coefficient_bps,
        max_participation,
        regulatory_fee_rounding,
    ):
        if calibration_mode not in {"retrospective", "causal"}:
            raise ValueError("calibration_mode must be 'retrospective' or 'causal'")
        self.calibration_mode = calibration_mode
        self.spread_quantile = _finite_positive(
            "spread_quantile", spread_quantile
        )
        if self.spread_quantile > 1:
            raise ValueError("spread_quantile must be at most 1")
        self.minimum_spread_coverage = _finite_positive(
            "minimum_spread_coverage", minimum_spread_coverage
        )
        if self.minimum_spread_coverage > 1:
            raise ValueError("minimum_spread_coverage must be at most 1")
        if isinstance(minimum_causal_samples, bool) or int(minimum_causal_samples) != minimum_causal_samples:
            raise ValueError("minimum_causal_samples must be a positive integer")
        self.minimum_causal_samples = int(minimum_causal_samples)
        if self.minimum_causal_samples <= 0:
            raise ValueError("minimum_causal_samples must be a positive integer")
        self.slippage_floor_bps = _finite_positive(
            "slippage_floor_bps", slippage_floor_bps, allow_zero=True
        )
        self.slippage_sqrt_coefficient_bps = _finite_positive(
            "slippage_sqrt_coefficient_bps",
            slippage_sqrt_coefficient_bps,
            allow_zero=True,
        )
        self.max_participation = _finite_positive(
            "max_participation", max_participation
        )
        if self.max_participation > 1:
            raise ValueError("max_participation must be at most 1")
        if regulatory_fee_rounding not in {
            "raw_statutory",
            "ceil_cent_per_component",
        }:
            raise ValueError("Unsupported regulatory_fee_rounding")
        self.regulatory_fee_rounding = regulatory_fee_rounding
        self._samples_path = Path(spread_samples_path)
        self._manifest_path = Path(spread_manifest_path)
        self._expected_plan_hash = str(expected_plan_hash)
        self._expected_samples_sha256 = str(expected_samples_sha256).lower()
        if len(self._expected_samples_sha256) != 64:
            raise ValueError("expected_samples_sha256 must be a SHA-256 hex digest")
        self._load_spreads()

    def cost_fraction(self, turnover):
        """Refuse accidental use by the legacy bar-only engine."""
        raise TypeError(
            "IntradayCostModel needs side, timestamp, raw shares/price, and "
            "causally available volume; call estimate_trade() explicitly"
        )

    @staticmethod
    def _plan_digest(plan):
        encoded = json.dumps(plan, sort_keys=True).encode()
        return hashlib.sha256(encoded).hexdigest()[:16]

    def _load_spreads(self):
        try:
            manifest = json.loads(self._manifest_path.read_text())
            sample_bytes = self._samples_path.read_bytes()
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot read spread provenance: {exc}") from None
        actual_sha = hashlib.sha256(sample_bytes).hexdigest()
        if actual_sha != self._expected_samples_sha256:
            raise ValueError("Spread sample SHA-256 does not match reviewed artifact")
        plan = manifest.get("sampling_plan")
        if not isinstance(plan, dict):
            raise ValueError("Spread manifest has no sampling plan")
        plan_hash = manifest.get("plan_hash")
        if (
            plan_hash != self._expected_plan_hash
            or self._plan_digest(plan) != plan_hash
        ):
            raise ValueError("Spread sampling-plan provenance mismatch")
        if plan.get("version") != 1 or plan.get("feed") != "sip":
            raise ValueError("Only the reviewed I1.4 SIP sampling design is supported")
        if manifest.get("backfill_complete") is not True:
            raise ValueError("Spread backfill is incomplete")
        if "spread_samples.csv" not in manifest.get("files", []):
            raise ValueError("Spread manifest does not declare spread_samples.csv")
        try:
            generated = datetime.fromisoformat(manifest["generated_at"])
            cutoff = date.fromisoformat(plan["cutoff_exclusive"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Spread manifest has invalid generation/cutoff dates") from None
        if generated.tzinfo is None or cutoff > generated.date():
            raise ValueError("Spread manifest timing provenance is invalid")
        symbols = plan.get("symbols")
        windows = plan.get("windows")
        if (
            not isinstance(symbols, list)
            or not symbols
            or len(symbols) != len(set(symbols))
            or not isinstance(windows, list)
            or not windows
        ):
            raise ValueError("Spread sampling plan has invalid symbols/windows")
        window_keys = []
        for window in windows:
            try:
                day = date.fromisoformat(window["day"])
                bucket = window["bucket"]
                start = datetime.fromisoformat(window["start"])
                end = datetime.fromisoformat(window["end"])
            except (KeyError, TypeError, ValueError):
                raise ValueError("Spread sampling plan contains an invalid window") from None
            if bucket not in _BUCKETS or start.tzinfo is None or end.tzinfo is None or end <= start:
                raise ValueError("Spread sampling plan contains an invalid window")
            if day >= cutoff:
                raise ValueError("Spread sample is not before the declared cutoff")
            window_keys.append((day, bucket))
        if len(window_keys) != len(set(window_keys)):
            raise ValueError("Spread sampling plan contains duplicate windows")

        expected = {(symbol, day, bucket) for symbol in symbols for day, bucket in window_keys}
        rows = {}
        statuses = {}
        try:
            decoded = sample_bytes.decode("utf-8")
            reader = csv.DictReader(decoded.splitlines())
            required = {"symbol", "day", "bucket", "status", "half_spread_bps"}
            if not required.issubset(reader.fieldnames or []):
                raise ValueError("Spread sample CSV is missing required columns")
            for row in reader:
                key = (row["symbol"], date.fromisoformat(row["day"]), row["bucket"])
                if key in rows:
                    raise ValueError("Spread sample CSV contains duplicate rows")
                status = row["status"]
                statuses[status] = statuses.get(status, 0) + 1
                if status == "ok":
                    value = _finite_positive(
                        "half_spread_bps", row["half_spread_bps"], allow_zero=True
                    )
                else:
                    value = None
                rows[key] = value
        except (UnicodeDecodeError, csv.Error, KeyError, ValueError) as exc:
            if isinstance(exc, ValueError) and str(exc).startswith("Spread sample"):
                raise
            raise ValueError(f"Invalid spread sample CSV: {exc}") from None
        if set(rows) != expected:
            raise ValueError("Spread sample coverage does not match the frozen plan")
        declared_statuses = manifest.get("sample_statuses")
        if declared_statuses != statuses:
            raise ValueError("Spread sample statuses do not match the manifest")
        self._symbols = frozenset(symbols)
        self._window_keys = tuple(window_keys)
        self._spread_rows = rows

    @staticmethod
    def _trade_time(value):
        if hasattr(value, "to_pydatetime"):
            value = value.to_pydatetime()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ValueError("trade_timestamp must be timezone-aware")
        return value.astimezone(_NY)

    @staticmethod
    def _bucket(local_time):
        from dq import schedule

        day = local_time.date().isoformat()
        sessions = schedule(f"{local_time.year}-01-01", f"{local_time.year}-12-31")
        if day not in sessions.index:
            raise ValueError("trade_timestamp is outside an exchange session")
        session = sessions.loc[day]
        if not session["open"] <= local_time < session["close"]:
            raise ValueError("trade_timestamp is outside the exchange session hours")
        if (session["close"] - session["open"]).total_seconds() != 390 * 60:
            raise ValueError("Early-close sessions have no calibrated spread buckets")
        minute = local_time.hour * 60 + local_time.minute
        if 570 <= minute < 600:
            return "open"
        if 600 <= minute < 930:
            return "mid"
        if 930 <= minute < 960:
            return "close"
        raise ValueError("trade_timestamp is outside 09:30-16:00 America/New_York")

    def _spread(self, symbol, bucket, trade_day):
        candidates = [
            self._spread_rows[(symbol, day, sample_bucket)]
            for day, sample_bucket in self._window_keys
            if sample_bucket == bucket
            and (self.calibration_mode == "retrospective" or day < trade_day)
        ]
        expected = len(candidates)
        values = [value for value in candidates if value is not None]
        coverage = len(values) / expected if expected else 0.0
        if self.calibration_mode == "causal" and len(values) < self.minimum_causal_samples:
            raise ValueError(
                f"Only {len(values)} prior spread samples for {symbol}/{bucket}; "
                f"need {self.minimum_causal_samples}"
            )
        if coverage < self.minimum_spread_coverage:
            raise ValueError(
                f"Spread coverage {coverage:.3f} is below required "
                f"{self.minimum_spread_coverage:.3f} for {symbol}/{bucket}"
            )
        if not values:
            raise ValueError(f"No admitted spread samples for {symbol}/{bucket}")
        spread = float(np.quantile(values, self.spread_quantile))
        if not math.isfinite(spread) or spread < 0:
            raise ValueError("Calibrated spread is nonfinite or negative")
        return spread, len(values), coverage

    def estimate_trade(
        self,
        *,
        symbol,
        trade_timestamp,
        side,
        shares,
        unadjusted_price,
        reference_volume_shares,
        volume_source,
        volume_available_at,
        inputs_are_unadjusted,
    ):
        """Estimate one trade; all share/price/volume inputs must be raw units.

        ``reference_volume_shares`` must have been known before the order for a
        causal estimate.  A completed bar's full volume is future information
        while executing within that bar and is allowed only in retrospective mode.
        """
        symbol = str(symbol).upper()
        if symbol not in self._symbols:
            raise ValueError(f"No admitted spread data for symbol {symbol}")
        side = str(side).lower()
        if side not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'")
        if inputs_are_unadjusted is not True:
            raise ValueError(
                "Actual unadjusted shares, price, and volume must be explicitly confirmed"
            )
        if volume_source not in _ALL_VOLUME_SOURCES:
            raise ValueError(f"Unsupported volume_source {volume_source!r}")
        if self.calibration_mode == "causal" and volume_source not in _CAUSAL_VOLUME_SOURCES:
            raise ValueError("Full-bar volume cannot size a causal within-bar execution")
        shares = _finite_positive("shares", shares)
        price = _finite_positive("unadjusted_price", unadjusted_price)
        volume = _finite_positive("reference_volume_shares", reference_volume_shares)
        participation = shares / volume
        if not math.isfinite(participation) or participation > self.max_participation:
            raise ValueError(
                f"Participation {participation:.6f} exceeds capacity limit "
                f"{self.max_participation:.6f}"
            )
        local_time = self._trade_time(trade_timestamp)
        if volume_source in _CAUSAL_VOLUME_SOURCES:
            available_time = self._trade_time(volume_available_at)
            if available_time > local_time:
                raise ValueError("Reference volume was not available by the order time")
        elif volume_available_at is not None:
            self._trade_time(volume_available_at)  # validate the audit field when supplied
        bucket = self._bucket(local_time)
        half_spread, sample_count, coverage = self._spread(
            symbol, bucket, local_time.date()
        )
        slippage = self.slippage_floor_bps + self.slippage_sqrt_coefficient_bps * math.sqrt(participation)
        if not math.isfinite(slippage) or slippage < 0:
            raise ValueError("Calculated slippage is nonfinite or negative")
        notional = shares * price
        if not math.isfinite(notional) or notional <= 0:
            raise ValueError("shares * unadjusted_price must be finite and positive")
        execution_cost = notional * (half_spread + slippage) / 10_000.0
        fees = (
            equity_sell_fees(
                local_time.date(),
                shares,
                price,
                rounding_mode=self.regulatory_fee_rounding,
            )
            if side == "sell"
            else RegulatoryFees(0.0, 0.0)
        )
        total = execution_cost + fees.total_dollars
        if not math.isfinite(execution_cost) or not math.isfinite(total):
            raise ValueError("Calculated trade cost is nonfinite")
        total_bps = total / notional * 10_000.0
        if not math.isfinite(total_bps):
            raise ValueError("Calculated trade cost bps is nonfinite")
        return IntradayCostEstimate(
            symbol=symbol,
            bucket=bucket,
            side=side,
            calibration_mode=self.calibration_mode,
            spread_half_bps=half_spread,
            spread_sample_count=sample_count,
            spread_coverage=coverage,
            participation=participation,
            slippage_bps=slippage,
            regulatory_fees=fees,
            execution_cost_dollars=execution_cost,
            total_cost_dollars=total,
            total_cost_bps=total_bps,
            volume_source=volume_source,
        )


def print_draft_table():
    """Offline illustration with reviewed quotes and hypothetical raw orders."""
    from datetime import timedelta

    model = IntradayCostModel(
        spread_samples_path='research_data/spread_samples.csv',
        spread_manifest_path='research_data/spreads_manifest.json',
        expected_plan_hash='f85ba067ce51c73c',
        expected_samples_sha256='8fad9510aaa36c42735db7ea6027986e19a2a4162cad01731c050a6654b81c7e',
        calibration_mode='retrospective', spread_quantile=0.95,
        minimum_spread_coverage=0.90, minimum_causal_samples=20,
        slippage_floor_bps=1.0, slippage_sqrt_coefficient_bps=25.0,
        max_participation=0.05,
        regulatory_fee_rounding='ceil_cent_per_component',
    )
    print('UNSIGNED INTRADAY DRAFT — retrospective quote calibration, not OOS evidence')
    print('Hypothetical SPY: 50 raw shares at $500, reference volume 10,000 shares')
    print('2024-06-03; participation 0.5%; fees rounded up per component')
    print('bucket  half-spread  slippage  buy-bps  sell-bps  round-trip-bps  total-$')
    for hour, minute in ((9, 45), (12, 0), (15, 45)):
        stamp = datetime(2024, 6, 3, hour, minute, tzinfo=_NY)
        kwargs = dict(symbol='SPY', trade_timestamp=stamp, shares=50,
                      unadjusted_price=500, reference_volume_shares=10_000,
                      volume_source='prior_bar',
                      volume_available_at=stamp - timedelta(minutes=1),
                      inputs_are_unadjusted=True)
        buy = model.estimate_trade(side='buy', **kwargs)
        sell = model.estimate_trade(side='sell', **kwargs)
        print(f'{buy.bucket:5s} {buy.spread_half_bps:11.6f} {buy.slippage_bps:9.6f}'
              f' {buy.total_cost_bps:8.6f} {sell.total_cost_bps:9.6f}'
              f' {buy.total_cost_bps + sell.total_cost_bps:15.6f}'
              f' {buy.total_cost_dollars + sell.total_cost_dollars:8.6f}')
    print('Legacy LIQUID ETF (3/1 bps): 5.000000 bps round trip; unchanged.')
    print('No INTRADAY singleton is adopted. Tenzing sign-off remains pending.')


if __name__ == '__main__':
    print_draft_table()
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


## Unsigned I1.5 execution draft — 2026-09-17

`IntradayCostModel` is opt-in and refuses the legacy turnover-only API. The full
canonical source above includes the offline table command `.venv/bin/python costs.py`.
The concrete proposal uses p95 quoted half-spreads, slippage `1 + 25*sqrt(p)` bps
per side, maximum participation 5%, minimum coverage 90%, 20 prior samples for
causal calibration and cent-ceiling sell fees. These are **unsigned assumptions**,
not measured fills or an adopted regime. See [[research/intraday-cost-proposal]]
for official fee sources, reproduction, stress assumptions and approval status.

Real I1.4 quotes with hypothetical SPY orders (50 raw shares at $500, reference
volume 10,000) produce round-trip costs of **6.509586 bps open**, **6.358773 midday**
and **6.332425 close**. This is retrospective calibration, not OOS evidence.
The adjusted ALL bar cache cannot supply raw execution inputs without a verified
conversion or raw companion data. Closed days and early-close sessions are refused;
causal volume must have been available before execution. Tenzing's signature is
pending; the legacy daily/options cost model is unchanged.
