"use client";

// Engine Room — the wide scan (scan.py) and Thesis 001 (xsect.py) run LIVE against
// the 30-stock universe, plus what data was pulled to produce them and the Alpaca
// paper account. Every number is computed by the canonical Python harness; this
// page only fetches and renders JSON (same hard rule as the main page).

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  fetchUniverse, fetchScan, fetchMomentum, fetchAlpacaStatus,
  pct, num, usd,
  type UniverseResponse, type ScanResponse, type ScanRow,
  type MomentumResponse, type AlpacaStatus, type Metrics,
} from "@/lib/api";
import { PerYearBarChart } from "@/components/Charts";

const AMBER = "#b45309"; // "suspect" — between good and bad; not in the 2-color palette

type Fetch<T> = { data: T | null; err: string | null; loading: boolean };

function useFetch<T>(fn: (refresh: boolean) => Promise<T>): [Fetch<T>, (refresh?: boolean) => void] {
  const [state, setState] = useState<Fetch<T>>({ data: null, err: null, loading: true });
  const load = useCallback((refresh = false) => {
    setState((s) => ({ ...s, err: null, loading: true }));
    fn(refresh)
      .then((data) => setState({ data, err: null, loading: false }))
      .catch((e) => setState((s) => ({ ...s, err: e.message, loading: false })));
  }, [fn]);
  useEffect(() => { load(false); }, [load]);
  return [state, load];
}

export default function EngineRoom() {
  const [universe, loadUniverse] = useFetch<UniverseResponse>(fetchUniverse);
  const [scan, loadScan] = useFetch<ScanResponse>(fetchScan);
  const [momentum, loadMomentum] = useFetch<MomentumResponse>(fetchMomentum);
  const [alpaca, loadAlpaca] = useFetch<AlpacaStatus>(fetchAlpacaStatus);

  const refreshAll = () => {
    loadUniverse(true);
    loadScan(true);
    loadMomentum(true);
    loadAlpaca();
  };

  return (
    <div className="container">
      <div className="sm-top">
        <div className="sm-title">The Skeptic&apos;s Machine <span>· engine room</span></div>
        <div className="sm-pickers">
          <span className="sm-pill"><Link href="/" style={{ textDecoration: "none" }}>← visualizer</Link></span>
          <button className="sm-pill" style={{ cursor: "pointer" }} onClick={refreshAll}
            disabled={universe.loading || scan.loading || momentum.loading}>
            ⟳ Refresh (re-fetch data + re-run)
          </button>
        </div>
      </div>
      <p className="sm-sub">
        The wide scan and Thesis 001, run <em>live</em> on the 30-stock universe — plus exactly
        what data was pulled, and which honesty gate each ticker × strategy passed or failed.
        Everything is computed by the Python engines (<code>scan.py</code>, <code>xsect.py</code>)
        on request; the first hit after a cold start can take a while (free backend + live
        vendor fetch — that slowness is real, not hidden).
      </p>

      <DataPanel state={universe} />
      <ScanPanel state={scan} />
      <MomentumPanel state={momentum} />
      <AlpacaPanel state={alpaca} />

      <div className="sm-foot">
        Engine Room = <code>scan.scan_universe()</code> + <code>xsect.py</code>&apos;s pipeline +{" "}
        <code>alpaca_paper.py</code>&apos;s account calls, served by <code>api_server.py</code> /
        {" "}<code>engine_api.py</code>. Zero forked math — the browser only draws.
      </div>
    </div>
  );
}

// ---------- shared bits ----------

function Section({ title, note, children }: {
  title: string; note?: string; children: React.ReactNode;
}) {
  return (
    <div className="sm-card" style={{ marginBottom: 12 }}>
      <div className="sm-card-h">{title}{note && <span>{note}</span>}</div>
      {children}
    </div>
  );
}

function Pending({ what }: { what: string }) {
  return (
    <p className="spinner" style={{ margin: "4px 0" }}>
      {what} — Python is running the real thing (cold backend + live data can take up to a
      minute the first time)…
    </p>
  );
}

function Failed({ err }: { err: string }) {
  return <div className="banner warn err">{err}</div>;
}

function GateRow({ label, ok, detail }: { label: string; ok: boolean; detail: string }) {
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "baseline", fontSize: 12, padding: "3px 0" }}>
      <b className={ok ? "pos" : "neg"} style={{ width: 16, textAlign: "center" }}>
        {ok ? "✓" : "✕"}
      </b>
      <span style={{ minWidth: 190 }}>{label}</span>
      <span className="tertiary" style={{ fontVariantNumeric: "tabular-nums" }}>{detail}</span>
    </div>
  );
}

