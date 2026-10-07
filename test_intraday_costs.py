"""Failure-boundary tests for the unsigned I1.5 intraday cost draft."""
from datetime import datetime, timedelta, timezone
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from costs import CostModel, IntradayCostModel, equity_sell_fees


class IntradayCostTests(unittest.TestCase):
    DAYS = ("2016-01-04", "2016-06-01", "2020-01-02", "2023-01-03")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _artifact(self, *, mutate_rows=None, mutate_manifest=None):
        windows = []
        rows = []
        values = {
            "open": (2.0, 4.0, 6.0, 100.0),
            "mid": (1.0, 1.5, 2.0, 3.0),
            "close": (1.5, 2.0, 2.5, 4.0),
        }
        for day_index, day in enumerate(self.DAYS):
            for bucket in ("open", "mid", "close"):
                windows.append(
                    {
                        "day": day,
                        "bucket": bucket,
                        "start": f"{day}T15:00:00+00:00",
                        "end": f"{day}T15:00:01+00:00",
                    }
                )
                rows.append(
                    {
                        "symbol": "SPY",
                        "day": day,
                        "bucket": bucket,
                        "status": "ok",
                        "half_spread_bps": values[bucket][day_index],
                    }
                )
        if mutate_rows:
            mutate_rows(rows)
        samples = self.root / "spread_samples.csv"
        with samples.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=("symbol", "day", "bucket", "status", "half_spread_bps"),
            )
            writer.writeheader()
            writer.writerows(rows)
        sample_sha = hashlib.sha256(samples.read_bytes()).hexdigest()
        plan = {
            "version": 1,
            "feed": "sip",
            "days_per_year": 20,
            "cutoff_exclusive": "2026-09-14",
            "symbols": ["SPY"],
            "windows": windows,
        }
        plan_hash = hashlib.sha256(
            json.dumps(plan, sort_keys=True).encode()
        ).hexdigest()[:16]
        statuses = {}
        for row in rows:
            statuses[row["status"]] = statuses.get(row["status"], 0) + 1
        manifest_doc = {
            "backfill_complete": True,
            "files": ["spreads.csv", "spreads_by_year.csv", "spread_samples.csv"],
            "generated_at": "2026-09-15T14:38:57+00:00",
            "plan_hash": plan_hash,
            "sample_statuses": statuses,
            "sampling_plan": plan,
        }
        if mutate_manifest:
            mutate_manifest(manifest_doc)
        manifest = self.root / "spreads_manifest.json"
        manifest.write_text(json.dumps(manifest_doc))
        return samples, manifest, plan_hash, sample_sha

    def _model(self, *, calibration_mode="retrospective", **overrides):
        artifact_args = overrides.pop("artifact_args", None)
        if artifact_args is None:
            artifact_args = self._artifact()
        samples, manifest, plan_hash, sample_sha = artifact_args
        kwargs = {
            "spread_samples_path": samples,
            "spread_manifest_path": manifest,
            "expected_plan_hash": plan_hash,
            "expected_samples_sha256": sample_sha,
            "calibration_mode": calibration_mode,
            "spread_quantile": 0.95,
            "minimum_spread_coverage": 0.90,
            "minimum_causal_samples": 2,
            "slippage_floor_bps": 1.0,
            "slippage_sqrt_coefficient_bps": 25.0,
            "max_participation": 0.05,
            "regulatory_fee_rounding": "ceil_cent_per_component",
        }
        kwargs.update(overrides)
        return IntradayCostModel(**kwargs)

    @staticmethod
    def _trade_kwargs(stamp, **overrides):
        kwargs = {
            "symbol": "SPY",
            "trade_timestamp": stamp,
            "side": "buy",
            "shares": 50,
            "unadjusted_price": 500,
            "reference_volume_shares": 10_000,
            "volume_source": "prior_bar",
            "volume_available_at": stamp - timedelta(minutes=1),
            "inputs_are_unadjusted": True,
        }
        kwargs.update(overrides)
        return kwargs

    def test_legacy_cost_model_outputs_are_unchanged(self):
        turnover = np.array([0.0, 0.5, 1.0])
        got = CostModel(3, 1, 2, 10_000).cost_fraction(turnover)
        expected = turnover * 2.5 / 10_000 + np.array([0.0, 0.0002, 0.0002])
        np.testing.assert_array_equal(got, expected)

    def test_intraday_model_cannot_enter_legacy_engine(self):
        with self.assertRaisesRegex(TypeError, "estimate_trade"):
            self._model().cost_fraction([1.0])

    def test_spread_artifact_identity_and_completeness_fail_closed(self):
        args = self._artifact()
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self._model(artifact_args=(*args[:3], "0" * 64))

        args = self._artifact(mutate_manifest=lambda doc: doc.update(backfill_complete=False))
        with self.assertRaisesRegex(ValueError, "backfill"):
            self._model(artifact_args=args)

        def remove_row(rows):
            rows.pop()

        args = self._artifact(mutate_rows=remove_row)
        with self.assertRaisesRegex(ValueError, "frozen plan"):
            self._model(artifact_args=args)

    def test_nonfinite_spread_and_low_coverage_are_rejected(self):
        def nonfinite(rows):
            rows[0]["half_spread_bps"] = "nan"

        with self.assertRaisesRegex(ValueError, "finite"):
            self._model(artifact_args=self._artifact(mutate_rows=nonfinite))

        def invalidate(rows):
            rows[0].update(status="locked_or_crossed", half_spread_bps="")

        model = self._model(
            artifact_args=self._artifact(mutate_rows=invalidate),
            minimum_spread_coverage=0.80,
        )
        with self.assertRaisesRegex(ValueError, "coverage"):
            model.estimate_trade(
                **self._trade_kwargs(datetime(2024, 6, 3, 13, 45, tzinfo=timezone.utc))
            )

    def test_causal_calibration_excludes_same_day_and_future_values(self):
        causal = self._model(calibration_mode="causal")
        retrospective = self._model(calibration_mode="retrospective")
        stamp = datetime(2020, 1, 2, 14, 45, tzinfo=timezone.utc)
        causal_cost = causal.estimate_trade(**self._trade_kwargs(stamp))
        retrospective_cost = retrospective.estimate_trade(**self._trade_kwargs(stamp))
        self.assertEqual(causal_cost.spread_sample_count, 2)
        self.assertAlmostEqual(causal_cost.spread_half_bps, 3.9)
        self.assertGreater(retrospective_cost.spread_half_bps, 80)

        early = datetime(2016, 1, 4, 14, 45, tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError, "prior spread samples"):
            causal.estimate_trade(**self._trade_kwargs(early))

    def test_causal_sizing_rejects_full_current_bar_volume(self):
        model = self._model(calibration_mode="causal")
        stamp = datetime(2024, 6, 3, 14, 45, tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError, "Full-bar volume"):
            model.estimate_trade(
                **self._trade_kwargs(
                    stamp,
                    volume_source="full_bar_retrospective",
                    volume_available_at=None,
                )
            )

        with self.assertRaisesRegex(ValueError, "not available"):
            model.estimate_trade(
                **self._trade_kwargs(
                    stamp,
                    volume_available_at=stamp + timedelta(seconds=1),
                )
            )

    def test_capacity_boundary_and_raw_input_assertion(self):
        model = self._model()
        stamp = datetime(2024, 6, 3, 16, 0, tzinfo=timezone.utc)
        accepted = model.estimate_trade(
            **self._trade_kwargs(stamp, shares=500, reference_volume_shares=10_000)
        )
        self.assertAlmostEqual(accepted.participation, 0.05)
        with self.assertRaisesRegex(ValueError, "capacity"):
            model.estimate_trade(
                **self._trade_kwargs(stamp, shares=501, reference_volume_shares=10_000)
            )
        with self.assertRaisesRegex(ValueError, "unadjusted"):
            model.estimate_trade(
                **self._trade_kwargs(stamp, inputs_are_unadjusted=False)
            )
        with self.assertRaisesRegex(ValueError, "finite"):
            model.estimate_trade(
                **self._trade_kwargs(stamp, unadjusted_price=float("inf"))
            )

    def test_time_buckets_and_regular_hours_fail_closed(self):
        model = self._model()
        cases = {
            datetime(2024, 6, 3, 13, 30, tzinfo=timezone.utc): "open",
            datetime(2024, 6, 3, 14, 0, tzinfo=timezone.utc): "mid",
            datetime(2024, 6, 3, 19, 30, tzinfo=timezone.utc): "close",
        }
        for stamp, bucket in cases.items():
            with self.subTest(bucket=bucket):
                got = model.estimate_trade(**self._trade_kwargs(stamp))
                self.assertEqual(got.bucket, bucket)
        with self.assertRaisesRegex(ValueError, "outside"):
            model.estimate_trade(
                **self._trade_kwargs(datetime(2024, 6, 3, 20, 0, tzinfo=timezone.utc))
            )
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            model.estimate_trade(
                **self._trade_kwargs(datetime(2024, 6, 3, 12, 0))
            )

    def test_regulatory_fee_effective_dates_sell_only_and_caps(self):
        before = equity_sell_fees(
            datetime(2024, 5, 21), 10, 500, rounding_mode="raw_statutory"
        )
        after = equity_sell_fees(
            datetime(2024, 5, 22), 10, 500, rounding_mode="raw_statutory"
        )
        self.assertAlmostEqual(before.section_31_dollars, 0.04)
        self.assertAlmostEqual(after.section_31_dollars, 0.139)
        self.assertEqual(
            equity_sell_fees(
                datetime(2025, 5, 14), 10, 500, rounding_mode="raw_statutory"
            ).section_31_dollars,
            0,
        )
        self.assertAlmostEqual(
            equity_sell_fees(
                datetime(2026, 4, 4), 10, 500, rounding_mode="raw_statutory"
            ).section_31_dollars,
            0.103,
        )
        self.assertAlmostEqual(
            equity_sell_fees(
                datetime(2026, 1, 2),
                100_000,
                1,
                rounding_mode="raw_statutory",
            ).finra_taf_dollars,
            9.79,
        )
        with self.assertRaisesRegex(ValueError, "outside"):
            equity_sell_fees(
                datetime(2026, 9, 17), 10, 500, rounding_mode="raw_statutory"
            )

        rounded = equity_sell_fees(
            datetime(2025, 5, 14),
            1,
            500,
            rounding_mode="ceil_cent_per_component",
        )
        self.assertEqual(rounded.section_31_dollars, 0)
        self.assertEqual(rounded.finra_taf_dollars, 0.01)
        with self.assertRaisesRegex(ValueError, "finite"):
            equity_sell_fees(
                datetime(2024, 1, 1),
                1e308,
                1e308,
                rounding_mode="raw_statutory",
            )

        model = self._model()
        stamp = datetime(2024, 6, 3, 16, 0, tzinfo=timezone.utc)
        buy = model.estimate_trade(**self._trade_kwargs(stamp, side="buy"))
        sell = model.estimate_trade(**self._trade_kwargs(stamp, side="sell"))
        self.assertEqual(buy.regulatory_fees.total_dollars, 0)
        self.assertGreater(sell.regulatory_fees.total_dollars, 0)

    def test_calendar_and_numerical_boundaries(self):
        model = self._model()
        for stamp in (
            datetime(2024, 6, 2, 16, tzinfo=timezone.utc),
            datetime(2024, 7, 4, 16, tzinfo=timezone.utc),
            datetime(2024, 11, 29, 15, tzinfo=timezone.utc),
            datetime(2024, 11, 29, 20, tzinfo=timezone.utc),
            datetime(2025, 1, 9, 16, tzinfo=timezone.utc),
        ):
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                model.estimate_trade(**self._trade_kwargs(stamp))
        stamp = datetime(2024, 6, 3, 16, tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError, "positive"):
            model.estimate_trade(**self._trade_kwargs(
                stamp, shares=1e-300, unadjusted_price=1e-300))
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            model.estimate_trade(**self._trade_kwargs(
                stamp, side="sell", shares=1e-308, unadjusted_price=1))

    def test_concrete_spy_open_round_trip_exceeds_midday(self):
        model = self._model()
        open_time = datetime(2024, 6, 3, 13, 45, tzinfo=timezone.utc)
        mid_time = datetime(2024, 6, 3, 16, 0, tzinfo=timezone.utc)

        def round_trip(stamp):
            buy = model.estimate_trade(**self._trade_kwargs(stamp, side="buy"))
            sell = model.estimate_trade(**self._trade_kwargs(stamp, side="sell"))
            return buy.total_cost_bps + sell.total_cost_bps

        self.assertGreater(round_trip(open_time), round_trip(mid_time))


if __name__ == "__main__":
    unittest.main()
