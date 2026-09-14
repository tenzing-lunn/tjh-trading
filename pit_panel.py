"""Point-in-time price panel + eligibility mask (P1.4, design doc §6.3).

`xsect.py` today runs on `realdata/` -- 30 tickers hand-picked in 2026. Every one of them
survived to 2026 (survivorship) and was picked *because* it won 2019-2026 (winner selection).
This module builds the honest alternative: the (dates x companies) close panel of everything
that was EVER in the S&P 500 over the window, plus a boolean `eligible[date, company]` saying
whether it was actually a member on that date -- including the names that went bankrupt or
were bought and no longer have a Yahoo page.

Inputs: research_data/universe/membership.csv (fetch_membership.py)
        research_data/pit_prices/*.csv + coverage.json (fetch_pit_prices.py)

THE PATCH RULES (design doc §2.3, applied verbatim except where noted):
  A acquired/merged   price ends at the last close, NO haircut (the deal is priced in by the
                      final day). Missing entirely -> held-period return 0%, flagged missing_acq.
  B bankruptcy        one synthetic final bar at last_close*(1-h): Shumway (1997) measured the
                      missing delisting return at ~-30% on NYSE/AMEX, Shumway & Warther (1999)
                      ~-55% on Nasdaq. Missing entirely -> -100%, flagged missing_bkr.
  C dropped, still listed  nothing to the prices; `eligible` flips False and the existing
                      turnover/cost machinery in xsect.run_panel sells at the next rebalance.
  D rename/spin-off   old and new symbol are ONE company (one panel column), joined by
                      research_data/universe/renames.csv.

`patch='optimistic' | 'pessimistic'` brackets what we cannot know (design doc §3, "the
skeptic's rail"): if the momentum-vs-EW verdict flips between the two, the free data is not
good enough to decide and we must say so instead of picking the answer we like.

    optimistic   class-B haircut h = 0; every missing span is held flat at 0% return.
    pessimistic  h = 0.30 NYSE/AMEX, 0.55 Nasdaq/OTC; a missing span whose exit was an actual
                 EXIT EVENT (class A or B) ends at -100%.

    python3 pit_panel.py            # build + run all five P1.4 acceptance tests
"""
import argparse
import collections
import datetime
import json
import os

import numpy as np
import pandas as pd

from fetch_membership import load_membership, load_renames
import fetch_pit_prices as fpp

WINDOW_START = '2009-01-01'          # the primary no-hindsight window (design doc §2.2)
WARMUP_DAYS = 500                    # calendar days of price history before WINDOW_START,
                                     # so the 12-1 score is already warm on day one
HAIRCUT_NYSE = 0.30                  # Shumway (1997), J. Finance 52:327-340
HAIRCUT_NASDAQ = 0.55                # Shumway & Warther (1999), J. Finance 54:2361-2379
NYSE_LIKE = {'NYSE', 'AMEX', 'NYSE MKT', 'NYSE ARCA', 'BATS'}


def _d(s):
    return datetime.date.fromisoformat(s) if s else None


def haircut_for(exchange):
    """Shumway's delisting-return haircut by listing venue. Tiingo's supported_tickers
    manifest carries an `exchange` column, which is where this comes from -- no separate
    exchange lookup is needed. JUDGMENT CALL: OTC/pink venues (a delisted name's last home)
    are not in either Shumway sample; they get the Nasdaq (worse) number, because a stock
    that has fallen to the pink sheets is not the NYSE case."""
    return HAIRCUT_NYSE if (exchange or '').upper() in NYSE_LIKE else HAIRCUT_NASDAQ


