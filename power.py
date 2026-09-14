"""Three-way gate: PASS / FAIL / INCONCLUSIVE, with statistical power (plan/14 I0.1).

The old binary gate (t >= 2 or not) cannot tell "no edge" from "not enough data to tell".
A monthly strategy with a real but modest edge needs decades of history to reach t >= 2,
so a short sample FAILing proves nothing. This module adds the third outcome.

Everything is in annualized information ratio (IR) of the ACTIVE return series
(strategy minus benchmark), with T = years of data and observed t = IR_hat * sqrt(T).
Pre-registered rule -- NOT tuned to any strategy's numbers:

  PASS          observed t >= 2
  FAIL          the edge is ruled out: IR_hat + 1.96/sqrt(T) < IR_MIN
                (upper end of the 95% CI on IR is below the minimum edge worth trading)
  INCONCLUSIVE  everything else

Also reported:
  power     = P(t >= 2 | true IR = IR_MIN) = 1 - Phi(2 - IR_MIN * sqrt(T))
  years_80  = years needed for 80% power = ((2 + 0.8416) / IR_MIN) ** 2

No scipy: the normal CDF uses math.erf.

    python3 power.py      # self-test
"""
import math

import numpy as np

IR_MIN = 0.5          # minimum annual IR worth trading (plan/14)
T_PASS = 2.0          # observed t needed to PASS
Z_CI = 1.96           # two-sided 95% CI
Z_POWER_80 = 0.8416   # Phi^-1(0.80)


def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def power_at(years, ir_min=IR_MIN):
    """P(observed t >= 2 | true IR = ir_min) over `years` of data."""
    return 1.0 - norm_cdf(T_PASS - ir_min * math.sqrt(years))


def years_for_80pct_power(ir_min=IR_MIN):
    return ((T_PASS + Z_POWER_80) / ir_min) ** 2


def three_way(ir_hat, years, ir_min=IR_MIN):
    """Apply the pre-registered rule to an annualized IR estimate over `years` of data."""
    t = ir_hat * math.sqrt(years)
    ci_hi = ir_hat + Z_CI / math.sqrt(years)
    if t >= T_PASS:
        verdict = 'PASS'
    elif ci_hi < ir_min:
        verdict = 'FAIL'
    else:
        verdict = 'INCONCLUSIVE'
    return {'verdict': verdict, 't': float(t), 'ir_hat': float(ir_hat), 'years': float(years),
            'ir_ci_hi': float(ci_hi), 'ir_min': float(ir_min),
            'power': float(power_at(years, ir_min)),
            'years_for_80pct_power': float(years_for_80pct_power(ir_min))}


def from_t(t, n_periods, ppy=12, ir_min=IR_MIN):
    """Same rule from an already-computed t-stat of the mean of n_periods active returns
    (t = IR_hat * sqrt(T), so IR_hat = t / sqrt(T) with T = n_periods / ppy)."""
    years = n_periods / ppy
    return three_way(t / math.sqrt(years), years, ir_min)


def from_active(active, ppy=12, ir_min=IR_MIN):
    """Same rule from a raw active-return series (strategy minus benchmark), per-period."""
    x = np.asarray(active, float)
    x = x[~np.isnan(x)]
    sd = x.std(ddof=1)
    return three_way(float(x.mean() / sd * math.sqrt(ppy)), len(x) / ppy, ir_min)


def _selftest():
    ok = True

    def chk(name, cond, detail=''):
        nonlocal ok
        ok &= bool(cond)
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ''))

    print('=== power.py self-test ===')
    chk('norm_cdf(0) = 0.5', abs(norm_cdf(0) - 0.5) < 1e-12)
    chk('norm_cdf(1.96) ~ 0.975', abs(norm_cdf(1.96) - 0.975) < 1e-3, f'{norm_cdf(1.96):.5f}')
    chk('norm_cdf(0.8416) ~ 0.80', abs(norm_cdf(Z_POWER_80) - 0.80) < 1e-4)
    # IR_MIN * sqrt(T) = 2 at T = 16 years -> power exactly 50%
    chk('power = 50% at T = (2/IR_MIN)^2 = 16y', abs(power_at(16) - 0.5) < 1e-12, f'{power_at(16):.4f}')
    y80 = years_for_80pct_power()
    chk('years for 80% power ~ 32.3', abs(y80 - 32.29) < 0.01, f'{y80:.2f}')
    chk('power at years_80 = 80%', abs(power_at(y80) - 0.80) < 1e-4, f'{power_at(y80):.4f}')

    chk('rule: t >= 2 -> PASS', three_way(0.5, 16.0)['verdict'] == 'PASS')
    chk('rule: IR 0 over 100y -> FAIL (ci_hi 0.196 < 0.5)', three_way(0.0, 100)['verdict'] == 'FAIL')
    chk('rule: IR 0.3 over 3y -> INCONCLUSIVE', three_way(0.3, 3)['verdict'] == 'INCONCLUSIVE')
    r = from_t(0.34, 84)
    chk('from_t round-trips t', abs(r['t'] - 0.34) < 1e-12, f"IR_hat={r['ir_hat']:.3f}, T={r['years']:.1f}y")

    # Monte Carlo: the closed-form power matches simulated PASS rate at true IR = IR_MIN.
    rng = np.random.default_rng(0)
    years, n = 10, 120
    mu = IR_MIN / math.sqrt(12) * 0.04
    sims = rng.normal(mu, 0.04, size=(4000, n))
    rate = np.mean([from_active(s)['verdict'] == 'PASS' for s in sims])
    chk('simulated PASS rate matches closed-form power (10y)',
        abs(rate - power_at(years)) < 0.03, f'sim {rate:.3f} vs formula {power_at(years):.3f}')

    print('All green.' if ok else 'FAILED.')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(_selftest())