// ---------- 1. data panel ----------

const SOURCE_LABEL: Record<string, string> = {
  realdata: "local realdata/",
  cache: "cache (this session)",
  alpaca: "Alpaca (IEX, adjusted)",
  "yfinance-fallback": "yfinance (fallback)",
  none: "FAILED",
};

function DataPanel({ state }: { state: Fetch<UniverseResponse> }) {
  const [open, setOpen] = useState(false);
  const d = state.data;
  return (
    <Section title="① What data is being pulled"
      note={d ? d.summary.source : "per-ticker provenance"}>
      {state.loading && <Pending what="Checking / fetching the 31-ticker universe" />}
      {state.err && <Failed err={state.err} />}
      {d && (
        <>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
            <span className="sm-pill">{d.summary.n_ok} / {d.tickers.length} tickers OK</span>
            {d.summary.n_failed > 0 && (
              <span className="sm-pill" style={{ color: "var(--bad)" }}>
                {d.summary.n_failed} failed
              </span>
            )}
            <span className="sm-pill tertiary">
              cache age {Math.round(d.summary.cache_age_seconds / 60)} min
              {" "}(TTL {Math.round(d.summary.ttl_seconds / 60)} min)
            </span>
            <span className="sm-pill tertiary">
              Alpaca keys on backend: {d.summary.alpaca_configured ? "yes" : "no → yfinance-only"}
            </span>
            <button className="sm-pill" style={{ cursor: "pointer" }}
              onClick={() => setOpen(!open)}>
              {open ? "hide" : "show"} all {d.tickers.length} tickers
            </button>
          </div>
          {open && (
            <table>
              <thead>
                <tr>
                  <th>Ticker</th><th>Sector</th><th>Source</th>
                  <th>Rows</th><th>Range</th><th>Status</th>
                </tr>
              </thead>
              <tbody>
                {d.tickers.map((t) => (
                  <tr key={t.ticker}>
                    <td>{t.ticker}</td>
                    <td>{t.sector}</td>
                    <td>{SOURCE_LABEL[t.source] ?? t.source}</td>
                    <td>{t.rows ?? "—"}</td>
                    <td>{t.start ? `${t.start} → ${t.end}` : "—"}</td>
                    <td className={t.ok ? "good" : "bad"}>{t.ok ? "ok" : t.error}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </Section>
  );
}

// ---------- 2. wide-scan panel ----------

type SortKey = "ticker" | "strategy" | "return" | "sharpe" | "tpf" | "dsr" | "verdict";

const VERDICT_RANK: Record<string, number> = { "EDGE?": 0, suspect: 1, "beats B&H": 2, dead: 3 };

function verdictColor(v: string) {
  return v === "EDGE?" ? "var(--good)" : v === "dead" ? "var(--bad)" : AMBER;
}

function ScanPanel({ state }: { state: Fetch<ScanResponse> }) {
  const [sortKey, setSortKey] = useState<SortKey>("return");
  const [asc, setAsc] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const d = state.data;

  const sortBy = (k: SortKey) => {
    if (k === sortKey) setAsc(!asc);
    else { setSortKey(k); setAsc(k === "ticker" || k === "strategy" || k === "verdict"); }
  };

  const rows = d ? [...d.rows].sort((a, b) => {
    const val = (r: ScanRow): number | string => ({
      ticker: r.ticker, strategy: r.strategy,
      return: r.metrics.total_return ?? -1e9,
      sharpe: r.metrics.sharpe ?? -1e9,
      tpf: r.trades_per_fold, dsr: r.dsr ?? -1,
      verdict: VERDICT_RANK[r.verdict] ?? 9,
    }[sortKey]);
    const va = val(a), vb = val(b);
    const cmp = typeof va === "string" ? va.localeCompare(vb as string) : (va as number) - (vb as number);
    return asc ? cmp : -cmp;
  }) : [];

  const Th = ({ k, children }: { k: SortKey; children: React.ReactNode }) => (
    <th style={{ cursor: "pointer", userSelect: "none" }} onClick={() => sortBy(k)}>
      {children}{sortKey === k ? (asc ? " ↑" : " ↓") : ""}
    </th>
  );

  return (
    <Section title="② Wide scan — every ticker × strategy, live"
      note={d ? `${d.summary.cost_regime} · ${d.summary.n_folds} folds · ran in ${d.summary.elapsed_seconds}s` : "walk-forward OOS, net of costs"}>
      {state.loading && <Pending what={"Running the wide scan (30 tickers × 3 strategies = 90 walk-forward backtests)"} />}
      {state.err && <Failed err={state.err} />}
      {d && (
        <>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
            <span className="sm-pill">{d.summary.n_backtests} backtests</span>
            <span className="sm-pill" style={{ color: "var(--good)" }}>{d.summary.n_edge} EDGE?</span>
            <span className="sm-pill" style={{ color: AMBER }}>{d.summary.n_suspect} suspect</span>
            <span className="sm-pill" style={{ color: "var(--bad)" }}>{d.summary.n_dead} dead</span>
            {!d.summary.has_spy_benchmark && (
              <span className="sm-pill" style={{ color: "var(--bad)" }}>no SPY benchmark on disk</span>
            )}
          </div>
          <p className="muted" style={{ margin: "0 0 8px", fontSize: 11.5 }}>
            Click a row to see every honesty gate it passed or failed. Sorted by{" "}
            {sortKey === "return" ? "OOS net return" : sortKey} — big numbers with a
            &quot;dead&quot; verdict are the trap this machine exists to catch.
          </p>
          <div style={{ maxHeight: 420, overflowY: "auto" }}>
            <table>
              <thead>
                <tr>
                  <Th k="ticker">Ticker</Th>
                  <Th k="strategy">Strategy</Th>
                  <th>N</th>
                  <Th k="return">OOS ret</Th>
                  <Th k="sharpe">Sharpe</Th>
                  <th>maxDD</th>
                  <Th k="tpf">Trades/fold</Th>
                  <th>vs SPY</th>
                  <Th k="dsr">DSR</Th>
                  <Th k="verdict">Verdict</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const id = `${r.ticker}/${r.strategy}`;
                  const vsSpy = r.spy_return != null && r.metrics.total_return != null
                    ? r.metrics.total_return - r.spy_return : null;
                  return (
                    <ScanRowView key={id} r={r} vsSpy={vsSpy}
                      open={expanded === id}
                      onToggle={() => setExpanded(expanded === id ? null : id)} />
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Section>
  );
}

function ScanRowView({ r, vsSpy, open, onToggle }: {
  r: ScanRow; vsSpy: number | null; open: boolean; onToggle: () => void;
}) {
  const m = r.metrics;
  const positive = (m.total_return ?? 0) > 0;
  return (
    <>
      <tr onClick={onToggle} style={{ cursor: "pointer", background: open ? "var(--bg-secondary)" : undefined }}>
        <td>{open ? "▾ " : "▸ "}{r.ticker}</td>
        <td>{r.strategy}</td>
        <td>{m.n_trials}</td>
        <td className={positive ? "good" : "bad"}>{pct(m.total_return)}</td>
        <td>{num(m.sharpe)}</td>
        <td className="bad">{pct(m.max_drawdown)}</td>
        <td>{r.trades_per_fold.toFixed(1)}{r.thin ? " *" : ""}</td>
        <td className={vsSpy != null && vsSpy >= 0 ? "good" : "bad"}>
          {vsSpy != null ? pct(vsSpy) : "n/a"}
        </td>
        <td>{num(r.dsr)}</td>
        <td style={{ color: verdictColor(r.verdict), fontWeight: 600 }}>{r.verdict}</td>
      </tr>
      {open && (
        <tr>
          <td colSpan={10} style={{ background: "var(--bg-secondary)", textAlign: "left" }}>
            <div style={{ padding: "4px 2px 8px" }}>
              <GateRow label="Beats buy & hold (Gate 2a)" ok={r.beats_bh}
                detail={`strategy ${pct(m.total_return)} vs B&H ${pct(r.bh_return)}`} />
              <GateRow label="Beats random (Gate 2b)" ok={r.beats_rand}
                detail={`vs random ${pct(r.rand_return)}`} />
              <GateRow label="Beats holding SPY (Gate 2c)" ok={r.beats_spy}
                detail={r.spy_return != null ? `vs SPY ${pct(r.spy_return)} over the same OOS window` : "no SPY on disk — not blocked on it"} />
              <GateRow label="Positive OOS return" ok={positive} detail={pct(m.total_return)} />
              <GateRow label="≥ 30 trades/fold (Gate 4)" ok={!r.thin}
                detail={`${r.trades_per_fold.toFixed(1)} per fold — fewer = luck, not edge`} />
              <GateRow label="Deflated Sharpe ≥ 0.95 (Gate 3)" ok={r.significant}
                detail={`DSR ${num(r.dsr)} after the best-of-${m.n_trials} discount`} />
              {r.red_flags.length > 0 && (
                <div style={{
                  marginTop: 6, padding: "6px 9px", borderRadius: 6, fontSize: 11.5,
                  background: "rgba(220,38,38,0.07)", border: "1px solid rgba(220,38,38,0.22)",
                }}>
                  <b className="bad">Red flag{r.red_flags.length > 1 ? "s" : ""}:</b>{" "}
                  {r.red_flags.join(" ")}
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ---------- 3. momentum panel ----------

function MomentumPanel({ state }: { state: Fetch<MomentumResponse> }) {
  const d = state.data;
  return (
    <Section title="③ Thesis 001 — cross-sectional momentum, live"
      note={d ? `${d.window[0]} → ${d.window[1]} · ran in ${d.elapsed_seconds}s` : "12-1, monthly, top 10, long-only"}>
      {state.loading && <Pending what="Running the panel backtest + 3 baselines + robustness gauntlet + sensitivity sweep" />}
      {state.err && <Failed err={state.err} />}
      {d && (
        <>
          <div className={`sm-badge ${d.verdict.survives ? "sm-live" : "sm-dead"}`}
            style={{ marginBottom: 8 }}>
            {d.verdict.survives ? "SURVIVES THE PANEL BAR" : "DOES NOT CLEAR THE BAR"}
          </div>
          <p className="muted" style={{ margin: "0 0 10px", fontSize: 12.5, lineHeight: 1.5 }}>
            {d.spec}. The bar: beat equal-weighting the <em>same universe</em> (selection skill,
            not survivorship), random picks, and SPY — identical dates and costs.
          </p>
          <div style={{ display: "flex", gap: 14, flexWrap: "wrap", fontSize: 12, marginBottom: 10 }}>
            <VerdictCheck label="beats EW universe" ok={d.verdict.beats_ew} />
            <VerdictCheck label="beats random picks" ok={d.verdict.beats_random} />
            <VerdictCheck label="beats holding SPY" ok={d.verdict.beats_spy} />
            <span className="muted">
              Probabilistic Sharpe (monthly, {d.psr_months} mo):{" "}
              <b className={(d.probabilistic_sharpe ?? 0) >= 0.95 ? "good" : "bad"}>
                {num(d.probabilistic_sharpe)}
              </b>
            </span>
          </div>

          <table>
            <thead>
              <tr><th>Portfolio</th><th>Total return</th><th>CAGR</th><th>Sharpe</th><th>Max DD</th><th>Trades</th></tr>
            </thead>
            <tbody>
              <PortfolioRow label="Momentum top-10" m={d.portfolios.momentum} strong />
              <PortfolioRow label="EW universe (all names)" m={d.portfolios.ew_universe} />
              <PortfolioRow label="Random top-10" m={d.portfolios.random} />
              {d.portfolios.spy && <PortfolioRow label="Hold SPY" m={d.portfolios.spy} />}
            </tbody>
          </table>

          <div style={{ marginTop: 14 }}>
            <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
              Per-year net return — momentum (red) vs EW universe (green)
            </div>
            <PerYearBarChart data={d.per_year} />
          </div>

          {d.regime_split && (
            <div style={{ marginTop: 10, fontSize: 12 }} className="muted">
              By SPY regime — up <b className="good">{pct(d.regime_split.up.return)}</b>
              {" "}({d.regime_split.up.bars} bars), down {pct(d.regime_split.down.return)}
              {" "}({d.regime_split.down.bars}), chop{" "}
              <b className="bad">{pct(d.regime_split.chop.return)}</b> ({d.regime_split.chop.bars}).
            </div>
          )}

          <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid var(--border)" }}>
            <p className="muted" style={{ margin: "0 0 6px", fontSize: 11.5, lineHeight: 1.5 }}>
              Sensitivity —{" "}
              <b style={{ color: "var(--text-primary)" }}>
                {d.sweep_beats_ew} neighbor specs beat their EW-universe
              </b>. We do <em>not</em> pick the winner; the pre-registered 12mo/top-10 (★) stays
              the verdict. A broad neighborhood means the edge is not one lucky config.
            </p>
            <table>
              <thead>
                <tr><th>Lookback</th><th>Top N</th><th>Total return</th><th>Sharpe</th><th>Beats EW</th></tr>
              </thead>
              <tbody>
                {d.sweep.map((s, i) => (
                  <tr key={i} style={s.canonical ? { fontWeight: 600 } : undefined}>
                    <td>{s.lookback}{s.canonical ? " ★" : ""}</td>
                    <td>{s.top_n}</td>
                    <td className={s.total_return >= 0 ? "good" : "bad"}>{pct(s.total_return)}</td>
                    <td>{num(s.sharpe)}</td>
                    <td className={s.beats_ew ? "good" : "bad"}>{s.beats_ew ? "YES" : "no"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {d.red_flags.length > 0 && (
            <div style={{
              marginTop: 10, padding: "8px 10px", borderRadius: 6, fontSize: 11.5,
              background: "rgba(220,38,38,0.08)", border: "1px solid rgba(220,38,38,0.25)",
            }}>
              <b className="bad">Red flag{d.red_flags.length > 1 ? "s" : ""}:</b>{" "}
              {d.red_flags.join(" ")}
            </div>
          )}
          <p className="tertiary" style={{ margin: "8px 0 0", fontSize: 11 }}>
            Caveats: {d.caveats.join("; ")}.
          </p>
        </>
      )}
    </Section>
  );
}

function VerdictCheck({ label, ok }: { label: string; ok: boolean }) {
  return (
    <span className="muted">
      <b className={ok ? "pos" : "neg"}>{ok ? "✓" : "✕"}</b> {label}
    </span>
  );
}

function PortfolioRow({ label, m, strong }: { label: string; m: Metrics; strong?: boolean }) {
  return (
    <tr style={strong ? { fontWeight: 600 } : undefined}>
      <td>{label}</td>
      <td className={(m.total_return ?? 0) >= 0 ? "good" : "bad"}>{pct(m.total_return)}</td>
      <td>{pct(m.cagr)}</td>
      <td>{num(m.sharpe)}</td>
      <td className="bad">{pct(m.max_drawdown)}</td>
      <td>{m.num_trades ?? "—"}</td>
    </tr>
  );
}

// ---------- 4. paper account panel ----------

function AlpacaPanel({ state }: { state: Fetch<AlpacaStatus> }) {
  const d = state.data;
  return (
    <Section title="④ Alpaca paper account" note="simulated money · display only, no orders from the app">
      {state.loading && <Pending what="Reading the paper account" />}
      {state.err && <Failed err={state.err} />}
      {d && !d.configured && (
        <p className="muted" style={{ margin: 0, fontSize: 12.5, lineHeight: 1.5 }}>
          <b>Alpaca keys are not set on this backend yet.</b> {d.reason}. Locally: put the
          PAPER keys in <code>.env</code>. Deployed: add <code>APCA_API_KEY_ID</code> /{" "}
          <code>APCA_API_SECRET_KEY</code> in the Render dashboard. Until then the data panel
          above runs yfinance-only — degraded, not broken.
        </p>
      )}
      {d && d.configured && d.ok === false && (
        <Failed err={`Alpaca API error: ${d.error}`} />
      )}
      {d && d.configured && d.ok && d.account && (
        <>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
            <span className="sm-pill">equity <b>{usd(d.account.equity)}</b></span>
            <span className="sm-pill">cash <b>{usd(d.account.cash)}</b></span>
            <span className="sm-pill">buying power <b>{usd(d.account.buying_power)}</b></span>
            <span className="sm-pill tertiary">
              paper acct {d.account.account_number} · {d.account.status}
            </span>
          </div>
          {d.positions && d.positions.length > 0 ? (
            <table>
              <thead>
                <tr><th>Symbol</th><th>Qty</th><th>Avg entry</th><th>Market value</th><th>Unrealized P&L</th></tr>
              </thead>
              <tbody>
                {d.positions.map((p) => (
                  <tr key={p.symbol}>
                    <td>{p.symbol}</td>
                    <td>{p.qty}</td>
                    <td>{usd(p.avg_entry_price)}</td>
                    <td>{usd(p.market_value)}</td>
                    <td className={p.unrealized_pl >= 0 ? "good" : "bad"}>{usd(p.unrealized_pl)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted" style={{ margin: 0, fontSize: 12.5, lineHeight: 1.5 }}>
              <b>Alpaca is connected — zero open positions.</b> That is correct, not broken:
              nothing has been promoted to paper trading yet. Thesis 001 is INCONCLUSIVE on
              the panel bar (above), and nothing moves to paper until a strategy PASSES
              (stage 7 of the roadmap). The account starts at $100k paper cash.
            </p>
          )}
        </>
      )}
    </Section>
  );
}