def build(patch='optimistic', window_start=WINDOW_START, window_end=None, verbose=True):
    """-> (panel, eligible, report).

    panel     DataFrame (trading dates x company) of adjusted closes, patched per the rules
              above. Columns are COMPANIES, not tickers: a rename is one column.
    eligible  boolean DataFrame, same shape: was this company an index member on this date.
              False everywhere before window_start, so the run window is exact.
    report    dict of patch counts / coverage, for the acceptance-test printout.
    """
    if patch not in ('optimistic', 'pessimistic'):
        raise ValueError("patch must be 'optimistic' or 'pessimistic'")
    meta = fpp.supported_tickers()
    companies = fpp.build_companies(meta=meta)
    man = fpp.load_manifest()

    ws = _d(window_start)
    we = _d(window_end) if window_end else fpp.TODAY
    px_start = ws - datetime.timedelta(days=WARMUP_DAYS)

    # The trading calendar. SPY is the cleanest US equity calendar we have from the same
    # vendor; using it keeps stray OTC session dates out of the panel.
    spy = fpp.load_prices('SPY')
    if spy is None:
        raise SystemExit('research_data/pit_prices/SPY.csv missing -- run fetch_pit_prices.py')
    calendar = spy.loc[str(px_start):str(we)].index

    closes, elig, patches = {}, {}, collections.Counter()
    span_status, notes = [], []
    for g in companies:
        sym = g['price_symbol']
        key = g['key']
        spans = [s for s in g['spans']
                 if (_d(s['end_date']) or fpp.TODAY) >= ws and _d(s['start_date']) <= we]
        if not spans:
            continue                                   # entirely outside the window
        raw = fpp.load_prices(sym) if sym else None
        if raw is not None and man['symbols'].get(sym, {}).get('status') != 'fetched':
            raw = None
        col = (raw['close'].reindex(calendar) if raw is not None
               else pd.Series(np.nan, index=calendar))
        e = pd.Series(False, index=calendar)
        exch = (meta.get(sym) or {}).get('exchange', '')

        # Is a gap in this company's prices a real data gap, or just a symbol this month's
        # 500-symbol budget has not reached yet? The two must not be conflated: a genuinely
        # absent dead name gets the §2.3 patch (that is the whole point of the exercise),
        # while a not-yet-fetched name is simply held OUT of the universe, because pretending
        # a live company was flat at 0% would corrupt the panel for a reason that has nothing
        # to do with survivorship.
        st = man['symbols'].get(sym, {}).get('status') if sym else 'missing_no_tiingo_data'
        vendor_has_nothing = (sym is None or st in ('missing_no_tiingo_data', 'error'))
        pending = (st is None)

        spans = sorted(spans, key=lambda s: s['start_date'])
        terminal = None                       # (date, kind, value) -- applied once, at the end
        for i, s in enumerate(spans):
            a, b = _d(s['start_date']), _d(s['end_date'])
            b_eff = b or (we + datetime.timedelta(days=1))
            # Eligible on [start_date, end_date): never selected ON or after the exit date.
            in_span = (calendar >= pd.Timestamp(a)) & (calendar < pd.Timestamp(b_eff))
            real = col[in_span].dropna()
            covered = len(real) > 0
            # Judge coverage against the part of the span INSIDE the panel window: a span
            # that started in 1996 is not "partial" just because the panel starts in 2007.
            a_win = max(a, calendar[0].date())
            b_win = min(b_eff, we)
            full = covered and (real.index[0].date() <= a_win + datetime.timedelta(days=10)
                                and real.index[-1].date() >= b_win - datetime.timedelta(days=10))
            status = ('priced_full' if full else 'priced_partial') if covered else (
                'pending_fetch' if pending else 'missing')
            span_status.append({'company': key, 'ticker': s['ticker'],
                                'exit_class': s['exit_class'], 'status': status})
            if status == 'pending_fetch':
                patches['pending_fetch_excluded'] += 1
                continue                       # NOT eligible: out of the universe entirely
            e |= pd.Series(in_span, index=calendar)
            # A terminal event may only be applied at the company's LAST span in the window.
            # Otherwise a re-entry would refill the column after it had been zeroed out and
            # the panel would show a +1e9 return on the join.
            is_last = (i == len(spans) - 1)

            if status == 'missing':
                # No prices at all, and the vendor genuinely has none. Hold it FLAT (0%
                # return) so the name is still IN the universe -- dropping it is exactly the
                # bias we are removing.
                fill = (calendar >= pd.Timestamp(a - datetime.timedelta(days=WARMUP_DAYS))) \
                    & (calendar < pd.Timestamp(b_eff))
                col[fill & col.isna()] = 1.0
                if patch == 'pessimistic' and s['exit_class'] in ('A', 'B') and is_last:
                    # The pessimistic bracket: an unpriced ACTUAL EXIT is a total loss.
                    # JUDGMENT CALL: not applied to class C (still listed, nothing happened to
                    # the holder) or D (a rename, not an exit) -- '-100% for every missing
                    # name' would not be a bracket there, it would be nonsense.
                    terminal = (pd.Timestamp(b_eff), 'zero', 0.0)
                    patches['missing_bkr' if s['exit_class'] == 'B' else 'missing_acq_zeroed'] += 1
                else:
                    patches['missing_flat'] += 1
                continue

            if s['exit_class'] == 'B' and is_last:
                # Shumway haircut -- but only if the series actually ENDS here. PCG filed and
                # kept trading (and re-entered the index); a holder could sell at the quote, so
                # there is no missing delisting return to impute. JUDGMENT CALL, documented.
                last = real.index[-1]
                series_ends = col.loc[last:].dropna().index[-1] <= pd.Timestamp(
                    min(b_eff, we) + datetime.timedelta(days=10))
                if series_ends:
                    h = 0.0 if patch == 'optimistic' else haircut_for(exch)
                    if h > 0:
                        terminal = (last, 'haircut', float(col.loc[last]) * (1 - h))
                        patches['haircut_bkr'] += 1
                        notes.append(f'{key} ({exch}): class B haircut {h:.0%} after {last.date()}')
                    else:
                        patches['haircut_bkr_zero'] += 1

        if terminal is not None:
            when, kind, value = terminal
            after = calendar[calendar > when] if kind == 'haircut' else \
                calendar[calendar >= when]
            if len(after):
                # One synthetic final bar, then the series ends (NaN -> 0% daily return; the
                # position is sold at the next rebalance by the engine's own turnover logic).
                col.loc[after[0]] = value if kind == 'haircut' else \
                    float(col.loc[:when].dropna().iloc[-1]) * 1e-9
                col.loc[after[1:]] = np.nan

        closes[key] = col
        elig[key] = e

    panel = pd.DataFrame(closes).sort_index()
    eligible = pd.DataFrame(elig).reindex(columns=panel.columns).fillna(False)
    eligible.loc[eligible.index < pd.Timestamp(ws)] = False     # exact run window

    by = collections.Counter((s['exit_class'], s['status']) for s in span_status)
    report = {'patch': patch, 'n_companies': panel.shape[1], 'n_spans': len(span_status),
              'window': [str(ws), str(we)], 'patches': dict(patches),
              'by_class_status': {f'{k[0]}|{k[1]}': v for k, v in by.items()},
              'span_status': span_status, 'notes': notes,
              'n_fetched': sum(1 for v in man['symbols'].values() if v.get('status') == 'fetched')}
    if verbose:
        print(f"Panel: {panel.shape[0]} bars x {panel.shape[1]} companies "
              f"({ws} -> {we}), patch={patch}")
    return panel, eligible, report


# ------------------------------------------------------------------ patch report

def patch_table(report):
    classes = ['A', 'B', 'C', 'D', 'active']
    statuses = ['priced_full', 'priced_partial', 'missing', 'pending_fetch']
    by = report['by_class_status']
    out = [f"  {'exit class':<12}" + ''.join(f'{s:>16}' for s in statuses) + f"{'total':>8}",
           '  ' + '-' * 84]
    for c in classes:
        row = [by.get(f'{c}|{s}', 0) for s in statuses]
        if not sum(row):
            continue
        out.append(f'  {c:<12}' + ''.join(f'{v:>16d}' for v in row) + f'{sum(row):>8d}')
    out.append('  ' + '-' * 84)
    tot = [sum(by.get(f'{c}|{s}', 0) for c in classes) for s in statuses]
    out.append(f"  {'ALL':<12}" + ''.join(f'{v:>16d}' for v in tot) + f'{sum(tot):>8d}')
    n = sum(tot)
    out.append(f'  priced (full or partial): {tot[0] + tot[1]}/{n} = '
               f'{(tot[0] + tot[1]) / n * 100:.1f}% of spans in the window')
    out.append(f'  patched (vendor has no data at all): {tot[2]} spans -- these are the dead '
               f'names the §2.3 rules impute')
    out.append(f'  NOT YET FETCHED (Tiingo 500/month budget): {tot[3]} spans -- held OUT of '
               f'the universe, not imputed')
    out.append(f"  patches applied: {report['patches'] or 'none'}")
    return '\n'.join(out)


# ------------------------------------------------------------- acceptance tests

def _pct(v):
    return f'{v * 100:8.1f}%' if v == v else '     nan'


def spans_by_company(membership, renames):
    out = collections.defaultdict(list)
    for r in membership:
        key = fpp.rename_chain(r['ticker'], renames)[-1].replace('.', '-')
        out[key].append((_d(r['start_date']), _d(r['end_date']) or datetime.date(2999, 1, 1)))
    return out


def test_lookahead(weights, eligible, membership, renames):
    """ACCEPTANCE TEST 1 -- asserted over the ACTUAL frames, not claimed by construction:
      1. every True cell of the eligibility mask lies inside a real membership span;
      2. no company is ever HELD on a date before its first membership start_date;
      3. no company is ever SELECTED -- given a freshly-set positive target weight on a
         rebalance date -- outside [start_date, end_date).
    A position carried between rebalances can outlive `end_date` (that is what the engine's
    turnover/cost logic is for); a fresh *selection* never can."""
    sp_by = spans_by_company(membership, renames)
    bad_mask, bad_hold, bad_pick = [], [], []

    for col in weights.columns:
        sp = sp_by.get(col, [])
        if not sp:
            bad_mask.append((col, 'no membership span at all'))
            continue
        e = eligible[col]
        on = e.index[e.values]
        if len(on):
            ok = np.zeros(len(on), dtype=bool)
            for a, b in sp:
                ok |= (on >= pd.Timestamp(a)) & (on < pd.Timestamp(b))
            if not ok.all():
                bad_mask.append((col, str(on[~ok][0].date())))

    held = weights.shift(1).fillna(0.0)
    for col in weights.columns:
        sp = sp_by.get(col, [])
        if not sp:
            continue
        h = held.index[held[col] > 0]
        if len(h) and h[0].date() < min(a for a, _ in sp):
            bad_hold.append((col, str(h[0].date()), str(min(a for a, _ in sp))))

    # A row that differs from the previous bar's row is a rebalance the engine actually set.
    changed = (weights != weights.shift(1)).any(axis=1)
    changed.iloc[0] = True
    for t in weights.index[changed]:
        row = weights.loc[t]
        for col in row.index[row > 0]:
            if not any(a <= t.date() < b for a, b in sp_by.get(col, [])):
                bad_pick.append((col, str(t.date())))
    return bad_mask, bad_hold, bad_pick


def main():
    ap = argparse.ArgumentParser(description='P1.4 point-in-time panel + acceptance tests')
    ap.add_argument('--window-start', default=WINDOW_START)
    ap.add_argument('--window-end', default=None)
    args = ap.parse_args()

    import xsect
    from backtest import run_backtest
    from metrics import compute_metrics
    from data import load_csv

    membership, renames = load_membership(), load_renames()
    man = fpp.load_manifest()
    n_fetched = sum(1 for v in man['symbols'].values() if v.get('status') == 'fetched')

    results = {}
    for patch in ('optimistic', 'pessimistic'):
        print('\n' + '=' * 78)
        print(f'POINT-IN-TIME S&P 500 PANEL -- patch = {patch}')
        print('=' * 78)
        panel, eligible, rep = build(patch, args.window_start, args.window_end)
        mom = xsect._first_active(xsect.run_panel(
            panel, xsect.target_weights(panel, eligible=eligible)))
        ew_w = xsect._ew_weights(panel, xsect.LOOKBACK, eligible=eligible)
        ew = xsect._first_active(xsect.run_panel(panel, ew_w)).reindex(mom.index).dropna()
        mom = mom.reindex(ew.index)
        m, m_ew = compute_metrics(mom), compute_metrics(ew)
        act = (xsect._monthly_returns(mom['net']) - xsect._monthly_returns(ew['net'])).dropna()
        t = xsect._tstat(act)
        results[patch] = {'report': rep, 'mom': m, 'ew': m_ew, 't': t, 'mom_res': mom,
                          'ew_res': ew, 'panel': panel, 'eligible': eligible,
                          'weights': xsect.target_weights(panel, eligible=eligible),
                          'ew_weights': ew_w, 'active': act}

        print(f"\nLive window {mom.index[0].date()} -> {mom.index[-1].date()} "
              f"({len(mom)} bars). Net of 3/1 bps on full turnover.")
        print(f"  {'portfolio':22s} {'total ret':>10s} {'CAGR':>8s} {'Sharpe':>7s} {'maxDD':>8s}")
        for name, mm in (('PIT momentum top-10', m), ('PIT EW eligible universe', m_ew)):
            print(f"  {name:22s} {_pct(mm['total_return'])} {mm['cagr']*100:7.1f}% "
                  f"{mm['sharpe']:7.2f} {_pct(mm['max_drawdown'])}")
        print(f"  momentum - EW monthly active t-stat: {t:.2f}  "
              f"(need ~2+; {len(act)} months)")

    # ---- TEST 3: patch report (both brackets) -----------------------------------
    print('\n' + '=' * 78)
    print('ACCEPTANCE TEST 3 -- patch report (spans by exit class x price status)')
    print('=' * 78)
    print(patch_table(results['optimistic']['report']))
    print(f"  patches applied (pessimistic): {results['pessimistic']['report']['patches']}")
    print(f"\n  Symbols fetched from Tiingo so far: {n_fetched}")
    print(f"  momentum-vs-EW t-stat   optimistic: {results['optimistic']['t']:.2f}   "
          f"pessimistic: {results['pessimistic']['t']:.2f}")
    flip = ((results['optimistic']['t'] >= 2) != (results['pessimistic']['t'] >= 2))
    print(f"  verdict flips between the brackets: {'YES -- free data cannot decide' if flip else 'no'}")
    for n in results['pessimistic']['report']['notes'][:10]:
        print(f'    {n}')

    # ---- TEST 1: lookahead guard -------------------------------------------------
    print('\n' + '=' * 78)
    print('ACCEPTANCE TEST 1 -- lookahead guard over the built weights frame')
    print('=' * 78)
    for patch in ('optimistic', 'pessimistic'):
        r = results[patch]
        for label, w in (('momentum', r['weights']), ('EW-eligible', r['ew_weights'])):
            bad_mask, bad_hold, bad_pick = test_lookahead(w, r['eligible'], membership, renames)
            print(f'  {patch:12s} {label:12s} mask-outside-span: {len(bad_mask)}   '
                  f'held-before-start: {len(bad_hold)}   selected-outside-span: {len(bad_pick)}')
            for b in (bad_mask + bad_hold + bad_pick)[:5]:
                print(f'      VIOLATION {b}')
            assert not (bad_mask or bad_hold or bad_pick), \
                f'LOOKAHEAD VIOLATION ({patch}/{label})'
    print('  PASS: no name is held before its start_date or selected on/after its end_date.')

    # ---- TEST 2: EW-of-eligible vs RSP -------------------------------------------
    print('\n' + '=' * 78)
    print('ACCEPTANCE TEST 2 -- EW-of-eligible-universe vs RSP (S&P 500 Equal Weight ETF)')
    print('=' * 78)
    rsp = fpp.load_prices('RSP')
    if rsp is None:
        print('  RSP not fetched yet -- skipped.')
    else:
        ew = results['optimistic']['ew_res']
        r = rsp['close'].reindex(ew.index).dropna()
        _, rsp_m = run_backtest(r, pd.Series(1.0, index=r.index), xsect.ETF_COST)
        ew_m = compute_metrics(ew.reindex(r.index).dropna())
        print(f"  {'leg':28s} {'total ret':>10s} {'CAGR':>8s} {'Sharpe':>7s} {'maxDD':>8s}")
        for name, mm in (('EW of eligible universe', ew_m), ('hold RSP (3/1 bps)', rsp_m)):
            print(f"  {name:28s} {_pct(mm['total_return'])} {mm['cagr']*100:7.1f}% "
                  f"{mm['sharpe']:7.2f} {_pct(mm['max_drawdown'])}")
        gap = ew_m['cagr'] - rsp_m['cagr']
        print(f"  CAGR gap: {gap*100:+.2f} pp/yr  "
              f"({'within a few points -- panel looks sane' if abs(gap) < 0.04 else 'LARGE -- investigate'})")

    # ---- TEST 4: reproduction of the committed 2026-09-13/14 numbers --------------
    print('\n' + '=' * 78)
    print('ACCEPTANCE TEST 4 -- default path (eligible=None) reproduces the committed result')
    print('=' * 78)
    import glob
    paths = sorted(p for p in glob.glob('realdata/*.csv')
                   if os.path.splitext(os.path.basename(p))[0] not in xsect.EXCLUDE)
    rd = xsect.load_panel(paths)
    w_default = xsect.target_weights(rd)
    w_none = xsect.target_weights(rd, eligible=None)
    identical = w_default.equals(w_none)
    ew_default = xsect._ew_weights(rd, xsect.LOOKBACK)
    ew_none = xsect._ew_weights(rd, xsect.LOOKBACK, eligible=None)
    identical &= ew_default.equals(ew_none)
    res = xsect._first_active(xsect.run_panel(rd, w_default))
    ewr = xsect._first_active(xsect.run_panel(rd, ew_default)).reindex(res.index).dropna()
    res = res.reindex(ewr.index)
    m, m_ew = compute_metrics(res), compute_metrics(ewr)
    sig_act = (xsect._monthly_returns(res['net']) - xsect._monthly_returns(ewr['net'])).dropna()
    t_rd, t_nw = xsect._tstat(sig_act), xsect._nw_tstat(sig_act)
    print(f'  target_weights / _ew_weights with eligible=None identical to no-arg call: '
          f'{"YES" if identical else "NO"}')
    print(f"  momentum total return  {m['total_return']*100:7.1f}%   (thesis: +309.4%)")
    print(f"  EW universe            {m_ew['total_return']*100:7.1f}%   (thesis: +284.5%)")
    print(f'  active t-stat          {t_rd:7.2f}     (thesis:   0.34)')
    print(f'  Newey-West t           {t_nw:7.2f}     (thesis:   0.41)')
    assert identical, 'eligible=None changed default behaviour'

    # ---- TEST 5: old vs new headline, SAME 2019-2026 dates -----------------------
    print('\n' + '=' * 78)
    print('ACCEPTANCE TEST 5 -- 30-name 2026 universe vs point-in-time universe, same dates')
    print('=' * 78)
    lo, hi = res.index[0], res.index[-1]
    print(f'  Common window: {lo.date()} -> {hi.date()}')
    print(f"  {'universe / leg':34s} {'total ret':>10s} {'CAGR':>8s} {'Sharpe':>7s}")
    label_30 = "30-name (2026 liquid names)"
    print(f"  {label_30:34s} {_pct(m['total_return'])} {m['cagr']*100:7.1f}% "
          f"{m['sharpe']:7.2f}   momentum")
    print(f"  {'':34s} {_pct(m_ew['total_return'])} {m_ew['cagr']*100:7.1f}% "
          f"{m_ew['sharpe']:7.2f}   EW")
    rows = {}
    for patch in ('optimistic', 'pessimistic'):
        r = results[patch]
        panel, eligible = r['panel'], r['eligible']
        sub = panel.loc[:hi]
        el = eligible.loc[:hi].copy()
        el.loc[el.index < lo] = False
        mom2 = xsect._first_active(xsect.run_panel(sub, xsect.target_weights(sub, eligible=el)))
        ew2 = xsect._first_active(xsect.run_panel(sub, xsect._ew_weights(sub, xsect.LOOKBACK,
                                                                        eligible=el)))
        ew2 = ew2.reindex(mom2.index).dropna()
        mom2 = mom2.reindex(ew2.index)
        mm, me = compute_metrics(mom2), compute_metrics(ew2)
        act2 = (xsect._monthly_returns(mom2['net']) - xsect._monthly_returns(ew2['net'])).dropna()
        rows[patch] = (mm, me, xsect._tstat(act2))
        print(f"  {'point-in-time S&P 500 (' + patch[:4] + ')':34s} "
              f"{_pct(mm['total_return'])} {mm['cagr']*100:7.1f}% {mm['sharpe']:7.2f}   momentum")
        print(f"  {'':34s} {_pct(me['total_return'])} {me['cagr']*100:7.1f}% "
              f"{me['sharpe']:7.2f}   EW   (active t={rows[patch][2]:.2f})")
    bias = m_ew['total_return'] - rows['optimistic'][1]['total_return']
    bias_p = m_ew['total_return'] - rows['pessimistic'][1]['total_return']
    print(f'\n  >>> MEASURED SURVIVORSHIP + WINNER-SELECTION BIAS (the EW row gap, same dates):')
    print(f'      30-name EW {_pct(m_ew["total_return"]).strip()}  vs  PIT EW '
          f'{_pct(rows["optimistic"][1]["total_return"]).strip()} (optimistic) / '
          f'{_pct(rows["pessimistic"][1]["total_return"]).strip()} (pessimistic)')
    print(f'      = +{bias*100:.1f} pp (optimistic) / +{bias_p*100:.1f} pp (pessimistic) of '
          f'total return that the hand-picked universe manufactures.')

    print('\n' + '=' * 78)
    print(f"COVERAGE CAVEAT: every point-in-time number above rests on {n_fetched} Tiingo "
          f"symbols fetched\nso far (free tier: {fpp.MAX_NEW_SYMBOLS_PER_MONTH} new symbols "
          f"per calendar month). See the TEST 3\ntable for the exact share of membership "
          f"spans that are priced.")
    print('=' * 78)


if __name__ == '__main__':
    main()
